"""Deploy Mesin WEC + halaman "Hackathon" ke Node-RED citaitb.com (tab "Turbin angin" milik Genis).

Dashboard Genis (/dashboard/dashboard) dibiarkan asli; semua tambahan ada di /dashboard/hackathon
(dulu /dashboard/v2; id node tetap wec_v2_* supaya kabel dari node Genis tidak berubah).
Yang dilakukan:
1. Backup seluruh flows ke folder --backup-dir (wajib; tidak masuk git karena berisi proyek lain).
2. Ambil template "ECharts Neon Component" asli dari server. Kalau di server sudah ter-patch (deploy lama),
   pulihkan dari backup --genis-from.
3. Halaman hackathon = skin_hackathon(patch_template(template asli)), mendapat masukan yang sama dengan template Genis.
4. Tambah/ganti node berawalan "wec_" (mesin ML, MQTT, inject, Open-Meteo, halaman hackathon); mesin ML hanya ke halaman hackathon.
5. Tambah kabel dari ui-control "Deteksi Refresh" ke mesin WEC (kirim ulang hasil saat browser tersambung).
6. POST /flows dengan Node-RED-Deployment-Type: nodes (hanya node yang berubah yang di-restart).

Pemakaian:
  NR_PASS=... python deploy.py --backup-dir DIR [--genis-from BACKUP_ASLI]   # deploy
  NR_PASS=... python deploy.py --backup-dir DIR --dry-run                    # hanya cek, tidak menulis
  NR_PASS=... python deploy.py --rollback FILE_BACKUP                        # kembalikan flows dari backup
"""

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patch_template  # noqa: E402
import skin_hackathon  # noqa: E402

URL = "http://citaitb.com:1880"
USER = "cita"
TEMPLATE_ID = "f0305fc45448cd21"
UI_CONTROL_NAME = "Deteksi Refresh"
TAB_LABEL = "Turbin angin"
BROKER_ID = "20523929991a95dc"
OPENMETEO = ("https://api.open-meteo.com/v1/forecast?latitude=-6.891&longitude=107.610"
             "&hourly=wind_speed_10m,surface_pressure&wind_speed_unit=ms&timezone=GMT&past_days=1&forecast_days=2")


