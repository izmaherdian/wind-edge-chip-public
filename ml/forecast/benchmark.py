"""Perbandingan semua metode prediksi rata-rata daya 60 menit ke depan.

Semua metode memakai split kronologis, target, dan metrik yang sama (test 1–20 Okt).
Kelompok: baseline, fisika (kurva daya), statistik (ARIMA), linear, kernel/tetangga,
pohon, jaringan saraf tabular, jaringan saraf sekuensial (CNN 1D, LSTM, GRU, TCN,
Transformer), probabilistik (kuantil), serta varian hardware (INT8, tanpa Open-Meteo).

Keluaran: ml/results/benchmark.csv, benchmark.json, dan grafik di ml/results/gambar/.
Pemakaian: python benchmark.py [--cepat]   (--cepat: lewati model sekuensial)
"""

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from baselines import predict_all
from features import FEATURES, OFFLINE_FEATURES, TARGET, build, split
from metrics import scores

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "ml" / "results"
torch.set_num_threads(6)
SEED = 0


def mac4_steps(sizes):
    """Langkah MAC4 di FPGA: Σ ⌈n_in/4⌉ · n_out (16-32-16-1 = 260)."""
    return int(sum(-(-a // 4) * b for a, b in zip(sizes[:-1], sizes[1:])))


# ------------------------------------------------------------------ tabular
def tabular_models():
    import lightgbm as lgb
    import xgboost as xgb
    from catboost import CatBoostRegressor
    from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
    from sklearn.neighbors import KNeighborsRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    from sklearn.svm import SVR
    from sklearn.tree import DecisionTreeRegressor

    sc = StandardScaler
    return {
        # nama: (model, kelompok, maks sampel latih (None = semua), MAC kira-kira per prediksi)
        "Regresi linear": (make_pipeline(sc(), LinearRegression()), "Linear", None, 16),
        "Ridge": (make_pipeline(sc(), Ridge(alpha=1.0)), "Linear", None, 16),
        "Lasso": (make_pipeline(sc(), Lasso(alpha=0.05)), "Linear", None, 16),
        "ElasticNet": (make_pipeline(sc(), ElasticNet(alpha=0.05, l1_ratio=0.5)), "Linear", None, 16),
        "Polinomial derajat 2 + Ridge": (make_pipeline(sc(), PolynomialFeatures(2), Ridge(alpha=10.0)), "Linear", None, 153),
        "SVR RBF (15 rb sampel)": (make_pipeline(sc(), SVR(C=10, epsilon=0.5)), "Kernel/tetangga", 15_000, None),
        "KNN (k=25)": (make_pipeline(sc(), KNeighborsRegressor(n_neighbors=25, n_jobs=-1)), "Kernel/tetangga", None, None),
        "Decision Tree": (DecisionTreeRegressor(max_depth=10, min_samples_leaf=50, random_state=SEED), "Pohon", None, None),
        "Random Forest": (RandomForestRegressor(n_estimators=200, min_samples_leaf=20, n_jobs=-1, random_state=SEED), "Pohon", None, None),
        "ExtraTrees": (ExtraTreesRegressor(n_estimators=200, min_samples_leaf=20, n_jobs=-1, random_state=SEED), "Pohon", None, None),
        "HistGradientBoosting": (HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=SEED), "Pohon", None, None),
        "XGBoost": (xgb.XGBRegressor(n_estimators=500, learning_rate=0.05, max_depth=6, subsample=0.8, n_jobs=6, random_state=SEED), "Pohon", None, None),
        "LightGBM": (lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, num_leaves=31, verbose=-1, random_state=SEED), "Pohon", None, None),
        "CatBoost": (CatBoostRegressor(iterations=800, learning_rate=0.05, depth=6, verbose=0, random_seed=SEED), "Pohon", None, None),
    }


def run_tabular(tr, va, te, cols, suffix=""):
    rows, preds = [], {}
    for name, (m, group, nmax, macs) in tabular_models().items():
        d = tr.sample(n=nmax, random_state=SEED) if nmax and len(tr) > nmax else tr
        t0 = time.perf_counter()
        m.fit(d[cols], d[TARGET])
        fit_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        p = np.clip(m.predict(te[cols]), 0, None)
        inf_us = (time.perf_counter() - t0) / len(te) * 1e6
        rows.append({"metode": name + suffix, "kelompok": group, **scores(te[TARGET], p, te["p_now"]),
                     "MAC_per_prediksi": macs, "latih_detik": round(fit_s, 1), "inferensi_us_per_sampel_PC": round(inf_us, 2),
                     "jalan_di_FPGA_MAC4": "ya" if macs else "tidak"})
        preds[name + suffix] = p
        print(f"  {name + suffix:45s} RMSE {rows[-1]['RMSE_W']:6.2f}")
    return rows, preds


# ------------------------------------------------------------------ fisika
def physical(tr, te):
    """Kurva daya empiris P(v) dari data latih (bin 0,25 m/s), dipakai pada angin rata-rata 60 menit
    terakhir dan pada prakiraan angin Open-Meteo yang dipetakan ke angin stasiun (regresi kuantil-ke-kuantil)."""
    bins = np.arange(0, 8.25, 0.25)
    curve = tr.groupby(pd.cut(tr["w_mean60"], bins), observed=False)[TARGET].mean().fillna(0).to_numpy()
    look = lambda v: curve[np.clip(np.digitize(v, bins) - 1, 0, len(curve) - 1)]
    qs = np.linspace(0.01, 0.99, 99)
    om_q, st_q = np.quantile(tr["om_wind_next"], qs), np.quantile(tr["w_mean60"], qs)
    om_mapped = np.interp(te["om_wind_next"], om_q, st_q)
    out = {}
    for name, v in (("Kurva daya × angin 60 menit terakhir", te["w_mean60"]),
                    ("Kurva daya × prakiraan Open-Meteo", om_mapped)):
        out[name] = look(np.asarray(v))
    return out


# ------------------------------------------------------------------ ARIMA
def arima(tr_series, te_series, te_index):
    """ARIMA(2,0,1) pada deret 10 menit; prakiraan 6 langkah (60 menit) dihitung dari state Kalman
    tiap titik uji (parameter dari data latih, tanpa latih ulang). Dinilai di titik uji kelipatan 10 menit."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    mu = tr_series.mean()
    res = SARIMAX(tr_series - mu, order=(2, 0, 1), trend="n").fit(disp=False)
    rt = res.apply(te_series - mu)
    fr = rt.filter_results
    T, Z = fr.transition[:, :, 0], fr.design[:, :, 0]
    st = fr.filtered_state                           # state setelah melihat data s.d. t
    fc = np.zeros(st.shape[1])
    x = st.copy()
    for _ in range(6):
        x = T @ x
        fc += (Z @ x)[0]
    fc = np.clip(fc / 6 + mu, 0, None)
    s = pd.Series(fc, index=te_series.index)
    # titik uji = akhir blok 10 menit; target sampel pada menit itu
    return s.reindex(te_index)


# ------------------------------------------------------------------ jaringan saraf
class Tabular(nn.Module):
    def __init__(self, sizes):
        super().__init__()
        layers = []
        for a, b in zip(sizes[:-2], sizes[1:-1]):
            layers += [nn.Linear(a, b), nn.ReLU()]
        layers += [nn.Linear(sizes[-2], sizes[-1])]
        self.net = nn.Sequential(*layers)

    def forward(self, x, seq=None):
        return self.net(x).squeeze(-1)


class SeqNet(nn.Module):
    """Riwayat 60 menit (daya, angin) + fitur statis → prediksi."""
    def __init__(self, kind, n_static, ch=2, hid=32):
        super().__init__()
        self.kind = kind
        if kind == "CNN 1D":
            self.enc = nn.Sequential(nn.Conv1d(ch, 16, 5, padding=2), nn.ReLU(), nn.MaxPool1d(2),
                                     nn.Conv1d(16, 32, 5, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
            out = 32
        elif kind in ("LSTM", "GRU"):
            self.enc = (nn.LSTM if kind == "LSTM" else nn.GRU)(ch, hid, batch_first=True)
            out = hid
        elif kind == "TCN":
            convs, c = [], ch
            for d in (1, 2, 4, 8, 16):
                convs += [nn.Conv1d(c, 24, 3, padding=d, dilation=d), nn.ReLU()]
                c = 24
            self.enc = nn.Sequential(*convs, nn.AdaptiveAvgPool1d(1))
            out = 24
        elif kind == "Transformer":
            self.proj = nn.Linear(ch, 32)
            self.pos = nn.Parameter(torch.randn(1, 60, 32) * 0.02)
            self.enc = nn.TransformerEncoder(nn.TransformerEncoderLayer(32, 4, 64, batch_first=True, dropout=0.0), 2)
            out = 32
        self.head = nn.Sequential(nn.Linear(out + n_static, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x, seq):
        if self.kind in ("CNN 1D", "TCN"):
            z = self.enc(seq.transpose(1, 2)).squeeze(-1)
        elif self.kind in ("LSTM", "GRU"):
            z = self.enc(seq)[0][:, -1]
        else:
            z = self.enc(self.proj(seq) + self.pos).mean(1)
        return self.head(torch.cat([z, x], 1)).squeeze(-1)


def sequences(idx, t):
    """Jendela 60 menit terakhir (daya/100, angin/5) untuk tiap waktu sampel."""
    pos = t.index.get_indexer(idx)
    p = (t["power_w"].to_numpy() / 100).astype("float32")
    w = (t["wind_ms"].to_numpy() / 5).astype("float32")
    off = np.arange(-59, 1)
    j = pos[:, None] + off[None]
    seq = np.stack([p[j], w[j]], -1)
    return np.nan_to_num(seq)          # NaN di dalam segmen (celah ≤ 10 menit) → 0


def train_torch(model, Xtr, Str, ytr, Xva, Sva, yva, epochs, lr=2e-3, batch=512):
    torch.manual_seed(SEED)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    best, state = np.inf, None
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(perm), batch):
            j = perm[i:i + batch]
            loss = torch.mean((model(Xtr[j], Str[j] if Str is not None else None) - ytr[j]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            v = torch.mean((model(Xva, Sva) - yva) ** 2).item()
        if v < best:
            best, state = v, {k: x.clone() for k, x in model.state_dict().items()}
    model.load_state_dict(state)
    return model


def run_neural(tr, va, te, with_seq):
    rows, preds = [], {}
    mu, sd = tr[FEATURES].mean(), tr[FEATURES].std()
    X = lambda d: torch.tensor(((d[FEATURES] - mu) / sd).to_numpy(), dtype=torch.float32)
    Y = lambda d: torch.tensor(d[TARGET].to_numpy() / 10, dtype=torch.float32)
    for sizes in ((16, 8, 1), (16, 16, 1), (16, 32, 16, 1), (16, 64, 32, 1)):
        name = "MLP float " + "-".join(map(str, sizes))
        t0 = time.perf_counter()
        m = train_torch(Tabular(sizes), X(tr), None, Y(tr), X(va), None, Y(va), epochs=40)
        with torch.no_grad():
            p = np.clip(m(X(te)).numpy() * 10, 0, None)
        macs = int(sum(a * b for a, b in zip(sizes[:-1], sizes[1:])))
        rows.append({"metode": name, "kelompok": "Jaringan saraf (tabular)", **scores(te[TARGET], p, te["p_now"]),
                     "MAC_per_prediksi": macs, "langkah_MAC4": mac4_steps(sizes), "latih_detik": round(time.perf_counter() - t0, 1),
                     "jalan_di_FPGA_MAC4": "ya (16-32-16-1 = RTL sekarang)" if sizes == (16, 32, 16, 1) else "ya, bila FSM diubah"})
        preds[name] = p
        print(f"  {name:45s} RMSE {rows[-1]['RMSE_W']:6.2f}")
    if not with_seq:
        return rows, preds
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")
    S = {k: torch.tensor(sequences(d.index, t)) for k, d in (("tr", tr), ("va", va), ("te", te))}
    for kind in ("CNN 1D", "LSTM", "GRU", "TCN", "Transformer"):
        t0 = time.perf_counter()
        m = train_torch(SeqNet(kind, len(FEATURES)), X(tr), S["tr"], Y(tr), X(va), S["va"], Y(va), epochs=12)
        with torch.no_grad():
            p = np.clip(m(X(te), S["te"]).numpy() * 10, 0, None)
        n_par = sum(x.numel() for x in m.parameters())
        fpga = {"CNN 1D": "mungkin (MAC sama, FSM lebih rumit)", "TCN": "mungkin (konvolusi)",
                "LSTM": "sulit (sigmoid/tanh, sekuensial)", "GRU": "sulit (sigmoid/tanh, sekuensial)",
                "Transformer": "sulit (softmax, memori besar)"}[kind]
        rows.append({"metode": kind + " (riwayat 60 menit)", "kelompok": "Jaringan saraf (sekuensial)",
                     **scores(te[TARGET], p, te["p_now"]), "parameter": n_par, "latih_detik": round(time.perf_counter() - t0, 1),
                     "jalan_di_FPGA_MAC4": fpga})
        preds[kind] = p
        print(f"  {kind:45s} RMSE {rows[-1]['RMSE_W']:6.2f}")
    return rows, preds


# ------------------------------------------------------------------ kuantil
def quantile(tr, te):
    import lightgbm as lgb
    q = {}
    for a in (0.1, 0.5, 0.9):
        m = lgb.LGBMRegressor(objective="quantile", alpha=a, n_estimators=500, learning_rate=0.05, verbose=-1, random_state=SEED)
        m.fit(tr[FEATURES], tr[TARGET])
        q[a] = np.clip(m.predict(te[FEATURES]), 0, None)
    y = te[TARGET].to_numpy()
    cover = float(np.mean((y >= q[0.1]) & (y <= q[0.9])))
    width = float(np.mean(q[0.9] - q[0.1]))
    return q, {"cakupan_P10_P90": round(cover, 3), "lebar_rata_rata_W": round(width, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cepat", action="store_true")
    args = ap.parse_args()
    np.random.seed(SEED)
    f = build()
    tr, va, te = split(f)
    rows, preds = [], {}
    print("[baseline]")
    for k, v in predict_all(tr, te).items():
        rows.append({"metode": k, "kelompok": "Baseline", **scores(te[TARGET], v, te["p_now"]), "MAC_per_prediksi": 0,
                     "jalan_di_FPGA_MAC4": "tidak perlu"})
        preds[k] = v
    print("[fisika]")
    for k, v in physical(tr, te).items():
        rows.append({"metode": k, "kelompok": "Fisika", **scores(te[TARGET], v, te["p_now"]), "jalan_di_FPGA_MAC4": "tabel di ESP32"})
        preds[k] = v
    print("[statistik]")
    t = pd.read_parquet(ROOT / "data" / "processed" / "turbine_1min.parquet")["power_w"]
    s10 = t.resample("10min", label="right", closed="right").mean()
    tr10, te10 = s10[s10.index < va.index[0]], s10[s10.index >= te.index[0] - pd.Timedelta("1min")]
    te_al = te[te.index.minute % 10 == 0]
    pa = arima(tr10, te10, te_al.index)
    ok = pa.notna().to_numpy()
    rows.append({"metode": "ARIMA(2,0,1) deret 10 menit*", "kelompok": "Statistik",
                 **scores(te_al[TARGET][ok], pa[ok], te_al["p_now"][ok]), "MAC_per_prediksi": 30,
                 "jalan_di_FPGA_MAC4": "ya (kecil)", "catatan": "dinilai di titik kelipatan 10 menit"})
    print(f"  ARIMA RMSE {rows[-1]['RMSE_W']:.2f}")
    print("[tabular]")
    r, p = run_tabular(tr, va, te, FEATURES)
    rows += r
    preds.update(p)
    print("[tabular tanpa Open-Meteo (mode offline)]")
    import lightgbm as lgb
    for name, m in (("LightGBM", lgb.LGBMRegressor(n_estimators=500, learning_rate=0.05, verbose=-1, random_state=SEED)),):
        m.fit(tr[OFFLINE_FEATURES], tr[TARGET])
        pp = np.clip(m.predict(te[OFFLINE_FEATURES]), 0, None)
        rows.append({"metode": name + " tanpa Open-Meteo (offline)", "kelompok": "Varian data", **scores(te[TARGET], pp, te["p_now"]),
                     "jalan_di_FPGA_MAC4": "tidak"})
    print("[jaringan saraf]")
    r, p = run_neural(tr, va, te, with_seq=not args.cepat)
    rows += r
    preds.update(p)
    print("[kuantil]")
    q, qinfo = quantile(tr, te)
    rows.append({"metode": "LightGBM kuantil P50 (+ interval P10–P90)", "kelompok": "Probabilistik",
                 **scores(te[TARGET], q[0.5], te["p_now"]), "jalan_di_FPGA_MAC4": "tidak", "catatan": json.dumps(qinfo)})
    preds["P10"], preds["P50"], preds["P90"] = q[0.1], q[0.5], q[0.9]
    mlp = json.loads((RESULTS / "mlp.json").read_text())
    for k, v in mlp.items():
        if k.startswith("MLP float"):
            k = k + " (acuan QAT, train_mlp.py)"
        rows.append({"metode": k, "kelompok": "Varian hardware (INT8)", **v["test"], "MAC_per_prediksi": 1040,
                     "langkah_MAC4": 260, "jalan_di_FPGA_MAC4": "ya (bobot ini)" if "QAT" in k else "ya"})

    df = pd.DataFrame(rows).sort_values("RMSE_W")
    RESULTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(RESULTS / "benchmark.csv", index=False)
    (RESULTS / "benchmark.json").write_text(json.dumps({"n_test": len(te), "periode_test": [str(te.index[0]), str(te.index[-1])],
                                                         "interval_kuantil": qinfo, "hasil": df.to_dict("records")},
                                                        indent=1, ensure_ascii=False, default=str))
    out = pd.DataFrame({"y": te[TARGET].to_numpy(), "p_now": te["p_now"].to_numpy(), **{k: v for k, v in preds.items()}}, index=te.index)
    out.to_parquet(RESULTS / "prediksi_test.parquet")
    print(df[["metode", "kelompok", "MAE_W", "RMSE_W", "skill_vs_persistence"]].to_string(index=False))


if __name__ == "__main__":
    main()
