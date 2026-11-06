"""Uji pasif plant → Raspi → Node-RED → ESP32-S3 → FPGA → MQTT.

ml/.venv/bin/python edge/bridge/check_live_path.py --seconds 150 --pairs 2 --report /tmp/wec-live.json
Tidak memublikasikan data, mengakses port serial, atau me-restart layanan.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import threading
import time

import paho.mqtt.client as mqtt

from fpga_bridge import BROKER, PORT, USER, PASS, MODEL, GoldenModelINT8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=150)
    parser.add_argument('--pairs', type=int, default=2)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.seconds <= 0 or args.pairs <= 0:
        parser.error('seconds dan pairs harus positif')
    golden = GoldenModelINT8(model_path=str(MODEL))
    counts = Counter()
    sensors, predictions, replies, completed = {}, {}, {}, {}
    retained, errors = [], []
    done = threading.Event()
    started = time.time()
    required = {'TurbinAngin/voltage', 'TurbinAngin/current', 'TurbinAngin/power',
                'TurbinAngin/windspeedstation'}

    def match(t):
        if t in completed or t not in predictions or t not in replies:
            return
        pred, pred_at = predictions[t]
        reply, reply_at = replies[t]
        xq = pred.get('xq')
        if not isinstance(xq, list) or len(xq) != 16 or any(type(x) is not int or not -128 <= x <= 127 for x in xq):
            return
        expected = golden.forward(xq)[0]
        checks = {
            'matches_golden': reply.get('out_q_fpga') == expected,
            'matches_cpu': reply.get('out_q_cpu') == expected,
            'matches_node_red': pred.get('out_q') is None or pred['out_q'] == expected,
            'cycles_309': reply.get('cycles') == 309,
            'hardware_source': reply.get('sumber') == 'tang-nano-4k' and reply.get('port') == 'ESP32-S3 UART1',
            'fresh_generation': abs(pred_at - t / 1000) < 120,
        }
        item = {'t': t, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t / 1000)),
                'xq': xq, 'golden_q': expected, 'prediction': pred, 'fpga': reply,
                'observed_reply_after_prediction_ms': round((reply_at - pred_at) * 1000, 2),
                'checks': checks, 'passed': all(checks.values())}
        completed[t] = item
        print('Siklus live:', json.dumps({k: item[k] for k in ['utc', 'golden_q', 'checks', 'passed']}), flush=True)
        if sum(p['passed'] for p in completed.values()) >= args.pairs and required <= sensors.keys():
            done.set()

    def on_connect(client, userdata, flags, reason, properties):
        if reason.is_failure:
            errors.append('MQTT connect: ' + str(reason)); done.set(); return
        client.subscribe([('TurbinAngin/#', 0), ('WEC/prediksi', 0), ('WEC/fpga', 0)])
        print('MQTT tersambung; menunggu pesan live baru.', flush=True)

    def on_message(client, userdata, msg):
        received = time.time()
        try:
            value = json.loads(msg.payload)
        except (ValueError, UnicodeDecodeError):
            value = msg.payload.decode(errors='replace')
        if msg.retain:
            if msg.topic in ['WEC/prediksi', 'WEC/fpga']:
                retained.append({'topic': msg.topic, 'payload': value})
                print('Retained (tidak dihitung sebagai uji baru):', msg.topic,
                      json.dumps(value), flush=True)
            return
        counts[msg.topic] += 1
        if msg.topic.startswith('TurbinAngin/'):
            sensors[msg.topic] = {'value': value, 'received_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(received))}
            return
        if not isinstance(value, dict) or type(value.get('t')) not in (int, float):
            return
        t = value['t']
        if msg.topic == 'WEC/prediksi':
            predictions[t] = (value, received)
            print('Fitur baru:', t, 'xq:', len(value.get('xq') or []), flush=True)
        else:
            replies[t] = (value, received)
            print('Balasan chip baru:', json.dumps(value), flush=True)
        match(t)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(USER, PASS)
    client.on_connect, client.on_message = on_connect, on_message
    try:
        client.connect(BROKER, PORT, 30)
        client.loop_start()
        done.wait(args.seconds)
    finally:
        client.disconnect()
        client.loop_stop()
    sensor_ok = required <= sensors.keys()
    # Do not hide a dropped/misidentified cycle just because later pairs matched.
    # Allow a short in-flight reply at the end of the observation window.
    unmatched = [t for t, (pred, seen) in predictions.items()
                 if len(pred.get('xq') or []) == 16 and t not in completed and time.time() - seen > 5]
    passed = sensor_ok and len(completed) >= args.pairs and all(p['passed'] for p in completed.values()) and not errors and not unmatched
    report = {'kind': 'passive live path via Raspberry Pi', 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
              'observed_seconds': round(time.time() - started, 2), 'passed': passed,
              'requested_pairs': args.pairs, 'fresh_sensor_topics_ok': sensor_ok,
              'message_counts': dict(counts), 'latest_sensors': sensors,
              'retained_not_counted': retained, 'cycles': list(completed.values()),
              'prediction_messages': [v[0] for v in predictions.values()],
              'reply_messages': [v[0] for v in replies.values()],
              'fresh_predictions': len(predictions), 'fresh_replies': len(replies), 'errors': errors}
    report['unmatched_prediction_timestamps'] = unmatched
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: report[k] for k in ['passed', 'fresh_sensor_topics_ok', 'fresh_predictions', 'fresh_replies', 'observed_seconds']}), flush=True)
    print('Laporan:', args.report, flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
