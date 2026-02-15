import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import uuid

# Veritabanı fonksiyonları
from app.core.database import fetch_data, add_data

# Excel kütüphanesi kontrolü
try:
    import xlsxwriter
except ImportError:
    pass

# --- YENİ EKLENEN: PAÇAL LİSTESİNİ ÇEKME ---
def get_active_mixing_batches():
    """Veritabanındaki kayıtlı paçalları (reçeteleri) çeker."""
    try:
        # mixing_batches tablosundan veriyi çek
        df = fetch_data("mixing_batches")
        if df.empty:
            return []
        
        # Tarihe göre sırala (En yeni en üstte)
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'])
            df = df.sort_values('tarih', ascending=False)
        
        # Dropdown listesi hazırla: "İsim | Tarih | ID"
        batch_list = []
        for _, row in df.iterrows():
            # Tarihi kısa formata çevir
            if isinstance(row['tarih'], pd.Timestamp):
                tarih_kisa = row['tarih'].strftime('%d.%m %H:%M')
            else:
                tarih_kisa = str(row['tarih'])[:16]
                
            label = f"{row.get('urun_adi', 'Paçal')} | {tarih_kisa} | {row.get('batch_id')}"
            batch_list.append(label)
            
        return batch_list
    except Exception as e:
        return []

# --- KAYIT FONKSİYONU (GÜNCELLENDİ) ---
def save_uretim_kaydi(uretim_tarihi, uretim_hatti, uretim_adi, vardiya, sorumlu, mixing_batch_id, **uretim_degerleri):
    """Üretim kaydını 'kullanilan_pacal' anahtarı ile kaydeder (Zincir Kurulumu)."""
    
    # 1. Zorunlu Alan Kontrolü
    if not uretim_hatti or not vardiya:
        return False, "Üretim Hattı ve Vardiya zorunludur!"
        
    try:
        tarih_str = uretim_tarihi.strftime('%Y-%m-%d %H:%M:%S')
        
        # PARTİ NO GÜVENLİĞİ (PRD-ID) - Otomatik Oluştur
        unique_suffix = str(uuid.uuid4())[:4].upper()
        tarih_kisa = datetime.now().strftime('%y%m%d')
        
        # Eğer üretim adı girilmişse onu görünür isim yap, ama arka planda PRD kodu şart
        if uretim_adi:
            parti_kodu = f"PRD-{tarih_kisa}-{unique_suffix}" 
            kayit_adi = uretim_adi 
        else:
            parti_kodu = f"PRD-{tarih_kisa}-{unique_suffix}"
            kayit_adi = parti_kodu

        # Veritabanı Paketi
        db_data = {
            'tarih': tarih_str,
            'uretim_hatti': uretim_hatti,
            'degirmen_uretim_adi': kayit_adi,
            'vardiya': vardiya,
            'sorumlu': sorumlu,
            # --- KRİTİK DÜZELTME BURASI ---
            'kullanilan_pacal': mixing_batch_id,  # Traceability için anahtar kelime bu
            # ------------------------------
            'kirilan_bugday': float(uretim_degerleri.get('kirilan_bugday', 0)),
            'nem_orani': float(uretim_degerleri.get('nem_orani', 0)),
            'tav_suresi': float(uretim_degerleri.get('tav_suresi', 0)),
            'un_1': float(uretim_degerleri.get('un_1', 0)),
            'un_2': float(uretim_degerleri.get('un_2', 0)),
            'razmol': float(uretim_degerleri.get('razmol', 0)),
            'kepek': float(uretim_degerleri.get('kepek', 0)),
            'bongalite': float(uretim_degerleri.get('bongalite', 0)),
            'kirik_bugday': float(uretim_degerleri.get('kirik_bugday', 0)),
            'randiman_1': float(uretim_degerleri.get('randiman_1', 0)),
            'toplam_randiman': float(uretim_degerleri.get('toplam_randiman', 0)),
            'kayip': float(uretim_degerleri.get('kayip', 0)),
            'parti_no': parti_kodu  # Benzersiz Anahtar
        }
        
        # Veritabanına Ekleme
        if add_data("uretim_kaydi", db_data):
            st.cache_data.clear()
            return True, f"✅ Üretim Başarılı! Parti No: **{parti_kodu}**"
        else:
            return False, "Kayıt sırasında veritabanı hatası oluştu."
            
    except Exception as e:
        return False, f"Sistem hatası: {str(e)}"
        
