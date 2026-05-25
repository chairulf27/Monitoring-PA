import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import date

# Konfigurasi Halaman Minimalis & Elegan
st.set_page_config(page_title="Portal Aktivasi", layout="wide", initial_sidebar_state="expanded")

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

    # --- MENU IMPORT ---
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
        # Filter Tabel Canggih & Global Search
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search_pelanggan = st.text_input("🔍 Cari Pelanggan (Ketik nama seperti: Indomarco, Siak, dll)", placeholder="Ketik nama pelanggan untuk memfilter tabel...")
        with col_f2:
            filter_status = st.selectbox("📂 Filter Status", ["Semua Project", "On Progress", "Selesai"])

        # Logika Filter Tabel
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

        # --- FITUR BARU: SAT SET COPY ID PROJECT ---
        st.markdown("---")
        st.write("⚡ **Quick Copy ID Project:** Pilih project dari daftar di bawah, lalu klik ikon **Copy** 📋 di pojok kanan kotak hitam!")
        
        col_copy1, col_copy2 = st.columns([2, 1])
        list_tampil_copy = [f"{row['id_project']} - {row['pelanggan']}" for _, row in df_tampil.iterrows()]
        
        if list_tampil_copy:
            with col_copy1:
                pilih_copy = st.selectbox("Pilih Project", list_tampil_copy, label_visibility="collapsed")
                id_copy = pilih_copy.split(" - ")[0]
            with col_copy2:
                # Menampilkan ID dalam format code block agar muncul tombol 'Copy' otomatis
                st.code(id_copy, language="text")
        else:
            st.info("Tidak ada data yang tersedia untuk disalin.")
        
        # Tombol Download
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
    st.title("Generate Preconfig Switch")
    st.info("Fitur Generate Preconfig tersedia di aplikasi Standalone.")
    df_project = load_data_project()
    if not df_project.empty:
        dict_project = {f"{row['id_project']} - {row['pelanggan']}": row['id_project'] for idx, row in df_project.iterrows()}
        pilih_id = dict_project[st.selectbox("Pilih Project", list(dict_project.keys()))]
        if st.button("Lanjutkan Tiket ke Tahap Validasi BAI", use_container_width=True):
            update_status_preconfig(pilih_id)
            st.success("✅ Status tiket dipindahkan ke Menu 5.")

# ==========================================
# HALAMAN: 5. STATUS PENYELESAIAN (BAI) DENGAN SMART SEARCH
# ==========================================
elif menu == "📁 5. Status Penyelesaian (BAI)":
    st.title("Validasi & Pencarian Tiket BAI")
    st.markdown("Cari tiket berdasarkan ID atau Nama Pelanggan untuk memproses penyelesaian.")
    
    df_project = load_data_project()
    
    # FILTER BARU: Saring hanya project yang BELUM SELESAI
    df_pending = df_project[df_project['status_akhir'] != 'Selesai']
    
    if df_pending.empty:
        st.success("🎉 Luar biasa! Saat ini tidak ada tiket yang menggantung. Semua project sudah selesai atau belum ada data baru.")
    else:
        # --- FITUR SMART SEARCH SEBELUM MEMILIH TIKET ---
        search_query = st.text_input("🔎 Cari Tiket (Ketik ID atau Nama Pelanggan)", placeholder="Contoh: A821... atau Indomarco")
        
        # Filter daftar project berdasarkan input search dari df_pending
        list_all = [f"{row['id_project']} - {row['pelanggan']}" for _, row in df_pending.iterrows()]
        if search_query:
            list_filtered = [item for item in list_all if search_query.lower() in item.lower()]
        else:
            list_filtered = list_all

        if not list_filtered:
            st.warning("⚠️ Tiket tidak ditemukan di daftar On Progress. Coba kata kunci lain atau pastikan tiket belum berstatus Selesai.")
        else:
            # User memilih dari daftar yang sudah tersaring
            pilih_str = st.selectbox(f"Ditemukan {len(list_filtered)} Tiket On Progress. Silakan pilih:", list_filtered)
            pilih_id = pilih_str.split(" - ")[0]
            data_terpilih = df_pending[df_pending['id_project'] == pilih_id].iloc[0]
            
            st.info(f"📍 **Alamat:** {data_terpilih['alamat']} | 🏢 **Mitra:** {data_terpilih['rekanan']} | 📌 **Status:** {data_terpilih['status_akhir']}")
            
            status_pekerjaan = st.radio(
                "Apakah dokumen BAI sudah ditandatangani dan pekerjaan selesai?", 
                ["Pilih Status...", "✅ Sudah Selesai (On-Air & BAI)", "⚠️ Belum Selesai (Ada Kendala)"],
                horizontal=True
            )
            
            st.markdown("---")
            
            if status_pekerjaan == "✅ Sudah Selesai (On-Air & BAI)":
                tgl_selesai = st.date_input("📅 Pilih Tanggal Selesai (Sesuai Dokumen BAI)", value=date.today())
                if st.button("Simpan & Selesaikan Project", use_container_width=True):
                    update_status_bai(pilih_id, 'Selesai', tgl_selesai, '-')
                    st.balloons()
                    st.success(f"✅ Hebat! Project {pilih_id} berhasil diselesaikan pada tanggal {tgl_selesai}. Status tiket berubah menjadi 'Selesai'!")
                    
            elif status_pekerjaan == "⚠️ Belum Selesai (Ada Kendala)":
                val_kendala = data_terpilih.get('kendala_bai', '-')
                kendala = st.text_area("Jelaskan Kendala (Contoh: Pelanggan sedang ke luar kota, belum bisa TTD)", 
                                       value=val_kendala if val_kendala != '-' else "", height=100)
                if st.button("Simpan Kendala", use_container_width=True):
                    if kendala.strip() == "":
                        st.error("⚠️ Harap isi kolom kendala terlebih dahulu!")
                    else:
                        update_status_bai(pilih_id, 'Kendala', '-', kendala)
                        st.warning(f"⚠️ Kendala untuk project {pilih_id} berhasil disimpan! Status tiket berubah menjadi 'Kendala BAI'.")
                        st.rerun()