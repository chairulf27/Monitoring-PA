import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date
import datetime
from docxtpl import DocxTemplate

# Konfigurasi Halaman Minimalis & Elegan
st.set_page_config(page_title="Portal Aktivasi", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# FUNGSI PINTAR UNTUK MENGUBAH ANGKA JADI HURUF (DARI BAI)
# ==========================================
def terbilang(n):
    satuan = ["", "Satu", "Dua", "Tiga", "Empat", "Lima", "Enam", "Tujuh", "Delapan", "Sembilan", "Sepuluh", "Sebelas"]
    n = int(n)
    if n < 12: return satuan[n]
    elif n < 20: return satuan[n - 10] + " Belas"
    elif n < 100: return (satuan[n // 10] + " Puluh " + satuan[n % 10]).strip()
    elif n < 200: return "Seratus " + terbilang(n - 100)
    elif n < 1000: return (satuan[n // 100] + " Ratus " + terbilang(n % 100)).strip()
    elif n < 2000: return "Seribu " + terbilang(n - 1000)
    elif n < 10000: return (satuan[n // 1000] + " Ribu " + terbilang(n % 1000)).strip()
    return str(n)

HARI = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
BULAN = {1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'}

# ==========================================
# 1. SETUP DATABASE LENGKAP & MIGRATION
# ==========================================
if not os.path.exists("uploads_bai"):
    os.makedirs("uploads_bai")

def init_db():
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rekanan (nama_rekanan TEXT PRIMARY KEY)''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS project_data (
            id_project TEXT PRIMARY KEY, pelanggan TEXT, alamat TEXT, layanan TEXT,
            rekanan TEXT, tgl_disposisi TEXT, status_survey TEXT DEFAULT 'Belum',
            progres_tarikan INTEGER DEFAULT 0, redaman TEXT DEFAULT '-',
            link_bai TEXT DEFAULT '-', status_akhir TEXT DEFAULT 'Disposisi'
        )
    ''')
    
    kolom_baru = {
        "koordinat": "TEXT DEFAULT '-'",
        "kebutuhan_material": "TEXT DEFAULT '-'",
        "estimasi_kabel": "TEXT DEFAULT '0'",
        "catatan_survey": "TEXT DEFAULT '-'",
        "mapping_core": "TEXT DEFAULT '-'",
        "catatan_penarikan": "TEXT DEFAULT '-'",
        "kabel_tertarik": "INTEGER DEFAULT 0",
        "catatan_commissioning": "TEXT DEFAULT '-'",
        "tanggal_selesai": "TEXT DEFAULT '-'", 
        "kendala_bai": "TEXT DEFAULT '-'"      
    }
    for col, dtype in kolom_baru.items():
        try:
            c.execute(f"ALTER TABLE project_data ADD COLUMN {col} {dtype}")
        except sqlite3.OperationalError:
            pass
            
    c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'Super Admin')")
    c.execute("INSERT OR IGNORE INTO users VALUES ('ptl', 'ptl123', 'PTL')")
    conn.commit()
    conn.close()

def cek_login(username, password):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user[0] if user else None

def get_all_users():
    conn = sqlite3.connect('monitoring_aktivasi.db')
    df = pd.read_sql_query("SELECT username, role FROM users", conn)
    conn.close()
    return df

def tambah_user(username, password, role):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_list_rekanan():
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    c.execute("SELECT nama_rekanan FROM rekanan")
    data = [row[0] for row in c.fetchall()]
    conn.close()
    return data

def tambah_rekanan(nama):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO rekanan (nama_rekanan) VALUES (?)", (nama,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def hapus_rekanan_callback(nama):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    c.execute("DELETE FROM rekanan WHERE nama_rekanan = ?", (nama,))
    conn.commit()
    conn.close()

def load_data_project():
    conn = sqlite3.connect('monitoring_aktivasi.db')
    df = pd.read_sql_query("SELECT * FROM project_data", conn)
    conn.close()
    return df

def insert_project_baru(id_project, pelanggan, alamat, layanan, rekanan, tgl):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO project_data 
                     (id_project, pelanggan, alamat, layanan, rekanan, tgl_disposisi, status_akhir) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                  (id_project, pelanggan, alamat, layanan, rekanan, tgl, 'Disposisi'))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_survey_rab(id_project, status_survey, material, estimasi_kabel, catatan):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    if status_survey == 'Selesai':
        status_akhir = 'Menunggu Penarikan'
    elif status_survey == 'Terkendala':
        status_akhir = 'Kendala Survey'
    else:
        status_akhir = 'Progres Survey'
    c.execute('''UPDATE project_data 
                 SET status_survey=?, kebutuhan_material=?, estimasi_kabel=?, catatan_survey=?, status_akhir=? 
                 WHERE id_project=?''', 
              (status_survey, material, estimasi_kabel, catatan, status_akhir, id_project))
    conn.commit()
    conn.close()

def update_penarikan_kabel(id_project, progres, kabel_tertarik, catatan):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    if progres >= 100:
        status_akhir = 'Menunggu Commissioning'
    else:
        status_akhir = f'Penarikan {progres}%'
    c.execute('''UPDATE project_data 
                 SET progres_tarikan=?, kabel_tertarik=?, catatan_penarikan=?, status_akhir=? 
                 WHERE id_project=?''', 
              (progres, kabel_tertarik, catatan, status_akhir, id_project))
    conn.commit()
    conn.close()

def update_status_preconfig(id_project):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    status_akhir = 'Menunggu Validasi BAI'
    c.execute('''UPDATE project_data SET status_akhir=? WHERE id_project=?''', (status_akhir, id_project))
    conn.commit()
    conn.close()

def hapus_project(id_project):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    c.execute("DELETE FROM project_data WHERE id_project = ?", (id_project,))
    conn.commit()
    conn.close()

def update_status_bai(id_project, status_pekerjaan, tgl_selesai, kendala):
    conn = sqlite3.connect('monitoring_aktivasi.db')
    c = conn.cursor()
    if status_pekerjaan == 'Selesai':
        status_akhir = 'Selesai'
        c.execute('''UPDATE project_data 
                     SET tanggal_selesai=?, kendala_bai=?, status_akhir=? 
                     WHERE id_project=?''', (str(tgl_selesai), '-', status_akhir, id_project))
    else:
        status_akhir = 'Kendala BAI'
        c.execute('''UPDATE project_data 
                     SET tanggal_selesai=?, kendala_bai=?, status_akhir=? 
                     WHERE id_project=?''', ('-', kendala, status_akhir, id_project))
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. SISTEM LOGIN
# ==========================================
if 'logged_in' not in st.session_state:
    if "user" in st.query_params and "role" in st.query_params:
        st.session_state.logged_in = True
        st.session_state.username = st.query_params["user"]
        st.session_state.role = st.query_params["role"]
    else:
        st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>Portal Aktivasi Jaringan</h1>", unsafe_allow_html=True)
    st.write("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk", use_container_width=True):
                role = cek_login(username, password)
                if role:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.query_params["user"] = username
                    st.query_params["role"] = role
                    st.rerun()
                else:
                    st.error("Kredensial tidak valid!")
    st.stop()

# ==========================================
# 3. KONTEN APLIKASI
# ==========================================
st.sidebar.title("📡 Panel Kontrol")
st.sidebar.info(f"👤 **{st.session_state.username}** \n\n🏷️ Role: {st.session_state.role}")

if st.sidebar.button("Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.query_params.clear()
    st.rerun()

st.sidebar.markdown("---")

if st.session_state.role == "Super Admin":
    menu = st.sidebar.radio("Navigasi Admin:", ["🏠 Dashboard Admin", "👥 Kelola Pengguna (Akun)", "🏢 Kelola Rekanan"])
else:
    menu = st.sidebar.radio("Proses Bisnis (PTL):", [
        "🏠 Dashboard Utama", 
        "📝 1. Disposisi Rekanan", 
        "🔍 2. Survey Detail & RAB", 
        "🧵 3. Penarikan Kabel", 
        "⚙️ 4. Generate Preconfig", 
        "📁 5. Status Penyelesaian (BAI)"
    ])

# ==========================================
# HALAMAN KHUSUS SUPER ADMIN
# ==========================================
if menu == "🏠 Dashboard Admin":
    st.title("Area Super Admin")
    df_project = load_data_project()
    st.subheader("📋 Semua Data Project")
    if df_project.empty:
        st.info("Belum ada data project di sistem.")
    else:
        st.dataframe(df_project[['id_project', 'pelanggan', 'rekanan', 'status_akhir']], use_container_width=True, hide_index=True)
        st.markdown("---")
        with st.expander("🗑️ Hapus Data Project (Pembersihan)"):
            with st.form("form_hapus_admin"):
                col1, col2 = st.columns([3, 1])
                list_hapus = [f"{row['id_project']} - {row['pelanggan']}" for idx, row in df_project.iterrows()]
                pilih_hapus = col1.selectbox("Pilih Project yang akan dihapus", list_hapus)
                if col2.form_submit_button("Hapus Permanen"):
                    id_hapus = pilih_hapus.split(" - ")[0]
                    hapus_project(id_hapus)
                    st.success(f"✅ Project **{id_hapus}** berhasil dihapus dari sistem!")
                    st.info("🔄 Silakan klik ulang menu 'Dashboard Admin' di sidebar.")

elif menu == "👥 Kelola Pengguna (Akun)":
    st.title("Kelola Akses Pengguna")
    with st.form("form_tambah_user"):
        col1, col2, col3 = st.columns(3)
        new_user = col1.text_input("Username Baru")
        new_pass = col2.text_input("Password")
        new_role = col3.selectbox("Pilih Role", ["PTL", "Super Admin"])
        if st.form_submit_button("Buat Akun"):
            if new_user and new_pass:
                if tambah_user(new_user, new_pass, new_role):
                    st.success(f"Akun '{new_user}' berhasil dibuat!")
                    st.rerun()
                else:
                    st.error("Username sudah terdaftar!")
            else:
                st.error("Isi Username dan Password!")
    st.markdown("---")
    st.subheader("Daftar Pengguna Aktif")
    st.dataframe(get_all_users(), use_container_width=True, hide_index=True)

elif menu == "🏢 Kelola Rekanan":
    st.title("Kelola Master Data Rekanan")
    with st.form("tambah_rekanan_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        nama_baru = col1.text_input("Nama Mitra Rekanan Baru")
        if col2.form_submit_button("Tambahkan"):
            if nama_baru:
                if tambah_rekanan(nama_baru):
                    st.success(f"{nama_baru} ditambahkan!")
                    st.rerun()
                else:
                    st.error("Nama rekanan sudah ada.")
            else:
                st.error("Nama tidak boleh kosong.")
    st.markdown("---")
    st.subheader("Daftar Mitra Rekanan")
    list_rekanan = get_list_rekanan()
    if not list_rekanan:
        st.info("Belum ada data rekanan.")
    else:
        for rek in list_rekanan:
            col_name, col_btn = st.columns([4, 1])
            with col_name:
                st.markdown(f"**🏢 {rek}**")
            with col_btn:
                st.button("Hapus", key=f"del_{rek}", on_click=hapus_rekanan_callback, args=(rek,))

# ==========================================
# HALAMAN KHUSUS PTL: DASHBOARD UTAMA
# ==========================================
elif menu == "🏠 Dashboard Utama":
    df_project = load_data_project()
    st.title("Dashboard Monitoring Aktivasi")
    st.markdown("---")
    
    total_project = len(df_project)
    project_selesai = len(df_project[df_project['status_akhir'] == 'Selesai']) if total_project > 0 else 0
    on_progress = total_project - project_selesai
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric(label="Total Project Disposisi", value=total_project)
    col_m2.metric(label="On Progress", value=on_progress)
    col_m3.metric(label="Project Selesai", value=project_selesai)

    st.markdown("---")
    with st.expander("📤 Import Data dari Google Sheets / Excel (Format CSV)", expanded=False):
        st.info("💡 Cara: Buka link Google Sheets kamu, klik **File -> Download -> Comma Separated Values (.csv)**, lalu upload ke kotak di bawah ini.")
        uploaded_csv = st.file_uploader("Pilih file CSV hasil download dari Google Sheets", type=["csv"])
        
        if uploaded_csv is not None:
            try:
                string_data = uploaded_csv.getvalue().decode("utf-8", errors="ignore")
                df_import = pd.read_csv(io.StringIO(string_data), sep=';', on_bad_lines='skip', engine='python')
                if len(df_import.columns) < 3:
                    df_import = pd.read_csv(io.StringIO(string_data), sep=',', on_bad_lines='skip', engine='python')

                df_import.columns = [str(c).strip().replace('"', '').lower() for c in df_import.columns]
                mapping_kolom = {'mitra': 'rekanan', 'id project': 'id_project', 'alamat': 'alamat'}
                df_import.rename(columns=mapping_kolom, inplace=True)
                df_import = df_import.replace('"', '', regex=True)

                st.write("Preview Data yang berhasil terbaca:")
                st.dataframe(df_import.head())
                
                if st.button("🚀 Proses Import ke Database", use_container_width=True):
                    conn = sqlite3.connect('monitoring_aktivasi.db')
                    kolom_target = ['id_project', 'pelanggan', 'alamat', 'layanan', 'rekanan']
                    missing_cols = [c for c in kolom_target if c not in df_import.columns]
                    
                    if missing_cols:
                        st.error(f"⚠️ Kolom berikut tidak ditemukan: {missing_cols}")
                    else:
                        df_final = df_import[kolom_target].copy()
                        df_final['tgl_disposisi'] = str(date.today())
                        df_final['status_akhir'] = 'Disposisi'
                        
                        df_final.to_sql('temp_import', conn, if_exists='replace', index=False)
                        c = conn.cursor()
                        c.execute('''
                            INSERT OR IGNORE INTO project_data 
                            (id_project, pelanggan, alamat, layanan, rekanan, tgl_disposisi, status_akhir)
                            SELECT id_project, pelanggan, alamat, layanan, rekanan, tgl_disposisi, status_akhir
                            FROM temp_import
                        ''')
                        count_import = c.rowcount
                        conn.commit()
                        c.execute('DROP TABLE temp_import')
                        conn.close()
                        
                        if count_import > 0:
                            st.success(f"✅ Berhasil mengimpor {count_import} data baru!")
                            st.balloons()
                            st.rerun()
                        else:
                            st.warning("⚠️ Data di file ini sudah ada di sistem.")
            except Exception as e:
                st.error(f"Gagal membaca file: {e}")

    st.markdown("### 📋 Tabel Status Project")
    if total_project == 0:
        st.info("Belum ada data project. Silakan gunakan menu Import di atas untuk memasukkan data dari Google Sheets.")
    else:
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search_pelanggan = st.text_input("🔍 Cari Pelanggan (Ketik nama seperti: Indomarco, Siak, dll)", placeholder="Ketik nama pelanggan untuk memfilter tabel...")
        with col_f2:
            filter_status = st.selectbox("📂 Filter Status", ["Semua Project", "On Progress", "Selesai"])

        df_tampil = df_project.copy()
        if search_pelanggan:
            df_tampil = df_tampil[df_tampil['pelanggan'].str.contains(search_pelanggan, case=False, na=False)]
        
        if filter_status == "Selesai":
            df_tampil = df_tampil[df_tampil['status_akhir'] == 'Selesai']
        elif filter_status == "On Progress":
            df_tampil = df_tampil[df_tampil['status_akhir'] != 'Selesai']

        st.dataframe(
            df_tampil[['id_project', 'pelanggan', 'alamat', 'layanan', 'rekanan', 'status_akhir', 'tanggal_selesai', 'kendala_bai']], 
            use_container_width=True, hide_index=True
        )

        st.markdown("---")
        st.write("⚡ **Quick Copy ID Project:** Pilih project dari daftar di bawah, lalu klik ikon **Copy** 📋 di pojok kanan kotak hitam!")
        
        col_copy1, col_copy2 = st.columns([2, 1])
        list_tampil_copy = [f"{row['id_project']} - {row['pelanggan']}" for _, row in df_tampil.iterrows()]
        
        if list_tampil_copy:
            with col_copy1:
                pilih_copy = st.selectbox("Pilih Project", list_tampil_copy, label_visibility="collapsed")
                id_copy = pilih_copy.split(" - ")[0]
            with col_copy2:
                st.code(id_copy, language="text")
        else:
            st.info("Tidak ada data yang tersedia untuk disalin.")
        
        st.markdown("---")
        col_ex1, col_ex2 = st.columns([1, 2])
        with col_ex1:
            csv_data = df_tampil.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download Laporan ({filter_status})",
                data=csv_data,
                file_name=f"Laporan_{filter_status}_{date.today()}.csv",
                mime="text/csv", use_container_width=True
            )
        
        st.markdown("---")
        with st.expander("🗑️ Hapus Project / Tiket (Salah Input)"):
            with st.form("form_hapus_ptl"):
                col_del1, col_del2 = st.columns([3, 1])
                list_hapus_ptl = [f"{row['id_project']} - {row['pelanggan']}" for idx, row in df_project.iterrows()]
                pilih_hapus_ptl = col_del1.selectbox("Pilih Project", list_hapus_ptl)
                if col_del2.form_submit_button("Hapus Tiket"):
                    hapus_project(pilih_hapus_ptl.split(" - ")[0])
                    st.success("✅ Tiket berhasil dihapus!")
                    st.rerun()

# ==========================================
# HALAMAN: 1. DISPOSISI REKANAN
# ==========================================
elif menu == "📝 1. Disposisi Rekanan":
    st.title("Disposisi Project ke Rekanan")
    list_rekanan = get_list_rekanan()
    if not list_rekanan:
        st.warning("⚠️ Daftar Mitra kosong. Login sebagai Super Admin untuk menambahkan.")
    else:
        with st.form("form_disposisi", clear_on_submit=True):
            col1, col2 = st.columns(2)
            id_proj = col1.text_input("ID Project / Ticket")
            pelanggan = col2.text_input("Nama Pelanggan")
            alamat = st.text_area("Alamat Lengkap Pelanggan")
            col3, col4 = st.columns(2)
            layanan = col3.text_input("Layanan / Service")
            rekanan_pilihan = col4.selectbox("Pilih Mitra Rekanan", list_rekanan)
            tanggal_hari_ini = st.date_input("Tanggal Disposisi", value=date.today())
            if st.form_submit_button("Simpan & Disposisi", use_container_width=True):
                if id_proj and pelanggan and alamat and layanan:
                    if insert_project_baru(id_proj, pelanggan, alamat, layanan, rekanan_pilihan, str(tanggal_hari_ini)):
                        st.success(f"Project '{id_proj}' berhasil didisposisi!")
                        st.balloons()
                    else:
                        st.error("ID Project sudah ada!")
                else:
                    st.error("Lengkapi semua data!")

# ==========================================
# HALAMAN: 2. SURVEY DETAIL & RAB
# ==========================================
elif menu == "🔍 2. Survey Detail & RAB":
    st.title("Update Survey Detail & RAB")
    df_project = load_data_project()
    if df_project.empty:
        st.info("Belum ada tiket project.")
    else:
        dict_project = {f"{row['id_project']} - {row['pelanggan']}": row['id_project'] for idx, row in df_project.iterrows()}
        pilih_id = dict_project[st.selectbox("Pilih Project", list(dict_project.keys()))]
        data_terpilih = df_project[df_project['id_project'] == pilih_id].iloc[0]
        
        st.info(f"**Layanan:** {data_terpilih['layanan']} | **Mitra:** {data_terpilih['rekanan']}")
        
        with st.form("form_survey"):
            status_surv = st.selectbox("Status Survey", ["Belum", "On Progress", "Terkendala", "Selesai"])
            col1, col2 = st.columns(2)
            material = col1.text_area("Daftar Material", value=data_terpilih['kebutuhan_material'] if data_terpilih['kebutuhan_material'] != '-' else "")
            estimasi = col2.number_input("Estimasi Kabel (Meter)", min_value=0, value=int(data_terpilih['estimasi_kabel']) if str(data_terpilih['estimasi_kabel']).isdigit() else 0)
            catatan = col2.text_area("Catatan Survey", value=data_terpilih['catatan_survey'] if data_terpilih['catatan_survey'] != '-' else "")
            if st.form_submit_button("Update Data Survey", use_container_width=True):
                update_survey_rab(pilih_id, status_surv, material, str(estimasi), catatan)
                st.success("✅ Data Survey berhasil disimpan!")

# ==========================================
# HALAMAN: 3. PENARIKAN KABEL
# ==========================================
elif menu == "🧵 3. Penarikan Kabel":
    st.title("Update Progres Penarikan Kabel")
    df_project = load_data_project()
    if df_project.empty:
        st.info("Belum ada tiket project.")
    else:
        dict_project = {f"{row['id_project']} - {row['pelanggan']}": row['id_project'] for idx, row in df_project.iterrows()}
        pilih_id = dict_project[st.selectbox("Pilih Project", list(dict_project.keys()))]
        data_terpilih = df_project[df_project['id_project'] == pilih_id].iloc[0]
        
        est = int(data_terpilih['estimasi_kabel']) if str(data_terpilih['estimasi_kabel']).isdigit() else 1
        skrg = int(data_terpilih['kabel_tertarik'])
        persen = int((skrg / est) * 100) if est > 0 else 0
        
        st.metric("Progres Penarikan", f"{skrg} / {est} Meter", f"{persen}%")
        st.progress(min(persen, 100) / 100)
        
        with st.form("form_penarikan"):
            input_tarikan = st.number_input("Total Kabel Terpasang (Meter)", min_value=0, value=skrg)
            catatan = st.text_area("Catatan Harian", value=data_terpilih['catatan_penarikan'] if data_terpilih['catatan_penarikan'] != '-' else "")
            if st.form_submit_button("Update Progres", use_container_width=True):
                new_p = int((input_tarikan / est) * 100)
                update_penarikan_kabel(pilih_id, new_p, input_tarikan, catatan)
                st.success("✅ Progres berhasil diupdate!")
                st.rerun()

# ==========================================
# HALAMAN: 4. GENERATE PRECONFIG
# ==========================================
elif menu == "⚙️ 4. Generate Preconfig":
    st.title("⚙️ Generate Preconfig & Update Tiket")
    
    # Membuat 2 Tab Bersebelahan
    tab_preconfig, tab_update4 = st.tabs(["🛠️ Alat Generator Preconfig", "➡️ Update Status Tiket"])

    with tab_preconfig:
        st.subheader("Auto-Generator Preconfig Switch")
        st.markdown("Portal otomatisasi *script* konfigurasi perangkat distribusi agar lebih *sat-set* dan bebas *typo*.")
        
        tipe_switch = st.selectbox(
            "Pilih Vendor Perangkat (Switch)", 
            ["Raisecom (Lama)", "Raisecom ISCOM2600-12G-AC", "BDCOM", "Fiberhome", "Huawei S2700", "H3C"]
        )
        ada_mikrotik = st.radio("Apakah ada perangkat Mikrotik Pelanggan setelah Switch ini?", ["Tidak", "Ya"], horizontal=True)

        st.markdown("---")

        if tipe_switch == "Raisecom (Lama)":
            with st.form("form_raisecom"):
                hostname = st.text_input("Hostname", placeholder="Contoh: SBT-INDOMARCO.TGPN-ISCOM2600-CPE-01")
                col1, col2, col3 = st.columns(3)
                vlan_nms = col1.text_input("VLAN NMS", placeholder="Contoh: 13")
                vlan_service = col2.text_input("VLAN Service", placeholder="Contoh: 2807")
                desc_vlan_service = col3.text_input("Deskripsi VLAN Service", placeholder="Contoh: INET.BB")
                col4, col5 = st.columns(2)
                ip_vlan_nms = col4.text_input("IP Address VLAN NMS", placeholder="Contoh: 172.28.189.126/30")
                ip_route_static = col5.text_input("IP Route Static", placeholder="Contoh: 172.28.189.125")
                st.markdown("**Deskripsi Interface**")
                desc_ge1 = st.text_input("Deskripsi ge 1/0/1 (Arah Pelanggan)", placeholder="Contoh: 221405000035 IBBC PT Indomarco")
                desc_ge2 = ""
                if ada_mikrotik == "Ya":
                    desc_ge2 = st.text_input("Deskripsi ge 1/0/2 (Trunk ke Mikrotik)", placeholder="Contoh: Trunk to Mikrotik Pelanggan")
                desc_ge9 = st.text_input("Deskripsi ge 1/0/9 (Arah POP / Trunk Uplink)", placeholder="Contoh: trunk to pop SBT-GI.RENGAT")
                submit_raisecom = st.form_submit_button("🔧 Generate Script Raisecom Lama", use_container_width=True)

            if submit_raisecom:
                if not (hostname and vlan_nms and vlan_service and desc_vlan_service and ip_vlan_nms and ip_route_static and desc_ge1 and desc_ge9):
                    st.error("Semua parameter wajib diisi!")
                elif ada_mikrotik == "Ya" and not desc_ge2:
                    st.error("Deskripsi ge 1/0/2 wajib diisi karena menggunakan Mikrotik!")
                else:
                    script = f"config\nhostname {hostname}\n"
                    script += f"vlan {vlan_nms}\ndescription NMS\nexit\n"
                    script += f"vlan {vlan_service}\ndescription {desc_vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"vlan 1132\ndescription nms.ms\nexit\n"
                    script += f"interface vlan {vlan_nms}\nip address {ip_vlan_nms}\nexit\n"
                    script += f"ip route-static 0.0.0.0 0.0.0.0 {ip_route_static}\n"
                    script += f"username plniconplussumbagteng password plain ic0nplusSumbagt3ng group administrators\n"
                    script += f"int ge 1/0/1\ndescription {desc_ge1}\nport link-type access\nport default vlan {vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"int ge 1/0/2\ndescription {desc_ge2}\nport link-type trunk\nport trunk allow-pass vlan {vlan_nms},{vlan_service},1132\nexit\n"
                        vlan_trunk_pop = f"{vlan_nms},{vlan_service},1132"
                    else:
                        vlan_trunk_pop = f"{vlan_nms},{vlan_service}"
                    script += f"int ge 1/0/9\ndescription {desc_ge9}\nport link-type trunk\nport trunk allow-pass vlan {vlan_trunk_pop}\nexit\n"
                    script += f"save running-config"

                    st.session_state['script_aktif'] = script
                    st.session_state['file_aktif'] = f"Preconfig_Raisecom_Lama_{hostname}.txt"
                    st.session_state['vendor_aktif'] = "Raisecom Lama"

        elif tipe_switch == "Raisecom ISCOM2600-12G-AC":
            with st.form("form_raisecom_baru"):
                hostname = st.text_input("Hostname", placeholder="Contoh: SBT-INDOMARCO.TI6Z.SUKARNOHATTA-ISCOM2600-CPE-01")
                col1, col2, col3 = st.columns(3)
                vlan_nms = col1.text_input("VLAN NMS", placeholder="Contoh: 13")
                vlan_service = col2.text_input("VLAN Service", placeholder="Contoh: 2882")
                desc_vlan_service = col3.text_input("Nama VLAN Service", placeholder="Contoh: IBBC")
                col4, col5 = st.columns(2)
                ip_vlan_nms = col4.text_input("IP Address & Mask VLAN NMS", placeholder="Contoh: 172.31.99.254 255.255.255.252")
                ip_route_static = col5.text_input("IP Route Static (Gateway)", placeholder="Contoh: 172.31.99.253")
                st.markdown("**Deskripsi Interface**")
                desc_ge1 = st.text_input("Deskripsi gi 1/1/1 (Arah Pelanggan)", placeholder="Contoh: 111405003855 IBBC Indomarco TI6Z")
                desc_ge2 = ""
                if ada_mikrotik == "Ya":
                    desc_ge2 = st.text_input("Deskripsi gi 1/1/2 (Trunk ke Mikrotik)", placeholder="Contoh: Trunk to Mikrotik Pelanggan")
                desc_ge9 = st.text_input("Deskripsi gi 1/1/9 (Arah POP / Trunk Uplink)", placeholder="Contoh: trunk to PoP SBT-ICON-PEKANBARU...")
                submit_raisecom_baru = st.form_submit_button("🔧 Generate Script Raisecom ISCOM2600", use_container_width=True)

            if submit_raisecom_baru:
                if not (hostname and vlan_nms and vlan_service and desc_vlan_service and ip_vlan_nms and ip_route_static and desc_ge1 and desc_ge9):
                    st.error("Semua parameter wajib diisi!")
                elif ada_mikrotik == "Ya" and not desc_ge2:
                    st.error("Deskripsi gi 1/1/2 wajib diisi karena menggunakan Mikrotik!")
                else:
                    script = f"user name plniconplussumbagteng password cipher $@!!b739611ce027cc159db8746a69630bff confirm\n"
                    script += f"hostname {hostname}\nconfig\n"
                    script += f"vlan {vlan_nms}\nname nms\nexit\n"
                    script += f"vlan {vlan_service}\nname {desc_vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"vlan 1132\nname nms.ms\nexit\n"
                    script += f"interface vlan {vlan_nms}\nip address {ip_vlan_nms}\nexit\n"
                    script += f"ip route 0.0.0.0 0.0.0.0 {ip_route_static}\n"
                    script += f"interface gi 1/1/1 \ndescription \"{desc_ge1}\"\nswitchport mode access\nswitchport access vlan {vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"interface gi 1/1/2\ndescription \"{desc_ge2}\"\nswitchport mode trunk\nswitchport trunk allowed vlan {vlan_nms},{vlan_service},1132 confirm\nexit\n"
                        vlan_trunk_pop = f"{vlan_nms},{vlan_service},1132"
                    else:
                        vlan_trunk_pop = f"{vlan_nms},{vlan_service}"
                    script += f"interface gi 1/1/9\ndescription \"{desc_ge9}\"\nswitchport trunk allowed vlan {vlan_trunk_pop} confirm\nswitchport mode trunk\nexit\n"
                    script += f"write\n"

                    st.session_state['script_aktif'] = script
                    st.session_state['file_aktif'] = f"Preconfig_Raisecom_12G_AC_{hostname}.txt"
                    st.session_state['vendor_aktif'] = "Raisecom ISCOM2600-12G-AC"

        elif tipe_switch == "BDCOM":
            with st.form("form_bdcom"):
                hostname = st.text_input("Hostname", placeholder="Contoh: SBT-INTERNETKU-BD.S2510-CPE-01")
                col1, col2, col3 = st.columns(3)
                vlan_nms = col1.text_input("VLAN NMS", placeholder="Contoh: 13")
                vlan_service = col2.text_input("VLAN Service", placeholder="Contoh: 2810")
                desc_vlan_service = col3.text_input("Deskripsi VLAN Service", placeholder="Contoh: INET.BB")
                col4, col5 = st.columns(2)
                ip_vlan_nms = col4.text_input("IP Address VLAN NMS & Mask", placeholder="Contoh: 172.28.164.44 255.255.255.248")
                ip_route_default = col5.text_input("IP Route Default", placeholder="Contoh: 172.28.164.41")
                st.markdown("**Deskripsi Interface**")
                desc_ge1 = st.text_input("Deskripsi gigaEthernet 0/1 (Arah Pelanggan)", placeholder="Contoh: 04000331490 IBBC Internetku")
                desc_ge2 = ""
                if ada_mikrotik == "Ya":
                    desc_ge2 = st.text_input("Deskripsi gigaEthernet 0/2 (Trunk ke Mikrotik)", placeholder="Contoh: Trunk to Mikrotik")
                desc_ge9 = st.text_input("Deskripsi gigaEthernet 0/9 (Arah POP / Trunk Uplink)", placeholder="Contoh: trunk to SBT-PASIR.PANGARAIAN")
                submit_bdcom = st.form_submit_button("🔧 Generate Script BDCOM", use_container_width=True)

            if submit_bdcom:
                if not (hostname and vlan_nms and vlan_service and desc_vlan_service and ip_vlan_nms and ip_route_default and desc_ge1 and desc_ge9):
                    st.error("Semua parameter wajib diisi!")
                elif ada_mikrotik == "Ya" and not desc_ge2:
                    st.error("Deskripsi gigaEthernet 0/2 wajib diisi karena menggunakan Mikrotik!")
                else:
                    script = f"enable\nconfig \nhostname {hostname}\n"
                    script += f"username plniconplussumbagteng password ic0nplusSumbagt3ng\n"
                    script += f"vlan {vlan_nms}\nname NMS\nexit\n"
                    script += f"vlan {vlan_service}\nname {desc_vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"vlan 1132\nname nms.ms\nexit\n"
                    script += f"interface vlan {vlan_nms}\nip address {ip_vlan_nms}\nexit \n"
                    script += f"ip route default {ip_route_default} \n"
                    script += f"interface gigaEthernet 0/1\ndescription {desc_ge1}\nswitchport mode access\nswitchport pvid {vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"interface gigaEthernet 0/2\ndescription {desc_ge2}\nswitchport mode trunk\nexit\n"
                    script += f"interface gigaEthernet 0/9\ndescription {desc_ge9}\nswitchport mode trunk\nexit\n"
                    script += f"exit \nwrite"

                    st.session_state['script_aktif'] = script
                    st.session_state['file_aktif'] = f"Preconfig_BDCOM_{hostname}.txt"
                    st.session_state['vendor_aktif'] = "BDCOM"

        elif tipe_switch == "Fiberhome":
            with st.form("form_fiberhome"):
                hostname = st.text_input("Hostname", placeholder="Contoh: SBT-SMKN1.PERHENTIAN.RAJA-FH.S4800-CPE-01")
                col1, col2, col3 = st.columns(3)
                vlan_nms = col1.text_input("VLAN NMS", placeholder="Contoh: 13")
                vlan_service = col2.text_input("VLAN Service", placeholder="Contoh: 2809")
                desc_vlan_service = col3.text_input("Deskripsi VLAN Service", placeholder="Contoh: INET.BB")
                col4, col5 = st.columns(2)
                ip_vlan_nms = col4.text_input("IP Address VLAN NMS", placeholder="Contoh: 172.28.171.174/27")
                ip_route_static = col5.text_input("IP Route Static / Gateway", placeholder="Contoh: 172.28.171.161")
                st.markdown("**Deskripsi (Alias) Interface**")
                desc_ge1 = st.text_input("Alias gi 1/0/1 (Arah Pelanggan)", placeholder="Contoh: 221401001435 IBBC SMKN 1")
                desc_ge2 = ""
                if ada_mikrotik == "Ya":
                    desc_ge2 = st.text_input("Alias gi 1/0/2 (Trunk ke Mikrotik)", placeholder="Contoh: Trunk to Mikrotik")
                desc_ge9 = st.text_input("Alias gi 1/0/9 (Arah POP / Trunk Uplink)", placeholder="Contoh: SBT-PLN.RAYONSIMPANGTIGA Port9")
                submit_fiberhome = st.form_submit_button("🔧 Generate Script Fiberhome", use_container_width=True)

            if submit_fiberhome:
                if not (hostname and vlan_nms and vlan_service and desc_vlan_service and ip_vlan_nms and ip_route_static and desc_ge1 and desc_ge9):
                    st.error("Semua parameter wajib diisi!")
                elif ada_mikrotik == "Ya" and not desc_ge2:
                    st.error("Alias gi 1/0/2 wajib diisi karena menggunakan Mikrotik!")
                else:
                    script = f"config\nhostname {hostname}\n"
                    script += f"vlan {vlan_nms}\nalias NMS\nexit\n"
                    script += f"vlan {vlan_service}\nalias {desc_vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"vlan 1132\nalias nms.ms\nexit\n"
                    script += f"interface vlan {vlan_nms}\nip address {ip_vlan_nms}\nexit\n"
                    script += f"interface gi 1/0/1\nalias \"{desc_ge1}\"\nport link-type access\nport default vlan {vlan_service}\nexit\n"
                    if ada_mikrotik == "Ya":
                        script += f"interface gi 1/0/2\nalias \"{desc_ge2}\"\nport link-type trunk\nport trunk allow-pass vlan {vlan_nms},{vlan_service},1132\nexit\n"
                        vlan_trunk_pop = f"{vlan_nms},{vlan_service},1132"
                    else:
                        vlan_trunk_pop = f"{vlan_nms},{vlan_service}"
                    script += f"interface gi 1/0/9\nalias \"{desc_ge9}\"\nport link-type trunk\nport trunk allow-pass vlan {vlan_trunk_pop}\nexit\n\n"
                    script += f"ip route-static 0.0.0.0 0.0.0.0 {ip_route_static}\n\n"
                    
                    tambahan_fiberhome = f"""end

header login "============================================================%. This system is the property of PT Indonesia Comnets Plus .%============================================================%"

username plniconplussumbagteng group administrators password ic0nplusSumbagt3ng 
aaa
 tacacs-server server1 ip-address 10.14.4.19 key iC0N-IPmpls+
 tacacs-server server2 ip-address 10.14.4.12 key iC0N-IPmpls+
 server-group grup1 tacacs-server server1
 server-group grup2 tacacs-server server2
 aaa authentication login method auten1 server-group grup1 local 
 aaa authentication login method auten2 server-group grup2 local 
 aaa authorization method otorisasi1 server-group grup1
 aaa authorization method otorisasi2 server-group grup2
 aaa account login method akunt1 server-group grup1
 aaa account login method akunt2 server-group grup2

line console 1
 timeout 5 0
line vty 1 5
 timeout 5 0
 login authentication aaa method auten1 
 login account aaa method akunt1
 login authorization aaa method otorisasi1
ntp
 ntp unicast-server 10.14.4.2
 ntp unicast-server 10.14.4.23

snmp version all
snmp location {hostname}
snmp community IPMPLS-ICON+ rw
snmp trap-server 10.14.3.12 IPMPLS-ICON+ v2 

syslog server 10.14.4.15

sshd
exit
wr file
y"""
                    script += tambahan_fiberhome

                    st.session_state['script_aktif'] = script
                    st.session_state['file_aktif'] = f"Preconfig_Fiberhome_{hostname}.txt"
                    st.session_state['vendor_aktif'] = "Fiberhome"

        elif tipe_switch == "Huawei S2700":
            with st.form("form_huawei"):
                hostname = st.text_input("Hostname", placeholder="Contoh: SBT-INDOMARCO.T54O-HUAWEI.S2700-CPE-01")
                col1, col2, col3 = st.columns(3)
                vlan_nms = col1.text_input("VLAN NMS", placeholder="Contoh: 13")
                vlan_service = col2.text_input("VLAN Service", placeholder="Contoh: 2807")
                desc_vlan_service = col3.text_input("Deskripsi VLAN Service", placeholder="Contoh: IBBC")
                col4, col5 = st.columns(2)
                ip_vlan_nms = col4.text_input("IP Address & Mask VLAN NMS", placeholder="Contoh: 172.28.184.251 255.255.255.248")
                ip_route_static = col5.text_input("IP Route Static (Gateway)", placeholder="Contoh: 172.28.184.249")
                st.markdown("**Deskripsi Interface**")
                desc_e1 = st.text_input("Deskripsi Ethernet 0/0/1 (Arah Pelanggan)", placeholder="Contoh: 221405000034 ICL Indomarco")
                desc_e2 = ""
                if ada_mikrotik == "Ya":
                    desc_e2 = st.text_input("Deskripsi Ethernet 0/0/2 (Trunk ke Mikrotik)", placeholder="Contoh: Trunk to Mikrotik")
                desc_ge1 = st.text_input("Deskripsi GigabitEthernet 0/0/1 (Arah POP / Trunk Uplink)", placeholder="Contoh: trunk to SBT-ULP.BANGKINANG...")
                submit_huawei = st.form_submit_button("🔧 Generate Script Huawei S2700", use_container_width=True)

            if submit_huawei:
                if not (hostname and vlan_nms and vlan_service and desc_vlan_service and ip_vlan_nms and ip_route_static and desc_e1 and desc_ge1):
                    st.error("Semua parameter wajib diisi!")
                elif ada_mikrotik == "Ya" and not desc_e2:
                    st.error("Deskripsi Ethernet 0/0/2 wajib diisi karena menggunakan Mikrotik!")
                else:
                    script = f"system-view\n"
                    script += f"sysname {hostname}\n"
                    script += f"vlan {vlan_nms}\ndescription NMS\nquit\n"
                    script += f"vlan {vlan_service}\ndescription {desc_vlan_service}\nquit\n"
                    if ada_mikrotik == "Ya":
                        script += f"vlan 1132\ndescription nms.ms\nquit\n"
                    script += f"int vlanif {vlan_nms}\n"
                    script += f"ip address {ip_vlan_nms}\n"
                    script += f"undo shutdown\nquit\n"
                    script += f"ip route-static 0.0.0.0 0.0.0.0 {ip_route_static}\n"
                    script += f"interface Ethernet 0/0/1\n"
                    script += f"description {desc_e1}\n"
                    script += f"port link-type access\n"
                    script += f"port default vlan {vlan_service}\nquit\n"
                    if ada_mikrotik == "Ya":
                        script += f"interface Ethernet 0/0/2\n"
                        script += f"description {desc_e2}\n"
                        script += f"port link-type trunk\n"
                        script += f"port trunk allow-pass vlan {vlan_nms} {vlan_service} 1132\nquit\n"
                        vlan_trunk_pop = f"1 {vlan_nms} {vlan_service} 1132"
                    else:
                        vlan_trunk_pop = f"1 {vlan_nms} {vlan_service}"
                    script += f"interface GigabitEthernet 0/0/1\n"
                    script += f"description {desc_ge1}\n"
                    script += f"port link-type trunk\n"
                    script += f"port trunk allow-pass vlan {vlan_trunk_pop}\nquit\n"
                    script += f"aaa\nlocal-user j2m password cipher multimedia123\n"
                    script += f"local-user j2m privilege level 15\n"
                    script += f"local-user j2m service-type telnet ssh\nquit\n\n"
                    script += f"user-interface vty 0 4\n"
                    script += f" authentication-mode aaa\n"
                    script += f" user privilege level 15\n"
                    script += f" idle-timeout 30 0\n"

                    st.session_state['script_aktif'] = script
                    st.session_state['file_aktif'] = f"Preconfig_Huawei_{hostname}.txt"
                    st.session_state['vendor_aktif'] = "Huawei"

        elif tipe_switch == "H3C":
            with st.form("form_h3c"):
                hostname = st.text_input("Hostname", placeholder="Contoh: SBT-KLINIK.RS.SEMEN.PADANG-H3C-CPE-01")
                col1, col2, col3 = st.columns(3)
                vlan_nms = col1.text_input("VLAN NMS", placeholder="Contoh: 13")
                vlan_service = col2.text_input("VLAN Service", placeholder="Contoh: 2810")
                desc_vlan_service = col3.text_input("Deskripsi VLAN Service", placeholder="Contoh: METRO")
                col4, col5 = st.columns(2)
                ip_vlan_nms = col4.text_input("IP Address & Mask VLAN NMS", placeholder="Contoh: 172.28.163.69 255.255.255.224")
                ip_route_static = col5.text_input("IP Route Static (Gateway)", placeholder="Contoh: 172.28.163.65")
                st.markdown("**Deskripsi Interface**")
                desc_ge5 = st.text_input("Deskripsi GigabitEthernet1/0/5 (Arah Pelanggan)", placeholder="Contoh: IBBC Klinik RS Semen Padang")
                desc_ge6 = ""
                if ada_mikrotik == "Ya":
                    desc_ge6 = st.text_input("Deskripsi GigabitEthernet1/0/6 (Trunk ke Mikrotik)", placeholder="Contoh: Trunk to Mikrotik")
                desc_ge9 = st.text_input("Deskripsi GigabitEthernet1/0/9 (Arah POP / Trunk Uplink)", placeholder="Contoh: Trunk to SBT-PLN.RKR.ULP...")
                submit_h3c = st.form_submit_button("🔧 Generate Script H3C", use_container_width=True)

            if submit_h3c:
                if not (hostname and vlan_nms and vlan_service and desc_vlan_service and ip_vlan_nms and ip_route_static and desc_ge5 and desc_ge9):
                    st.error("Semua parameter wajib diisi!")
                elif ada_mikrotik == "Ya" and not desc_ge6:
                    st.error("Deskripsi GigabitEthernet1/0/6 wajib diisi karena menggunakan Mikrotik!")
                else:
                    script = f"system-view\n"
                    script += f"sysname {hostname}\n#\n"
                    script += f"vlan 1\n#\n"
                    script += f"vlan {vlan_nms}\n name NMS\n#\n"
                    script += f"vlan {vlan_service}\n name {desc_vlan_service}\n#\n"
                    if ada_mikrotik == "Ya":
                        script += f"vlan 1132\n name nms.ms\n#\n"
                    script += f"interface Vlan-interface{vlan_nms}\n"
                    script += f" ip address {ip_vlan_nms}\n#\n"
                    script += f"interface GigabitEthernet1/0/5\n"
                    script += f" description {desc_ge5}\n"
                    script += f" port link-type access\n"
                    script += f" port access vlan {vlan_service}\n#\n"
                    if ada_mikrotik == "Ya":
                        script += f"interface GigabitEthernet1/0/6\n"
                        script += f" description {desc_ge6}\n"
                        script += f" port link-type trunk\n"
                        script += f" port trunk permit vlan 1 {vlan_nms} {vlan_service} 1132\n#\n"
                        vlan_trunk_pop = f"1 {vlan_nms} {vlan_service} 1132"
                    else:
                        vlan_trunk_pop = f"1 {vlan_nms} {vlan_service}"
                    script += f"interface GigabitEthernet1/0/9\n"
                    script += f" description {desc_ge9}\n"
                    script += f" port link-type trunk\n"
                    script += f" port trunk permit vlan {vlan_trunk_pop}\n#\n"
                    script += f"ip route-static 0.0.0.0 0 {ip_route_static}\n#\n"
                    
                    tambahan_h3c = """telnet server enable
#
 irf mac-address persistent timer
 irf auto-update enable
 undo irf link-delay
 irf member 1 priority 1
#
 lldp global enable
#
 password-recovery enable
#
 stp global enable
#
line class aux
 user-role network-admin
#
line class vty
 user-role network-operator
#
line aux 0
 user-role network-admin
#
line vty 0 4
 authentication-mode scheme
 user-role network-admin
 user-role network-operator
#
line vty 5 63
 user-role network-operator
#
radius scheme system
 user-name-format without-domain
#
domain system
#
 domain default enable system
#
user-group system
#
local-user j2m class manage
 password hash $h$6$qCbH5KEAFHjIk85L$OLqloKuHN0clUKgrVZOG8bAJTS0iM3pqwirAPfsn3A5HWCCYLzEOhn6kVwgOQkpRXemPC2slULYslik6oygDpg==
 service-type telnet
 authorization-attribute user-role network-admin
 authorization-attribute user-role network-operator
#
return"""
                    script += tambahan_h3c

                    st.session_state['script_aktif'] = script
                    st.session_state['file_aktif'] = f"Preconfig_H3C_{hostname}.txt"
                    st.session_state['vendor_aktif'] = "H3C"

        if st.session_state.get('vendor_aktif') in ["Raisecom Lama", "Raisecom ISCOM2600-12G-AC", "BDCOM", "Fiberhome", "Huawei", "H3C"] and 'script_aktif' in st.session_state:
            st.success("✅ Script berhasil di-generate! Silakan copy kode di bawah ini:")
            st.code(st.session_state['script_aktif'], language='bash')
            st.download_button(
                label="📥 Download Preconfig (.txt)",
                data=st.session_state['script_aktif'],
                file_name=st.session_state['file_aktif'],
                mime="text/plain",
                use_container_width=True
            )

    with tab_update4:
        st.subheader("Lanjutkan Tiket ke Tahap Selanjutnya")
        df_project = load_data_project()
        if not df_project.empty:
            dict_project = {f"{row['id_project']} - {row['pelanggan']}": row['id_project'] for idx, row in df_project.iterrows()}
            pilih_id = dict_project[st.selectbox("Pilih Project", list(dict_project.keys()), key="proj_preconfig")]
            if st.button("Lanjutkan Tiket ke Tahap Validasi BAI", use_container_width=True):
                update_status_preconfig(pilih_id)
                st.success("✅ Status tiket dipindahkan ke Menu 5.")

# ==========================================
# HALAMAN: 5. STATUS PENYELESAIAN (BAI)
# ==========================================
elif menu == "📁 5. Status Penyelesaian (BAI)":
    st.title("📁 Validasi & Pembuatan Dokumen BAI")
    
    # Membuat 2 Tab Bersebelahan
    tab_bai, tab_update5 = st.tabs(["📝 Alat Generator BAI", "✅ Tutup Tiket Project"])

    with tab_bai:
        st.subheader("Generator BAI Icon+")
        tipe_bai = st.radio("Pilih Mode Dokumen:", ["Individu (1 Lokasi)", "Terlampir (Banyak Lokasi / Massal)"], horizontal=True)
        st.markdown("---")

        if tipe_bai == "Individu (1 Lokasi)":
            with st.form("form_individu"):
                st.subheader("📝 Form BAI Individu")
                col1, col2 = st.columns(2)
                with col1:
                    no_pa = st.text_input("Nomor PA", placeholder="Contoh: A221401007204")
                    nama_layanan_header = st.text_input("Jenis Layanan", placeholder="Contoh: INTERNET BROADBAND CORPORATE")
                    sid_layanan = st.text_input("SID / ID Layanan (Opsional)")
                with col2:
                    tgl_input = st.date_input("Pilih Tanggal Instalasi / Generate", value=datetime.date.today())
                
                col3, col4 = st.columns(2)
                with col3:
                    nama_pelanggan = st.text_input("Nama Pelanggan", placeholder="Contoh: BUMDES KEMBANG KENANGA")
                    koordinat_pelanggan = st.text_input("Titik Koordinat Pelanggan")
                with col4:
                    alamat_pelanggan = st.text_area("Alamat Lengkap Pelanggan")

                col5, col6 = st.columns(2)
                with col5:
                    perangkat_pelanggan = st.text_input("Nama Perangkat (Pelanggan)")
                    port_pelanggan = st.text_input("Kanal Port (Pelanggan)")
                with col6:
                    lokasi_pop = st.text_input("Alamat/Lokasi POP")
                    perangkat_pop = st.text_input("Nama Perangkat & SN (POP)")
                    port_pop = st.text_input("Kanal / Port (POP)")

                btn_generate_individu = st.form_submit_button("🚀 Generate BAI Individu (Word)", use_container_width=True)

            if btn_generate_individu:
                if not (no_pa and nama_pelanggan and nama_layanan_header):
                    st.error("⚠️ Mohon lengkapi minimal Nomor PA, Jenis Layanan, dan Nama Pelanggan!")
                else:
                    try:
                        detail_layanan = f"{nama_layanan_header} ({sid_layanan})" if sid_layanan else nama_layanan_header
                        hari_ini = HARI[tgl_input.weekday()]
                        bulan_teks = BULAN[tgl_input.month]
                        
                        data_mapping = {
                            'tanggal_generate': tgl_input.strftime(f"%B %d, %Y"),
                            'nama_layanan_header': nama_layanan_header,
                            'no_pa': no_pa,
                            'hari_ini': hari_ini,
                            'tgl_terbilang': terbilang(tgl_input.day),
                            'bulan_teks': bulan_teks,
                            'tahun_terbilang': terbilang(tgl_input.year),
                            'detail_layanan': detail_layanan,
                            'nama_pelanggan': nama_pelanggan,
                            'alamat_pelanggan': alamat_pelanggan,
                            'koordinat_pelanggan': koordinat_pelanggan,
                            'perangkat_pelanggan': perangkat_pelanggan,
                            'port_pelanggan': port_pelanggan,
                            'lokasi_pop': lokasi_pop,
                            'perangkat_pop': perangkat_pop,
                            'port_pop': port_pop,
                            'tanggal_ttd': f"{tgl_input.day} {bulan_teks} {tgl_input.year}"
                        }

                        doc = DocxTemplate("template_bai.docx")
                        doc.render(data_mapping)
                        file_buffer = io.BytesIO()
                        doc.save(file_buffer)
                        file_buffer.seek(0)
                        
                        st.success(f"✅ Dokumen berhasil digenerate!")
                        st.download_button(
                            label="📥 Download File BAI Individu (.docx)",
                            data=file_buffer,
                            file_name=f"BAI_{nama_pelanggan}_{no_pa}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            type="primary", use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"❌ Error: {e}. Pastikan file 'template_bai.docx' tersedia.")

        elif tipe_bai == "Terlampir (Banyak Lokasi / Massal)":
            st.subheader("📑 Form BAI Massal (Dengan Lampiran)")
            
            col_a, col_b = st.columns(2)
            with col_a:
                nama_instansi = st.text_input("Nama Pelanggan (Instansi Induk)", placeholder="Contoh: PT. PLN (PERSERO)")
            with col_b:
                tgl_massal = st.date_input("Pilih Tanggal Instalasi / Generate", key="tgl_massal")

            st.markdown("**Paste Data dari Excel ke Tabel di Bawah Ini:**")
            
            df_kosong = pd.DataFrame(columns=["ID PA", "Layanan", "SID", "SN Perangkat", "Alamat / Tanggal"])
            tabel_input = st.data_editor(df_kosong, num_rows="dynamic", use_container_width=True)

            btn_generate_massal = st.button("🚀 Generate BAI Terlampir (Word)", use_container_width=True, type="primary")

            if btn_generate_massal:
                if not nama_instansi or tabel_input.empty:
                    st.error("⚠️ Nama Instansi wajib diisi dan tabel tidak boleh kosong!")
                else:
                    try:
                        hari_ini = HARI[tgl_massal.weekday()]
                        bulan_teks = BULAN[tgl_massal.month]
                        
                        data_mapping_massal = {
                            'tanggal_generate': tgl_massal.strftime(f"%B %d, %Y"),
                            'nama_pelanggan': nama_instansi,
                            'hari_ini': hari_ini,
                            'tgl_terbilang': terbilang(tgl_massal.day),
                            'bulan_teks': bulan_teks,
                            'tahun_terbilang': terbilang(tgl_massal.year),
                            'tanggal_ttd': f"{tgl_massal.day} {bulan_teks} {tgl_massal.year}"
                        }

                        doc_massal = DocxTemplate("template_bai_lampiran.docx")
                        doc_massal.render(data_mapping_massal)
                        
                        tabel_target = doc_massal.docx.tables[-1] 
                        
                        for index, row in tabel_input.iterrows():
                            if pd.notna(row['ID PA']): 
                                row_cells = tabel_target.add_row().cells
                                row_cells[0].text = str(index + 1)
                                row_cells[1].text = str(row['ID PA'])
                                row_cells[2].text = str(row['Layanan'])
                                row_cells[3].text = str(row['SID'])
                                row_cells[4].text = str(row['SN Perangkat'])
                                row_cells[5].text = str(row['Alamat / Tanggal'])
                        
                        file_buffer_massal = io.BytesIO()
                        doc_massal.save(file_buffer_massal)
                        file_buffer_massal.seek(0)
                        
                        st.success(f"✅ Dokumen berhasil digenerate dengan {len(tabel_input)} lokasi!")
                        st.download_button(
                            label="📥 Download File BAI Terlampir (.docx)",
                            data=file_buffer_massal,
                            file_name=f"BAI_Massal_{nama_instansi}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            type="primary", use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"❌ Error: {e}. Pastikan file Word benar dan tabel lampiran berada di posisi paling bawah.")

    with tab_update5:
        st.subheader("Validasi & Pencarian Tiket BAI")
        st.markdown("Cari tiket berdasarkan ID atau Nama Pelanggan untuk memproses penyelesaian.")
        
        df_project = load_data_project()
        df_pending = df_project[df_project['status_akhir'] != 'Selesai']
        
        if df_pending.empty:
            st.success("🎉 Luar biasa! Saat ini tidak ada tiket yang menggantung.")
        else:
            search_query = st.text_input("🔎 Cari Tiket (Ketik ID atau Nama Pelanggan)", placeholder="Contoh: A821... atau Indomarco")
            list_all = [f"{row['id_project']} - {row['pelanggan']}" for _, row in df_pending.iterrows()]
            list_filtered = [item for item in list_all if search_query.lower() in item.lower()] if search_query else list_all

            if not list_filtered:
                st.warning("⚠️ Tiket tidak ditemukan di daftar On Progress.")
            else:
                pilih_str = st.selectbox(f"Ditemukan {len(list_filtered)} Tiket. Silakan pilih:", list_filtered)
                pilih_id = pilih_str.split(" - ")[0]
                data_terpilih = df_pending[df_pending['id_project'] == pilih_id].iloc[0]
                
                st.info(f"📍 **Alamat:** {data_terpilih['alamat']} | 🏢 **Mitra:** {data_terpilih['rekanan']} | 📌 **Status:** {data_terpilih['status_akhir']}")
                
                status_pekerjaan = st.radio(
                    "Apakah dokumen BAI sudah ditandatangani dan pekerjaan selesai?", 
                    ["Pilih Status...", "✅ Sudah Selesai (On-Air & BAI)", "⚠️ Belum Selesai (Ada Kendala)"], horizontal=True
                )
                st.markdown("---")
                if status_pekerjaan == "✅ Sudah Selesai (On-Air & BAI)":
                    tgl_selesai = st.date_input("📅 Pilih Tanggal Selesai", value=date.today())
                    if st.button("Simpan & Selesaikan Project", use_container_width=True):
                        update_status_bai(pilih_id, 'Selesai', tgl_selesai, '-')
                        st.balloons()
                        st.success(f"✅ Project {pilih_id} berhasil diselesaikan pada {tgl_selesai}!")
                        
                elif status_pekerjaan == "⚠️ Belum Selesai (Ada Kendala)":
                    val_kendala = data_terpilih.get('kendala_bai', '-')
                    kendala = st.text_area("Jelaskan Kendala", value=val_kendala if val_kendala != '-' else "", height=100)
                    if st.button("Simpan Kendala", use_container_width=True):
                        if kendala.strip() == "":
                            st.error("⚠️ Harap isi kolom kendala terlebih dahulu!")
                        else:
                            update_status_bai(pilih_id, 'Kendala', '-', kendala)
                            st.warning(f"⚠️ Kendala untuk project {pilih_id} berhasil disimpan!")
                            st.rerun()