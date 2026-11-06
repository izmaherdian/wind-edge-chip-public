# ml/ta/models/ — Model SVM dari Raspi

Disalin dari `~/Desktop/` di Raspi turbin, 20 Okt 2026.

| File | Isi |
|---|---|
| `model_pltb_svm_rbf.pkl` | Model yang dipakai `NodeRED_DuaData.py` (fitur: tegangan, arus, angin Arduino) |
| `svm_model_pltb.pkl`, `scaler_pltb.pkl` | Model dan scaler versi lain (25 Mei 2026); belum dipakai oleh program yang sedang berjalan |

Untuk memuatnya perlu versi yang sama dengan di Raspi: scikit-learn 1.8.0 dan joblib 1.5.3 (`edge/ta/raspi/requirements-raspi.txt`). File `.pkl` hanya boleh dimuat dari sumber yang dipercaya.