# --- CACHING VE VERİ ÇEKME (BU KISIM EKSİK OLDUĞU İÇİN HATA ALIYORSUN) ---
@st.cache_data(ttl=300)
def get_uretim_kayitlari_cached():
    return fetch_data("uretim_kaydi")

def get_uretim_kayitlari():
    try:
        df = get_uretim_kayitlari_cached() 
        if df.empty: return pd.DataFrame()
        
        # Tarih formatını düzelt ve sırala
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
            df = df.sort_values('tarih', ascending=False)
            
        return df
    except Exception as e:
        return pd.DataFrame()
# --- EKRAN 1: ÜRETİM GİRİŞİ (PAÇAL SEÇİMLİ) ---
def show_uretim_kaydi():
    
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
        
    st.header("🏭 Değirmen Üretim Kaydı")
    
    # Veritabanından Paçalları Çek
    pacal_listesi = get_active_mixing_batches()
    
    tab1, tab2, tab3 = st.tabs([
        "📋 Üretim Bilgileri",
        "🌾 Hammadde Girişi", 
        "📦 Üretim Çıktıları"
    ])
    
    with tab1:
        st.markdown("### 📋 ÜRETİM BİLGİLERİ")
        uretim_tarihi = st.date_input("Üretim Tarihi *", value=datetime.now())
        
        # --- YENİ: PAÇAL SEÇİM KUTUSU ---
        selected_pacal = st.selectbox(
            "Kullanılan Paçal (Reçete) *", 
            options=["Seçiniz..."] + pacal_listesi,
            help="Bu üretimde hangi paçalın (reçetenin) kullanıldığını seçiniz."
        )
        
        uretim_hatti = st.text_input("Üretim Hattı *", placeholder="Yeni Degirmen, Eski Degirmen...")
        uretim_adi = st.text_input("Üretim Adı", placeholder="Lüks Ekmeklik (Otomatik Parti No için boş bırakın)")
        vardiya = st.text_input("Vardiya *", placeholder="08:00 - 18:00")
        sorumlu = st.text_input("Vardiya Sorumlusu")
    
    with tab2:
        st.markdown("### 🌾 HAMMADDE GİRİŞİ")
        kirilan_bugday = st.number_input("Kırılan Buğday (Kg)", min_value=0.0, step=100.0, format="%.0f")
        b1_rutubet = st.number_input("B1 Buğday Rutubeti (%)", min_value=0.0, max_value=20.0, step=0.1)
        tav_suresi = st.number_input("Tav Süresi (Saat)", min_value=0.0, step=0.5)
    
    with tab3:
        st.markdown("### 📦 ÜRETİM ÇIKTILARI (KG)")
        un_1 = st.number_input("UN (1) (KG)", min_value=0.0, step=50.0)
        un_2 = st.number_input("UN (2) (KG)", min_value=0.0, step=50.0)
        razmol = st.number_input("RAZMOL (KG)", min_value=0.0, step=50.0)
        kepek = st.number_input("KEPEK (KG)", min_value=0.0, step=50.0)
        bongalite = st.number_input("BONGALİTE (KG)", min_value=0.0, step=50.0)
        kirik = st.number_input("KIRIK (KG)", min_value=0.0, step=50.0)

    st.divider()

    # Randıman Hesaplamaları
    if kirilan_bugday > 0:
        rand_un1 = (un_1 / kirilan_bugday) * 100
        rand_un2 = (un_2 / kirilan_bugday) * 100
        rand_kepek = (kepek / kirilan_bugday) * 100
        rand_razmol = (razmol / kirilan_bugday) * 100
        rand_bongalite = (bongalite / kirilan_bugday) * 100
        rand_toplam_un = rand_un1 + rand_un2
        
        toplam_cikan_kg = un_1 + un_2 + kepek + razmol + bongalite + kirik
        kayip_kg = kirilan_bugday - toplam_cikan_kg
        kayip_yuzde = (kayip_kg / kirilan_bugday) * 100
    else:
        rand_un1 = rand_un2 = rand_kepek = rand_razmol = rand_bongalite = rand_toplam_un = kayip_yuzde = 0.0
        
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Un 1 Randıman", f"%{rand_un1:.2f}")
    m1.metric("Un 2 Randıman", f"%{rand_un2:.2f}")
    m2.metric("Kepek Randıman", f"%{rand_kepek:.2f}")
    m2.metric("Razmol Randıman", f"%{rand_razmol:.2f}")
    m3.metric("Bongalite Randıman", f"%{rand_bongalite:.2f}")
    m3.metric("Toplam Un (1+2)", f"%{rand_toplam_un:.2f}")
    m4.metric("Toplam Kayıp", f"%{kayip_yuzde:.2f}", delta_color="inverse")
    
    st.divider()
    
    if st.button("✅ ÜRETİM KAYDINI KAYDET", type="primary"):
        # Validasyon için config import
        try:
            from app.core.config import validate_numeric_input
        except ImportError:
            # Yedek basit validasyon
            def validate_numeric_input(val, name, **kwargs): return True, "", val

        # 1. Zorunlu Alan Kontrolü
        if not uretim_hatti or not vardiya:
            st.error("⚠️ Üretim Hattı ve Vardiya alanları zorunludur!")
            return
            
        # 2. PAÇAL SEÇİM KONTROLÜ
        if selected_pacal == "Seçiniz...":
            st.warning("⚠️ Lütfen kullanılan Paçal (Reçete) seçimini yapınız.")
            return

        # Paçal ID'sini String'den Ayıkla
        try:
            mixing_batch_id = selected_pacal.split(' | ')[-1].strip()
        except:
            mixing_batch_id = "BILINMIYOR"

        # 3. Sayısal Validasyonlar
        uretim_degerleri_kontrol = {
            'Kırılan Buğday': kirilan_bugday, 'Un 1': un_1, 'Un 2': un_2,
            'Razmol': razmol, 'Kepek': kepek, 'Bongalite': bongalite,
            'Kırık': kirik, 'Tav Süresi': tav_suresi
        }
        
        validasyon_hatalari = []
        for alan_adi, deger in uretim_degerleri_kontrol.items():
            valid, msg, _ = validate_numeric_input(deger, alan_adi.lower().replace(' ', '_'), allow_zero=True, allow_negative=False)
            if not valid: validasyon_hatalari.append(f"{alan_adi}: {msg}")
        
        if b1_rutubet < 0 or b1_rutubet > 20: validasyon_hatalari.append("B1 Buğday Rutubeti: %0-%20 arasında olmalıdır!")
        
        if kirilan_bugday > 0:
            toplam_cikan = un_1 + un_2 + razmol + kepek + bongalite + kirik
            if toplam_cikan > kirilan_bugday * 1.05:
                validasyon_hatalari.append(f"Toplam çıktı giren buğdaydan fazla olamaz! (Max %5 tolerans)")
        
        if validasyon_hatalari:
            st.error("🚫 Hatalar var:")
            for hata in validasyon_hatalari: st.write(f"- {hata}")
            return
        
        # 4. KAYIT İŞLEMİ
        uretim_verileri = {
            'kirilan_bugday': kirilan_bugday, 'nem_orani': b1_rutubet, 'tav_suresi': tav_suresi,
            'un_1': un_1, 'un_2': un_2, 'razmol': razmol, 'kepek': kepek, 'bongalite': bongalite,
            'kirik_bugday': kirik, 'randiman_1': rand_un1, 'toplam_randiman': rand_toplam_un, 'kayip': kayip_yuzde
        }
        
        success, msg = save_uretim_kaydi(uretim_tarihi, uretim_hatti, uretim_adi, vardiya, sorumlu, mixing_batch_id, **uretim_verileri)
        
        if success:
            st.success(f"✅ Üretim Kaydedildi! (Kullanılan Reçete ID: {mixing_batch_id})")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"❌ {msg}")

