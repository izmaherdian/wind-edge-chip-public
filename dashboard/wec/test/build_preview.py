"""Pratinjau lokal template dashboard (Vue 3 asli) dengan pesan contoh Mesin WEC.
Pemakaian: python build_preview.py template.vue keluaran.html"""
import json, re, sys, time
from pathlib import Path
tpl = Path(sys.argv[1]).read_text()
msgs = json.loads((Path(__file__).with_name("ref") / "sample_msgs.json").read_text())
now = int(time.time() * 1000)
for m in msgs:
    if m["topic"] == "prediction_1h":
        m["payload"]["generated_at"], m["payload"]["target_at"] = now - 30000, now - 30000 + 3600000
    if m["topic"] == "wec_ml":
        m["payload"]["t"] = now
template = re.search(r"^<template>\n(.*)\n</template>", tpl, re.S | re.M).group(1)
script = tpl[tpl.index("<script>") + 8: tpl.index("</script>\n\n<style>")]
style = tpl[tpl.rindex("<style>") + 7: tpl.rindex("</style>")]
html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/vue@3.4.38/dist/vue.global.prod.js"></script><style>body{{margin:0;background:#fff}}{style}</style></head>
<body><div id="app"></div>
<script id="tpl" type="text/x-template">{template}</script>
<script>
window.__errors = [];
window.addEventListener('error', e => window.__errors.push(String(e.message)));
const opts = (function() {{ {script.replace("export default", "return")} }})();
const MSGS = {json.dumps(msgs)};
const app = Vue.createApp({{ ...opts, template: '#tpl',
  data() {{ const d = opts.data ? opts.data.call(this) : {{}}; d.msg = null; d.id = 'preview'; return d; }},
  methods: {{ ...(opts.methods || {{}}), send(m) {{ console.log('send', JSON.stringify(m)); }} }} }});
app.config.errorHandler = (err) => {{ window.__errors.push('vue: ' + err.message); console.error(err); }};
const vm = app.mount('#app');
let k = 0; const feed = () => {{ if (k < MSGS.length) {{ vm.msg = MSGS[k++]; setTimeout(feed, 200); }} }};
setTimeout(feed, 800);
setTimeout(() => {{ document.title = 'errors:' + window.__errors.length + ' ' + window.__errors.slice(0, 3).join(' | '); }}, 9000);
</script></body></html>"""
Path(sys.argv[2]).write_text(html)
print("pratinjau:", sys.argv[2])
