"""Eksperimen usulan RTL: pengali requantize M per lapisan (S = 8 tetap), untuk Alif.

RTL sekarang: out = clamp(((acc + b) * 32) >>> 8, 0, 127) di semua lapisan, sehingga bobot hasil latih hanya
memakai sekitar ±5 dari ±127. Di sini tiap lapisan boleh punya M sendiri (out = clamp(((acc + b) * M_l) >>> 8)),
model dilatih ulang dengan QAT yang sama, lalu dibandingkan pada data uji 1-20 Okt.

Keluaran: ml/results/eksperimen_ms_per_lapisan.json
Pemakaian: ml/.venv/bin/python ml/forecast/eksperimen_ms_per_lapisan.py
"""

import json

import numpy as np
import torch
from torch import nn

import train_mlp as T
from features import TARGET, build, split
from metrics import scores

KOMBINASI = [(32, 32, 32), (16, 16, 16), (8, 8, 8), (4, 4, 4), (8, 8, 32), (16, 8, 32), (8, 4, 32)]


class IntMLPMS(nn.Module):
    """Sama dengan train_mlp.IntMLP, tetapi tiap lapisan punya pengali M sendiri (pembagi 256 / M)."""

    def __init__(self, x_rms, ms):
        super().__init__()
        g = torch.Generator().manual_seed(T.SEED)
        self.div = [256.0 / m for m in ms]
        self.W, self.b = nn.ParameterList(), nn.ParameterList()
        rms = x_rms
        for (n_in, n_out), d in zip(zip(T.SIZES[:-1], T.SIZES[1:]), self.div):
            std = d * 30 / (np.sqrt(n_in) * rms)
            self.W.append(nn.Parameter(torch.randn(n_in, n_out, generator=g) * std))
            self.b.append(nn.Parameter(torch.full((n_out,), d * 5)))
            rms = 30.0
        self.quant = False

    def forward(self, x):
        h = x
        for W, b, d in zip(self.W, self.b, self.div):
            w, bb = torch.clamp(W, -127, 127), b
            if self.quant:
                w, bb = T.ste_round(w), T.ste_round(bb)
            a = (h @ w + bb) / d
            if self.quant:
                a = T.ste_floor(a)
            h = torch.clamp(a, 0, 127)
        return h.squeeze(-1)

    def integer_params(self):
        return [(np.round(np.clip(W.detach().numpy(), -127, 127)).astype(int), np.round(b.detach().numpy()).astype(int))
                for W, b in zip(self.W, self.b)]


def integer_forward(x_q, params, ms):
    h = x_q.astype(np.int64)
    for (w, b), m in zip(params, ms):
        h = np.clip(((h @ w + b) * m) >> 8, 0, 127)
    return h[:, 0]


def main():
    utama = json.loads((T.MODEL_DIR / "mlp_int8.json").read_text())
    table, s_y = utama["skala_fitur"], utama["skala_keluaran_W_per_lsb"]
    tr, va, te = split(build())
    xq = {k: T.quantize_inputs(d, table) for k, d in (("tr", tr), ("va", va), ("te", te))}
    tq = lambda a: torch.tensor(a, dtype=torch.float32)
    y_q = {k: torch.tensor(np.clip(d[TARGET].to_numpy() / s_y, 0, 127), dtype=torch.float32) for k, d in (("tr", tr), ("va", va))}
    rms = float(np.sqrt(np.mean(xq["tr"].astype(float) ** 2)))
    hasil = {}
    for ms in KOMBINASI:
        torch.manual_seed(T.SEED)
        np.random.seed(T.SEED)
        im = IntMLPMS(rms, ms)
        T.fit(im, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=5e-2)
        im.quant = True
        T.fit(im, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=1e-2)
        p = im.integer_params()
        out = integer_forward(xq["te"], p, ms)
        with torch.no_grad():
            beda = int(np.sum(np.round(im(tq(xq["te"])).numpy()).astype(int) != out))
        sc = scores(te[TARGET], out * s_y, te["p_now"])
        key = "M=" + "/".join(map(str, ms))
        hasil[key] = {"MAE_W": round(sc["MAE_W"], 3), "RMSE_W": round(sc["RMSE_W"], 3), "skill": round(sc["skill_vs_persistence"], 3),
                      "max_abs_bobot": [int(np.abs(w).max()) for w, _ in p], "beda_pytorch_vs_integer": beda}
        print(f"{key:12s} MAE {sc['MAE_W']:.3f}  RMSE {sc['RMSE_W']:.3f}  skill {sc['skill_vs_persistence']:+.3f}  max|w| {hasil[key]['max_abs_bobot']}  beda {beda}")
    res = {"n_menit_uji": int(len(te)), "catatan": "S = 8 tetap; M=32/32/32 = RTL sekarang (dilatih ulang dengan seed sama)", "hasil": hasil}
    (T.RESULTS / "eksperimen_ms_per_lapisan.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
