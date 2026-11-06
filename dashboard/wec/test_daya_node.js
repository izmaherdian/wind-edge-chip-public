// Run: node dashboard/wec/test_daya_node.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const run = new Function('msg', 'node', fs.readFileSync(__dirname + '/daya_node.js', 'utf8'));
const reading = { sensor_ok: true, voltage_v: 5.1, current_a: 0.5, power_w: 2.55, energy_wh: 1 };
const check = x => run({payload: {fpga: x}}, {status() {}}).payload.raspberry_pi;
assert.equal(check(reading).power_w, 2.55); // preserve physical channel swap
assert.equal(check(reading).current_available, true);
assert.equal(check({...reading, voltage_v:0.05}).current_available, true);
assert.equal(check({...reading, voltage_v:0.05}).power_w, null);
assert.equal(check({...reading, sensor_ok:false}).current_available, false);
assert.equal(check({...reading, error:'math_overflow', measurement_valid:false}).current_available, false);
assert.equal(check({...reading, error:'conversion_timeout', measurement_valid:false}).current_available, false);
assert.equal(check({...reading, current_a:NaN}).current_available, false);
assert.equal(check({...reading, current_a:-0.5}).current_available, false);
assert.equal(check({...reading, current_a:0, power_w:0}).current_available, true);
for (const bad of [
  {voltage_v: 0.85, power_w: 0.066}, // observed legacy failure
  {sensor_ok: false}, {current_a: -0.5}, {current_a: 3.3},
  {power_w: NaN}, {voltage_v: null}, {power_w: 1},
  {measurement_valid: false, error: 'math_overflow'},
]) {
  const r = check({...reading, ...bad});
  assert.equal(r.power_w, null);
  assert.equal(r.measurement_valid, false);
  assert.ok(r.error);
}
assert.equal(check({...reading, voltage_v: 0.85}).voltage_v, 0.85); // retain diagnostic evidence
assert.deepEqual(check({...reading, voltage_v: 0.7, current_a: 0.5}).raw, {voltage_v: 0.7, current_a: 0.5, power_w: 0.35}); // raw for labelled display
assert.equal(run({payload: {raspberry_pi: reading}}, {status() {}}).payload.fpga.installed, true);
assert.equal(run({payload: '{'}, {status(){}}), null);
console.log('INA219 dashboard validation passed');
