import json
from pathlib import Path
import subprocess
import unittest

import patch_template
import skin_hackathon


class ComparisonPanelTests(unittest.TestCase):
    def test_freshness_and_unverified_energy(self):
        path=Path(__file__).resolve().parents[1]/'ta/node-red-flow.json'
        flows=json.loads(path.read_text())
        source=next(n['format'] for n in flows if n.get('id')=='f0305fc45448cd21')
        tpl=skin_hackathon.skin(patch_template.patch(source))
        code=tpl.split('<script>',1)[1].split('</script>',1)[0]
        test='''const assert=require('node:assert/strict');
const o=(new Function(process.argv[1].replace('export default','return')))();
const vm=Object.assign(o.data(),o.methods);
assert.equal(vm.comparisonTiming('raspberry_pi'),null);
const summary={kind:'normal_live',generated_at_ms:Date.now(),matched_pairs:2,mismatches:0,
  rpi_core_us_median:3,fpga_uart_us_median:562,energy:{rpi:{valid:false,average_w:100}}};
o.watch.msg.call(vm,{topic:'WEC/comparison/summary',payload:JSON.stringify(summary)});
assert.equal(vm.comparisonTiming('raspberry_pi'),3);
assert.equal(vm.comparisonTiming('fpga'),562);
assert.equal(vm.comparisonEnergy('raspberry_pi','average_w'),null);
o.watch.msg.call(vm,{topic:'WEC/comparison/summary',payload:{...summary,generated_at_ms:summary.generated_at_ms-1,matched_pairs:1}});
assert.equal(vm.computeComparison.matched_pairs,2);
vm.nowMs+=31000;
assert.equal(vm.comparisonTiming('raspberry_pi'),null);
vm.updateComputeSensor('fpga',{installed:false,current_available:false,current_note:'Belum dipasang',timestamp:Date.now(),current_a:0});
assert.equal(vm.sensorStatus('fpga'),'BELUM DIPASANG');
assert.equal(vm.computePower.fpga.current_a,null);
'''
        subprocess.run(['node','-e',test,code],check=True)


if __name__=='__main__':
    unittest.main()
