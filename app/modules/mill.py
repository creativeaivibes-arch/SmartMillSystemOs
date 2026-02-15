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
# --- SİLME FONKSİYONU ---
def delete_uretim_record(parti_no):
    """Üretim kaydını siler"""
    try:
        from app.core.database import get_conn
        conn = get_conn()
        df = fetch_data("uretim_kaydi")
        if df.empty:
            return False, "Kayıt bulunamadı"
        
        # Parti No'ya göre filtrele (silmek istediğimiz hariç)
        df_new = df[df['parti_no'] != parti_no]
        
        if len(df_new) < len(df):
            conn.update(worksheet="uretim_kaydi", data=df_new)
            st.cache_data.clear()
            return True, "✅ Kayıt silindi!"
        else:
            return False, "Kayıt bulunamadı"
    except Exception as e:
        return False, f"Hata: {str(e)}"

# --- GÜNCELLEME FONKSİYONU ---
def update_uretim_record(parti_no, updated_data):
    """Üretim kaydını günceller"""
    try:
        from app.core.database import get_conn
        conn = get_conn()
        df = fetch_data("uretim_kaydi")
        if df.empty:
            return False, "Kayıt bulunamadı"
        
        # Parti No'yu bul
        mask = df['parti_no'] == parti_no
        if not mask.any():
            return False, "Kayıt bulunamadı"
        
        # Güncelle
        for key, value in updated_data.items():
            if key in df.columns:
                df.loc[mask, key] = value
        
        conn.update(worksheet="uretim_kaydi", data=df)
        st.cache_data.clear()
        return True, "✅ Kayıt güncellendi!"
    except Exception as e:
        return False, f"Hata: {str(e)}"
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
    st.header("📊 Üretim Performans Analizi")
    
    df = get_uretim_kayitlari()
    if df.empty:
        st.info("📭 Henüz üretim kaydı bulunmamaktadır.")
        return
    
    # ========== FİLTRELEME PANELİ ==========
    st.subheader("🔍 Filtreler")
    
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        period = st.selectbox("📅 Dönem", ["Son 7 Gün", "Son 30 Gün", "Son 3 Ay", "Son 6 Ay", "Tümü"], index=1)
    
    with col_f2:
        # Üretim Hattı Filtresi
        hat_listesi = ["Tümü"] + sorted(df['uretim_hatti'].dropna().unique().tolist())
        secili_hat = st.selectbox("🏭 Üretim Hattı", hat_listesi)
    
    with col_f3:
        # Ürün Adı Filtresi
        urun_listesi = ["Tümü"] + sorted(df['degirmen_uretim_adi'].dropna().unique().tolist())
        secili_urun = st.selectbox("📦 Ürün Adı", urun_listesi)
    
    with col_f4:
        # Vardiya Filtresi
        vardiya_listesi = ["Tümü"] + sorted(df['vardiya'].dropna().unique().tolist())
        secili_vardiya = st.selectbox("⏰ Vardiya", vardiya_listesi)
    
    # Dönem Filtreleme
    today = datetime.now().date()
    if period == "Son 7 Gün": start_date = today - timedelta(days=7)
    elif period == "Son 30 Gün": start_date = today - timedelta(days=30)
    elif period == "Son 3 Ay": start_date = today - timedelta(days=90)
    elif period == "Son 6 Ay": start_date = today - timedelta(days=180)
    else: start_date = None
    
    # Filtreleri Uygula
    df_filtered = df.copy()
    if start_date:
        df_filtered = df_filtered[df_filtered['tarih'].dt.date >= start_date]
    if secili_hat != "Tümü":
        df_filtered = df_filtered[df_filtered['uretim_hatti'] == secili_hat]
    if secili_urun != "Tümü":
        df_filtered = df_filtered[df_filtered['degirmen_uretim_adi'] == secili_urun]
    if secili_vardiya != "Tümü":
        df_filtered = df_filtered[df_filtered['vardiya'] == secili_vardiya]
    
    if df_filtered.empty:
        st.warning("⚠️ Seçili filtrelere uygun kayıt bulunamadı.")
        return
    
    st.divider()
    
    # ========== ÖZET KPI'LAR ==========
    st.subheader("📈 Özet Göstergeler")
    
    # SATIR 1: Temel KPI'lar
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    toplam_bugday_ton = df_filtered['kirilan_bugday'].sum() / 1000
    toplam_un_ton = (df_filtered['un_1'].sum() + df_filtered['un_2'].sum()) / 1000
    ort_randiman = df_filtered['toplam_randiman'].mean()
    uretim_sayisi = len(df_filtered)
    
    kpi1.metric("🌾 Toplam Buğday", f"{toplam_bugday_ton:,.1f} Ton")
    kpi2.metric("🍞 Toplam Un", f"{toplam_un_ton:,.1f} Ton")
    kpi3.metric("📊 Ort. Randıman", f"%{ort_randiman:.2f}")
    kpi4.metric("🏭 Üretim Sayısı", f"{uretim_sayisi}")
    
    # SATIR 2: Yan Ürün & Verimlilik
    kpi5, kpi6, kpi7, kpi8 = st.columns(4)
    
    toplam_kepek_ton = df_filtered['kepek'].sum() / 1000
    toplam_razmol_ton = df_filtered['razmol'].sum() / 1000
    ort_kayip = df_filtered['kayip'].mean()
    ort_tav = df_filtered['tav_suresi'].mean()
    
    kpi5.metric("🟤 Toplam Kepek", f"{toplam_kepek_ton:,.1f} Ton")
    kpi6.metric("⚪ Toplam Razmol", f"{toplam_razmol_ton:,.1f} Ton")
    kpi7.metric("📉 Ort. Kayıp", f"%{ort_kayip:.2f}", delta_color="inverse")
    kpi8.metric("⏱️ Ort. Tav Süresi", f"{ort_tav:.1f} Saat")
    
    # SATIR 3: Max/Min Performans
    kpi9, kpi10, kpi11, kpi12 = st.columns(4)
    
    max_rand_row = df_filtered.loc[df_filtered['toplam_randiman'].idxmax()]
    min_rand_row = df_filtered.loc[df_filtered['toplam_randiman'].idxmin()]
    
    kpi9.metric("🏆 En Yüksek Randıman", 
                f"%{max_rand_row['toplam_randiman']:.2f}",
                delta=f"{max_rand_row['tarih'].strftime('%d.%m')}")
    
    kpi10.metric("⚠️ En Düşük Randıman", 
                 f"%{min_rand_row['toplam_randiman']:.2f}",
                 delta=f"{min_rand_row['tarih'].strftime('%d.%m')}",
                 delta_color="inverse")
    
    # En Verimli Hat
    if 'uretim_hatti' in df_filtered.columns:
        hat_randiman = df_filtered.groupby('uretim_hatti')['toplam_randiman'].mean()
        if not hat_randiman.empty:
            en_iyi_hat = hat_randiman.idxmax()
            en_iyi_hat_rand = hat_randiman.max()
            # Başlığa hat adını ekle
            kpi11.metric("🏭 En Verimli Hat", 
                        f"%{en_iyi_hat_rand:.2f}",  # Randımanı value olarak göster
                        delta=f"{en_iyi_hat}")
    
    # En Verimli Vardiya
    if 'vardiya' in df_filtered.columns:
        vardiya_randiman = df_filtered.groupby('vardiya')['toplam_randiman'].mean()
        if not vardiya_randiman.empty:
            en_iyi_vardiya = vardiya_randiman.idxmax()
            en_iyi_vardiya_rand = vardiya_randiman.max()
            kpi12.metric("⏰ En Verimli Vardiya", 
                        f"{en_iyi_vardiya[:8]}...",
                        delta=f"%{en_iyi_vardiya_rand:.2f}")
    
    st.divider()
    
    # ========== GRAFİK PANELİ ==========
    st.subheader("📊 Grafiksel Analizler")
    
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        
        tab1, tab2, tab3 = st.tabs(["📈 Randıman Analizleri", "📊 Üretim Analizleri", "🥧 Yan Ürün Analizleri"])
        
        # --- TAB 1: RANDIMAN ANALİZLERİ ---
        with tab1:
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                # Günlük Randıman Trendi
                fig1 = px.line(df_filtered.sort_values('tarih'), 
                              x='tarih', y='toplam_randiman',
                              title='📈 Günlük Randıman Trendi',
                              labels={'tarih': 'Tarih', 'toplam_randiman': 'Randıman (%)'},
                              markers=True)
                fig1.update_traces(line_color='#2E7D32')
                st.plotly_chart(fig1, use_container_width=True)
            
            with col_g2:
                # Hat Bazında Ortalama Randıman
                if 'uretim_hatti' in df_filtered.columns:
                    hat_data = df_filtered.groupby('uretim_hatti')['toplam_randiman'].mean().reset_index()
                    fig2 = px.bar(hat_data, 
                                 x='uretim_hatti', y='toplam_randiman',
                                 title='🏭 Hat Bazında Ortalama Randıman',
                                 labels={'uretim_hatti': 'Üretim Hattı', 'toplam_randiman': 'Ort. Randıman (%)'},
                                 color='toplam_randiman',
                                 color_continuous_scale='Greens')
                    st.plotly_chart(fig2, use_container_width=True)
            
            # Kayıp Trendi
            fig3 = px.line(df_filtered.sort_values('tarih'),
                          x='tarih', y='kayip',
                          title='📉 Kayıp Oranı Trendi',
                          labels={'tarih': 'Tarih', 'kayip': 'Kayıp (%)'},
                          markers=True)
            fig3.update_traces(line_color='#C62828')
            st.plotly_chart(fig3, use_container_width=True)
        
        # --- TAB 2: ÜRETİM ANALİZLERİ ---
        with tab2:
            col_g3, col_g4 = st.columns(2)
            
            with col_g3:
                # Ürün Dağılımı (Pie Chart)
                if 'degirmen_uretim_adi' in df_filtered.columns:
                    urun_data = df_filtered.groupby('degirmen_uretim_adi')['kirilan_bugday'].sum().reset_index()
                    fig4 = px.pie(urun_data, 
                                 values='kirilan_bugday', names='degirmen_uretim_adi',
                                 title='🥧 Ürün Bazında Üretim Dağılımı')
                    st.plotly_chart(fig4, use_container_width=True)
            
            with col_g4:
                # Hat Bazında Üretim Hacmi
                if 'uretim_hatti' in df_filtered.columns:
                    hat_uretim = df_filtered.groupby('uretim_hatti')['kirilan_bugday'].sum().reset_index()
                    hat_uretim['kirilan_bugday'] = hat_uretim['kirilan_bugday'] / 1000  # Ton'a çevir
                    fig5 = px.bar(hat_uretim,
                                 x='uretim_hatti', y='kirilan_bugday',
                                 title='🏭 Hat Bazında Toplam Üretim (Ton)',
                                 labels={'uretim_hatti': 'Üretim Hattı', 'kirilan_bugday': 'Toplam Buğday (Ton)'},
                                 color='kirilan_bugday',
                                 color_continuous_scale='Blues')
                    st.plotly_chart(fig5, use_container_width=True)
            
            # Hammadde Kullanım Trendi
            df_gunluk = df_filtered.groupby(df_filtered['tarih'].dt.date)['kirilan_bugday'].sum().reset_index()
            df_gunluk['kirilan_bugday'] = df_gunluk['kirilan_bugday'] / 1000
            fig6 = px.area(df_gunluk,
                          x='tarih', y='kirilan_bugday',
                          title='🌾 Günlük Buğday Tüketimi Trendi (Ton)',
                          labels={'tarih': 'Tarih', 'kirilan_bugday': 'Buğday (Ton)'})
            fig6.update_traces(fill='tozeroy', line_color='#F57C00')
            st.plotly_chart(fig6, use_container_width=True)
        
        # --- TAB 3: YAN ÜRÜN ANALİZLERİ ---
        with tab3:
            # Yan Ürün Dağılımı
            yan_urun_data = {
                'Ürün': ['Un-2', 'Kepek', 'Razmol', 'Bongalite', 'Kırık'],
                'Miktar (Ton)': [
                    df_filtered['un_2'].sum() / 1000,
                    df_filtered['kepek'].sum() / 1000,
                    df_filtered['razmol'].sum() / 1000,
                    df_filtered['bongalite'].sum() / 1000,
                    df_filtered['kirik_bugday'].sum() / 1000
                ]
            }
            df_yan_urun = pd.DataFrame(yan_urun_data)
            
            col_g5, col_g6 = st.columns(2)
            
            with col_g5:
                fig7 = px.bar(df_yan_urun,
                             x='Ürün', y='Miktar (Ton)',
                             title='📊 Yan Ürün Toplam Miktarları',
                             color='Miktar (Ton)',
                             color_continuous_scale='Oranges')
                st.plotly_chart(fig7, use_container_width=True)
            
            with col_g6:
                fig8 = px.pie(df_yan_urun,
                             values='Miktar (Ton)', names='Ürün',
                             title='🥧 Yan Ürün Oransal Dağılımı')
                st.plotly_chart(fig8, use_container_width=True)
    
    except ImportError:
        st.warning("📊 Grafik görüntüleme için `plotly` kütüphanesi gereklidir.")
    except Exception as e:
        st.error(f"Grafik oluşturulurken hata: {str(e)}")
    
    st.divider()
    
    # ========== KARŞILAŞTIRMA TABLOLARI ==========
    st.subheader("📋 Detaylı Karşılaştırma Tabloları")
    
    with st.expander("🏭 Hat Bazında Performans Karşılaştırması", expanded=False):
        if 'uretim_hatti' in df_filtered.columns:
            hat_analiz = df_filtered.groupby('uretim_hatti').agg({
                'kirilan_bugday': 'sum',
                'un_1': 'sum',
                'un_2': 'sum',
                'toplam_randiman': 'mean',
                'kayip': 'mean',
                'tav_suresi': 'mean',
                'parti_no': 'count'
            }).reset_index()
            
            hat_analiz.columns = ['Üretim Hattı', 'Toplam Buğday (kg)', 'Toplam Un-1 (kg)', 
                                  'Toplam Un-2 (kg)', 'Ort. Randıman (%)', 'Ort. Kayıp (%)', 
                                  'Ort. Tav (saat)', 'Üretim Sayısı']
            
            hat_analiz['Toplam Buğday (Ton)'] = (hat_analiz['Toplam Buğday (kg)'] / 1000).round(1)
            hat_analiz['Toplam Un-1 (Ton)'] = (hat_analiz['Toplam Un-1 (kg)'] / 1000).round(1)
            hat_analiz['Toplam Un-2 (Ton)'] = (hat_analiz['Toplam Un-2 (kg)'] / 1000).round(1)
            
            hat_analiz = hat_analiz.drop(['Toplam Buğday (kg)', 'Toplam Un-1 (kg)', 'Toplam Un-2 (kg)'], axis=1)
            
            hat_analiz['Ort. Randıman (%)'] = hat_analiz['Ort. Randıman (%)'].round(2)
            hat_analiz['Ort. Kayıp (%)'] = hat_analiz['Ort. Kayıp (%)'].round(2)
            hat_analiz['Ort. Tav (saat)'] = hat_analiz['Ort. Tav (saat)'].round(1)
            
            hat_analiz = hat_analiz.sort_values('Ort. Randıman (%)', ascending=False)
            
            st.dataframe(hat_analiz, use_container_width=True, hide_index=True)
            
            en_iyi = hat_analiz.iloc[0]
            st.success(f"🏆 **En Verimli Hat:** {en_iyi['Üretim Hattı']} - Ort. Randıman: %{en_iyi['Ort. Randıman (%)']:.2f}")
    
    with st.expander("⏰ Vardiya Bazında Performans Karşılaştırması", expanded=False):
        if 'vardiya' in df_filtered.columns:
            vardiya_analiz = df_filtered.groupby('vardiya').agg({
                'kirilan_bugday': 'sum',
                'toplam_randiman': 'mean',
                'kayip': 'mean',
                'un_1': 'sum',
                'un_2': 'sum',
                'parti_no': 'count'
            }).reset_index()
            
            vardiya_analiz.columns = ['Vardiya', 'Toplam Buğday (kg)', 'Ort. Randıman (%)', 
                                     'Ort. Kayıp (%)', 'Toplam Un-1 (kg)', 'Toplam Un-2 (kg)', 
                                     'Üretim Sayısı']
            
            vardiya_analiz['Toplam Buğday (Ton)'] = (vardiya_analiz['Toplam Buğday (kg)'] / 1000).round(1)
            vardiya_analiz['Toplam Un (Ton)'] = ((vardiya_analiz['Toplam Un-1 (kg)'] + vardiya_analiz['Toplam Un-2 (kg)']) / 1000).round(1)
            
            vardiya_analiz = vardiya_analiz.drop(['Toplam Buğday (kg)', 'Toplam Un-1 (kg)', 'Toplam Un-2 (kg)'], axis=1)
            
            vardiya_analiz['Ort. Randıman (%)'] = vardiya_analiz['Ort. Randıman (%)'].round(2)
            vardiya_analiz['Ort. Kayıp (%)'] = vardiya_analiz['Ort. Kayıp (%)'].round(2)
            
            vardiya_analiz = vardiya_analiz.sort_values('Ort. Randıman (%)', ascending=False)
            
            st.dataframe(vardiya_analiz, use_container_width=True, hide_index=True)
            
            en_iyi_vardiya = vardiya_analiz.iloc[0]
            st.success(f"🏆 **En Verimli Vardiya:** {en_iyi_vardiya['Vardiya']} - Ort. Randıman: %{en_iyi_vardiya['Ort. Randıman (%)']:.2f}")
    
    with st.expander("📦 Ürün Bazında Performans Karşılaştırması", expanded=False):
        if 'degirmen_uretim_adi' in df_filtered.columns:
            urun_analiz = df_filtered.groupby('degirmen_uretim_adi').agg({
                'kirilan_bugday': 'sum',
                'toplam_randiman': 'mean',
                'kayip': 'mean',
                'parti_no': 'count'
            }).reset_index()
            
            urun_analiz.columns = ['Ürün Adı', 'Toplam Buğday (kg)', 'Ort. Randıman (%)', 
                                  'Ort. Kayıp (%)', 'Üretim Sayısı']
            
            urun_analiz['Toplam Buğday (Ton)'] = (urun_analiz['Toplam Buğday (kg)'] / 1000).round(1)
            urun_analiz = urun_analiz.drop(['Toplam Buğday (kg)'], axis=1)
            
            urun_analiz['Ort. Randıman (%)'] = urun_analiz['Ort. Randıman (%)'].round(2)
            urun_analiz['Ort. Kayıp (%)'] = urun_analiz['Ort. Kayıp (%)'].round(2)
            
            urun_analiz = urun_analiz.sort_values('Ort. Randıman (%)', ascending=False)
            
            st.dataframe(urun_analiz, use_container_width=True, hide_index=True)
            
            en_iyi_urun = urun_analiz.iloc[0]
            st.success(f"🏆 **En Verimli Ürün:** {en_iyi_urun['Ürün Adı']} - Ort. Randıman: %{en_iyi_urun['Ort. Randıman (%)']:.2f}")
    
    with st.expander("📅 Aylık Özet Tablo", expanded=False):
        df_filtered['ay'] = df_filtered['tarih'].dt.to_period('M').astype(str)
        
        aylik_analiz = df_filtered.groupby('ay').agg({
            'kirilan_bugday': 'sum',
            'un_1': 'sum',
            'un_2': 'sum',
            'toplam_randiman': 'mean',
            'kayip': 'mean',
            'parti_no': 'count'
        }).reset_index()
        
        aylik_analiz.columns = ['Ay', 'Toplam Buğday (kg)', 'Toplam Un-1 (kg)', 
                               'Toplam Un-2 (kg)', 'Ort. Randıman (%)', 'Ort. Kayıp (%)', 
                               'Üretim Sayısı']
        
        aylik_analiz['Toplam Buğday (Ton)'] = (aylik_analiz['Toplam Buğday (kg)'] / 1000).round(1)
        aylik_analiz['Toplam Un (Ton)'] = ((aylik_analiz['Toplam Un-1 (kg)'] + aylik_analiz['Toplam Un-2 (kg)']) / 1000).round(1)
        
        aylik_analiz = aylik_analiz.drop(['Toplam Buğday (kg)', 'Toplam Un-1 (kg)', 'Toplam Un-2 (kg)'], axis=1)
        
        aylik_analiz['Ort. Randıman (%)'] = aylik_analiz['Ort. Randıman (%)'].round(2)
        aylik_analiz['Ort. Kayıp (%)'] = aylik_analiz['Ort. Kayıp (%)'].round(2)
        
        aylik_analiz = aylik_analiz.sort_values('Ay', ascending=False)
        
        st.dataframe(aylik_analiz, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # ========== AKILLI ÖNERİLER & UYARILAR ==========
    st.subheader("💡 Akıllı Öneriler & Uyarılar")
    
    with st.expander("🔔 Sistem Tavsiyeleri", expanded=True):
        uyarilar = []
        oneriler = []
        
        # UYARI 1: Düşük Randıman
        if ort_randiman < 70:
            uyarilar.append(f"⚠️ **Ortalama randıman düşük:** %{ort_randiman:.2f} (Hedef: %70+)")
        
        # UYARI 2: Yüksek Kayıp
        if ort_kayip > 2:
            uyarilar.append(f"⚠️ **Ortalama kayıp yüksek:** %{ort_kayip:.2f} (Hedef: %2 altı)")
        
        # UYARI 3: Tav Süresi Kontrolü
        if ort_tav < 10:
            uyarilar.append(f"⚠️ **Tav süresi kısa:** {ort_tav:.1f} saat (Önerilen: 10-14 saat)")
        elif ort_tav > 16:
            uyarilar.append(f"⚠️ **Tav süresi uzun:** {ort_tav:.1f} saat (Önerilen: 10-14 saat)")
        
        # ÖNERİ 1: Hat Karşılaştırması
        if 'uretim_hatti' in df_filtered.columns:
            hat_randiman = df_filtered.groupby('uretim_hatti')['toplam_randiman'].mean()
            if len(hat_randiman) > 1:
                en_iyi_hat = hat_randiman.idxmax()
                en_kotu_hat = hat_randiman.idxmin()
                fark = hat_randiman.max() - hat_randiman.min()
                if fark > 3:
                    oneriler.append(f"💡 **Hat optimizasyonu:** '{en_iyi_hat}' hattı '{en_kotu_hat}' hattından %{fark:.1f} daha verimli çalışıyor.")
        
        # ÖNERİ 2: Vardiya Karşılaştırması
        if 'vardiya' in df_filtered.columns:
            vardiya_randiman = df_filtered.groupby('vardiya')['toplam_randiman'].mean()
            if len(vardiya_randiman) > 1:
                en_iyi_vardiya = vardiya_randiman.idxmax()
                en_kotu_vardiya = vardiya_randiman.idxmin()
                fark_vardiya = vardiya_randiman.max() - vardiya_randiman.min()
                if fark_vardiya > 2:
                    oneriler.append(f"💡 **Vardiya optimizasyonu:** '{en_iyi_vardiya}' vardiyası '{en_kotu_vardiya}' vardiyasından %{fark_vardiya:.1f} daha verimli.")
        
        # ÖNERİ 3: Trend Analizi
        if len(df_filtered) >= 7:
            df_sorted = df_filtered.sort_values('tarih')
            son_7 = df_sorted.tail(7)['toplam_randiman'].mean()
            onceki = df_sorted.head(len(df_sorted) - 7)['toplam_randiman'].mean() if len(df_sorted) > 7 else son_7
            
            if son_7 > onceki + 2:
                oneriler.append(f"📈 **Pozitif trend:** Son kayıtlarda randıman %{son_7 - onceki:.1f} artış gösteriyor! Sürdürün!")
            elif son_7 < onceki - 2:
                uyarilar.append(f"📉 **Negatif trend:** Son kayıtlarda randıman %{onceki - son_7:.1f} düşüş var. İnceleme gerekebilir.")
        
        # Uyarıları Göster
        if uyarilar:
            st.markdown("### ⚠️ Dikkat Gereken Noktalar:")
            for uyari in uyarilar:
                st.warning(uyari)
        else:
            st.success("✅ Tüm parametreler normal aralıkta!")
        
        # Önerileri Göster
        if oneriler:
            st.markdown("### 💡 İyileştirme Önerileri:")
            for oneri in oneriler:
                st.info(oneri)
        else:
            st.info("💡 Şu an için özel öneri bulunmuyor.")
        
        # Genel Değerlendirme
        st.divider()
        st.markdown("### 📊 Genel Değerlendirme:")
        
        if ort_randiman >= 72:
            genel_durum = "🌟 **Mükemmel Performans!** Randıman hedefin üzerinde."
        elif ort_randiman >= 70:
            genel_durum = "✅ **İyi Performans!** Hedef seviyedesiniz."
        elif ort_randiman >= 65:
            genel_durum = "⚠️ **Orta Performans.** İyileştirme alanları mevcut."
        else:
            genel_durum = "🚨 **Düşük Performans!** Acil inceleme gerekiyor."
        
        st.markdown(genel_durum)
# --- EKRAN 3: ÜRETİM ARŞİVİ (YENİLENMİŞ) ---
def show_uretim_arsivi():
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("🗄️ Üretim Arşivi")
    
    df = get_uretim_kayitlari()
    
    if df.empty:
        st.info("📭 Henüz üretim kaydı bulunmamaktadır.")
        return
    
    # Tarih formatını düzelt
    if 'tarih' in df.columns:
        df['tarih_str'] = df['tarih'].dt.strftime('%d.%m.%Y %H:%M')
    
    st.divider()
    st.subheader("📋 Tüm Üretim Kayıtları")
    
    # Gösterilecek kolonları seç
    display_cols = ['tarih_str', 'parti_no', 'degirmen_uretim_adi', 'uretim_hatti', 
                    'vardiya', 'kirilan_bugday', 'un_1', 'un_2', 'toplam_randiman', 'kullanilan_pacal']
    display_cols = [c for c in display_cols if c in df.columns]
    
    df_display = df[display_cols].copy()
    
    # Kolon isimlerini Türkçeleştir
    rename_dict = {
        'tarih_str': 'Tarih',
        'parti_no': 'Parti No',
        'degirmen_uretim_adi': 'Üretim Adı',
        'uretim_hatti': 'Hat',
        'vardiya': 'Vardiya',
        'kirilan_bugday': 'Buğday (kg)',
        'un_1': 'Un-1 (kg)',
        'un_2': 'Un-2 (kg)',
        'toplam_randiman': 'Randıman (%)',
        'kullanilan_pacal': 'Paçal ID'
    }
    df_display = df_display.rename(columns=rename_dict)
    
    st.dataframe(df_display, use_container_width=True, hide_index=True, height=400)
    
    st.divider()
    
    # İşlem Paneli (Sadece Admin ve Operations)
    if st.session_state.get('user_role') in ['admin', 'operations']:
        st.subheader("⚙️ Kayıt İşlemleri")
        
        tab_edit, tab_delete = st.tabs(["✏️ Düzenle", "🗑️ Sil"])
        
        # --- DÜZENLEME TAB'I ---
        with tab_edit:
            st.markdown("#### Düzenlenecek Kaydı Seçin")
            
            # Kayıt seçimi için liste
            kayit_listesi = df.to_dict('records')
            
            def format_kayit(row):
                tarih = row.get('tarih_str', str(row.get('tarih', '')))[:16]
                parti = row.get('parti_no', 'Bilinmiyor')
                isim = row.get('degirmen_uretim_adi', '-')
                return f"{tarih} | {parti} | {isim}"
            
            secili_kayit = st.selectbox(
                "Kayıt Seçin:",
                kayit_listesi,
                format_func=format_kayit,
                key="edit_select"
            )
            
            if secili_kayit:
                st.info(f"**Düzenlenen Kayıt:** {secili_kayit.get('parti_no')}")
                
                # 3 TAB'LI DÜZENLEME FORMU
                edit_tab1, edit_tab2, edit_tab3 = st.tabs([
                    "📋 Üretim Bilgileri",
                    "🌾 Hammadde Girişi",
                    "📦 Üretim Çıktıları"
                ])
                
                with edit_tab1:
                    st.markdown("### 📋 ÜRETİM BİLGİLERİ")
                    edit_uretim_adi = st.text_input("Üretim Adı", value=secili_kayit.get('degirmen_uretim_adi', ''), key="edit_uretim_adi")
                    edit_uretim_hatti = st.text_input("Üretim Hattı", value=secili_kayit.get('uretim_hatti', ''), key="edit_hat")
                    edit_vardiya = st.text_input("Vardiya", value=secili_kayit.get('vardiya', ''), key="edit_vardiya")
                    edit_sorumlu = st.text_input("Sorumlu", value=secili_kayit.get('sorumlu', ''), key="edit_sorumlu")
                
                with edit_tab2:
                    st.markdown("### 🌾 HAMMADDE GİRİŞİ")
                    edit_kirilan = st.number_input("Kırılan Buğday (kg)", value=float(secili_kayit.get('kirilan_bugday', 0)), step=100.0, format="%.0f", key="edit_kirilan")
                    edit_nem = st.number_input("Nem Oranı (%)", value=float(secili_kayit.get('nem_orani', 0)), step=0.1, key="edit_nem")
                    edit_tav = st.number_input("Tav Süresi (saat)", value=float(secili_kayit.get('tav_suresi', 0)), step=0.5, key="edit_tav")
                
                with edit_tab3:
                    st.markdown("### 📦 ÜRETİM ÇIKTILARI (KG)")
                    edit_un1 = st.number_input("Un-1 (kg)", value=float(secili_kayit.get('un_1', 0)), step=50.0, format="%.0f", key="edit_un1")
                    edit_un2 = st.number_input("Un-2 (kg)", value=float(secili_kayit.get('un_2', 0)), step=50.0, format="%.0f", key="edit_un2")
                    edit_razmol = st.number_input("Razmol (kg)", value=float(secili_kayit.get('razmol', 0)), step=50.0, format="%.0f", key="edit_razmol")
                    edit_kepek = st.number_input("Kepek (kg)", value=float(secili_kayit.get('kepek', 0)), step=50.0, format="%.0f", key="edit_kepek")
                    edit_bongalite = st.number_input("Bongalite (kg)", value=float(secili_kayit.get('bongalite', 0)), step=50.0, format="%.0f", key="edit_bongalite")
                    edit_kirik = st.number_input("Kırık (kg)", value=float(secili_kayit.get('kirik_bugday', 0)), step=50.0, format="%.0f", key="edit_kirik")
                
                st.divider()
                
                # Randımanları yeniden hesapla
                if edit_kirilan > 0:
                    yeni_rand1 = (edit_un1 / edit_kirilan) * 100
                    yeni_toplam_rand = ((edit_un1 + edit_un2) / edit_kirilan) * 100
                    toplam_cikan = edit_un1 + edit_un2 + edit_razmol + edit_kepek + edit_bongalite + edit_kirik
                    yeni_kayip = ((edit_kirilan - toplam_cikan) / edit_kirilan) * 100
                else:
                    yeni_rand1 = yeni_toplam_rand = yeni_kayip = 0
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Yeni Un-1 Randıman", f"%{yeni_rand1:.2f}")
                col_m2.metric("Yeni Toplam Randıman", f"%{yeni_toplam_rand:.2f}")
                col_m3.metric("Yeni Kayıp", f"%{yeni_kayip:.2f}", delta_color="inverse")
                
                st.divider()
                
                if st.button("💾 DEĞİŞİKLİKLERİ KAYDET", type="primary", key="btn_update"):
                    updated_data = {
                        'degirmen_uretim_adi': edit_uretim_adi,
                        'uretim_hatti': edit_uretim_hatti,
                        'vardiya': edit_vardiya,
                        'sorumlu': edit_sorumlu,
                        'kirilan_bugday': edit_kirilan,
                        'nem_orani': edit_nem,
                        'tav_suresi': edit_tav,
                        'un_1': edit_un1,
                        'un_2': edit_un2,
                        'razmol': edit_razmol,
                        'kepek': edit_kepek,
                        'bongalite': edit_bongalite,
                        'kirik_bugday': edit_kirik,
                        'randiman_1': yeni_rand1,
                        'toplam_randiman': yeni_toplam_rand,
                        'kayip': yeni_kayip
                    }
                    
                    success, msg = update_uretim_record(secili_kayit['parti_no'], updated_data)
                    if success:
                        st.success("✅ Kayıt başarıyla güncellendi!")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
        
        # --- SİLME TAB'I ---
        with tab_delete:
            st.markdown("#### Silinecek Kaydı Seçin")
            st.warning("⚠️ DİKKAT: Bu işlem geri alınamaz!")
            
            secili_kayit_sil = st.selectbox(
                "Kayıt Seçin:",
                kayit_listesi,
                format_func=format_kayit,
                key="delete_select"
            )
            
            if secili_kayit_sil:
                # Kayıt detaylarını göster
                st.error(f"**Silinecek Kayıt:** {secili_kayit_sil.get('parti_no')}")
                
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.write(f"📅 **Tarih:** {secili_kayit_sil.get('tarih_str', 'Bilinmiyor')}")
                    st.write(f"🏭 **Hat:** {secili_kayit_sil.get('uretim_hatti', '-')}")
                    st.write(f"📦 **Üretim:** {secili_kayit_sil.get('degirmen_uretim_adi', '-')}")
                with col_info2:
                    st.write(f"⏰ **Vardiya:** {secili_kayit_sil.get('vardiya', '-')}")
                    st.write(f"🌾 **Buğday:** {secili_kayit_sil.get('kirilan_bugday', 0):,.0f} kg")
                    st.write(f"📊 **Randıman:** %{secili_kayit_sil.get('toplam_randiman', 0):.2f}")
                
                st.divider()
                
                # Onay Mekanizması
                onay = st.checkbox(
                    "✅ Riskleri anladım, bu kaydı kalıcı olarak silmek istiyorum.",
                    key="delete_confirm_check"
                )
                
                if onay:
                    if st.button("🔥 KAYDI KALİCİ OLARAK SİL", type="primary", key="btn_delete"):
                        success, msg = delete_uretim_record(secili_kayit_sil['parti_no'])
                        if success:
                            st.success("✅ Kayıt başarıyla silindi!")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                else:
                    st.info("💡 Silme işlemi için yukarıdaki onay kutusunu işaretleyin.")
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







