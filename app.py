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
# FUNGSI PEMBERSIH & FORMAT DATA (ANTI-CRASH)
# ==========================================
def bersihkan_nama(nama):
    # Membuang semua simbol aneh, spasi, dan tanda baca. Hanya menyisakan Huruf & Angka
    return re.sub(r'[^A-Za-z0-9]', '', str(nama)).upper()

def bersihkan_angka(teks):
    # Sistem kebal error: Jika AI mengosongkan data (None/NaN), otomatis jadikan 0
    try:
        if pd.isna(teks) or teks is None or str(teks).strip() == "":
            return 0
        angka = re.sub(r'[^0-9]', '', str(teks))
        return int(angka) if angka else 0
    except Exception:
        return 0

# Inisialisasi Penyimpanan Memori di Session State
if "database_match" not in st.session_state:
    st.session_state["database_match"] = {f"Match {i}": [] for i in range(1, 7)}

# Kunci API di Sidebar
st.sidebar.header("⚙️ Pengaturan API")
api_key = st.sidebar.text_input("Masukkan Gemini API Key Anda:", type="password")

# Navigasi Match
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
            with st.spinner("AI sedang menganalisis seluruh data pemain pada gambar..."):
                try:
                    images_to_process = []
                    if foto_1: images_to_process.append(Image.open(foto_1))
                    if foto_2: images_to_process.append(Image.open(foto_2))
                    
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    prompt = """
                    Kamu adalah sistem AI penilai turnamen esports Free Fire.
                    Tugasmu menganalisis gambar hasil akhir pertandingan.
                    
                    Aturan SANGAT KETAT (ANTI-AUTOCORRECT):
                    1. DILARANG KERAS memperbaiki ejaan menjadi kata bahasa Inggris (Contoh: JANGAN ubah 'citcuit' menjadi 'circuit'). Tuliskan huruf demi huruf apa adanya sesuai gambar.
                    2. team: Ambil nickname pemain PERTAMA (paling atas) di kotak tim tersebut.
                    3. semua_nick: Ekstrak SEMUA nickname pemain yang ada di dalam kotak tersebut (Pemain 1, 2, 3, dan 4 jika ada). Pisahkan dengan tanda koma.
                    4. place: Angka peringkat tim. HANYA TULIS ANGKA (contoh: 1).
                    5. kill: Total kill dari seluruh pemain di kotak tersebut. HANYA TULIS ANGKA (contoh: 12).
                    6. HANYA ekstrak data tim yang benar-benar TERLIHAT di gambar. Jangan mengarang data.
                    
                    Keluarkan output JSON array mentah, contoh:
                    [
                        {"team": "citcuit ell", "semua_nick": "citcuit ell, falz, 120Hz", "place": 1, "kill": 12}
                    ]
                    """
                    
                    response = model.generate_content([prompt] + images_to_process)
                    clean_json = response.text.strip().replace("```json", "").replace("```", "")
                    parsed_data = json.loads(clean_json)
                    
                    st.session_state["database_match"][selected_match] = parsed_data
                    st.success(f"Data {selected_match} berhasil diekstrak!")
                except Exception as e:
                    st.error(f"Gagal memproses gambar. Error dari AI: {str(e)}")

    if st.session_state["database_match"][selected_match]:
        st.subheader(f"📝 Koreksi Hasil Sementara ({selected_match})")
        df_current = pd.DataFrame(st.session_state["database_match"][selected_match])
        edited_df = st.data_editor(df_current, num_rows="dynamic", key=f"editor_{selected_match}")
        st.session_state["database_match"][selected_match] = edited_df.to_dict(orient="records")

# ==========================================
# PROSES AKUMULASI KLASEMEN GLOBAL (ANTI-BUG)
# ==========================================
st.markdown("---")
st.header("🏆 KLASEMEN GLOBAL (TOTAL HASIL 6 MATCH)")

global_records = {}
player_to_team = {}  
official_teams = []  

match_1_list = st.session_state["database_match"].get("Match 1", [])
for row in match_1_list:
    nama_utama = str(row.get("team", "")).strip()
    if not nama_utama or nama_utama.lower() == "none":
        continue
    if nama_utama not in official_teams:
        official_teams.append(nama_utama)
    
    semua_nick_str = str(row.get("semua_nick", ""))
    daftar_cek_nick = [nama_utama] + [n.strip() for n in semua_nick_str.split(",")]
    for nick in daftar_cek_nick:
        cleaned_n = bersihkan_nama(nick)
        if cleaned_n:
            player_to_team[cleaned_n] = nama_utama

for m_idx in range(1, 7):
    m_name = f"Match {m_idx}"
    match_list = st.session_state["database_match"].get(m_name, [])
    
    for row in match_list:
        nama_utama = str(row.get("team", "")).strip()
        if not nama_utama or nama_utama.lower() == "none":
            continue
            
        place = bersihkan_angka(row.get("place", 0))
        kill = bersihkan_angka(row.get("kill", 0))
        
        semua_nick_str = str(row.get("semua_nick", ""))
        daftar_cek_nick = [nama_utama] + [n.strip() for n in semua_nick_str.split(",")]
        
        nama_resmi = None
        
        if m_idx == 1:
            nama_resmi = nama_utama
        else:
            for nick in daftar_cek_nick:
                cleaned_n = bersihkan_nama(nick)
                if cleaned_n in player_to_team:
                    nama_resmi = player_to_team[cleaned_n]
                    break
            
            if not nama_resmi:
                for nick in daftar_cek_nick:
                    cleaned_n = bersihkan_nama(nick)
                    if cleaned_n and player_to_team:
                        mirip = difflib.get_close_matches(cleaned_n, player_to_team.keys(), n=1, cutoff=0.6)
                        if mirip:
                            nama_resmi = player_to_team[mirip[0]]
                            break
            
            if not nama_resmi:
                cleaned_team = bersihkan_nama(nama_utama)
                cleaned_official_teams = {bersihkan_nama(t): t for t in official_teams}
                mirip_team = difflib.get_close_matches(cleaned_team, cleaned_official_teams.keys(), n=1, cutoff=0.6)
                if mirip_team:
                    nama_resmi = cleaned_official_teams[mirip_team[0]]
        
        if not nama_resmi:
            nama_resmi = nama_utama
            for nick in daftar_cek_nick:
                cleaned_n = bersihkan_nama(nick)
                if cleaned_n:
                    player_to_team[cleaned_n] = nama_resmi
        
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
