"""Raspberry Pi MQTT inference service; native persistent C++ worker.

Uses WEC/prediksi for live operation and an isolated benchmark request topic.
Secrets come from environment only. No sensor acquisition changes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import paho.mqtt.client as mqtt


def valid_request(d):
    return (isinstance(d, dict) and type(d.get('t')) is int and d['t'] > 0
            and isinstance(d.get('xq'), list) and len(d['xq']) == 16
            and all(type(x) is int and -128 <= x <= 127 for x in d['xq']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--model-header', type=Path, required=True)
    args = parser.parse_args()
    header_hash = hashlib.sha256(args.model_header.read_bytes()).hexdigest()
    worker = subprocess.Popen([str(args.worker.resolve())], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, text=True, bufsize=1)
    state = {'last_live_t': 0, 'benchmark_until': 0.0}
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='wec-rpi-native-' + os.uname().nodename)
    client.username_pw_set(os.environ['MQTT_USER'], os.environ['MQTT_PASS'])

    def on_connect(c, userdata, flags, reason, properties):
        if reason.is_failure:
            return
        c.subscribe([('WEC/prediksi', 0), ('WEC/benchmark/request', 0)])
        print('Raspi native INT8 connected; model header SHA256:', header_hash, flush=True)

    def on_message(c, userdata, msg):
        try:
            d = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError):
            return
        if not valid_request(d):
            return
        benchmark = msg.topic == 'WEC/benchmark/request'
        if benchmark:
            # Retained control/test messages must never restart a benchmark.
            if msg.retain or not isinstance(d.get('run_id'), str) or d.get('phase') not in ('baseline', 'active') or type(d.get('seq')) is not int:
                return
            state['benchmark_until'] = time.monotonic() + 5
        elif time.monotonic() < state['benchmark_until'] or d['t'] == state['last_live_t']:
            return
        execute = not benchmark or d['phase'] == 'active'
        started = time.perf_counter_ns()
        worker.stdin.write(str(int(execute)) + ' ' + ' '.join(map(str, d['xq'])) + '\n')
        worker.stdin.flush()
        line = worker.stdout.readline()
        if not line:
            raise RuntimeError('Native inference worker stopped')
        out, core_ns = map(int, line.split())
        dispatch_us = (time.perf_counter_ns() - started) / 1000
        result = {'t': d['t'], 'out_q': out if execute else None,
                  'core_us': core_ns / 1000 if execute else None,
                  'dispatch_us': round(dispatch_us, 3), 'executed': execute,
                  'source': 'raspberry-pi', 'implementation': 'C++17 -O2, exported INT8 model',
                  'model_header_sha256': header_hash, 'xq': d['xq']}
        if benchmark:
            result.update(run_id=d['run_id'], phase=d['phase'], seq=d['seq'])
            topic, retain = 'WEC/benchmark/rpi', False
        else:
            state['last_live_t'] = d['t']
            topic, retain = 'WEC/rpi', True
        c.publish(topic, json.dumps(result, separators=(',', ':')), retain=retain)
        if not benchmark:
            print(json.dumps(result), flush=True)

    client.on_connect, client.on_message = on_connect, on_message
    try:
        client.connect(os.environ.get('MQTT_HOST', 'citaitb.com'), int(os.environ.get('MQTT_PORT', '1883')), 30)
        client.loop_forever()
    finally:
        client.disconnect()
        worker.terminate()
        worker.wait(timeout=5)


if __name__ == '__main__':
    main()
