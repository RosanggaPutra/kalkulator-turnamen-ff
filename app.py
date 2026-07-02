import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
from PIL import Image

# Pengaturan Dasar Halaman Web
st.set_page_config(page_title="Kalkulator Turnamen FF AI", layout="wide")
st.title("🏆 Kalkulator Poin Otomatis Turnamen Free Fire")
st.write("Unggah screenshot hasil match, biar AI yang menghitung klasemen secara otomatis!")

# Regulasi Poin Resmi Free Fire (Dapat disesuaikan)
PLACEMENT_POINTS = {1: 12, 2: 9, 3: 8, 4: 7, 5: 6, 6: 5, 7: 4, 8: 3, 9: 2, 10: 1, 11: 0, 12: 0}
KILL_POINT = 1

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
    
    # Input Upload Foto (2 Gambar per Match)
    col1, col2 = st.columns(2)
    with col1:
        foto_1 = st.file_uploader(f"Upload Gambar 1 (Rank Atas) - {selected_match}", type=["jpg", "jpeg", "png"])
    with col2:
        foto_2 = st.file_uploader(f"Upload Gambar 2 (Rank Bawah) - {selected_match}", type=["jpg", "jpeg", "png"])
        
    if foto_1 and foto_2:
        if st.button(f"🚀 Proses & Hitung {selected_match} via AI"):
            with st.spinner("AI sedang membaca foto dan menghitung poin..."):
                try:
                    img1 = Image.open(foto_1)
                    img2 = Image.open(foto_2)
                    
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    
                    prompt = "Kamu adalah AI penilai turnamen Free Fire. Ekstrak data seluruh blok tim dari peringkat 1 hingga 12 dari kedua gambar ini. Aturan: 1. Nama Tim: Ambil dari kesamaan Tag Clan, atau nickname urutan teratas di kotak tersebut. 2. Rank/Place: Angka peringkat kotak (1-12). 3. Total Kill: Jumlahkan kill 4 pemain di kotak peringkat tersebut. Keluarkan output HANYA dalam bentuk JSON array objek mentah tanpa markdown, contoh: [{'team': 'NamaTim', 'place': 1, 'kill': 29}]"
                    
                    response = model.generate_content([prompt, img1, img2])
                    clean_json = response.text.strip().replace("```json", "").replace("```", "")
                    parsed_data = json.loads(clean_json)
                    
                    st.session_state["database_match"][selected_match] = parsed_data
                    st.success(f"Data {selected_match} berhasil diekstrak!")
                except Exception as e:
                    st.error(f"Gagal memproses gambar. Error: {str(e)}")

    # Menampilkan data match aktif yang bisa diedit langsung oleh user
    if st.session_state["database_match"][selected_match]:
        st.subheader(f"📝 Koreksi Hasil Sementara ({selected_match})")
        
        df_current = pd.DataFrame(st.session_state["database_match"][selected_match])
        edited_df = st.data_editor(df_current, num_rows="dynamic", key=f"editor_{selected_match}")
        
        st.session_state["database_match"][selected_match] = edited_df.to_dict(orient="records")

# 2. PROSES AKUMULASI GLOBAL
st.markdown("---")
st.header("🏆 KLASEMEN GLOBAL (TOTAL HASIL 6 MATCH)")

global_records = {}

for m_idx in range(1, 7):
    m_name = f"Match {m_idx}"
    match_list = st.session_state["database_match"][m_name]
    
    for row in match_list:
        nama_tim = str(row.get("team", "")).strip()
        if not nama_tim:
            continue
            
        place = row.get("place", "-")
        kill = row.get("kill", 0)
        
        try:
            p_p = PLACEMENT_POINTS.get(int(place), 0)
        except:
            p_p = 0
        total_p_match = p_p + (int(kill) * KILL_POINT)
        
        if nama_tim not in global_records:
            global_records[nama_tim] = {}
            
        global_records[nama_tim][f"{m_name} PLACE"] = place
        global_records[nama_tim][f"{m_name} KILL"] = kill
        global_records[nama_tim][f"{m_name} POINT"] = total_p_match

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
