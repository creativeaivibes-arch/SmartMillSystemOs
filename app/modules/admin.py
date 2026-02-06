# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Database importları
from app.core.database import fetch_data, add_data, update_data, get_conn

# ----------------------------------------------------------------
# 1. KULLANICI YÖNETİMİ
# ----------------------------------------------------------------
def show_user_management():
    """Kullanıcı ekleme, çıkarma ve listeleme"""
    st.markdown("### 👥 Kullanıcı Yönetimi")
    
    try:
        users = fetch_data("users")
        
        # Kullanıcı Listesi Tablosu
        if not users.empty:
            # Görsel güvenlik: Şifreleri gizle
            display_users = users.copy()
            if 'password' in display_users.columns:
                display_users['password'] = "********"
            
            st.dataframe(display_users, use_container_width=True)
        else:
            st.info("Sistemde kayıtlı kullanıcı bulunamadı.")

        st.divider()

        # Yeni Kullanıcı Ekleme Formu
        with st.expander("➕ Yeni Kullanıcı Ekle", expanded=False):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                new_user = col1.text_input("Kullanıcı Adı (Username)")
                new_pass = col2.text_input("Şifre", type="password")
                
                new_name = st.text_input("Ad Soyad")
                new_role = st.selectbox("Yetki Rolü", ["admin", "quality", "operations", "management"])
                
                submitted = st.form_submit_button("Kullanıcıyı Kaydet")
                
                if submitted:
                    if new_user and new_pass:
                        # Not: Prodüksiyonda şifreler hashlenmelidir.
                        user_data = {
                            "username": new_user,
                            "password": new_pass,
                            "role": new_role,
                            "full_name": new_name,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        add_data("users", user_data)
                        st.success(f"✅ {new_user} kullanıcısı başarıyla eklendi!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Kullanıcı adı ve şifre boş olamaz.")

    except Exception as e:
        st.error(f"Kullanıcı verileri yüklenirken hata oluştu: {e}")

# ----------------------------------------------------------------
# 2. SILO YÖNETİMİ
# ----------------------------------------------------------------
def show_silo_management():
    """Silo tanımları ve kapasite ayarları"""
    st.markdown("### 🏭 Silo Konfigürasyonu")
    st.info("Buradan silo kapasitelerini ve isimlerini düzenleyebilirsiniz.")
    
    try:
        silos = fetch_data("silolar")
        
        if not silos.empty:
            # Streamlit Data Editor ile interaktif düzenleme
            edited_silos = st.data_editor(
                silos,
                num_rows="dynamic",
                use_container_width=True,
                key="silo_editor_admin"
            )
            
            if st.button("💾 Silo Değişikliklerini Kaydet"):
                # Güvenlik önlemi: Toplu güncelleme karmaşıktır, şimdilik uyarı veriyoruz.
                # İleride buraya 'conn.update' ile toplu yazma eklenebilir.
                st.warning("⚠️ Toplu güncelleme modu şu an 'salt okunur' güvenli moddadır. Lütfen veritabanı yöneticisi ile görüşün.")
        else:
            st.warning("Tanımlı silo bulunamadı.")
            
    except Exception as e:
        st.error(f"Silo verileri yüklenemedi: {e}")

# ----------------------------------------------------------------
# 3. YEDEKLEME VE GERİ YÜKLEME
# ----------------------------------------------------------------
def show_backup_restore():
    """Veritabanı yedekleme işlemleri"""
    st.markdown("### 💾 Yedekleme ve Veri Güvenliği")
    
    st.info("""
    ℹ️ **Bilgi:** Sisteminiz **Google Sheets (Bulut)** altyapısı üzerinde çalışmaktadır.
    
    **Otomatik Koruma:**
    1. ☁️ Verileriniz Google sunucularında anlık saklanır.
    2. 🕒 Hata durumunda Google E-Tablolar'da **"Dosya > Sürüm Geçmişi"** menüsünden eski tarihe dönebilirsiniz.
    """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Excel Yedeği Al")
        tablolar = {
            "Kullanıcılar": "users", 
            "Buğday Siloları": "silolar", 
            "Stok Hareketleri": "hareketler", 
            "Tavlı Analizler": "tavli_analiz"
        }
        selected_table = st.selectbox("İndirilecek Tablo", list(tablolar.keys()))
        
        if st.button("📥 Yedeği İndir", type="primary"):
            try:
                df = fetch_data(tablolar[selected_table])
                csv = df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label=f"📄 {selected_table} CSV İndir",
                    data=csv,
                    file_name=f"{tablolar[selected_table]}_backup_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"İndirme hatası: {e}")
    
    with col2:
        st.subheader("📤 Geri Yükleme (Restore)")
        st.warning("⚠️ Geri yükleme işlemi mevcut verilerin üzerine yazar. Sadece acil durumlarda kullanın.")
        uploaded_file = st.file_uploader("Yedek Dosyası Seç", type=["csv", "xlsx"])
        if uploaded_file:
            st.error("Geri yükleme özelliği sistem güvenliği için bu panelden kapatılmıştır. Lütfen manuel yükleme yapın.")

# ----------------------------------------------------------------
# 4. SİSTEM LOGLARI
# ----------------------------------------------------------------
def show_system_logs():
    """Sistemdeki hareketleri ve hataları gösterir"""
    st.markdown("### 📜 Sistem Hareket Kayıtları")
    
    try:
        # Hareketler tablosunu log olarak kullanıyoruz
        logs = fetch_data("hareketler")
        
        if not logs.empty:
            # Tarihe göre en yeniden eskiye sırala
            if 'tarih' in logs.columns:
                logs['tarih'] = pd.to_datetime(logs['tarih'])
                logs = logs.sort_values('tarih', ascending=False)
            
            # Filtreleme
            filter_text = st.text_input("Loglarda Ara (Silo, İşlem Tipi vb.)")
            if filter_text:
                mask = logs.astype(str).apply(lambda x: x.str.contains(filter_text, case=False, na=False)).any(axis=1)
                logs = logs[mask]
            
            st.dataframe(logs, use_container_width=True)
        else:
            st.info("Henüz kaydedilmiş bir hareket logu yok.")
            
    except Exception as e:
        st.error(f"Loglar okunamadı: {e}")

# ----------------------------------------------------------------
# 5. DEBUG ARAÇLARI
# ----------------------------------------------------------------
def show_debug_tools():
    """Geliştirici ve hata ayıklama araçları"""
    st.markdown("### 🛠️ Geliştirici Araçları")
    
    tab_d1, tab_d2 = st.tabs(["🧹 Önbellek & Session", "ℹ️ Sistem Bilgisi"])
    
    with tab_d1:
        st.write("Sistem yavaşladığında veya veriler güncellenmediğinde kullanın.")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🧹 Cache (Önbellek) Temizle", type="primary"):
                st.cache_data.clear()
                st.success("Tüm veri önbelleği temizlendi! Veriler yeniden çekilecek.")
                time.sleep(1)
                st.rerun()
                
        with col_c2:
             if st.button("🔄 Session State Sıfırla"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
                
        st.write("**Aktif Session State Verileri:**")
        st.json(dict(st.session_state))

    with tab_d2:
        st.write(f"**Pandas Version:** {pd.__version__}")
        st.write(f"**Streamlit Version:** {st.__version__}")
        st.write(f"**Backend:** Google Sheets API")
        st.write(f"**Aktif Kullanıcı:** {st.session_state.get('username', 'Bilinmiyor')}")
        st.write(f"**Rol:** {st.session_state.get('user_role', 'Bilinmiyor')}")
