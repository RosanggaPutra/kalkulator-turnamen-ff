import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import re
from PIL import Image

# Pengaturan Dasar Halaman Web
st.set_page_config(page_title="Kalkulator Turnamen FF AI", layout="wide")
st.title("🏆 Kalkulator Poin Otomatis Turnamen Free Fire")
st.write("Unggah screenshot hasil match, biar AI yang menghitung klasemen secara otomatis!")

# Regulasi Poin Resmi Free Fire
PLACEMENT_POINTS = {1: 12, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1, 11: 0, 12: 0}
KILL_POINT = 1

# Fungsi Cerdas untuk Mengambil 3 Huruf Depan Nama Tim
def ambil_3_huruf_depan(nama):
    nama_bersih = re.sub(r'[^A-Za-z0-9]', '', str(nama)).upper()
    return nama_bersih[:3]

# 1. Inisialisasi Penyimpanan Memori (Session State) untuk 6 Match
if "database_match" not in st.session_state:
    st.session_state["database_match"] = {f"Match {i}": [] for i in range(1, 7)}

# Kunci API di Sidebar
st.sidebar.header("⚙️ Pengaturan API")
api_key = st.sidebar.text_input("Masukkan Gemini API Key Anda:", type="password")

# Pilihan Match Aktif
st.sidebar.header("🎮 Navigasi Match")
selected_match = st.sidebar.selectbox("Pilih Match yang Ingin Diproses:", [f"Match {i}" for i in range(1, 7)])

if not api_key:
    st.warning("Silakan masukkan Gemini API Key Anda di sidebar sebelah kiri untuk memulai.")
else:
    genai.configure(api_key=api_key)
    
    st.header(f"📊 Pemrosesan Data - {selected_match}")
    
    # Input Upload Foto
    col1, col2 = st.columns(2)
    with col1:
        foto_1 = st.file_uploader(f"Upload Gambar 1 (Opsional/Wajib) - {selected_match}", type=["jpg", "jpeg", "png"])
    with col2:
        foto_2 = st.file_uploader(f"Upload Gambar 2 (Opsional) - {selected_match}", type=["jpg", "jpeg", "png"])
        
    # LOGIKA BARU: Tombol akan muncul jika MINIMAL ADA 1 FOTO yang diunggah
    if foto_1 or foto_2:
        if st.button(f"🚀 Proses & Hitung {selected_match} via AI"):
            with st.spinner("AI sedang membaca foto dan menganalisis pemain..."):
                try:
                    # Menyiapkan daftar gambar yang diunggah (bisa 1, bisa 2)
                    images_to_process = []
                    if foto_1:
                        images_to_process.append(Image.open(foto_1))
                    if foto_2:
                        images_to_process.append(Image.open(foto_2))
                    
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # PROMPT BARU: Fleksibel, hanya mengekstrak yang terlihat di gambar
                    prompt = """
                    Kamu adalah sistem AI penilai turnamen esports Free Fire.
                    Tugasmu menganalisis gambar hasil akhir pertandingan yang diberikan.
                    
                    Aturan SANGAT KETAT:
                    1. NAMA TIM: Ambil nickname pemain urutan PERTAMA (paling atas) di dalam setiap kotak peringkat. Jika pemain pertama kabur atau kosong, ambil dari pemain urutan KEDUA, KETIGA, atau KEEMPAT. Tuliskan nickname utuhnya.
                    2. RANK/PLACE: Angka peringkat dari kotak tersebut.
                    3. TOTAL KILL: Hitung jumlah kill seluruh pemain di kotak tersebut.
                    4. OUTPUT SESUAI GAMBAR SAJA: Hanya ekstrak tim yang benar-benar TERLIHAT di gambar. JANGAN MENGARANG atau menambahkan rank/tim fiktif. Jika di gambar hanya terlihat 11 tim, maka keluarkan 11 tim saja.
                    
                    Keluarkan output HANYA dalam bentuk JSON array mentah, contoh:
                    [
                        {"team": "EVOS Budi", "place": 1, "kill": 15},
                        {"team": "SAD BoyZzz", "place": 2, "kill": 10}
                    ]
                    """
                    
                    # AI membaca prompt beserta berapapun gambar yang dikirim (1 atau 2)
                    response = model.generate_content([prompt] + images_to_process)
                    clean_json = response.text.strip().replace("```json", "").replace("```", "")
                    parsed_data = json.loads(clean_json)
                    
                    st.session_state["database_match"][selected_match] = parsed_data
                    st.success(f"Data {selected_match} berhasil diekstrak!")
                except Exception as e:
                    st.error(f"Gagal memproses gambar. Error: {str(e)}")
                    st.info("Pastikan format gambar didukung dan tidak rusak.")

    # Menampilkan data match aktif (Data Editor)
    if st.session_state["database_match"][selected_match]:
        st.subheader(f"📝 Koreksi Hasil Sementara ({selected_match})")
        st.info("Jika nama pemain berbeda drastis dari Match 1, edit nama depannya (minimal 3 huruf) agar mirip dengan Match 1 supaya poinnya bisa bergabung di Klasemen Global.")
        
        df_current = pd.DataFrame(st.session_state["database_match"][selected_match])
        edited_df = st.data_editor(df_current, num_rows="dynamic", key=f"editor_{selected_match}")
        st.session_state["database_match"][selected_match] = edited_df.to_dict(orient="records")

