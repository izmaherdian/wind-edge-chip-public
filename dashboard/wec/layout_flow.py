"""Rapikan editor tab Turbin angin tanpa mengubah kode/wiring runtime.

NR_PASS=... python dashboard/wec/layout_flow.py --backup-dir DIR [--apply]
"""
import argparse
import copy
import json
from pathlib import Path
import time

import requests

from deploy import URL, token


EDITOR_KEYS = {'x', 'y', 'w', 'h', 'g', 'nodes'}


def arrange(flows):
    result = copy.deepcopy(flows)
    lookup = {n['id']: n for n in result}
    tab = lookup['wec_engine']['z']
    assert lookup[tab]['label'] == 'Turbin angin'
    positioned = set()

    def group(group_id, name, box, positions, color='#e8f0f5'):
        if group_id not in lookup:
            node = {'id': group_id, 'type': 'group', 'z': tab, 'name': name,
                    'style': {'label': True, 'stroke': '#8296a3', 'fill': color,
                              'fill-opacity': '0.35', 'color': '#34495e'}}
            result.append(node)
            lookup[group_id] = node
        node = lookup[group_id]
        assert node['type'] == 'group' and node['z'] == tab
        node.update(dict(zip(('x', 'y', 'w', 'h'), box)))
        node['nodes'] = list(positions)
        for node_id, (x, y) in positions.items():
            child = lookup[node_id]
            assert child.get('z') == tab and node_id not in positioned
            assert box[0] < x < box[0] + box[2] and box[1] < y < box[1] + box[3]
            child.update(x=x, y=y, g=group_id)
            positioned.add(node_id)

    topics = ['voltage', 'current', 'power', 'energy', 'Windspeed', 'ML_Status',
              'windspeedstation', 'winddirdeg', 'temperature', 'humidity', 'noise', 'rainfall']
    for number, prefix, y0, height in [(1, 'TurbinAngin/', 80, 800), (2, 'TurbinAngin2/', 940, 440)]:
        positions = {}
        inputs = [n for n in result if n.get('z') == tab and n.get('type') == 'mqtt in'
                  and n.get('topic', '').startswith(prefix) and not n['id'].startswith('wec_')]
        inputs.sort(key=lambda n: topics.index(n['topic'][len(prefix):]))
        assert len(inputs) == (12 if number == 1 else 6)
        for row, node in enumerate(inputs):
            y = y0 + 70 + row * 60
            positions[node['id']] = (280, y)
            debug = [target for output in node.get('wires', []) for target in output
                     if lookup[target]['type'] == 'debug']
            assert len(debug) == 1
            positions[debug[0]] = (650, y)
        group(f'wec_layout_inputs_{number}', f'0{number} · Sensor Turbin {number} + debug',
              (40, y0, 740, height), positions)

    group('wec_layout_processing', '03 · Pengolahan, penyimpanan & replay', (850, 80, 800, 420), {
        'a9da8f077ca7adc5': (1070, 150), '451097ab252e6e1f': (1460, 150),
        '872496a0174ecdf1': (1070, 230), 'a80ba0f53fd29d4e': (1460, 230),
        'c813e4310414e222': (1070, 330), 'node_storage_manager': (1460, 330),
        'ui_control_trigger': (1070, 430),
    })
    group('wec_layout_dashboards', '04 · Halaman dashboard', (1720, 80, 650, 420), {
        'f0305fc45448cd21': (2030, 190), 'wec_v2_tpl': (2030, 350),
    }, '#f5ede1')
    group('wec_group', '', (850, 560, 1520, 460), {
        'wec_mqtt_in': (1100, 630), 'wec_tick': (1100, 690),
        'wec_om_tick': (1100, 760), 'wec_om_http': (1450, 760),
        'wec_state_sub': (1100, 850), 'wec_state_in': (1450, 850),
        'wec_fpga_in': (1450, 940),
        'wec_engine': (1840, 690), 'wec_mqtt_out': (2190, 790),
    })
    current_positions = {'wec_daya_in': (1130, 1190), 'wec_daya_fn': (1630, 1190)}
    if 'wec_comparison_in' in lookup:
        current_positions['wec_comparison_in'] = (1130, 1310)
    group('wec_layout_current', '06 · INA219 → arus perangkat (A)',
          (850, 1080, 1520, 310 if 'wec_comparison_in' in lookup else 210), current_positions, '#edf3e5')
    for group_id, y, ids in [
        ('group_backend_logic', 1460, ['link_in_dash', 'switch_topic_handler', 'gsheet_read_all',
                                     'func_filter_logic', 'link_out_dash', 'debug_backend']),
        ('50a658999c079d89', 1720, ['8cf5eb2c2cfa98e3', 'a327a7d7dea1feac', '41dbabce4acbefb8',
                                 'd259aff03afc6bb1', '291d51c2749e1fea', 'd54dfa8868045fc5']),
    ]:
        coordinates = [(100, y + 80), (310, y + 80), (660, y + 80),
                       (1050, y + 80), (1370, y + 80), (1370, y + 150)]
        group(group_id, '', (40, y, 1500, 210), dict(zip(ids, coordinates)))

    if 'wec_history_manager' in lookup:
        group('wec_history_group', '09 · Riwayat 3 jam & pemulihan ML', (850, 2000, 1260, 300), {
            'wec_history_refresh': (1080, 2080), 'wec_history_cursor': (1080, 2170),
            'wec_history_manager': (1420, 2160), 'wec_history_sheet': (1840, 2110),
            'wec_history_error': (1840, 2210),
        })

    expected = {n['id'] for n in flows if n.get('z') == tab
                and n.get('type') != 'group' and 'x' in n and 'y' in n}
    assert positioned == expected, f'Node belum ditata: {expected - positioned}'
    # Prove every pre-existing non-editor property is unchanged, including wires.
    for old in flows:
        new = lookup[old['id']]
        assert {k: v for k, v in old.items() if k not in EDITOR_KEYS} == {
            k: v for k, v in new.items() if k not in EDITOR_KEYS}, old['id']
        if old.get('z') != tab:
            assert old == new, old['id']
    return result, len(positioned)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    headers = {'Authorization': 'Bearer ' + token('*'), 'Node-RED-API-Version': 'v2'}
    response = requests.get(URL + '/flows', headers=headers, timeout=20)
    response.raise_for_status()
    original = response.json()
    candidate, count = arrange(original['flows'])
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    for label, content in [('before', original), ('candidate', {'rev': original['rev'], 'flows': candidate})]:
        path = args.backup_dir / f'layout_{label}_{stamp}.json'
        path.write_text(json.dumps(content, ensure_ascii=False))
        path.chmod(0o600)
        print(label + ':', path)
    print('Node ditata:', count, '· kode, wiring dan konfigurasi runtime identik.')
    if not args.apply:
        return
    response = requests.post(URL + '/flows', headers={**headers, 'Node-RED-Deployment-Type': 'nodes'},
                             json={'rev': original['rev'], 'flows': candidate}, timeout=30)
    response.raise_for_status()
    response = requests.get(URL + '/flows', headers=headers, timeout=20)
    response.raise_for_status()
    assert {n['id']: n for n in response.json()['flows']} == {n['id']: n for n in candidate}
    print('Deploy dan pemeriksaan ulang layout berhasil.')


if __name__ == '__main__':
    main()
