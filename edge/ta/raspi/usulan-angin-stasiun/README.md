# Usulan: SVM status turbin memakai angin stasiun

Status: **dipasang 21 Okt 2026** atas keputusan tim (lihat bagian Riwayat pemasangan). Diameter rotor ditetapkan **2,5 m**.

## Kenapa
`ML_Status` di Raspi hampir selalu "Anomaly". Penyebabnya bukan turbin, melainkan masukan SVM: anemometer Arduino macet di **1,25 m/s**. Delapan bacaan berturut-turut pukul 08.35 semuanya 1,25, dan di data historis 42% bacaannya 1,25. Dengan angin tercatat 1,25 m/s, daya 70 W memberi Cp jauh di atas 0,59, sehingga label menjadi "Anomaly".

## Apa yang berubah
Sumber angin (stasiun, bukan Arduino) dan diameter rotor (2,5 m, keputusan tim; TA memakai 3 m). Rumus label, ambang Cp, ρ = 1,156, dan bentuk model (SVC RBF tanpa scaler, masukan `[voltage, current, wind]`) tetap sama dengan TA.

| | Model TA sekarang | Usulan |
|---|---|---|
| Angin | Arduino (`Windspeed`) | stasiun (`windspeedstation`, Modbus 0x01F4) |
| File model | `model_pltb_svm_rbf.pkl` (sklearn 1.6.1) | `svm_angin_stasiun.pkl` (sklearn 1.8.0 = venv Raspi) |
| Uji 1–20 Okt (12.002 menit) | — | akurasi 96,2% vs label Cp; Anomaly 27,5% label / 31,0% prediksi; Cp median 0,46 |

`NodeRED_DuaData.py` di folder ini sama dengan yang berjalan di Raspi (md5 `845ff2d0…`), kecuali 3 baris: nama file model, dan angin stasiun sebagai pengganti angin Arduino untuk prediksi. Topik MQTT, format, dan interval tidak berubah, sehingga Node-RED dan Google Sheets tidak perlu diubah.

Catatan: label tetap rumus Cp. Dengan diameter 2,5 m, ±28% menit Oktober punya Cp > 0,59 (di atas batas Betz, tidak mungkin secara fisika), sehingga tetap berlabel "Anomaly". Artinya angin stasiun lebih rendah daripada angin di rotor atau koefisien lain belum tepat; badge Anomaly berkurang dari "hampir selalu" tetapi tidak hilang. Dengan 3 m porsinya ±10%. Status di dashboard hackathon memakai pendekatan lain, yaitu kurva daya wajar yang dipelajari dari data, sehingga tidak bergantung pada asumsi diameter.

## Pasang (oleh Genis)
```bash
scp edge/ta/raspi/usulan-angin-stasiun/svm_angin_stasiun.pkl RASPI-TURBIN:~/Desktop/
ssh RASPI-TURBIN 'cp ~/Desktop/NodeRED_DuaData.py ~/Desktop/NodeRED_DuaData.py.bak-20261021'
scp edge/ta/raspi/usulan-angin-stasiun/NodeRED_DuaData.py RASPI-TURBIN:~/Desktop/NodeRED_DuaData.py
ssh RASPI-TURBIN 'sudo systemctl restart nodered_duadata && journalctl -u nodered_duadata -n 20 --no-pager'
```
Cek log menampilkan `-> ML : TurbinAngin/ML_Status = Optimal` atau label lain.

## Kembalikan
```bash
ssh RASPI-TURBIN 'cp ~/Desktop/NodeRED_DuaData.py.bak-20261021 ~/Desktop/NodeRED_DuaData.py && sudo systemctl restart nodered_duadata'
```

Latih ulang: `ml/.venv/bin/python ml/status/svm_angin_stasiun.py` (hasil di `ml/results/status_svm_angin_stasiun.json`).

## Riwayat pemasangan
- **21 Okt 2026 13.15 WIB** (atas keputusan tim): `svm_angin_stasiun.pkl` (D 2,5 m) disalin ke `~/Desktop/`, program lama di-backup ke `~/Desktop/NodeRED_DuaData.py.bak-20261021` (md5 `845ff2d0…`), program baru dipasang (md5 `cafd9317…`), model diuji di venv Raspi, lalu `nodered_duadata` di-restart. Log setelah restart: `ML_Status = Optimal` pada angin stasiun 1,4–2,9 m/s (sebelumnya hampir selalu `Anomaly`).
