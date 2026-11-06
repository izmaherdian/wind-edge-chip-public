"""Backup lalu ubah hanya function INA219 dan template hackathon.

NR_PASS=... python dashboard/wec/deploy_power.py --backup-dir /tmp/wec-backup [--apply]
Tanpa --apply, hanya menyiapkan kandidat flow untuk diperiksa.
"""
import argparse
import copy
import json
import time
from pathlib import Path

import requests

from deploy import URL, token
from comparison_panel import patch_comparison
from power_panel import patch_current_panel


def prepare(flows):
    result = copy.deepcopy(flows)
    for node_id in ('wec_daya_fn', 'wec_v2_tpl'):
        assert sum(n.get('id') == node_id for n in result) == 1, f'{node_id} tidak tunggal'
    for node in result:
        if node.get('id') == 'wec_daya_fn':
            assert node['type'] == 'function'
            node['func'] = Path(__file__).with_name('daya_node.js').read_text()
        elif node.get('id') == 'wec_v2_tpl':
            assert node['type'] == 'ui-template'
            node['format'] = patch_comparison(patch_current_panel(node['format']))
    changed = {a['id'] for a, b in zip(flows, result) if a != b}
    assert changed <= {'wec_daya_fn', 'wec_v2_tpl'}
    return result, sorted(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    headers = {'Authorization': 'Bearer ' + token('*'), 'Node-RED-API-Version': 'v2'}
    response = requests.get(URL + '/flows', headers=headers, timeout=20)
    response.raise_for_status()
    original = response.json()
    candidate, changed = prepare(original['flows'])
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    backup = args.backup_dir / f'power_before_{stamp}.json'
    backup.write_text(json.dumps(original, ensure_ascii=False))
    backup.chmod(0o600)
    proposal = args.backup_dir / f'power_candidate_{stamp}.json'
    proposal.write_text(json.dumps({'rev': original['rev'], 'flows': candidate}, ensure_ascii=False))
    proposal.chmod(0o600)
    print('Backup:', backup)
    print('Node berubah:', ', '.join(changed) or 'tidak ada')
    if not args.apply or not changed:
        print('Kandidat:', proposal)
        return
    response = requests.post(URL + '/flows', headers={**headers, 'Node-RED-Deployment-Type': 'nodes'},
                             json={'rev': original['rev'], 'flows': candidate}, timeout=30)
    response.raise_for_status()
    response = requests.get(URL + '/flows', headers=headers, timeout=20)
    response.raise_for_status()
    deployed = {n['id']: n for n in response.json()['flows']}
    for node in candidate:
        assert deployed[node['id']] == node, f'Verifikasi gagal: {node["id"]}'
    print('Deploy dan verifikasi berhasil; hanya dua node panel INA219 berubah.')


if __name__ == '__main__':
    main()
