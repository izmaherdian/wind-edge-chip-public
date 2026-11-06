"""Deploy read-only 3-hour Sheet history to the Hackathon page and ML warm start.

NR_PASS=... python deploy_history.py --seed-row 326586 --backup-dir DIR [--apply]
The seed row comes from a local CSV export; append acknowledgements and a
retained MQTT cursor keep it current. Existing Sheet writes and TA UI stay intact.
"""
import argparse
import copy
import json
from pathlib import Path
import time

import requests
from deploy import URL, token
from history_panel import patch_history_panel, patch_history_seed

HERE = Path(__file__).resolve().parent
GROUP = 'wec_history_group'
MANAGER = 'wec_history_manager'


def manager_code(seed_row):
    assert isinstance(seed_row, int) and seed_row >= 2
    core = '\n'.join(line for line in (HERE / 'history_core.js').read_text().splitlines()
                     if not line.startswith('if (typeof module'))
    return core + f'\nconst HISTORY_SEED_ROW = {seed_row};\n' + (HERE / 'history_node.js').read_text()


def prepare(flows, seed_row):
    result = copy.deepcopy(flows)
    nodes = {n['id']: n for n in result}
    tab = nodes['wec_engine']['z']
    nodes['wec_engine']['func'] = patch_history_seed(nodes['wec_engine']['func'])
    tpl = nodes['wec_v2_tpl']
    tpl['format'] = patch_history_panel(tpl['format'])
    for owner in [tpl, nodes['451097ab252e6e1f']]:
        if not owner.get('wires'):
            owner['wires'] = [[]]
        if MANAGER not in owner['wires'][0]:
            owner['wires'][0].append(MANAGER)
    def put(node):
        old = nodes.get(node['id'])
        if old is not None:
            result[result.index(old)] = node
        else:
            result.append(node)
        nodes[node['id']] = node
    common = {'z': tab, 'g': GROUP}
    put({**common, 'id': MANAGER, 'type': 'function', 'name': 'Riwayat 3 jam · cache + cursor',
         'func': manager_code(seed_row), 'outputs': 4, 'timeout': 0, 'noerr': 0,
         'initialize': '', 'finalize': '', 'libs': [], 'x': 1420, 'y': 2160,
         'wires': [['wec_history_sheet'], ['wec_v2_tpl'], ['wec_engine'], ['wec_mqtt_out']]})
    reader = copy.deepcopy(nodes['gsheet_read_all'])
    assert reader['type'] == 'GSheet' and reader['method'] == 'get'
    reader.update({**common, 'id': 'wec_history_sheet', 'name': 'Baca Sheet · rentang terbatas',
                   'cells': '', 'flatten': False, 'x': 1840, 'y': 2110, 'wires': [[MANAGER]]})
    put(reader)
    put({**common, 'id': 'wec_history_refresh', 'type': 'inject', 'name': 'Riwayat: boot + tiap 5 menit',
         'props': [{'p': 'topic', 'vt': 'str'}], 'repeat': '300', 'crontab': '', 'once': True,
         'onceDelay': '8', 'topic': 'wec/history/refresh', 'x': 1080, 'y': 2080, 'wires': [[MANAGER]]})
    sub = copy.deepcopy(nodes['wec_fpga_in'])
    sub.update({**common, 'id': 'wec_history_cursor', 'name': 'Cursor Sheet (retained)',
                'topic': 'WEC/history/cursor', 'datatype': 'utf8', 'x': 1080, 'y': 2170, 'wires': [[MANAGER]]})
    put(sub)
    put({**common, 'id': 'wec_history_error', 'type': 'catch', 'name': 'Gagal baca riwayat',
         'scope': ['wec_history_sheet'], 'uncaught': False, 'x': 1840, 'y': 2210, 'wires': [[MANAGER]]})
    put({'id': GROUP, 'type': 'group', 'z': tab, 'name': '09 · Riwayat 3 jam & pemulihan ML',
         'style': {'label': True, 'stroke': '#8296a3', 'fill': '#e8f0f5', 'fill-opacity': '0.35', 'color': '#34495e'},
         'nodes': [MANAGER, 'wec_history_sheet', 'wec_history_refresh', 'wec_history_cursor', 'wec_history_error'],
         'x': 850, 'y': 2000, 'w': 1260, 'h': 300})
    allowed = {'wec_engine', 'wec_v2_tpl', '451097ab252e6e1f'}
    after = {n['id']: n for n in result}
    for old in flows:
        if old['id'] not in allowed and old['id'] not in {GROUP, MANAGER, 'wec_history_sheet', 'wec_history_refresh', 'wec_history_cursor', 'wec_history_error'}:
            assert after[old['id']] == old, old['id']
    # The writer changes only its output wiring, never credentials/method/range.
    before_writer = nodes['451097ab252e6e1f']
    original_writer = next(n for n in flows if n['id'] == '451097ab252e6e1f')
    assert {k: v for k, v in before_writer.items() if k != 'wires'} == {k: v for k, v in original_writer.items() if k != 'wires'}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seed-row', type=int, required=True)
    ap.add_argument('--backup-dir', type=Path, required=True)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    headers = {'Authorization': 'Bearer ' + token('*'), 'Node-RED-API-Version': 'v2'}
    r = requests.get(URL + '/flows', headers=headers, timeout=30); r.raise_for_status()
    before = r.json()
    candidate = prepare(before['flows'], args.seed_row)
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    for name, body in [('before', before), ('candidate', {'rev': before['rev'], 'flows': candidate})]:
        p = args.backup_dir / f'history_{name}_{stamp}.json'
        p.write_text(json.dumps(body, ensure_ascii=False)); p.chmod(0o600)
        print(name + ':', p, flush=True)
    if not args.apply:
        return
    r = requests.post(URL + '/flows', headers={**headers, 'Node-RED-Deployment-Type': 'nodes'},
                      json={'rev': before['rev'], 'flows': candidate}, timeout=45); r.raise_for_status()
    r = requests.get(URL + '/flows', headers=headers, timeout=30); r.raise_for_status()
    assert {n['id']: n for n in r.json()['flows']} == {n['id']: n for n in candidate}
    print('Riwayat 3 jam diterapkan; writer Sheet dan dashboard TA tidak diubah.', flush=True)


if __name__ == '__main__':
    main()
