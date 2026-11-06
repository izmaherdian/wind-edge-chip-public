"""Run: python3 dashboard/wec/test_power_panel.py"""
import json
from pathlib import Path
import subprocess
import unittest

import patch_template
import skin_hackathon
from deploy_power import prepare
from power_panel import patch_current_panel

ROOT = Path(__file__).resolve().parents[2]


class CurrentPanelTest(unittest.TestCase):
    def test_current_lifecycle_and_targeted_deploy(self):
        flows = json.loads((ROOT / 'dashboard/ta/node-red-flow.json').read_text())
        source = next(n['format'] for n in flows if n.get('id') == 'f0305fc45448cd21')
        template = skin_hackathon.skin(patch_template.patch(source))
        self.assertEqual(patch_current_panel(template), template)
        panel = template.split('<!-- wec-power-vaw-v5 -->')[1].split('</section>', 1)[0]
        self.assertIn('power_w', panel)
        self.assertIn('voltage_v', panel)
        self.assertIn('current_a', panel)
        self.assertNotIn('energy_wh', panel)
        code = template.split('<script>', 1)[1].split('</script>', 1)[0]
        js = '''const assert = require('node:assert/strict');
const opts = (new Function(process.argv[1].replace('export default', 'return')))();
const vm = Object.assign(opts.data(), opts.methods);
const key = 'raspberry_pi';
assert.equal(vm.sensorStatus(key), 'MENUNGGU SENSOR');
const t = Date.now();
const good = {voltage_v:5.1,current_a:0.5866,power_w:2.9917,measurement_valid:true,current_available:true,timestamp:t};
vm.updateComputeSensor(key, good);
assert.equal(vm.computePower[key].current_a,0.5866);
assert.equal(vm.sensorStatus(key),'DATA TERBACA');
assert.equal(vm.computeMetric(key,'power_w'),2.9917);
assert.equal(vm.computeMetric(key,'voltage_v'),5.1);
vm.nowMs = t+31000;
assert.equal(vm.sensorStatus(key),'DATA LAMA');
assert.equal(vm.computeMetric(key,'power_w'),null);
vm.updateComputeSensor(key, {...good,measurement_valid:false, timestamp:t+1});
assert.equal(vm.computePower[key].current_a,null);
assert.equal(vm.sensorStatus(key),'DATA TIDAK VALID');
vm.updateComputeSensor(key, {...good,current_a:0.6,power_w:3.06,timestamp:t+2});
assert.equal(vm.sensorStatus(key),'DATA TERBACA');
vm.updateComputeSensor(key, {...good,timestamp:t});
assert.equal(vm.computePower[key].current_a,0.6);
vm.updateComputeSensor(key, {...good,timestamp:t+100000});
assert.equal(vm.sensorStatus(key),'DATA TIDAK VALID');
vm.updateComputeSensor(key, {...good,voltage_v:0.5,timestamp:t+100001});
assert.equal(vm.computeMetric(key,'voltage_v'),null);
vm.updateComputeSensor(key, {...good,voltage_v:0.7,power_w:null,measurement_valid:false,error:'voltage_outside_5v_rail',raw:{voltage_v:0.7,current_a:0.55,power_w:0.385},timestamp:Date.now()});
assert.equal(vm.sensorStatus(key),'MENTAH · BELUM VALID');
assert.equal(vm.computeMetric(key,'voltage_v'),0.7);
assert.equal(vm.computeMetric(key,'current_a'),0.55);
vm.nowMs = Date.now()+40000;
assert.equal(vm.sensorStatus(key),'DATA TIDAK VALID');
assert.equal(vm.computeMetric(key,'current_a'),null);
vm.updateComputeSensor('fpga', {...good,installed:false});
assert.equal(vm.sensorStatus('fpga'),'BELUM DIPASANG');
assert.equal(vm.computeMetric('fpga','power_w'),null);
'''
        subprocess.run(['node', '-e', js, code], check=True)
        sample = [
            {'id': 'wec_daya_fn', 'type': 'function', 'func': 'old', 'wires': [['wec_v2_tpl']]},
            {'id': 'wec_v2_tpl', 'type': 'ui-template', 'format': template},
            {'id': 'wec_engine', 'func': 'unchanged'},
        ]
        candidate, changed = prepare(sample)
        self.assertEqual(changed, ['wec_daya_fn'])
        self.assertEqual(candidate[2], sample[2])


if __name__ == '__main__':
    unittest.main()
