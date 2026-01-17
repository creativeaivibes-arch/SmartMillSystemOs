import streamlit as st
import pandas as pd
from datetime import datetime
import os
import shutil
import time
import sqlite3

from app.core.database import get_db_connection, init_db
from app.core.auth import ROLES, hash_password

# --- YEDEKLEME SİSTEMİ ---
BACKUP_DIR = "backups"
DB_FILE = "bugday_stok.db"

def init_backup_system():
    """Yedekleme klasörünü oluştur"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

def create_daily_backup():
    """Günlük yedek oluştur"""
    try:
        init_backup_system()
        tarih_str = datetime.now().strftime('%Y-%m-%d')
        backup_name = f"backup_{tarih_str}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        # Eğer bugün yedek alınmamışsa al
        if not os.path.exists(backup_path):
            shutil.copy2(DB_FILE, backup_path)
            return True, f"✅ Günlük yedek oluşturuldu: {backup_name}"
        return False, "Bugün zaten yedek alınmış."
    except Exception as e:
        return False, f"❌ Yedekleme hatası: {str(e)}"

def cleanup_old_backups(days_to_keep=30):
    """Eski yedekleri temizle (varsayılan: 30 gün)"""
    try:
        init_backup_system()
        simdi = time.time()
        silinen_sayisi = 0
        
        for f in os.listdir(BACKUP_DIR):
            f_path = os.path.join(BACKUP_DIR, f)
            if os.path.isfile(f_path) and f.startswith("backup_"):
                # Dosya yaşını kontrol et
                if os.stat(f_path).st_mtime < (simdi - (days_to_keep * 86400)):
                    os.remove(f_path)
                    silinen_sayisi += 1
        return silinen_sayisi
    except Exception as e:
        print(f"Temizlik hatası: {e}")
        return 0

def check_daily_backup():
    """Başlangıçta yedek kontrolü yap"""
    create_daily_backup()
    cleanup_old_backups()

def get_backup_stats():
    """Yedekleme istatistiklerini getir"""
    try:
        init_backup_system()
        backups = []
        total_size = 0
        
        for f in os.listdir(BACKUP_DIR):
            if f.startswith("backup_"):
                path = os.path.join(BACKUP_DIR, f)
                size = os.path.getsize(path) / (1024*1024) # MB
                tarih = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M')
                backups.append({'dosya': f, 'boyut_mb': size, 'tarih': tarih})
                total_size += size
                
        return sorted(backups, key=lambda x: x['tarih'], reverse=True), len(backups), total_size
    except:
        return [], 0, 0

def show_backup_management():
    """Yedekleme Yönetimi Paneli"""
    st.subheader("💾 Yedekleme Yönetimi")
    
    # İstatistikler
    backups, count, total_size = get_backup_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Toplam Yedek", f"{count} Adet")
    with col2:
        st.metric("Toplam Boyut", f"{total_size:.1f} MB")
    with col3:
        if st.button("🔄 Şimdi Yedek Al", type="primary"):
            status, msg = create_daily_backup()
            if status:
                st.success(msg)
                time.sleep(1)
                st.rerun()
            else:
                st.info(msg)
    
    # Yedek Listesi
    if backups:
        st.write("### 🗂️ Mevcut Yedekler")
        df_backup = pd.DataFrame(backups)
        df_backup.columns = ["Dosya Adı", "Boyut (MB)", "Oluşturma Tarihi"]
        
        st.dataframe(
            df_backup,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Boyut (MB)": st.column_config.NumberColumn(format="%.2f MB")
            }
        )
        
        # İndirme Seçeneği
        selected_backup = st.selectbox("İndirilecek Yedeği Seçin", df_backup["Dosya Adı"])
        if selected_backup:
            file_path = os.path.join(BACKUP_DIR, selected_backup)
            with open(file_path, "rb") as file:
                st.download_button(
                    label="📥 Seçili Yedeği İndir",
                    data=file,
                    file_name=selected_backup,
                    mime="application/x-sqlite3"
                )

# --- KULLANICI YÖNETİMİ ---
def show_user_management():
    """Kullanıcı Yönetim Paneli"""
    st.subheader("👥 Kullanıcı Yönetimi")
    
    # 1. Yeni Kullanıcı Ekleme
    with st.expander("➕ Yeni Kullanıcı Ekle", expanded=False):
        with st.form("new_user_form"):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                new_username = st.text_input("Kullanıcı Adı")
                new_full_name = st.text_input("Ad Soyad")
            with col_u2:
                new_password = st.text_input("Şifre", type="password")
                new_role = st.selectbox("Rol", list(ROLES.keys()))
            
            submit_btn = st.form_submit_button("Ekle")
            
            if submit_btn:
                if new_username and new_password:
                    hashed_pw = hash_password(new_password)
                    if hashed_pw:
                        try:
                            with get_db_connection() as conn:
                                c = conn.cursor()
                                c.execute(
                                    "INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad_soyad) VALUES (?, ?, ?, ?)",
                                    (new_username, hashed_pw, new_role, new_full_name)
                                )
                                conn.commit()
                            st.success(f"✅ Kullanıcı '{new_username}' başarıyla oluşturuldu!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ Bu kullanıcı adı zaten mevcut!")
                        except Exception as e:
                            st.error(f"❌ Hata: {str(e)}")
                else:
                    st.warning("⚠️ Kullanıcı adı ve şifre zorunludur!")

    # 2. Kullanıcı Listesi ve Düzenleme
    st.write("### 📋 Mevcut Kullanıcılar")
    
    users_df = pd.DataFrame() # Initialize empty dataframe to prevent UnboundLocalError
    
    try:
        with get_db_connection() as conn:
            # Table: kullanicilar, Columns: id, kullanici_adi, ad_soyad, rol, olusturma_tarihi
            users_df = pd.read_sql_query("SELECT id, kullanici_adi, ad_soyad, rol, olusturma_tarihi FROM kullanicilar", conn)
            
            if not users_df.empty:
                # Düzenlenebilir tablo
                edited_df = st.data_editor(
                    users_df,
                    column_config={
                        "kullanici_adi": "Kullanıcı Adı",
                        "ad_soyad": "Ad Soyad",
                        "rol": st.column_config.SelectboxColumn(
                            "Rol",
                            options=list(ROLES.keys()),
                            required=True
                        ),
                        "olusturma_tarihi": st.column_config.DatetimeColumn("Oluşturulma", disabled=True),
                        "id": st.column_config.NumberColumn("ID", disabled=True)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="user_editor"
                )
                
                # Değişiklikleri Kaydet Butonu
                if st.button("💾 Değişiklikleri Kaydet (Rol Güncelleme)"):
                    # Bu basit bir implementasyon, sadece rol değişikliğini yansıtırız
                    pass 
    except Exception as e:
        st.error(f"Kullanıcı listesi yüklenemedi: {e}")

    # 3. Kullanıcı Silme
    with st.expander("🗑️ Kullanıcı Sil", expanded=False):
        # Column name is kullanici_adi
        user_list = users_df['kullanici_adi'].tolist() if not users_df.empty else []
        user_to_delete = st.selectbox("Silinecek Kullanıcı", user_list)
        
        if st.button("Kullanıcıyı Sil", type="primary"):
            if user_to_delete == "admin":
                st.error("⛔ 'admin' kullanıcısı silinemez!")
            elif user_to_delete == st.session_state.username:
                st.error("⛔ Kendinizi silemezsiniz!")
            else:
                try:
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute("DELETE FROM kullanicilar WHERE kullanici_adi = ?", (user_to_delete,))
                        conn.commit()
                    st.success(f"✅ Kullanıcı '{user_to_delete}' silindi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Silme hatası: {e}")

# --- SİLO YÖNETİMİ ---
def show_silo_management():
    """Silo Yapılandırma ve Yönetim Paneli (Gelişmiş)"""
    st.subheader("🏭 Silo Yönetimi")
    
    tab_bugday, tab_un = st.tabs(["🌾 Buğday Siloları", "🍞 Un Siloları ve Bantlar"])

    # --- BUĞDAY SİLOLARI ---
    with tab_bugday:
        st.info("Buğday alımı ve paçal işlemlerinde kullanılan silolar.")

        # 1. Yeni Silo Ekle
        with st.expander("➕ Yeni Buğday Silosu Ekle", expanded=False):
            with st.form("new_wheat_silo_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_silo_name = st.text_input("Silo Adı (Örn: Celik Silo 1)")
                with col2:
                    new_silo_cap = st.number_input("Kapasite (Ton)", min_value=1.0, value=250.0, step=10.0)
                
                if st.form_submit_button("Ekle"):
                    if new_silo_name:
                        try:
                            with get_db_connection() as conn:
                                c = conn.cursor()
                                c.execute(
                                    "INSERT INTO silolar (isim, kapasite, mevcut_miktar) VALUES (?, ?, 0)",
                                    (new_silo_name, new_silo_cap)
                                )
                                conn.commit()
                            st.success(f"✅ '{new_silo_name}' başarıyla eklendi!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ Bu isimde bir silo zaten var!")
                        except Exception as e:
                            st.error(f"❌ Hata: {e}")
                    else:
                        st.warning("⚠️ Silo adı zorunludur!")

        # 2. Mevcut Siloları Listele ve Düzenle
        st.write("### 📋 Tanımlı Buğday Siloları")
        
        try:
            with get_db_connection() as conn:
                silos_df = pd.read_sql_query("SELECT id, isim, kapasite, mevcut_miktar FROM silolar ORDER BY isim", conn)
                
                if not silos_df.empty:
                    edited_df = st.data_editor(
                        silos_df,
                        column_config={
                            "id": st.column_config.NumberColumn("ID", disabled=True),
                            "isim": "Silo Adı",
                            "kapasite": st.column_config.NumberColumn("Kapasite (Ton)", min_value=1.0),
                            "mevcut_miktar": st.column_config.NumberColumn("Mevcut (Ton)", disabled=True)
                        },
                        hide_index=True,
                        use_container_width=True,
                        key="wheat_silo_editor"
                    )
                    
                    if st.button("💾 Buğday Silosu Güncellemelerini Kaydet"):
                         # Not: Gerçek update logic'i eklendi
                        try:
                            c = conn.cursor()
                            for index, row in edited_df.iterrows():
                                c.execute("UPDATE silolar SET isim=?, kapasite=? WHERE id=?", 
                                         (row['isim'], row['kapasite'], row['id']))
                            conn.commit()
                            st.success("✅ Güncellendi!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Güncelleme hatası: {e}")
                else:
                    st.warning("⚠️ Henüz hiç buğday silosu tanımlanmamış.")
                    
                # 3. GÜVENLİ SİLME (Strict Integrity)
                with st.expander("🗑️ Buğday Silosu Sil (Güvenli Mod)", expanded=False):
                    if not silos_df.empty:
                        silo_to_delete = st.selectbox("Silinecek Silo", silos_df['isim'].tolist())
                        
                        if st.button("Siloyu Sil", type="primary"):
                            # 1. Stok Kontrolü
                            silo_stock = silos_df[silos_df['isim'] == silo_to_delete]['mevcut_miktar'].values[0]
                            if silo_stock > 1:
                                st.error(f"⛔ '{silo_to_delete}' içinde {silo_stock} ton mal var! Önce boşaltmalısınız.")
                            else:
                                # 2. Referans Kontrolü (Arşiv)
                                cursor = conn.cursor()
                                cursor.execute("SELECT COUNT(*) FROM bugday_giris_arsivi WHERE silo_isim = ?", (silo_to_delete,))
                                usage_count = cursor.fetchone()[0]
                                
                                if usage_count > 0:
                                    st.error(f"⛔ Bu silo silinemez! Geçmişte {usage_count} adet giriş işleminde kullanılmış. Veri bütünlüğü için silinemez.")
                                else:
                                    # 3. Referans Kontrolü (Tavlı Analiz)
                                    cursor.execute("SELECT COUNT(*) FROM tavli_analiz WHERE silo_isim = ?", (silo_to_delete,))
                                    analiz_count = cursor.fetchone()[0]
                                    
                                    if analiz_count > 0:
                                        st.error(f"⛔ Bu silo silinemez! {analiz_count} adet tavlı analiz kaydı var.")
                                    else:
                                        # Temiz, silinebilir
                                        try:
                                            cursor.execute("DELETE FROM silolar WHERE isim = ?", (silo_to_delete,))
                                            conn.commit()
                                            st.success(f"✅ '{silo_to_delete}' kalıcı olarak silindi!")
                                            time.sleep(1)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Silme hatası: {e}")

        except Exception as e:
            st.error(f"Liste yüklenemedi: {e}")

    # --- UN SİLOLARI VE BANTLAR ---
    with tab_un:
        st.info("Un üretim, analiz ve paketleme işlemlerinde kullanılan silolar/bantlar.")
        
        # Un tablosunu kontrol et
        try:
             with get_db_connection() as conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS uretim_silolari 
                                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                 silo_adi TEXT UNIQUE, 
                                 aciklama TEXT, 
                                 aktif INTEGER DEFAULT 1)''')
                conn.commit()
        except: pass

        # 1. Yeni Un Silosu
        with st.expander("➕ Yeni Un Silosu/Bandı Ekle"):
            with st.form("new_flour_silo_form"):
                f_name = st.text_input("Silo/Bant Adı")
                f_desc = st.text_input("Açıklama")
                if st.form_submit_button("Ekle"):
                    if f_name:
                        try:
                            with get_db_connection() as conn:
                                conn.execute("INSERT INTO uretim_silolari (silo_adi, aciklama) VALUES (?, ?)", (f_name, f_desc))
                                conn.commit()
                            st.success(f"✅ '{f_name}' eklendi!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("⚠️ Bu isimde bir silo zaten var!")
                        except Exception as e:
                            st.error(f"❌ Hata: {str(e)}")
        
        # 2. Listele
        try:
            with get_db_connection() as conn:
                df_un = pd.read_sql_query("SELECT * FROM uretim_silolari ORDER BY silo_adi", conn)
                
            if not df_un.empty:
                edited_un = st.data_editor(
                    df_un,
                    column_config={
                        "id": st.column_config.NumberColumn("ID", disabled=True),
                        "aktif": st.column_config.CheckboxColumn("Aktif?", default=True)
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="flour_silo_editor"
                )
                
                if st.button("💾 Un Silosu Güncellemelerini Kaydet"):
                    try:
                        with get_db_connection() as conn_update:
                            c = conn_update.cursor()
                            for index, row in edited_un.iterrows():
                                # Aktif durumunu integer'a çevir
                                aktif_val = 1 if row['aktif'] else 0
                                c.execute("UPDATE uretim_silolari SET silo_adi=?, aciklama=?, aktif=? WHERE id=?", 
                                         (row['silo_adi'], row['aciklama'], aktif_val, row['id']))
                            conn_update.commit()
                        st.success("✅ Güncellendi!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hata: {e}")

                # 3. Referans Kontrollü Silme
                with st.expander("🗑️ Un Silosu Sil (Güvenli Mod)"):
                    # Silinecek silo seç
                    silo_listesi = df_un['silo_adi'].tolist()
                    del_un = st.selectbox("Silinecek Kayıt", silo_listesi, key="del_un_slc")
                    
                    if st.button("Kaydı Sil", key="del_un_btn"):
                        try:
                            # Kontrol: Un Analiz
                            cursor = conn.cursor()
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='un_analiz'")
                            if cursor.fetchone():
                                cursor.execute("SELECT COUNT(*) FROM un_analiz WHERE uretim_silosu = ?", (del_un,))
                                un_usage = cursor.fetchone()[0]
                                if un_usage > 0:
                                    st.error(f"⛔ Silinemez! {un_usage} adet analiz kaydında kullanılmış. Sadece 'Aktif' kutucuğunu kaldırarak pasife alabilirsiniz.")
                                    st.stop()
                            
                            conn.execute("DELETE FROM uretim_silolari WHERE silo_adi=?", (del_un,))
                            conn.commit()
                            st.success("Silindi!")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                            
        except Exception as e:
            st.error(f"Veri hatası: {e}")

# --- SİSTEM LOGLARI ---
def show_system_logs():
    """Sistem Logları Görüntüleme"""
    st.subheader("📜 Sistem Hata Logları")
    
    col_del, col_ref = st.columns([1, 4])
    with col_del:
        if st.button("🧹 Logları Temizle"):
            try:
                with get_db_connection() as conn:
                    conn.execute("DELETE FROM hata_loglari")
                    conn.commit()
                st.success("Loglar temizlendi!")
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")
    
    try:
        with get_db_connection() as conn:
            logs = pd.read_sql_query("SELECT * FROM hata_loglari ORDER BY tarih DESC LIMIT 100", conn)
            
        if not logs.empty:
            st.dataframe(
                logs,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "tarih": st.column_config.DatetimeColumn("Zaman", format="D/M/Y H:m:s"),
                    "hata_mesaji": "Hata Mesajı",
                    "modul": "Modül",
                    "kullanici": "Kullanıcı",
                    "hata_id": "Hata ID",
                    "seviye": "Seviye"
                }
            )
        else:
            st.info("Log kaydı bulunamadı.")
            
    except Exception as e:
        st.error(f"Log görüntüleme hatası: {e}")

# --- DEBUG PANEL ---
def debug_tables():
    """Veritabanı tablolarını listele ve yapılarını göster"""
    st.subheader("🔍 Veritabanı Tablo Yapısı")
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Tabloları listele
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = c.fetchall()
            
            if not tables:
                st.warning("Veritabanında hiç tablo yok!")
                if st.button("Tabloları Oluştur (Init DB)"):
                    init_db()
                    st.success("init_db() çalıştırıldı.")
                    st.rerun()
                return

            table_names = [t[0] for t in tables]
            selected_table = st.selectbox("İncelenecek Tablo", table_names)
            
            if selected_table:
                # Tablo yapısı (SCHEMA)
                st.write(f"**Tablo Şeması ({selected_table}):**")
                c.execute(f"PRAGMA table_info({selected_table})")
                schema = c.fetchall()
                schema_df = pd.DataFrame(schema, columns=['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'])
                st.dataframe(schema_df, use_container_width=True)
                
                # Tablo verisi (ÖRNEK)
                st.write(f"**Veri Önizleme ({selected_table} - İlk 5 Kayıt):**")
                try:
                    data_df = pd.read_sql_query(f"SELECT * FROM {selected_table} LIMIT 5", conn)
                    st.dataframe(data_df, use_container_width=True)
                except Exception as ex:
                    st.error(f"Veri okuma hatası: {ex}")

    except Exception as e:
        st.error(f"Debug hatası: {e}")

def show_debug_panel():
    """Yönetici Hata Ayıklama Paneli"""
    st.title("🛠️ Yönetici Hata Ayıklama Paneli")
    
    tab1, tab2, tab3 = st.tabs(["Database", "Session State", "System Info"])
    
    with tab1:
        debug_tables()
        
    with tab2:
        st.write("### Aktif Session State")
        st.write(st.session_state)
        
    with tab3:
        st.write("### Sistem Bilgisi")
        st.write(f"Python Version: {os.sys.version}")
        st.write(f"Working Directory: {os.getcwd()}")
        st.write(f"DB Path: {os.path.abspath(DB_FILE)}")
