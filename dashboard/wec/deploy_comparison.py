"""Deploy only comparison subscription, current function and hackathon template."""
import argparse
import copy
import json
from pathlib import Path
import time

import requests
from deploy import URL, token
from deploy_power import prepare as prepare_power
from comparison_panel import patch_comparison
from layout_flow import arrange, EDITOR_KEYS


def prepare(flows):
    result,_=prepare_power(flows)
    lookup={n['id']:n for n in result}
    lookup['wec_v2_tpl']['format']=patch_comparison(lookup['wec_v2_tpl']['format'])
    if 'wec_comparison_in' not in lookup:
        node=copy.deepcopy(lookup['wec_daya_in'])
        node.update(id='wec_comparison_in',name='WEC: perbandingan Raspi dan FPGA',
                    topic='WEC/comparison/summary',datatype='utf8',wires=[['wec_v2_tpl']])
        result.append(node)
    result,_=arrange(result)
    lookup={n['id']:n for n in result}
    for old in flows:
        if old['id'] in ('wec_daya_fn','wec_v2_tpl'):
            continue
        assert {k:v for k,v in old.items() if k not in EDITOR_KEYS} == {
            k:v for k,v in lookup[old['id']].items() if k not in EDITOR_KEYS},old['id']
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    headers={'Authorization':'Bearer '+token('*'),'Node-RED-API-Version':'v2'}
    r=requests.get(URL+'/flows',headers=headers,timeout=20);r.raise_for_status()
    original=r.json()
    candidate=prepare(original['flows'])
    args.backup_dir.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime('%Y%m%d_%H%M%S',time.gmtime())
    for label,data in [('before',original),('candidate',{'rev':original['rev'],'flows':candidate})]:
        path=args.backup_dir/f'comparison_{label}_{stamp}.json'
        path.write_text(json.dumps(data,ensure_ascii=False));path.chmod(0o600)
        print(label+':',path,flush=True)
    if not args.apply:
        return
    r=requests.post(URL+'/flows',headers={**headers,'Node-RED-Deployment-Type':'nodes'},
                    json={'rev':original['rev'],'flows':candidate},timeout=30);r.raise_for_status()
    r=requests.get(URL+'/flows',headers=headers,timeout=20);r.raise_for_status()
    assert {n['id']:n for n in r.json()['flows']}=={n['id']:n for n in candidate}
    print('Comparison deployed; acquisition and ML engine unchanged.',flush=True)


if __name__=='__main__':
    main()
