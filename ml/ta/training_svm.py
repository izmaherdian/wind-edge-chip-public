import pandas as pd
import io
import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from google.colab import files
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.svm import SVC
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

print("="*50)
print("STEP 1: UPLOAD DATASET")
print("="*50)
print("Silakan jalankan cell ini, lalu klik 'Choose Files' untuk memilih file CSV Anda:")
uploaded = files.upload()
file_name = list(uploaded.keys())[0]
print(f"[INFO] File '{file_name}' berhasil diunggah!")

print("\n" + "="*50)
print("STEP 2: MEMBACA DATASET")
print("="*50)
print(f"Membaca isi file '{file_name}'...")
# Menggunakan titik koma (;) sebagai pemisah sesuai format file CSV
df = pd.read_csv(io.BytesIO(uploaded[file_name]), sep=';', low_memory=False)

# Menghapus spasi gaib di awal/akhir nama kolom bawaan Excel
df.columns = df.columns.str.strip()

print(f"[INFO] Total baris awal: {df.shape[0]} | Total kolom: {df.shape[1]}")
print("\n[PREVIEW] 5 Baris Pertama Dataset Asli (Sebelum dipotong):")
print(df.head())

print("\n" + "="*50)
print("STEP 3: PRA-PEMROSESAN DATA (CLEANING)")
print("="*50)
# NAMA KOLOM SUDAH DISESUAIKAN:
col_v = 'voltage'
col_i = 'current'
col_wind = 'Windspeed'
col_status = 'Status'

kolom_wajib = [col_v, col_i, col_wind, col_status]
kolom_tersedia = [k for k in kolom_wajib if k in df.columns]

if len(kolom_tersedia) < 4:
    print(f"[ERROR] Kolom yang terdeteksi di file Anda: {list(df.columns)}")
    print(f"[ERROR] Program membutuhkan kolom: {kolom_wajib}")
    print("[SOLUSI] Pastikan nama kolom di baris pertama Excel Anda sama persis.")
