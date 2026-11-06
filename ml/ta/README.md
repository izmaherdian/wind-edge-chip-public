# ml/ta/ — Training ML dari TA

Program dari TA Genis, apa adanya. Hanya untuk acuan.

| File | Isi |
|---|---|
| `training_svm.py` | Notebook Colab: unggah CSV (pemisah `;`), bersihkan, latih SVM RBF dengan RandomizedSearchCV, simpan `model_pltb_svm_rbf.pkl` |
| `program-training-ml.docx` | Berkas asli dari Genis |

Catatan: model TA adalah **klasifikasi** status turbin, bukan prakiraan daya. Data dibagi dengan `train_test_split` acak. Pipeline baru di `ml/` memakai pembagian kronologis (lihat `ml/README.md`).

Laporan TA: `docs/ta-genis/`.
