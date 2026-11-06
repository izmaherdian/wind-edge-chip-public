"""Deploy native model and an independent user service; preserve sensor service.

Uses the SSH alias already configured by the team. MQTT credentials are sent via
stdin to a private environment file, never embedded in the command or logged.
"""
import argparse
import csv
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'edge/bridge'))
from fpga_bridge import BROKER, PORT, USER, PASS

REMOTE = r'''
import hashlib, json, os, pathlib, shutil, subprocess, sys, time
d = json.load(sys.stdin)
root = pathlib.Path.home() / 'wec-comparison'
root.mkdir(mode=0o700, exist_ok=True)
root.chmod(0o700)
backup = root / ('backup-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
for name, content in d['files'].items():
    assert pathlib.Path(name).name == name
    path = root / name
    if path.exists():
        backup.mkdir(mode=0o700, exist_ok=True)
        shutil.copy2(path, backup / name)
    path.write_text(content)
    path.chmod(0o600)
subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I', str(root), str(root/'inference_worker.cpp'), '-o', str(root/'inference_worker')], check=True)
lines = ['1 ' + ' '.join(map(str, x)) for x,y in d['vectors']]
p = subprocess.run([str(root/'inference_worker')], input='\n'.join(lines)+'\n', capture_output=True, text=True, check=True)
values = [int(line.split()[0]) for line in p.stdout.splitlines()]
assert values == [y for x,y in d['vectors']]
print('Raspi native model:', len(values), '/', len(values), 'vectors identical', flush=True)
unitdir = pathlib.Path.home()/'.config/systemd/user'
unitdir.mkdir(parents=True, exist_ok=True)
unit = unitdir/'wec-inference.service'
if unit.exists():
    backup.mkdir(mode=0o700, exist_ok=True)
    shutil.copy2(unit, backup/'wec-inference.service')
unit.write_text(d['unit'])
recorder = unitdir/'wec-comparison-record.service'
recorder.write_text(d['recorder_unit'])
if not (root/'meter.json').exists():
    shutil.copy2(root/'meter.example.json',root/'meter.json')
env = dict(os.environ, XDG_RUNTIME_DIR='/run/user/'+str(os.getuid()))
env['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path='+env['XDG_RUNTIME_DIR']+'/bus'
for command in [['systemctl','--user','daemon-reload'],
                ['systemctl','--user','enable','wec-inference.service'],
                ['systemctl','--user','restart','wec-inference.service'],
                ['systemctl','--user','enable','wec-comparison-record.service'],
                ['systemctl','--user','restart','wec-comparison-record.service'],
                ['systemctl','--user','is-active','wec-comparison-record.service'],
                ['systemctl','--user','is-active','wec-inference.service'],
                ['systemctl','is-active','nodered_duadata']]:
    subprocess.run(command, env=env, check=True)
subprocess.run(['loginctl','show-user',os.environ['USER'],'-p','Linger'], check=True)
print('Model header SHA256:',hashlib.sha256((root/'mlp_int8.h').read_bytes()).hexdigest(), flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='RASPI-TURBIN')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    sources = {'inference_worker.cpp': ROOT/'measurements/inference_worker.cpp',
               'rpi_inference.py': ROOT/'measurements/rpi_inference.py',
               'live_record.py': ROOT/'measurements/live_record.py',
               'energy.py': ROOT/'measurements/energy.py',
               'meter.example.json': ROOT/'measurements/meter.example.json',
               'mlp_int8.h': ROOT/'ml/forecast/model/export/mlp_int8.h'}
    if not args.apply:
        print('Deploy candidate:', ', '.join(sources), 'and user service wec-inference.service to', args.host)
        return
    files = {name: path.read_text() for name, path in sources.items()}
    files['mqtt.env'] = '\n'.join(k+'='+json.dumps(str(v)) for k,v in {
        'MQTT_HOST': BROKER, 'MQTT_PORT': PORT, 'MQTT_USER': USER, 'MQTT_PASS': PASS}.items())+'\n'
    with (ROOT/'ml/forecast/model/export/test_vectors.csv').open() as f:
        vectors = [([int(row[f'x{i}']) for i in range(16)], int(row['out_q'])) for row in csv.DictReader(f)]
    payload = {'files': files, 'vectors': vectors, 'unit': (ROOT/'measurements/rpi-inference.service').read_text(),
               'recorder_unit': (ROOT/'measurements/comparison-record.service').read_text()}
    subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',args.host,
                    'python3 -c '+shlex.quote(REMOTE)], input=json.dumps(payload), text=True, check=True)


if __name__ == '__main__':
    main()
