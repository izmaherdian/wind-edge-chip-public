"""MLP 16-32-16-1: versi float (acuan) dan versi INT8 yang identik dengan RTL FPGA.

Aritmetika RTL (feature/fpga: hw/rtl/post_process.v, top.v), sama untuk tiap lapisan:
    acc = Σ x_q·w_q (INT8 × INT8, akumulator INT32)
    out = clamp(((acc + b_q) · 32) >>> 8, 0, 127)  =  clamp(floor((acc + b_q) / 8), 0, 127)
ReLU + clamp juga berlaku di lapisan keluaran, jadi prediksi = out · s_y (W), out ∈ 0…127.

Versi INT8 dilatih langsung dalam satuan bilangan bulat (quantization-aware training):
bobot dibulatkan dan floor dikerjakan dengan straight-through estimator, sehingga model
hasil latih sudah persis aturan hardware. Skala tiap fitur (float → INT8) ditentukan
dari data latih dan menjadi bagian kontrak ESP32 ↔ FPGA.
"""

import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from features import FEATURES, TARGET, build, split
from metrics import scores

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "ml" / "forecast" / "model"
RESULTS = ROOT / "ml" / "results"
SIZES = (16, 32, 16, 1)
SIGNED = {"dir_sin", "dir_cos", "hour_sin", "hour_cos", "rho"}   # fitur yang bisa negatif
SEED = 7


# ---------- skala fitur (dipakai ESP32: x_q = clamp(round((x - c)/s), -128, 127)) ----------
def feature_scales(train):
    table = {}
    for f in FEATURES:
        x = train[f].to_numpy()
        if f == "rho":
            c, s = float(np.mean(x)), float(4 * np.std(x) / 127)
        elif f in SIGNED:
            c, s = 0.0, 1 / 127
        else:
            c, s = 0.0, float(np.quantile(x, 0.999) / 127)
        table[f] = {"center": c, "scale": s}
    return table


def quantize_inputs(df, table):
    x = np.stack([(df[f].to_numpy() - table[f]["center"]) / table[f]["scale"] for f in FEATURES], 1)
    return np.clip(np.round(x), -128, 127).astype(np.int64)


# ---------- MLP float (acuan) ----------
class FloatMLP(nn.Module):
    def __init__(self):
        super().__init__()
        a, b, c, d = SIZES
        self.net = nn.Sequential(nn.Linear(a, b), nn.ReLU(), nn.Linear(b, c), nn.ReLU(), nn.Linear(c, d), nn.ReLU())

    def forward(self, x):
        return self.net(x).squeeze(-1)


# ---------- MLP integer (QAT, identik RTL) ----------
def ste_round(x):
    return x + (torch.round(x) - x).detach()


def ste_floor(x):
    return x + (torch.floor(x) - x).detach()


class IntMLP(nn.Module):
    def __init__(self, x_rms):
        super().__init__()
        g = torch.Generator().manual_seed(SEED)
        self.W, self.b = nn.ParameterList(), nn.ParameterList()
        rms = x_rms
        for n_in, n_out in zip(SIZES[:-1], SIZES[1:]):
            # inisialisasi: keluaran lapisan (acc/8) kira-kira ±30 satuan
            std = 8 * 30 / (np.sqrt(n_in) * rms)
            self.W.append(nn.Parameter(torch.randn(n_in, n_out, generator=g) * std))
            self.b.append(nn.Parameter(torch.full((n_out,), 8.0 * 5)))
            rms = 30.0
        self.quant = False

    def forward(self, x, return_hidden=False):
        hs = []
        h = x
        for W, b in zip(self.W, self.b):
            w = torch.clamp(W, -127, 127)
            bb = b
            if self.quant:
                w, bb = ste_round(w), ste_round(bb)
            a = (h @ w + bb) / 8
            if self.quant:
                a = ste_floor(a)
            h = torch.clamp(a, 0, 127)
            hs.append(h)
        return (h.squeeze(-1), hs) if return_hidden else h.squeeze(-1)

    def integer_params(self):
        out = []
        for W, b in zip(self.W, self.b):
            out.append((np.round(np.clip(W.detach().numpy(), -127, 127)).astype(int),
                        np.round(b.detach().numpy()).astype(int)))
        return out


def integer_forward(x_q, params):
    """Inferensi murni bilangan bulat (numpy), sama dengan golden model dan RTL."""
    h = x_q.astype(np.int64)
    hidden = []
    for w, b in params:
        acc = h @ w + b
        h = np.clip((acc * 32) >> 8, 0, 127)
        hidden.append(h)
    return h[:, 0], hidden


