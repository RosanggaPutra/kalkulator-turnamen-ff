import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import re
import difflib
from PIL import Image

# Pengaturan Dasar Halaman Web
st.set_page_config(page_title="Kalkulator Turnamen FF AI", layout="wide")
st.title("🏆 Kalkulator Poin Otomatis Turnamen Free Fire")
st.write("Unggah screenshot hasil match, biar AI yang menghitung klasemen secara otomatis!")

# Regulasi Poin Resmi Free Fire
PLACEMENT_POINTS = {1: 12, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1, 11: 0, 12: 0}
KILL_POINT = 1

# ==========================================
# FUNGSI PEMBANTU
# ==========================================
def ambil_prefix(nama):
    # Bersihkan simbol/spasi, ambil maksimal 4 huruf pertama
    nama_bersih = re.sub(r'[^A-Za-z0-9]', '', str(nama)).upper()
    return nama_bersih[:4] if len(nama_bersih) >= 4 else nama_bersih

def bersihkan_angka(teks):
    # Memaksa teks menjadi angka (contoh: "15 kills" -> 15)
    angka = re.sub(r'[^0-9]', '', str(teks))
    return int(angka) if angka else 0

# Inisialisasi Penyimpanan Memori
if "database_match" not in st.session_state:
    st.session_state["database_match"] = {f"Match {i}": [] for i in range(1, 7)}

st.sidebar.header("⚙️ Pengaturan API")
api_key = st.sidebar.text_input("Masukkan Gemini API Key Anda:", type="password")
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
                    if foto_1: images_to_process.append(Image.open(foto_1))
                    if foto_2: images_to_process.append(Image.open(foto_2))
                    
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    prompt = """
                    Kamu adalah sistem AI penilai turnamen esports Free Fire.
                    Tugasmu menganalisis gambar hasil akhir pertandingan.
                    
                    Aturan SANGAT KETAT (ANTI-AUTOCORRECT):
                    1. DILARANG KERAS memperbaiki ejaan menjadi kata bahasa Inggris. Tuliskan persis huruf demi huruf apa adanya sesuai gambar.
                    2. team: Ambil nickname pemain PERTAMA (paling atas).
                    3. semua_nick: Ekstrak SEMUA nickname pemain di kotak tersebut. Pisahkan dengan koma.
                    4. place: Angka peringkat. HANYA TULIS ANGKA (contoh: 1).
                    5. kill: Total kill dari seluruh pemain. HANYA TULIS ANGKA (contoh: 15).
                    6. HANYA ekstrak tim yang benar-benar TERLIHAT di gambar.
                    
                    Keluarkan output JSON array mentah, contoh:
                    [
                        {"team": "EVOS Budi", "semua_nick": "EVOS Budi, EVOS Agus, Joko12", "place": 1, "kill": 15}
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

# ==========================================
# PROSES AKUMULASI GLOBAL (MULTI-MEMORI PEMAIN)
# ==========================================
st.markdown("---")
st.header("🏆 KLASEMEN GLOBAL (TOTAL HASIL 6 MATCH)")

global_records = {}
kunci_nama_tim = {} # Format: {"PREF_P1": "Nama Tim", "PREF_P2": "Nama Tim"}

for m_idx in range(1, 7):
    m_name = f"Match {m_idx}"
    match_list = st.session_state["database_match"][m_name]
    
    for row in match_list:
        nama_utama = str(row.get("team", "")).strip()
        semua_nick_str = str(row.get("semua_nick", ""))
        
        if not nama_utama:
            continue
            
        place = bersihkan_angka(row.get("place", 0))
        kill = bersihkan_angka(row.get("kill", 0))
        
        # Gabungkan semua pemain di kotak ini jadi detektif pencari
        daftar_cek_nick = [nama_utama] + [n.strip() for n in semua_nick_str.split(",")]
        nama_resmi = None
        
        # 1. Cek apakah ada 1 saja pemain di tim ini yang nyangkut di memori
        for nick in daftar_cek_nick:
            if not nick: continue
            prefix = ambil_prefix(nick)
            if not prefix: continue
            
            # Cek Persis
            if prefix in kunci_nama_tim:
                nama_resmi = kunci_nama_tim[prefix]
                break
            
            # Cek Typo AI (Toleransi 75% mirip)
            if kunci_nama_tim:
                mirip = difflib.get_close_matches(prefix, kunci_nama_tim.keys(), n=1, cutoff=0.75)
                if mirip:
                    nama_resmi = kunci_nama_tim[mirip[0]]
                    break

        # 2. Registrasi / Penetapan Nama
        if nama_resmi:
            # Jika tim ini sudah ada, TAMBAHKAN juga hafalan pemain barunya (cadangan) ke memori
            for nick in daftar_cek_nick:
                p = ambil_prefix(nick)
                if p and p not in kunci_nama_tim:
                    kunci_nama_tim[p] = nama_resmi
        else:
            # Jika tim ini benar-benar baru (saat Match 1 / belum dikenal)
            # Pastikan daftar tim resmi belum mencapai batas 12
            if len(set(kunci_nama_tim.values())) < 12:
                nama_resmi = nama_utama
                for nick in daftar_cek_nick:
                    p = ambil_prefix(nick)
                    if p and p not in kunci_nama_tim:
                        kunci_nama_tim[p] = nama_resmi
            else:
                continue # Tim ke-13 ditolak
        
        # 3. Hitung Poin Pasti (Aman dari huruf/error)
        p_p = PLACEMENT_POINTS.get(place, 0)
        total_p_match = p_p + (kill * KILL_POINT)
        
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
