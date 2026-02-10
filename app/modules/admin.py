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
    """Silo Konfigürasyonu - TİP SEÇİMİ VE GÜNCELLEME AKTİF"""
    st.markdown("### 🏭 Silo Konfigürasyonu ve Tanımları")
    st.info("Buradan silo isimlerini, kapasitelerini ve kullanım amaçlarını (Buğday/Un) ayarlayabilirsiniz.")
    
    try:
        # Veriyi çek (Force refresh ile en güncel hali)
        df = fetch_data("silolar", force_refresh=True)
        
        if df.empty:
            st.warning("Tanımlı silo bulunamadı. Yeni eklemek için aşağıdaki tabloyu kullanın.")
            # Boş şablon oluştur
            df = pd.DataFrame(columns=['isim', 'kapasite', 'silo_tipi', 'mevcut_miktar', 'aciklama'])
        
        # Eğer 'silo_tipi' sütunu yoksa oluştur (Eski veritabanı uyumluluğu)
        if 'silo_tipi' not in df.columns:
            df['silo_tipi'] = "BUĞDAY"
            
        # Sütunları düzenle (Analiz detaylarını gizle, sadece konfigürasyon)
        config_cols = ['isim', 'kapasite', 'silo_tipi', 'mevcut_miktar', 'aciklama']
        # Mevcut olmayan sütunları ekle
        for col in config_cols:
            if col not in df.columns:
                df[col] = "" if col == 'aciklama' else 0
                
        # Sadece konfigürasyon sütunlarını al, diğerlerini (protein, gluten vb) arka planda korumak için sakla
        df_display = df[config_cols].copy()
        
        # --- EDİTÖR ---
        edited_df = st.data_editor(
            df_display,
            num_rows="dynamic",
            use_container_width=True,
            key="silo_config_editor",
            column_config={
                "isim": st.column_config.TextColumn("Silo Adı", required=True),
                "kapasite": st.column_config.NumberColumn("Kapasite (Ton)", min_value=0, required=True, format="%.0f"),
                "silo_tipi": st.column_config.SelectboxColumn(
                    "Kullanım Amacı", 
                    options=["BUĞDAY", "UN", "DİNLENDİRME", "DİĞER"],
                    required=True,
                    default="BUĞDAY"
                ),
                "mevcut_miktar": st.column_config.NumberColumn("Mevcut (Ton)", disabled=True, help="Stok hareketlerinden otomatik hesaplanır"),
                "aciklama": st.column_config.TextColumn("Açıklama / Konum")
            }
        )
        
        st.caption("ℹ️ Not: Yeni satır eklemek için tablonun en altına tıklayın. Silmek için satırı seçip 'Del' tuşuna basın.")
        
        if st.button("💾 Silo Değişikliklerini Kaydet", type="primary"):
            try:
                conn = get_conn()
                
                # --- BİRLEŞTİRME MANTIĞI ---
                # Kullanıcı sadece konfigürasyon sütunlarını değiştirdi.
                # Veritabanındaki diğer sütunları (protein, gluten vs.) kaybetmemek için merge işlemi yapmalıyız.
                
                # 1. Mevcut veriyi tekrar çek
                original_df = fetch_data("silolar", force_refresh=True)
                
                # 2. Yeni eklenen siloları tespit et
                final_rows = []
                
                for _, new_row in edited_df.iterrows():
                    silo_name = new_row['isim']
                    
                    # Bu silo eski listede var mı?
                    match = original_df[original_df['isim'] == silo_name] if not original_df.empty else pd.DataFrame()
                    
                    if not match.empty:
                        # Varsa: Eski verileri al, üzerine yeni konfigürasyonu yaz
                        existing_data = match.iloc[0].to_dict()
                        existing_data.update(new_row.to_dict()) # Yeni isim, kapasite, tipi güncelle
                        final_rows.append(existing_data)
                    else:
                        # Yoksa (Yeni Silo): Sadece yeni veriyi ekle, analizleri 0 yap
                        new_data = new_row.to_dict()
                        # Varsayılan analiz değerleri
                        defaults = {'protein':0, 'gluten':0, 'rutubet':0, 'sedim':0, 'maliyet':0}
                        for k, v in defaults.items():
                            if k not in new_data: new_data[k] = v
                        final_rows.append(new_data)
                
                # 3. DataFrame oluştur ve kaydet
                df_to_save = pd.DataFrame(final_rows)
                
                # Google Sheets Update
                conn.update(worksheet="silolar", data=df_to_save)
                
                # Cache Temizle
                st.cache_data.clear()
                if 'db_cache' in st.session_state:
                    del st.session_state.db_cache
                
                st.success("✅ Silo konfigürasyonu başarıyla güncellendi!")
                time.sleep(1.5)
                st.rerun()
                
            except Exception as e:
                st.error(f"Kayıt sırasında hata oluştu: {str(e)}")
            
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

