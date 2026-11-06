"""Same MQTT request → native Raspi and ESP32-S3+FPGA; baseline then active.

Reports latency and verifies every response. Energy stays null unless both
the meter manifest and every power sample are valid. Uses separate test topics.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'edge/bridge'))
from fpga_bridge import BROKER, PORT, USER, PASS, MODEL, GoldenModelINT8
import paho.mqtt.client as mqtt
from energy import integrate, valid_power, energy_metrics


def stats(values):
    values = sorted(values)
    if not values:
        return None
    return {'n': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values),
            'p95': values[min(len(values)-1, math.ceil(.95*len(values))-1)], 'min': values[0], 'max': values[-1]}


def meter_verified(config, device):
    d = config.get('devices', {}).get(device, {})
    return (d.get('installed') is True and d.get('verified') is True and bool(d.get('instrument')) and bool(d.get('verified_utc'))
            and type(d.get('reference_voltage_v')) in (int,float) and 4 <= d['reference_voltage_v'] <= 6
            and type(d.get('reference_current_a')) in (int,float) and d['reference_current_a'] >= 0
            and type(d.get('shunt_ohm')) in (int,float) and d['shunt_ohm'] > 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase-seconds', type=float, default=30)
    parser.add_argument('--hz', type=float, default=10)
    parser.add_argument('--meter-config', type=Path, default=Path(__file__).with_name('meter.example.json'))
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if not 2 <= args.phase_seconds <= 3600 or not 0.1 <= args.hz <= 50 or args.phase_seconds*args.hz < 1:
        parser.error('Use phase-seconds 2..3600, hz 0.1..50, and at least one request.')
    config = json.loads(args.meter_config.read_text())
    run_id = uuid.uuid4().hex
    header_sha = hashlib.sha256((ROOT/'ml/forecast/model/export/mlp_int8.h').read_bytes()).hexdigest()
    state = {'latest': None, 'connected': False}
    responses, sent, power, invalid_power = {}, {}, {'rpi': [], 'fpga': []}, {'rpi': 0, 'fpga': 0}
    raw_power = []
    lock = threading.Lock()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='wec-compare-'+run_id[:12])
    client.username_pw_set(USER, PASS)

    def on_connect(c,u,f,reason,p):
        if not reason.is_failure:
            c.subscribe([('WEC/prediksi',0),('WEC/benchmark/rpi',0),('WEC/benchmark/fpga',0),('WEC/daya',0)])
            state['connected'] = True

    def on_message(c,u,msg):
        try:
            d = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError):
            return
        now = time.monotonic()
        if not isinstance(d, dict):
            return
        with lock:
            if msg.topic == 'WEC/prediksi':
                if isinstance(d.get('xq'), list) and len(d['xq']) == 16 and all(type(x) is int and -128 <= x <= 127 for x in d['xq']):
                    state['latest'] = d
            elif msg.topic == 'WEC/daya' and not msg.retain:
                raw_power.append({'received_monotonic_s': now, 'payload': d})
                for device, key in [('rpi','fpga'),('fpga','raspberry_pi')] if config.get('physical_channel_swap',True) else [('rpi','raspberry_pi'),('fpga','fpga')]:
                    # Reject stale sensor packets even if they are not marked retained.
                    fresh = type(d.get('t')) in (int,float) and abs(time.time()-d['t']/1000) <= 5
                    p = valid_power(d.get(key)) if fresh else None
                    invalid_power[device] += p is None
                    power[device].append((now,p))
            elif not msg.retain and d.get('run_id') == run_id and d.get('phase') in ('baseline','active') and type(d.get('seq')) is int:
                device = 'rpi' if msg.topic.endswith('/rpi') else 'fpga'
                key = (d['phase'],d['seq'])
                if key in sent:
                    responses[(device,*key)] = {'payload':d,'mqtt_roundtrip_ms':(now-sent[key])*1000}

    client.on_connect, client.on_message = on_connect, on_message
    client.connect(BROKER,PORT,30)
    client.loop_start()
    started_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    windows, startup_error = {}, None
    xq, feature_source = None, None
    try:
        deadline = time.monotonic()+30
        while time.monotonic()<deadline and state['latest'] is None:
            time.sleep(.1)
        if state['latest'] is None or abs(time.time()-state['latest']['t']/1000)>180:
            raise RuntimeError('No recent live INT8 feature vector. No synthetic sensor data injected.')
        xq = list(state['latest']['xq'])
        feature_source = dict(state['latest'])

        def send(phase,seq):
            d = {'run_id':run_id,'phase':phase,'seq':seq,'t':int(time.time()*1000),'xq':xq}
            with lock:
                sent[(phase,seq)] = time.monotonic()
            result = client.publish('WEC/benchmark/request',json.dumps(d,separators=(',',':')),retain=False)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError('MQTT publish failed')

        # Both devices must acknowledge a no-inference probe before measurement.
        deadline = time.monotonic()+60
        while time.monotonic()<deadline:
            send('baseline',-1)
            time.sleep(1)
            with lock:
                ready = all((device,'baseline',-1) in responses for device in ('rpi','fpga'))
            if ready:
                break
        else:
            raise RuntimeError('Missing benchmark receiver: '+', '.join(device for device in ('rpi','fpga') if (device,'baseline',-1) not in responses))
        time.sleep(2.5)  # acquire boundary power samples before baseline
        count = int(args.phase_seconds*args.hz)
        for phase in ('baseline','active'):
            start = time.monotonic()
            windows[phase] = (start,start+args.phase_seconds)
            print('Phase',phase,'requests',count,'rate',args.hz,'Hz',flush=True)
            for seq in range(count):
                delay = start+seq/args.hz-time.monotonic()
                if delay>0:
                    time.sleep(delay)
                send(phase,seq)
            delay = start+args.phase_seconds-time.monotonic()
            if delay>0:
                time.sleep(delay)
        time.sleep(5)  # late acknowledgements + final power interpolation boundary
    except (RuntimeError, KeyError, TypeError) as exc:
        startup_error = str(exc)
        print(startup_error,flush=True)
    finally:
        client.disconnect()
        client.loop_stop()

    golden = GoldenModelINT8(model_path=str(MODEL)).forward(xq)[0] if xq else None
    devices, comparisons = {}, []
    count = int(args.phase_seconds*args.hz)
    for device in ('rpi','fpga'):
        phases = {}
        for phase in ('baseline','active'):
            items = [responses.get((device,phase,seq)) for seq in range(count)]
            good = []
            for item in items:
                if not item:
                    good.append(False); continue
                d = item['payload']
                ok = d.get('xq') == xq and d.get('executed') == (phase=='active')
                if device=='rpi':
                    ok = ok and d.get('model_header_sha256') == header_sha
                else:
                    ok = ok and d.get('ok') is True
                if phase=='active':
                    ok = ok and d.get('out_q') == golden and (device!='fpga' or d.get('cycles')==309)
                else:
                    ok = ok and d.get('out_q') is None
                good.append(ok)
            complete = all(good) and bool(items)
            meter = integrate(power[device],*windows[phase],meter_verified(config,device)) if phase in windows else None
            phases[phase] = {'requested':count,'received':sum(x is not None for x in items),'verified_responses':sum(good),
                             'complete':complete,'power':meter,
                             'mqtt_roundtrip_ms':stats([x['mqtt_roundtrip_ms'] for x in items if x]),
                             'rpi_core_us' if device=='rpi' else 'fpga_uart_us':stats([
                                 x['payload'][('core_us' if device=='rpi' else 'uart_us')] for x in items
                                 if x and type(x['payload'].get('core_us' if device=='rpi' else 'uart_us')) in (int,float)])}
        energy = energy_metrics(phases['baseline']['power'],phases['active']['power'],phases['active']['verified_responses'],
                                phases['baseline']['complete'] and phases['active']['complete']) if len(windows)==2 else {'valid':False}
        devices[device] = {'phases':phases,'energy_per_prediction':energy,'invalid_power_samples':invalid_power[device]}
    passed = startup_error is None and all(ph['complete'] for d in devices.values() for ph in d['phases'].values())
    report = {'run_id':run_id,'started_utc':started_utc,'inference_passed':passed,
              'energy_comparison_ready':all(d['energy_per_prediction']['valid'] for d in devices.values()),
              'error':startup_error,'phase_seconds':args.phase_seconds,'request_rate_hz':args.hz,
              'xq':xq,'golden_q':golden,'feature_source':feature_source, 'model_header_sha256':header_sha,
              'devices':devices,'meter_config':config,
              'limitations':['Pi continues sensor acquisition and TA software; whole-board workloads differ.',
                             'C++ core time excludes IPC; FPGA UART time includes transport. Do not divide them for speedup.',
                             'MQTT round-trip uses one common observing host; includes broker/network and device handling.',
                             'Power timing uses MQTT receipt monotonic timestamps, not synchronous ADC triggers.',
                             'Wh/day is a projection at this benchmark rate, not a measured 24-hour total.',
                             'Incremental energy requires uncertainty analysis; 1-Hz meters cannot resolve one microsecond inference.'],
              'responses':[{'device':k[0],'phase':k[1],'seq':k[2],**v} for k,v in responses.items() if k[2]>=0],
              'raw_power':raw_power}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:report[k] for k in ['inference_passed','energy_comparison_ready','error']}),flush=True)
    print('Report:',args.report,flush=True)
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