def fit(model, x_tr, y_tr, x_va, y_va, epochs, lr, batch=1024):
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    best, best_state = np.inf, None
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(x_tr))
        for i in range(0, len(perm), batch):
            j = perm[i:i + batch]
            loss = torch.mean((model(x_tr[j]) - y_tr[j]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        model.eval()
        with torch.no_grad():
            v = torch.mean((model(x_va) - y_va) ** 2).item()
        if v < best:
            best, best_state = v, {k: t.clone() for k, t in model.state_dict().items()}
    model.load_state_dict(best_state)
    return best


def main():
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    tr, va, te = split(build())
    table = feature_scales(tr)
    s_y = float(np.quantile(tr[TARGET], 0.999) / 127)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    res = {}

    # --- float ---
    mu, sd = tr[FEATURES].mean(), tr[FEATURES].std()
    def z(df):
        return torch.tensor(((df[FEATURES] - mu) / sd).to_numpy(), dtype=torch.float32)
    yz = lambda df: torch.tensor(df[TARGET].to_numpy() / s_y, dtype=torch.float32)
    fm = FloatMLP()
    fit(fm, z(tr), yz(tr), z(va), yz(va), epochs=40, lr=3e-3)
    with torch.no_grad():
        pf_te = fm(z(te)).numpy() * s_y
        pf_va = fm(z(va)).numpy() * s_y
    res["MLP float 16-32-16-1"] = {"val": scores(va[TARGET], pf_va, va["p_now"]),
                                   "test": scores(te[TARGET], pf_te, te["p_now"])}
    torch.save(fm.state_dict(), MODEL_DIR / "mlp_float.pt")

    # --- INT8 (QAT) ---
    xq = {k: quantize_inputs(d, table) for k, d in (("tr", tr), ("va", va), ("te", te))}
    tq = lambda a: torch.tensor(a, dtype=torch.float32)
    y_q = {k: torch.tensor(np.clip(d[TARGET].to_numpy() / s_y, 0, 127), dtype=torch.float32)
           for k, d in (("tr", tr), ("va", va), ("te", te))}
    im = IntMLP(x_rms=float(np.sqrt(np.mean(xq["tr"].astype(float) ** 2))))
    fit(im, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=5e-2)   # tahap 1: kontinu
    im.quant = True
    fit(im, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=1e-2)   # tahap 2: QAT
    params = im.integer_params()
    out_va, _ = integer_forward(xq["va"], params)
    out_te, hid_te = integer_forward(xq["te"], params)
    with torch.no_grad():                     # integer numpy == model PyTorch mode quant
        torch_te = im(tq(xq["te"])).numpy()
    mismatch = int(np.sum(np.round(torch_te).astype(int) != out_te))
    res["MLP INT8 (QAT, identik RTL)"] = {"val": scores(va[TARGET], out_va * s_y, va["p_now"]),
                                          "test": scores(te[TARGET], out_te * s_y, te["p_now"]),
                                          "beda_pytorch_vs_integer": mismatch}

    # --- INT8 PTQ (tanpa QAT) sebagai pembanding: bobot float dibulatkan ke aturan RTL ---
    im_ptq = IntMLP(x_rms=float(np.sqrt(np.mean(xq["tr"].astype(float) ** 2))))
    fit(im_ptq, tq(xq["tr"]), y_q["tr"], tq(xq["va"]), y_q["va"], epochs=30, lr=5e-2)
    out_ptq, _ = integer_forward(xq["te"], im_ptq.integer_params())
    res["MLP INT8 (PTQ: dibulatkan tanpa QAT)"] = {"test": scores(te[TARGET], out_ptq * s_y, te["p_now"])}

    # --- simpan model integer untuk golden model, ESP32, dan FPGA ---
    w_used = [int(np.abs(w).max()) for w, _ in params]
    sat = [float(np.mean(h == 127)) for h in hid_te]
    model = {
        "topologi": list(SIZES),
        "fitur": FEATURES,
        "skala_fitur": table,
        "skala_keluaran_W_per_lsb": s_y,
        "requantize": {"multiplier": 32, "shift": 8, "relu_clamp": [0, 127]},
        "weights": [w.tolist() for w, _ in params],
        "bias": [b.tolist() for _, b in params],
        "info": {"max_abs_bobot_per_lapisan": w_used, "fraksi_saturasi_127_test": sat,
                 "periode_train": [str(tr.index[0]), str(tr.index[-1])]},
    }
    (MODEL_DIR / "mlp_int8.json").write_text(json.dumps(model, indent=1))
    np.savez(MODEL_DIR / "test_set_int8.npz", x_q=xq["te"], y_true_w=te[TARGET].to_numpy(),
             out_q=out_te, time=te.index.astype("int64"))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "mlp.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    for k, v in res.items():
        t = v["test"]
        print(f"{k:40s} MAE {t['MAE_W']:6.2f}  RMSE {t['RMSE_W']:6.2f}  skill {t['skill_vs_persistence']:+.3f}")
    print("beda PyTorch vs integer:", mismatch, "| max|w|:", w_used, "| saturasi:", np.round(sat, 3), "| s_y:", round(s_y, 3))


if __name__ == "__main__":
    main()
