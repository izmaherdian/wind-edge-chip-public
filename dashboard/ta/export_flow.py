"""Ekspor tab "Turbin angin" + node config yang dipakainya dari Node-RED citaitb.com (token baca-saja).

Admin API tidak mengirim credentials (password broker, token Google), jadi file aman di-commit.
Tab proyek lain tidak ikut. Pemakaian: NR_PASS=... ml/.venv/bin/python dashboard/ta/export_flow.py
"""

import json
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "wec"))
import deploy  # noqa: E402

TAB_LABEL = "Turbin angin"


def main():
    tok = deploy.token("read")
    flows = requests.get(f"{deploy.URL}/flows", headers={"Authorization": f"Bearer {tok}", "Node-RED-API-Version": "v2"},
                         timeout=30).json()["flows"]
    by_id = {n["id"]: n for n in flows}
    tab = next(n for n in flows if n.get("type") == "tab" and n.get("label") == TAB_LABEL)
    keep = [tab] + [n for n in flows if n.get("z") == tab["id"]]
    # node config (tanpa z) yang dirujuk lewat properti string, dicari berulang (page -> ui-base, theme, dst.)
    seen = {n["id"] for n in keep}
    todo = list(keep)
    while todo:
        n = todo.pop()
        for k, v in n.items():
            if k in ("id", "z", "wires", "g") or not isinstance(v, str):
                continue
            c = by_id.get(v)
            if c and "z" not in c and c["id"] not in seen and c.get("type") != "tab":
                seen.add(c["id"])
                keep.append(c)
                todo.append(c)
    out = HERE / "node-red-flow.json"
    out.write_text(json.dumps(keep, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(keep)} node -> {out.relative_to(HERE.parents[1])}")


if __name__ == "__main__":
    main()
