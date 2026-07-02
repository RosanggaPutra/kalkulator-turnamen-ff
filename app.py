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

# Fungsi Cerdas untuk Mengambil 3 Huruf Depan Nama
def ambil_3_huruf_depan(nama):
    nama_bersih = re.sub(r'[^A-Za-z0-9]', '', str(nama)).upper()
    return nama_bersih[:3] if len(nama_bersih) >= 3 else nama_bersih

# 1. Inisialisasi Penyimpanan Memori
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
    
    col1, col2 = st.columns(2)
    with col1:
        foto_1 = st.file_uploader(f"Upload Gambar 1 (Opsional/Wajib) - {selected_match}", type=["jpg", "jpeg", "png"])
    with col2:
        foto_2 = st.file_uploader(f"Upload Gambar 2 (Opsional) - {selected_match}", type=["jpg", "jpeg", "png"])
        
    if foto_1 or foto_2:
        if st.button(f"🚀 Proses & Hitung {selected_match} via AI"):
            with st.spinner("AI sedang membaca foto dan menganalisis seluruh pemain..."):
                try:
                    images_to_process = []
                    if foto_1:
                        images_to_process.append(Image.open(foto_1))
                    if foto_2:
                        images_to_process.append(Image.open(foto_2))
                    
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    # PROMPT BARU: Meminta AI mengekstrak SEMUA NICKNAME
                    prompt = """
                    Kamu adalah sistem AI penilai turnamen esports Free Fire.
                    Tugasmu menganalisis gambar hasil akhir pertandingan.
                    
                    Aturan KETAT:
                    1. team: Ambil nickname pemain PERTAMA (paling atas) yang terlihat paling jelas di kotak peringkat tersebut.
                    2. semua_nick: Ekstrak SEMUA nickname pemain yang ada di kotak peringkat tersebut (pemain 1, 2, 3, dan 4). Gabungkan dengan tanda koma.
                    3. place: Angka peringkat.
                    4. kill: Total kill dari seluruh pemain di kotak tersebut.
                    5. HANYA ekstrak tim yang TERLIHAT di gambar. Jangan mengarang.
                    
                    Keluarkan output JSON array mentah, contoh:
                    [
                        {"team": "EVOS Budi", "semua_nick": "EVOS Budi, EVOS Agus, Joko123", "place": 1, "kill": 15},
                        {"team": "SAD BoyZzz", "semua_nick": "SAD BoyZzz, falz, 120Hz", "place": 2, "kill": 10}
                    ]
                    """
                    
                    response = model.generate_content([prompt] + images_to_process)
                    clean_json = response.text.strip().replace("```json", "").replace("```", "")
                    parsed_data = json.loads(clean_json)
                    
                    st.session_state["database_match"][selected_match] = parsed_data
                    st.success(f"Data {selected_match} berhasil diekstrak!")
                except Exception as e:
                    st.error(f"Gagal memproses gambar. Error: {str(e)}")

    if st.session_state["database_match"][selected_match]:
        st.subheader(f"📝 Koreksi Hasil Sementara ({selected_match})")
        
        df_current = pd.DataFrame(st.session_state["database_match"][selected_match])
        edited_df = st.data_editor(df_current, num_rows="dynamic", key=f"editor_{selected_match}")
        st.session_state["database_match"][selected_match] = edited_df.to_dict(orient="records")

# 2. PROSES AKUMULASI GLOBAL DENGAN PENGECEKAN MULTI-ANGGOTA
st.markdown("---")
st.header("🏆 KLASEMEN GLOBAL (TOTAL HASIL 6 MATCH)")

global_records = {}
kunci_nama_tim = {} 

for m_idx in range(1, 7):
    m_name = f"Match {m_idx}"
    match_list = st.session_state["database_match"][m_name]
    
    for row in match_list:
        nama_utama = str(row.get("team", "")).strip()
        semua_nick_str = str(row.get("semua_nick", ""))
        
        if not nama_utama:
            continue
            
        place = row.get("place", "-")
        kill = row.get("kill", 0)
        
        # Buat daftar pencarian dari nama utama DAN semua nick yang dipisah koma
        daftar_cek_nick = [nama_utama] + [n.strip() for n in semua_nick_str.split(",")]
        
        id_ditemukan = None
        
        # LOGIKA BARU: Cek satu per satu nick pemain, adakah yang cocok dengan tim Match 1?
        for nick in daftar_cek_nick:
            if not nick: 
                continue
            prefix = ambil_3_huruf_depan(nick)
            if prefix and prefix in kunci_nama_tim:
                id_ditemukan = prefix
                break # Jika ketemu 1 saja, langsung berhenti mencari!
                
        # Jika berhasil menemukan ID yang cocok (Match 2, 3, dst)
        if id_ditemukan:
            nama_resmi = kunci_nama_tim[id_ditemukan]
        else:
            # Jika tidak ada yang cocok sama sekali, anggap tim baru (Khusus Match 1)
            prefix_baru = ambil_3_huruf_depan(nama_utama)
            if prefix_baru not in kunci_nama_tim:
                if len(kunci_nama_tim) < 12:
                    kunci_nama_tim[prefix_baru] = nama_utama
                    nama_resmi = nama_utama
                else:
                    continue # Abaikan jika sudah 12 tim
            else:
                nama_resmi = kunci_nama_tim[prefix_baru]
        
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
    st.info("Belum ada data match yang diproses.")