# 2. PROSES AKUMULASI GLOBAL (DETEKSI 3 HURUF DEPAN)
st.markdown("---")
st.header("🏆 KLASEMEN GLOBAL (TOTAL HASIL 6 MATCH)")

global_records = {}
kunci_nama_tim = {} # Menyimpan nama resmi tim berdasarkan 3 huruf depannya

for m_idx in range(1, 7):
    m_name = f"Match {m_idx}"
    match_list = st.session_state["database_match"][m_name]
    
    for row in match_list:
        nama_mentah = str(row.get("team", "")).strip()
        if not nama_mentah:
            continue
            
        place = row.get("place", "-")
        kill = row.get("kill", 0)
        
        # Ambil 3 huruf depan sebagai ID Unik penggabung
        id_3_huruf = ambil_3_huruf_depan(nama_mentah)
        
        # Jika nama depan ini belum pernah ada, jadikan nama_mentah sebagai Nama Resmi
        if id_3_huruf not in kunci_nama_tim:
            # Batasi maksimal agar klasemen global hanya 12 tim
            if len(kunci_nama_tim) < 12:
                kunci_nama_tim[id_3_huruf] = nama_mentah
            else:
                continue # Abaikan tim siluman yang ke-13 agar tabel tidak rusak
                
        nama_resmi = kunci_nama_tim[id_3_huruf]
        
        # Hitung poin match ini
        try:
            p_p = PLACEMENT_POINTS.get(int(place), 0)
        except:
            p_p = 0
        total_p_match = p_p + (int(kill) * KILL_POINT)
        
        if nama_resmi not in global_records:
            global_records[nama_resmi] = {}
            
        global_records[nama_resmi][f"{m_name} PLACE"] = place
        global_records[nama_resmi][f"{m_name} KILL"] = kill
        global_records[nama_resmi][f"{m_name} POINT"] = total_p_match

if global_records:
    table_rows = []
    for t_name, m_data in global_records.items():
        row_dict = {"NAMA TEAM": t_name}
        grand_total = 0
        
        for i in range(1, 7):
            m_name = f"Match {i}"
            row_dict[f"M{i} PLACE"] = m_data.get(f"{m_name} PLACE", "-")
            row_dict[f"M{i} KILL"] = m_data.get(f"{m_name} KILL", "-")
            row_dict[f"M{i} POINT"] = m_data.get(f"{m_name} POINT", 0)
            grand_total += m_data.get(f"{m_name} POINT", 0)
            
        row_dict["TOTAL POINT"] = grand_total
        table_rows.append(row_dict)
        
    df_global = pd.DataFrame(table_rows)
    df_global = df_global.sort_values(by="TOTAL POINT", ascending=False).reset_index(drop=True)
    df_global.insert(0, "RANK", df_global.index + 1)
    
    st.dataframe(df_global, use_container_width=True, hide_index=True)
    
    if st.sidebar.button("🧹 Reset Semua Data Klasemen"):
        st.session_state["database_match"] = {f"Match {i}": [] for i in range(1, 7)}
        st.rerun()
else:
    st.info("Belum ada data match yang diproses. Klasemen global akan muncul otomatis di sini setelah Anda memproses minimal satu match.")
