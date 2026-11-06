"""Continuous passive comparison at the real plant cadence (~one prediction/min).

Write raw MQTT evidence and a compact summary; publish WEC/comparison/summary.
Energy is null until meter verification and sufficient valid power coverage.
The live window starts at the first valid power sample of both channels (not at boot, before
MQTT connects), uses the ESP32 sample time t, bridges gaps <= 15 s and needs >= 95% coverage.
State (energy per minute, matched prediction pairs, window start) is saved to <output-dir>/state.json
every minute and resumed after a restart (22 Okt: Raspi reboots often), so the window does not restart
from zero; recorder downtime is excluded from the window duration and reported as downtime_excluded_s.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import statistics
import threading
import time

import paho.mqtt.client as mqtt
from energy import MinuteEnergy, valid_power, window_result

MIN_COVERAGE = 0.95
MAX_GAP_S = 15      # ESP32 pengukur sesekali kehilangan sampel ~11 s (WiFi/MQTT)
MAX_DELAY_S = 15    # pesan bisa tiba sampai ~7 s terlambat di Raspi
WINDOW_S = 86400
MAX_RESUME_S = 6 * 3600   # status lebih tua dari ini tidak dilanjutkan (mulai jendela baru)
DEVICES = ('rpi', 'fpga')


def verified(d):
    return (d.get('installed') is True and d.get('verified') is True
            and bool(d.get('instrument')) and bool(d.get('verified_utc'))
            and type(d.get('reference_voltage_v')) in (int,float) and 4 <= d['reference_voltage_v'] <= 6
            and type(d.get('reference_current_a')) in (int,float) and d['reference_current_a'] >= 0
            and type(d.get('shunt_ohm')) in (int,float) and d['shunt_ohm'] > 0)


def overlap(intervals, a, b):
    return sum(max(0.0, min(b, y) - max(a, x)) for x, y in intervals)


def load_state(path, model_sha, now):
    """Resume a recent state of the same model; recorder downtime becomes an excluded interval."""
    try:
        st = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if st.get('v') != 1 or st.get('model_sha') != model_sha or not 0 <= now - st.get('saved_utc', 0) <= MAX_RESUME_S:
        return None
    st['energy'] = {d: MinuteEnergy.from_json(st['energy'][d]) for d in DEVICES}
    st['downtime'] = st.get('downtime', []) + [[st['saved_utc'], now]]
    return st


def save_state(path, st):
    data = dict(st, energy={d: st['energy'][d].to_json() for d in DEVICES}, saved_utc=time.time())
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, separators=(',', ':')))
    os.replace(tmp, path)                             # atomik: aman bila listrik putus saat menulis


def new_state(model_sha, now):
    return {'v': 1, 'model_sha': model_sha, 'started_utc': now, 'first_valid_utc': None, 'downtime': [],
            'energy': {d: MinuteEnergy(MAX_GAP_S) for d in DEVICES}, 'pairs': [], 'mismatch_t': [], 'resumed': 0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--meter-config',type=Path,required=True)
    parser.add_argument('--model-header',type=Path,required=True)
    parser.add_argument('--seconds',type=float,default=0,help='0 = continuous')
    args=parser.parse_args()
    config=json.loads(args.meter_config.read_text())
    model_sha=hashlib.sha256(args.model_header.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    state_path=args.output_dir/'state.json'
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    evidence_day=time.strftime('%Y%m%d',time.gmtime())
    evidence=(args.output_dir/(evidence_day+'.jsonl')).open('a',buffering=1)
    started_mono=time.monotonic()
    st=load_state(state_path,model_sha,time.time())
    if st:
        st['resumed']+=1
    else:
        st=new_state(model_sha,time.time())
    records={}
    control={'benchmark_until':0.,'reset_after_benchmark':False,'last_save':0.}
    done=threading.Event()
    lock=threading.Lock()
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda s,f:done.set())
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='wec-comparison-recorder-'+os.uname().nodename)
    client.username_pw_set(os.environ['MQTT_USER'],os.environ['MQTT_PASS'])

    def connect(c,u,f,reason,p):
        if not reason.is_failure:
            c.subscribe([(t,0) for t in ('WEC/prediksi','WEC/rpi','WEC/fpga','WEC/daya','WEC/benchmark/request')])

    def message(c,u,msg):
        nonlocal evidence, evidence_day
        if msg.retain:
            return
        try:
            d=json.loads(msg.payload)
        except (ValueError,UnicodeDecodeError):
            return
        if not isinstance(d,dict):
            return
        now=time.time()
        with lock:
            day=time.strftime('%Y%m%d',time.gmtime())
            if day!=evidence_day:
                evidence.close();evidence=(args.output_dir/(day+'.jsonl')).open('a',buffering=1);evidence_day=day
            evidence.write(json.dumps({'received_utc_ms':int(now*1000),'topic':msg.topic,'payload':d},separators=(',',':'))+'\n')
            if msg.topic=='WEC/benchmark/request':
                if d.get('phase') in ('baseline','active') and isinstance(d.get('run_id'),str):
                    control.update(benchmark_until=time.monotonic()+5,reset_after_benchmark=True)
                return
            if msg.topic=='WEC/daya':
                mapping={'rpi':'fpga','fpga':'raspberry_pi'} if config.get('physical_channel_swap',True) else {'rpi':'raspberry_pi','fpga':'fpga'}
                # Waktu sampel ESP32 (t, NTP): jitter WiFi/broker tidak membuat celah palsu; sebelum jam Raspi
                # tersinkron NTP (setelah boot) sampel tidak "segar" sehingga tidak dihitung.
                fresh=type(d.get('t')) in (int,float) and abs(now-d['t']/1000)<=MAX_DELAY_S
                ts=d['t']/1000 if fresh else now
                values={dev:(valid_power(d.get(key)) if fresh else None) for dev,key in mapping.items()}
                for dev,v in values.items():
                    st['energy'][dev].add(ts,v)
                if st['first_valid_utc'] is None and all(v is not None for v in values.values()):
                    st['first_valid_utc']=ts
            elif type(d.get('t')) in (int,float) and abs(now*1000-d['t'])<180000:
                key={'WEC/prediksi':'input','WEC/rpi':'rpi','WEC/fpga':'fpga'}[msg.topic]
                records.setdefault(d['t'],{})[key]=d

    client.on_connect,client.on_message=connect,message
    client.connect(os.environ.get('MQTT_HOST','citaitb.com'),int(os.environ.get('MQTT_PORT','1883')),30)
    client.loop_start()
    try:
        while not done.wait(5):
            now=time.time()
            with lock:
                benchmarking=time.monotonic()<control['benchmark_until']
                if control['reset_after_benchmark'] and not benchmarking:
                    # Do not mix a 10-Hz test burst into the normal 1/min energy window.
                    st=new_state(model_sha,now);records.clear()
                    control['reset_after_benchmark']=False
                    continue
                # Pasangan prediksi lengkap dipindah ke daftar tersimpan; yang tak lengkap > 10 menit dibuang.
                for t in list(records):
                    r=records[t]
                    if all(k in r for k in ('input','rpi','fpga')):
                        xq=r['input'].get('xq')
                        ok=(r['rpi'].get('model_header_sha256')==model_sha and r['rpi'].get('xq')==xq
                            and type(r['rpi'].get('out_q')) is int and r['rpi']['out_q']==r['fpga'].get('out_q_fpga')
                            and r['fpga'].get('cycles')==309 and r['fpga'].get('sumber')=='tang-nano-4k'
                            and r['fpga'].get('port')=='ESP32-S3 UART1')
                        if ok:
                            st['pairs'].append({'t':t,'out_q':r['rpi']['out_q'],'rpi_core_us':r['rpi']['core_us'],'fpga_uart_us':r['fpga']['us']})
                        else:
                            st['mismatch_t'].append(t)
                        del records[t]
                    elif now*1000-t>600000:
                        del records[t]
                if st['first_valid_utc'] is None:
                    continue
                window_start=max(st['first_valid_utc'],st['started_utc'],now-WINDOW_S)
                m0=math.floor(window_start/60)*60
                st['downtime']=[iv for iv in st['downtime'] if iv[1]>m0]
                st['pairs']=[p for p in st['pairs'] if p['t']>=m0*1000]
                st['mismatch_t']=[t for t in st['mismatch_t'] if t>=m0*1000]
                for e in st['energy'].values():
                    e.prune(m0)
                downtime=overlap(st['downtime'],window_start,now)
                duration=now-window_start-downtime
                pairs,mismatch=st['pairs'],len(st['mismatch_t'])
                energy={}
                for device in DEVICES:
                    metadata=config.get('devices',{}).get(device,{})
                    joules,covered=st['energy'][device].totals(m0)
                    covered=min(covered,duration)          # menit pertama dihitung utuh di ember
                    value=window_result(joules,covered,duration,verified(metadata),MIN_COVERAGE)
                    value.update(min_coverage=MIN_COVERAGE,max_gap_s=MAX_GAP_S)
                    if benchmarking:
                        value.update(valid=False,energy_j=None,energy_wh=None,average_w=None,projected_wh_per_day_at_this_workload=None)
                        value['reasons'].append('controlled_benchmark_in_progress')
                    if metadata.get('installed') is not True:
                        value.update(valid=False,energy_j=None,energy_wh=None,average_w=None,projected_wh_per_day_at_this_workload=None)
                        value['reasons'].append('channel_not_installed')
                    value['total_j_per_prediction']=value['energy_j']/len(pairs) if value['valid'] and pairs and mismatch==0 else None
                    value['incremental_j_per_prediction']=None
                    if duration<1800:
                        value['projected_wh_per_day_at_this_workload']=None
                        value['daily_projection_reason']='minimum_normal_observation_1800_seconds'
                    energy[device]=value
                summary={'kind':'normal_live','generated_at_ms':int(now*1000),'started_utc_ms':int(st['started_utc']*1000),
                         'observed_seconds':duration,'window':'last 24 hours or since recorder start, recorder downtime excluded',
                         'downtime_excluded_s':downtime,'resumed_after_restart':st['resumed'],
                         'matched_pairs':len(pairs),'mismatches':mismatch,
                         'benchmark_running':benchmarking,
                         'last_pair':max(pairs,key=lambda p:p['t']) if pairs else None,
                         'rpi_core_us_median':statistics.median(p['rpi_core_us'] for p in pairs) if pairs else None,
                         'fpga_uart_us_median':statistics.median(p['fpga_uart_us'] for p in pairs) if pairs else None,
                         'energy':energy,'energy_comparison_ready':all(x['valid'] for x in energy.values()),
                         'notes':['Same INT8 features; Pi also acquires sensors and runs TA software.',
                                  'Core time and UART round-trip time have different boundaries.',
                                  'Wh/day is projected at the observed normal workload; not a measured daily total.',
                                  'Total J/prediction amortizes whole-board energy including idle/background tasks.',
                                  'Incremental J/prediction requires a controlled baseline experiment.',
                                  'Recorder downtime (Raspi reboot) is excluded from the window, not filled.']}
                (args.output_dir/'latest.json').write_text(json.dumps(summary,indent=2)+'\n')
                (args.output_dir/(stamp+'-summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
                if now-control['last_save']>=60:
                    save_state(state_path,st); control['last_save']=now
            client.publish('WEC/comparison/summary',json.dumps(summary,separators=(',',':')),retain=True)
            if args.seconds>0 and time.monotonic()-started_mono>=args.seconds:
                break
    finally:
        with lock:
            save_state(state_path,st)
        client.disconnect();client.loop_stop();evidence.close()


if __name__=='__main__':
    main()