def token(scope):
    r = requests.post(f"{URL}/auth/token", data={"client_id": "node-red-admin", "grant_type": "password", "scope": scope,
                                                 "username": USER, "password": os.environ["NR_PASS"]}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def engine_code():
    core = (HERE / "engine_core.js").read_text()
    core = "\n".join(l for l in core.splitlines() if not l.startswith("if (typeof module"))
    bundle = (HERE / "model_bundle.json").read_text()
    return core + "\nconst BUNDLE = " + bundle + ";\n" + (HERE / "engine_node.js").read_text()


def wec_nodes(tab, x0=140, y0=1180):
    g = "wec_group"
    n = lambda **k: {"z": tab, "g": g, **k}
    nodes = [
        n(id="wec_mqtt_in", type="mqtt in", name="WEC: data turbin live", topic="TurbinAngin/#", qos="0", datatype="utf8",
          broker=BROKER_ID, nl=False, rap=True, rh=0, inputs=0, x=x0 + 60, y=y0, wires=[["wec_engine"]]),
        # subscribe dinamis 5 detik setelah start: pesan retained baru datang saat mesin sudah siap
        n(id="wec_state_sub", type="inject", name="WEC: minta snapshot", props=[{"p": "action", "v": "subscribe", "vt": "str"},
          {"p": "topic", "v": "WEC/state", "vt": "str"}], repeat="", crontab="", once=True, onceDelay="5", topic="WEC/state",
          x=x0 + 60, y=y0 + 150, wires=[["wec_state_in"]]),
        n(id="wec_state_in", type="mqtt in", name="WEC: pulihkan riwayat (WEC/state)", topic="", topicType="dynamic", qos="0", datatype="utf8",
          broker=BROKER_ID, nl=False, rap=True, rh=0, inputs=1, x=x0 + 260, y=y0 + 150, wires=[["wec_engine"]]),
        n(id="wec_fpga_in", type="mqtt in", name="WEC: hasil chip FPGA (WEC/fpga)", topic="WEC/fpga", qos="0", datatype="utf8",
          broker=BROKER_ID, nl=False, rap=True, rh=0, inputs=0, x=x0 + 520, y=y0 + 150, wires=[["wec_engine"]]),
        n(id="wec_daya_in", type="mqtt in", name="WEC: daya komputasi (WEC/daya)", topic="WEC/daya", qos="0", datatype="utf8",
          broker=BROKER_ID, nl=False, rap=True, rh=0, inputs=0, x=x0 + 80, y=y0 + 200, wires=[["wec_daya_fn"]]),
        n(id="wec_daya_fn", type="function", name="INA219 -> panel Konsumsi Daya", func=(HERE / "daya_node.js").read_text(), outputs=1,
          timeout=0, noerr=0, initialize="", finalize="", libs=[], x=x0 + 360, y=y0 + 200, wires=[["wec_v2_tpl"]]),
        n(id="wec_comparison_in", type="mqtt in", name="WEC: perbandingan Raspi dan FPGA", topic="WEC/comparison/summary", qos="0", datatype="utf8",
          broker=BROKER_ID, nl=False, rap=True, rh=0, inputs=0, x=x0 + 80, y=y0 + 260, wires=[["wec_v2_tpl"]]),
        n(id="wec_tick", type="inject", name="WEC: tiap menit", props=[{"p": "topic", "vt": "str"}], repeat="60", crontab="",
          once=False, onceDelay=0.1, topic="wec/tick", x=x0 + 50, y=y0 + 50, wires=[["wec_engine"]]),
        n(id="wec_om_tick", type="inject", name="WEC: Open-Meteo tiap jam", props=[{"p": "topic", "vt": "str"}], repeat="3600",
          crontab="", once=True, onceDelay="5", topic="wec/openmeteo", x=x0 + 80, y=y0 + 100, wires=[["wec_om_http"]]),
        n(id="wec_om_http", type="http request", name="Open-Meteo prakiraan", method="GET", ret="obj", paytoqs="ignore",
          url=OPENMETEO, tls="", persist=False, proxy="", insecureHTTPParser=False, authType="", senderr=False, headers=[],
          x=x0 + 320, y=y0 + 100, wires=[["wec_engine"]]),
        n(id="wec_engine", type="function", name="Mesin WEC (ML 3 fitur, INT8 = FPGA)", func=engine_code(), outputs=2,
          timeout=0, noerr=0, initialize="", finalize="", libs=[], x=x0 + 600, y=y0 + 40, wires=[["wec_v2_tpl"], ["wec_mqtt_out"]]),
        n(id="wec_mqtt_out", type="mqtt out", name="WEC/* (hasil ML)", topic="", qos="0", retain="", respTopic="", contentType="",
          userProps="", correl="", expiry="", broker=BROKER_ID, x=x0 + 880, y=y0 + 80, wires=[]),
    ]
    group = {"id": g, "type": "group", "z": tab, "name": "Wind Edge Chip · Mesin ML (prediksi 1 jam, status, baterai)",
             "style": {"label": True, "stroke": "#2c5e68", "fill": "#e6f0f1", "fill-opacity": "0.5", "color": "#2c5e68"},
             "nodes": [x["id"] for x in nodes], "x": x0 - 26, "y": y0 - 40, "w": 1020, "h": 282}
    return [group] + nodes


V2_FEEDERS = ["node_storage_manager", "func_filter_logic", "d259aff03afc6bb1"]


def is_patched(fmt):
    return "Wind Edge Chip: panel ML" in fmt


def v2_nodes(tab, ui_base, tpl):
    """Halaman 'Hackathon' (/dashboard/hackathon): salinan dashboard Genis + ML, gaya cloaked.com."""
    theme = {"id": "wec_v2_theme", "type": "ui-theme", "name": "Hackathon (cloaked)",
             "colors": {"surface": "#fffdf7", "primary": "#ff550c", "bgPage": "#fbf8ef", "groupBg": "#fbf8ef", "groupOutline": "#fbf8ef"},
             "sizes": {"pagePadding": "0px", "groupGap": "0px", "groupBorderRadius": "0px", "widgetGap": "0px", "density": "default"}}
    page = {"id": "wec_v2_page", "type": "ui-page", "z": tab, "name": "Hackathon", "ui": ui_base, "path": "/hackathon", "icon": "leaf",
            "layout": "grid", "theme": "wec_v2_theme",
            "breakpoints": [{"name": "Default", "px": "0", "cols": "3"}, {"name": "Tablet", "px": "576", "cols": "6"},
                            {"name": "Small Desktop", "px": "768", "cols": "9"}, {"name": "Desktop", "px": "1024", "cols": "12"}],
            "order": 4, "className": "", "visible": True, "disabled": False}
    group = {"id": "wec_v2_group", "type": "ui-group", "z": tab, "name": "Hackathon", "page": "wec_v2_page", "width": "12", "height": "1",
             "order": 1, "showTitle": False, "className": "", "visible": "true", "disabled": "false"}
    node = {k: v for k, v in tpl.items() if k not in ("id", "format", "group", "x", "y", "g")}
    node.update({"id": "wec_v2_tpl", "group": "wec_v2_group", "name": "Hackathon (gaya cloaked.com)", "format": skin_hackathon.skin(patch_template.patch(tpl["format"])),
                 "x": tpl.get("x", 1840), "y": tpl.get("y", 920) + 80, "wires": [list(tpl["wires"][0]) + ["wec_engine"]]})   # wec/replay -> mesin
    return [theme, page, group, node]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback")
    ap.add_argument("--genis-from", help="backup flows berisi template Genis yang belum di-patch")
    ap.add_argument("--history-seed-row", type=int, help="Baris terakhir ekspor CSV Sheet untuk pemasangan riwayat pertama")
    args = ap.parse_args()
    tok = token("*")
    H = {"Authorization": f"Bearer {tok}", "Node-RED-API-Version": "v2"}
    cur = requests.get(f"{URL}/flows", headers=H, timeout=30).json()

    if args.rollback:
        old = json.loads(Path(args.rollback).read_text())
        body = {"rev": cur["rev"], "flows": old["flows"]}
    else:
        history_seed = args.history_seed_row
        if history_seed is None:
            current = next((n for n in cur['flows'] if n.get('id') == 'wec_history_manager'), {})
            found = re.search(r'const HISTORY_SEED_ROW = (\d+);', current.get('func', ''))
            if found:
                history_seed = int(found.group(1))
        if history_seed is None or history_seed < 2:
            sys.exit('Riwayat 3 jam memerlukan --history-seed-row <baris terakhir CSV> pada pemasangan pertama.')
        bdir = Path(args.backup_dir); bdir.mkdir(parents=True, exist_ok=True)
        bfile = bdir / f"backup_flows_{time.strftime('%Y%m%d_%H%M%S')}.json"
        bfile.write_text(json.dumps(cur))
        print("backup:", bfile)
        flows = copy.deepcopy(cur["flows"])
        tab = next(n for n in flows if n.get("type") == "tab" and n.get("label") == TAB_LABEL)["id"]
        k = next(i for i, n in enumerate(flows) if n["id"] == TEMPLATE_ID)
        if is_patched(flows[k]["format"]):
            if not args.genis_from:
                sys.exit("template Genis di server ter-patch; beri --genis-from BACKUP berisi versi asli")
            orig = next(n for n in json.loads(Path(args.genis_from).read_text())["flows"] if n["id"] == TEMPLATE_ID)
            assert not is_patched(orig["format"]), "backup --genis-from juga sudah ter-patch"
            flows[k] = copy.deepcopy(orig)
            print("template Genis dipulihkan ke asli", hashlib.sha256(orig["format"].encode()).hexdigest()[:12])
        else:
            print("template Genis asli; tidak diubah")
        flows = [n for n in flows if not (str(n.get("id", "")).startswith("wec_"))]
        flows += wec_nodes(tab)
        ui_base = next(n for n in flows if n["id"] == "page_neon_db2")["ui"]
        flows += v2_nodes(tab, ui_base, flows[k])
        for n in flows:
            if n["id"] in V2_FEEDERS and n.get("wires") and "wec_v2_tpl" not in n["wires"][0]:
                n["wires"][0].append("wec_v2_tpl")
        ctl = next(n for n in flows if n.get("type") == "ui-control" and n.get("name") == UI_CONTROL_NAME and n.get("z") == tab)
        if "wec_engine" not in ctl["wires"][0]:
            ctl["wires"][0].append("wec_engine")
        from deploy_history import prepare as prepare_history
        flows = prepare_history(flows, history_seed)
        # Pertahankan susunan editor yang sudah dirapikan saat deploy ulang.
        from layout_flow import arrange
        flows, _ = arrange(flows)
        body = {"rev": cur["rev"], "flows": flows}
        added = len(flows) - len(cur["flows"])
        print(f"node: {len(cur['flows'])} -> {len(flows)} (+{added})")
    if args.dry_run:
        print("dry-run: tidak ada yang ditulis")
        return
    r = requests.post(f"{URL}/flows", headers={**H, "Content-Type": "application/json", "Node-RED-Deployment-Type": "nodes"},
                      data=json.dumps(body), timeout=60)
    print("deploy:", r.status_code, r.text[:200])
    r.raise_for_status()


if __name__ == "__main__":
    main()