# --- EKRAN 2: YÖNETİM DASHBOARD ---
def show_yonetim_dashboard():
    df = get_uretim_kayitlari()
    if df.empty:
        st.info("📭 Henüz üretim kaydı bulunmamaktadır.")
        return
    
    col_period1, col_period2 = st.columns([1, 3])
    with col_period1:
        period = st.selectbox("Dönem Seçin", ["Son 7 Gün", "Son 30 Gün", "Son 3 Ay", "Son 6 Ay", "Tümü"], index=1)
    
    today = datetime.now().date()
    if period == "Son 7 Gün": start_date = today - timedelta(days=7)
    elif period == "Son 30 Gün": start_date = today - timedelta(days=30)
    elif period == "Son 3 Ay": start_date = today - timedelta(days=90)
    elif period == "Son 6 Ay": start_date = today - timedelta(days=180)
    else: start_date = None
    
    if start_date: df_filtered = df[df['tarih'].dt.date >= start_date].copy()
    else: df_filtered = df.copy()
    
    st.divider()
    
    # KPI
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Buğday", f"{df_filtered['kirilan_bugday'].sum()/1000:,.1f} Ton")
    c2.metric("Toplam Un", f"{(df_filtered['un_1'].sum() + df_filtered['un_2'].sum())/1000:,.1f} Ton")
    c3.metric("Ort. Randıman", f"%{df_filtered['toplam_randiman'].mean():.2f}")
    c4.metric("Üretim Sayısı", f"{len(df_filtered)}")
    
    st.divider()
    
    try:
        import plotly.express as px
        fig = px.bar(df_filtered, x='tarih', y='toplam_randiman', title='Günlük Randıman Trendi')
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.warning("Grafik için plotly gereklidir.")