else:
    print("Memotong tabel... Hanya mengambil kolom utama...")
    # Membuang kolom lain yang tidak dibutuhkan agar memori lebih ringan
    df = df[kolom_wajib]

    print("Mengecek dan menghapus baris yang kosong (NaN)...")
    df = df.dropna(subset=kolom_wajib)

    print("Memastikan format angka menggunakan desimal titik (.) ...")
    def clean_number(x):
        if isinstance(x, str):
            # Hilangkan spasi ekstra dan ubah koma menjadi titik
            x = x.replace(' ', '').replace(',', '.')
            try:
                return float(x)
            except ValueError:
                return np.nan
        return float(x)

    # Hanya bersihkan angka di fitur input, kolom Status dibiarkan teks
    for col in [col_v, col_i, col_wind]:
        df[col] = df[col].apply(clean_number)

    # Hapus lagi jika ada data error yang gagal dikonversi menjadi angka
    df = df.dropna(subset=kolom_wajib)
    print(f"[INFO] Total baris setelah format angka dibersihkan: {df.shape[0]}")
    print("\n[PREVIEW] 5 Baris Data Setelah Dipotong & Dibersihkan:")
    print(df.head())

    print("\n" + "="*50)
    print("STEP 4: SAMPLING DATA (BALANCING 5000 DATA PER KELAS)")
    print("="*50)
    print("Mengambil masing-masing 5000 data acak untuk kelas Optimal, Anomaly, dan Infisien...")

    # Memastikan data mencukupi sebelum disampling
    for status in ['Optimal', 'Anomaly', 'Infisien']:
        jumlah_tersedia = len(df[df[col_status] == status])
        if jumlah_tersedia < 5000:
            print(f"[PERINGATAN] Data '{status}' hanya ada {jumlah_tersedia} baris. Akan diambil semua.")

    df_optimal = df[df[col_status] == 'Optimal'].sample(n=min(5000, len(df[df[col_status] == 'Optimal'])), random_state=42)
    df_anomaly = df[df[col_status] == 'Anomaly'].sample(n=min(5000, len(df[df[col_status] == 'Anomaly'])), random_state=42)
    df_infisien = df[df[col_status] == 'Infisien'].sample(n=min(5000, len(df[df[col_status] == 'Infisien'])), random_state=42)

    # Menggabungkan ketiga dataframe tersebut
    df_balanced = pd.concat([df_optimal, df_anomaly, df_infisien])

    # Mengacak ulang urutan baris agar model tidak menghafal urutan
    df_balanced = df_balanced.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"\n[INFO] Total baris dataset final untuk training: {df_balanced.shape[0]}")
    print("[INFO] Distribusi kelas pada dataset seimbang:")
    print(df_balanced[col_status].value_counts())

    print("\n" + "="*50)
    print("STEP 5: PEMBAGIAN DATA (TRAIN 70% & TEST 30%)")
    print("="*50)
    X = df_balanced[[col_v, col_i, col_wind]]
    y = df_balanced[col_status]

    # Split data menjadi 70% Train dan 30% Test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    print(f"[INFO] Data latih (Train 70%) : {X_train.shape[0]} baris")
    print(f"[INFO] Data uji (Test 30%)    : {X_test.shape[0]} baris")

    print("\n" + "="*50)
    print("STEP 6: HYPERPARAMETER TUNING (KERNEL RBF ONLY)")
    print("="*50)
    params = {
        "C": np.arange(2, 10, 2),
        "gamma": np.arange(0.1, 1, 0.01),
        "kernel": ['rbf']
    }

    base_svm = SVC(random_state=42)
    random_search = RandomizedSearchCV(
        base_svm,
        param_distributions=params,
        random_state=42,
        n_iter=30,
        cv=3,
        verbose=3,
        n_jobs=1,
        return_train_score=True,
        scoring='accuracy'
    )

    print("\nDetail Konfigurasi RandomizedSearchCV:")
    print("-" * 50)
    print("MEMULAI PENCARIAN PARAMETER TERBAIK (Tunggu hingga selesai)...\n")
    random_search.fit(X_train, y_train)

    print("\n" + "="*50)
    print("STEP 7: HASIL RANKING MODEL (TOP 3 TERBAIK)")
    print("="*50)
    def report_best_scores(results, n_top=3):
        for i in range(1, n_top + 1):
            candidates = np.flatnonzero(results['rank_test_score'] == i)
            for candidate in candidates:
                print("Model dengan Ranking: {0}".format(i))
                print("Rata-rata skor validasi: {0:.3f} (std: {1:.3f})".format(
                    results['mean_test_score'][candidate],
                    results['std_test_score'][candidate]))
                best_params = results['params'][candidate]
                print("Parameter terbaik:")
                for param, value in best_params.items():
                    print("  {0}: {1}".format(param, value))
                print("")

    report_best_scores(random_search.cv_results_, n_top=3)

    print("\n" + "="*50)
    print("STEP 8: EVALUASI PADA DATA TEST & CONFUSION MATRIX")
    print("="*50)
    best_svm_model = random_search.best_estimator_
    y_pred = best_svm_model.predict(X_test)

    print(f"Akurasi Test (menggunakan model ranking 1): {accuracy_score(y_test, y_pred)*100:.2f}%\n")
    print("Laporan Klasifikasi:")
    print(classification_report(y_test, y_pred))

    # Menampilkan grafik Confusion Matrix
    print("\nMenampilkan Visualisasi Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=best_svm_model.classes_,
                yticklabels=best_svm_model.classes_)
    plt.title('Confusion Matrix - Model SVM (RBF)\nDataset Seimbang (70% Train, 30% Test)', pad=15)
    plt.xlabel('Prediksi Sistem', labelpad=10)
    plt.ylabel('Kondisi Aktual', labelpad=10)
    plt.show()

    print("\n" + "="*50)
    print("STEP 9: MENYIMPAN DAN MENGUNDUH MODEL")
    print("="*50)
    model_filename = 'model_pltb_svm_rbf.pkl'
    with open(model_filename, 'wb') as file:
        pickle.dump(best_svm_model, file)

    print(f"[INFO] Berhasil menyimpan model ke dalam bentuk '{model_filename}'.")
    print("[INFO] Mengunduh otomatis ke komputer Anda...")
    try:
        files.download(model_filename)
        print("=== SELURUH PROSES SELESAI DENGAN SUKSES ===")
    except Exception as e:
        print(f"Gagal mengunduh otomatis. Silakan download manual dari tab 'Files' di sebelah kiri. Error: {e}")
