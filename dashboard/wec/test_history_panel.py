import json
from pathlib import Path
import subprocess
import unittest

import patch_template
import skin_hackathon
from history_panel import patch_history_panel, patch_history_seed
from deploy_history import prepare


class HistoryPanelTests(unittest.TestCase):
    def test_history_does_not_change_live_values(self):
        flows = json.loads((Path(__file__).parents[1] / 'ta/node-red-flow.json').read_text())
        original = next(n['format'] for n in flows if n['id'] == 'f0305fc45448cd21')
        template = skin_hackathon.skin(patch_template.patch(original))
        self.assertEqual(patch_history_panel(template), template)
        code = template.split('<script>', 1)[1].split('</script>', 1)[0]
        test = '''const assert=require('node:assert/strict');
const opts=(new Function(process.argv[1].replace('export default','return')))();
const vm=Object.assign(opts.data(),opts.methods);vm.chartsReady=false;
vm.t1.currentData.power=99;vm.t1.energyVal='1234';
const t=Math.floor(Date.now()/60000)*60000-120000;
vm.applyHistory3h({rows:[{serverTime:t,power:10,voltage:40,current:0.25}]});
assert.equal(vm.t1.currentData.power,99);assert.equal(vm.t1.energyVal,'1234');
assert.ok(vm.t1.powerData.includes(10));assert.ok(vm.t1.powerData.includes(null));
vm.applyHistory3h({rows:[{serverTime:t,power:88}]},true);
vm.applyHistory3h({rows:[{serverTime:t,power:11}]});
assert.equal(vm.history3h.find(r=>r.serverTime===t).power,88);
assert.ok(vm.history3h.length<=181);
'''
        subprocess.run(['node', '-e', test, code], check=True)

    def test_targeted_and_idempotent_prepare(self):
        flows = json.loads((Path(__file__).parents[1] / 'ta/node-red-flow.json').read_text())
        candidate = prepare(flows, 326586)
        self.assertEqual(prepare(candidate, 326586), candidate)
        old = {n['id']: n for n in flows}
        new = {n['id']: n for n in candidate}
        changed = {k for k in old if old[k] != new[k]}
        self.assertEqual(changed, {'wec_engine', 'wec_v2_tpl', '451097ab252e6e1f'})
        self.assertEqual(old['f0305fc45448cd21'], new['f0305fc45448cd21'])
        self.assertEqual(new['wec_history_sheet']['method'], 'get')
        self.assertEqual(new['wec_history_sheet']['cells'], '')
        self.assertEqual(patch_history_seed(new['wec_engine']['func']), new['wec_engine']['func'])


if __name__ == '__main__':
    unittest.main()
