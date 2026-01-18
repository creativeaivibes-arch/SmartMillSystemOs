import streamlit as st
import pandas as pd
from datetime import datetime
import time

from app.core.database import fetch_data, add_data, get_conn
from app.core.auth import ROLES, hash_password, update_user_password

def show_backup_management():
    """Yedekleme Yönetimi Paneli - Google Sheets Versiyonu"""
    st.subheader("💾 Yedekleme ve Veri Güvenliği")
    st.info("""
    ℹ️ **Bilgi:** Sisteminiz şu an **Google Sheets (Bulut)** altyapısı üzerinde çalışmaktadır.
    
    **Avantajları:**
    1. ☁️ Verileriniz Google sunucularında otomatik olarak saklanır.
    2. 🕒 Google E-Tablolar üzerinden "Dosya > Sürüm Geçmişi" diyerek geçmişe dönebilirsiniz.
    3. 💾 Manuel olarak dosya kopyalamaya gerek yoktur.
    """)
    st.divider()
    st.write("### 📥 Verileri Excel Olarak İndir")
    tablolar = {"Kullanıcılar": "kullanicilar", "Buğday Siloları": "silolar", "Üretim Siloları": "uretim_silolari", "Hata Logları": "hata_loglari"}
    selected_table = st.selectbox("Tablo Seçin", list(tablolar.keys()))
    if st.button("📥 Veriyi İndir"):
        try:
            df = fetch_data(tablolar[selected_table])
            if not df.empty:
                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                processed_data = output.getvalue()
                st.download_button(label=f"📥 {selected_table}.xlsx İndir", data=processed_data, file_name=f"{tablolar[selected_table]}_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.warning("Bu tabloda veri yok.")
        except Exception as e:
            st.error(f"İndirme hatası: {e}")

def show_user_management():
    """Kullanıcı Yönetim Paneli - Google Sheets"""
    st.subheader("👥 Kullanıcı Yönetimi")
    
    with st.expander("➕ Yeni Kullanıcı Ekle", expanded=False):
        with st.form("new_user_form"):
            col_u1, col_u2 = st.columns(2)
            with col_u1:
                new_username = st.text_input("Kullanıcı Adı")
                new_full_name = st.text_input("Ad Soyad")
                new_email = st.text_input("Email Adresi", help="Şifre sıfırlama işlemlerinde kullanılacak")
            with col_u2:
                new_password = st.text_input("Şifre", type="password")
                new_role = st.selectbox("Rol", list(ROLES.keys()))
                send_welcome_email = st.checkbox("Kullanıcıya hoşgeldin maili gönder", value=True)
            submit_btn = st.form_submit_button("Ekle")
            if submit_btn:
                if new_username and new_password:
                    df_users = fetch_data("kullanicilar")
                    if not df_users.empty and 'kullanici_adi' in df_users.columns:
                        if new_username in df_users['kullanici_adi'].values:
                            st.error("❌ Bu kullanıcı adı zaten mevcut!")
                            st.stop()
                    hashed_pw = hash_password(new_password)
                    if hashed_pw:
                        try:
                            new_user_data = {"kullanici_adi": new_username, "sifre_hash": hashed_pw, "rol": new_role, "ad_soyad": new_full_name, "email": new_email.strip(), "olusturma_tarihi": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                            if add_data("kullanicilar", new_user_data):
                                st.success(f"✅ Kullanıcı '{new_username}' başarıyla oluşturuldu!")
                                if send_welcome_email and new_email.strip():
                                    from app.core.auth import send_password_email
                                    mail_success, mail_msg = send_password_email(new_email.strip(), new_full_name, new_username, new_password)
                                    if mail_success:
                                        st.info(f"📧 Hoşgeldin maili gönderildi: {new_email}")
                                    else:
                                        st.warning(f"⚠️ Mail gönderilemedi: {mail_msg}")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Kullanıcı eklenirken hata oluştu.")
                        except Exception as e:
                            st.error(f"❌ Hata: {str(e)}")
                else:
                    st.warning("⚠️ Kullanıcı adı ve şifre zorunludur!")

    st.write("### 📋 Mevcut Kullanıcılar")
    try:
        users_df = fetch_data("kullanicilar")
        if not users_df.empty:
            display_df = users_df.drop(columns=['sifre_hash'], errors='ignore')
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Kullanıcı listesi yüklenemedi: {e}")
        users_df = pd.DataFrame()

    with st.expander("🔑 Kullanıcı Şifre Sıfırlama", expanded=False):
        st.warning("⚠️ **Uyarı:** Bu bölüm unutulan şifreleri sıfırlamak içindir.")
        if not users_df.empty and 'kullanici_adi' in users_df.columns:
            user_list = [u for u in users_df['kullanici_adi'].tolist() if u != st.session_state.get('username')]
            if not user_list:
                st.info("Şifresi sıfırlanabilecek başka kullanıcı yok.")
            else:
                with st.form("reset_password_form"):
                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        user_to_reset = st.selectbox("Kullanıcı Seçin", user_list)
                    with col_r2:
                        new_temp_password = st.text_input("Yeni Geçici Şifre", type="password", help="Kullanıcıya vereceğiniz geçici şifre")
                    selected_user_data = users_df[users_df['kullanici_adi'] == user_to_reset]
                    has_email = False
                    user_email_display = ""
                    if not selected_user_data.empty and 'email' in selected_user_data.columns:
                        user_email = selected_user_data.iloc[0]['email']
                        if user_email and user_email.strip():
                            has_email = True
                            user_email_display = user_email
                    if has_email:
                        st.info(f"📧 Kullanıcının kayıtlı email adresi: **{user_email_display}**")
                        send_email_option = st.checkbox("Yeni şifreyi kullanıcıya mail ile gönder", value=True)
                    else:
                        send_email_option = False
                        st.warning("⚠️ Bu kullanıcının kayıtlı email adresi yok. Şifreyi manuel olarak iletmeniz gerekecek.")
                    reset_btn = st.form_submit_button("Şifreyi Sıfırla", type="primary")
                    if reset_btn:
                        if not new_temp_password:
                            st.error("❌ Lütfen yeni bir şifre girin!")
                        elif len(new_temp_password) < 6:
                            st.warning("⚠️ Şifre en az 6 karakter olmalıdır.")
                        else:
                            success, msg, email = update_user_password(user_to_reset, new_temp_password, send_email=send_email_option)
                            if success:
                                st.success(f"✅ **{user_to_reset}** kullanıcısının şifresi başarıyla sıfırlandı!")
                                if send_email_option and email:
                                    if "mail gönderildi" in msg.lower():
                                        st.success(f"📧 Yeni şifre kullanıcıya mail ile gönderildi: {email}")
                                    else:
                                        st.warning(f"⚠️ {msg}")
                                        st.info(f"💡 Yeni geçici şifreyi manuel olarak kullanıcıya bildirin: `{new_temp_password}`")
                                else:
                                    st.info(f"💡 Yeni geçici şifreyi kullanıcıya bildirin: `{new_temp_password}`")
                                st.caption("Kullanıcı, giriş yaptıktan sonra 'Profil Ayarları' bölümünden kendi şifresini değiştirebilir.")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
        else:
            st.info("Henüz kullanıcı kaydı bulunmuyor.")

    with st.expander("🗑️ Kullanıcı Sil", expanded=False):
        if not users_df.empty and 'kullanici_adi' in users_df.columns:
            user_list = users_df['kullanici_adi'].tolist()
            user_to_delete = st.selectbox("Silinecek Kullanıcı", user_list)
            if st.button("Kullanıcıyı Sil", type="primary"):
                if user_to_delete == "admin":
                    st.error("⛔ 'admin' kullanıcısı silinemez!")
                elif user_to_delete == st.session_state.get('username'):
                    st.error("⛔ Kendinizi silemezsiniz!")
                else:
                    try:
                        conn = get_conn()
                        new_df = users_df[users_df['kullanici_adi'] != user_to_delete]
                        conn.update(worksheet="kullanicilar", data=new_df)
                        st.success(f"✅ Kullanıcı '{user_to_delete}' silindi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Silme hatası: {e}")

def show_silo_management():
    """Silo Yapılandırma ve Yönetim Paneli - Google Sheets"""
    st.subheader("🏭 Silo Yönetimi")
    tab_bugday, tab_un = st.tabs(["🌾 Buğday Siloları", "🍞 Un Siloları ve Bantlar"])
    with tab_bugday:
        st.info("Buğday alımı ve paçal işlemlerinde kullanılan silolar.")
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
                            df_silo = fetch_data("silolar")
                            if not df_silo.empty and 'isim' in df_silo.columns:
                                if new_silo_name in df_silo['isim'].values:
                                    st.error("Bu isimde silo zaten var.")
                                    st.stop()
                            new_data = {"isim": new_silo_name, "kapasite": float(new_silo_cap), "mevcut_miktar": 0.0}
                            if add_data("silolar", new_data):
                                st.success(f"✅ '{new_silo_name}' başarıyla eklendi!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Ekleme başarısız.")
                        except Exception as e:
                            st.error(f"❌ Hata: {e}")
                    else:
                        st.warning("⚠️ Silo adı zorunludur!")
        st.write("### 📋 Tanımlı Buğday Siloları")
        try:
            silos_df = fetch_data("silolar")
            if not silos_df.empty:
                st.dataframe(silos_df, use_container_width=True, hide_index=True)
            else:
                st.warning("Tanımlı silo yok.")
        except:
            st.error("Veri alınamadı.")
            silos_df = pd.DataFrame()
        with st.expander("🗑️ Buğday Silosu Sil"):
            if not silos_df.empty and 'isim' in silos_df.columns:
                silo_to_del = st.selectbox("Silinecek Silo", silos_df['isim'].tolist())
                if st.button("Siloyu Sil"):
                    current_stock = float(silos_df[silos_df['isim'] == silo_to_del]['mevcut_miktar'].iloc[0])
                    if current_stock > 1:
                        st.error(f"⛔ İçinde {current_stock} ton mal var! Önce boşaltmalısınız.")
                    else:
                        try:
                            conn = get_conn()
                            new_df = silos_df[silos_df['isim'] != silo_to_del]
                            conn.update(worksheet="silolar", data=new_df)
                            st.success("Silo silindi.")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Silme hatası: {e}")
    with tab_un:
        st.info("Un üretim, analiz ve paketleme işlemlerinde kullanılan silolar/bantlar.")
        with st.expander("➕ Yeni Un Silosu/Bandı Ekle"):
            with st.form("new_flour_silo_form"):
                f_name = st.text_input("Silo/Bant Adı")
                f_desc = st.text_input("Açıklama")
                if st.form_submit_button("Ekle"):
                    if f_name:
                        try:
                            new_data = {"silo_adi": f_name, "aciklama": f_desc, "aktif": 1}
                            if add_data("uretim_silolari", new_data):
                                st.success(f"✅ '{f_name}' eklendi!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Hata oluştu.")
                        except Exception as e:
                            st.error(f"❌ Hata: {str(e)}")
        try:
            df_un = fetch_data("uretim_silolari")
            if not df_un.empty:
                st.dataframe(df_un, use_container_width=True, hide_index=True)
            else:
                st.info("Kayıt yok.")
        except:
            st.error("Veri okunamadı.")
            df_un = pd.DataFrame()
        with st.expander("🗑️ Un Silosu Sil"):
            if not df_un.empty and 'silo_adi' in df_un.columns:
                del_un = st.selectbox("Silinecek Kayıt", df_un['silo_adi'].tolist())
                if st.button("Kaydı Sil", key="del_un_btn"):
                    try:
                        conn = get_conn()
                        new_df = df_un[df_un['silo_adi'] != del_un]
                        conn.update(worksheet="uretim_silolari", data=new_df)
                        st.success("Silindi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Hata: {e}")

def show_system_logs():
    """Sistem Logları Görüntüleme"""
    st.subheader("📜 Sistem Hata Logları")
    col_del, col_ref = st.columns([1, 4])
    with col_del:
        if st.button("🧹 Logları Temizle"):
            try:
                conn = get_conn()
                df = fetch_data("hata_loglari")
                if not df.empty:
                    empty_df = pd.DataFrame(columns=df.columns)
                    conn.update(worksheet="hata_loglari", data=empty_df)
                    st.success("Loglar temizlendi!")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")
    try:
        logs = fetch_data("hata_loglari")
        if not logs.empty:
            if 'tarih' in logs.columns:
                logs['tarih'] = pd.to_datetime(logs['tarih'])
                logs = logs.sort_values('tarih', ascending=False)
            st.dataframe(logs, use_container_width=True, hide_index=True)
        else:
            st.info("Log kaydı bulunamadı.")
    except Exception as e:
        st.error(f"Log görüntüleme hatası: {e}")

def debug_tables():
    """Veritabanı tablolarını listele ve yapılarını göster"""
    st.subheader("🔍 Google Sheets Veri İnceleyici")
    tables = ["kullanicilar", "silolar", "bugday_giris_arsivi", "hareketler", "un_analiz", "un_spekleri", "uretim_kaydi", "uretim_silolari"]
    selected_table = st.selectbox("İncelenecek Tablo (Worksheet)", tables)
    if st.button("Veriyi Getir"):
        try:
            df = fetch_data(selected_table)
            st.write(f"**Tablo: {selected_table}** - {len(df)} kayıt")
            st.dataframe(df)
        except Exception as e:
            st.error(f"Okuma hatası: {e}")

def show_debug_panel():
    """Yönetici Hata Ayıklama Paneli"""
    st.title("🛠️ Yönetici Hata Ayıklama Paneli")
    tab1, tab2, tab3 = st.tabs(["Data Inspector", "Session State", "System Info"])
    with tab1:
        debug_tables()
    with tab2:
        st.write("### Aktif Session State")
        st.write(st.session_state)
    with tab3:
        st.write("### Sistem Bilgisi")
        st.write(f"Python Version: {pd.__version__} (Pandas)")
        st.write("Backend: Google Sheets API")