# --- EKRAN 3: ÜRETİM ARŞİVİ ---
def show_uretim_arsivi():
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    st.header("🗄️ Üretim Arşivi")
    df = get_uretim_kayitlari()
    if not df.empty:
        # Tabloyu göster
        st.dataframe(
            df.sort_values('tarih', ascending=False), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Kayıt yok.")

# --- ANA YÖNLENDİRİCİ ---
def show_production_yonetimi():
    """Değirmen Bölümü Ana Kontrol Paneli"""
    st.markdown("""
    <div style='background-color: #E3F2FD; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #1565C0;'>
        <h2 style='color: #0D47A1; margin:0;'>🏭 Değirmen Üretim Merkezi</h2>
        <p style='color: #546E7A; margin:0; font-size: 14px;'>Traceability Entegreli Sürüm v2.1</p>
    </div>
    """, unsafe_allow_html=True)

    secim = st.radio("Modül Seçiniz:", ["📝 Günlük Üretim Girişi", "📂 Üretim Arşivi & Rapor", "📊 Üretim Performans Analizi"], horizontal=True, label_visibility="collapsed")
    st.markdown("---")

    if secim == "📝 Günlük Üretim Girişi":
        with st.container(border=True): show_uretim_kaydi()
    elif secim == "📂 Üretim Arşivi & Rapor":
        with st.container(border=True): show_uretim_arsivi()
    elif secim == "📊 Üretim Performans Analizi":
        with st.container(border=True): show_yonetim_dashboard()



