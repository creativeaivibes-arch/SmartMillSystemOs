import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --- DATABASE IMPORTLARI ---
from app.core.database import fetch_data
from app.core.styles import card_metric
from app.core.error_handling import error_handler, log_warning

# PDF Raporlama (Hata önleyici blok)
try:
    from app.modules.reports import create_silo_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    def create_silo_pdf_report(*args): return None
    def turkce_karakter_duzelt_pdf(x): return x

# --------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# --------------------------------------------------------------------------

def draw_silo(fill_ratio, name):
    """Silo görseli çiz - Renkli ve Dinamik"""
    try:
        fill_ratio = float(fill_ratio)
        fill_ratio = max(0.0, min(1.0, fill_ratio))
    except:
        fill_ratio = 0.0
    
    height = 100
    fill_height = int(height * fill_ratio)
    empty_height = height - fill_height
    
    # Renk Skalası
    try:
        if fill_ratio < 0.2: fill_color = "#EF4444" # Kırmızı (Boşalıyor)
        elif fill_ratio < 0.5: fill_color = "#3B82F6" # Mavi (Normal)
        elif fill_ratio < 0.8: fill_color = "#10B981" # Yeşil (İyi)
        else: fill_color = "#F59E0B" # Turuncu (Çok Dolu)
    except:
        fill_color = "#CBD5E1"
    
    svg = f'''<svg width="100%" height="{height + 20}" viewBox="0 0 60 {height + 20}">
        <rect x="10" y="5" width="40" height="{height}" rx="5" ry="5" 
              style="fill: #f8fafc; stroke: #64748b; stroke-width:2;"/>
        <rect x="10" y="{5 + empty_height}" width="40" height="{fill_height}" 
              rx="2" ry="2" style="fill: {fill_color}; stroke: none;"/>
        <text x="30" y="{height + 15}" font-family="sans-serif" font-size="8" text-anchor="middle" 
              fill="#334155">{name}</text>
    </svg>'''
    return svg

@error_handler(context="Dashboard Veri")
def get_dashboard_data():
    """Tüm dashboard verilerini tek seferde çeker"""
    try:
        # 1. Silo Verileri
        df_silo = fetch_data("silolar")
        if df_silo.empty:
            df_silo = pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])
        
        # NaN temizliği
        df_silo = df_silo.fillna({
            'protein': 0, 'gluten': 0, 'mevcut_miktar': 0, 'kapasite': 100, 'maliyet': 0
        })
        if 'isim' in df_silo.columns:
            df_silo = df_silo.sort_values('isim')

        # 2. Hareket Verileri (Son 24 Saat İçin)
        df_hareket = fetch_data("hareketler")
        
        return df_silo, df_hareket
    except Exception as e:
        log_warning(f"Veri çekme hatası: {e}", "Dashboard")
        return pd.DataFrame(), pd.DataFrame()

def calculate_last_24h(df_hareket):
    """Son 24 saatteki giriş ve çıkışları hesaplar"""
    if df_hareket.empty or 'tarih' not in df_hareket.columns:
        return 0.0, 0.0
    
    try:
        df_hareket['tarih'] = pd.to_datetime(df_hareket['tarih'])
        now = datetime.now()
        start_time = now - timedelta(hours=24)
        
        # Son 24 saat filtresi
        mask_24h = df_hareket['tarih'] >= start_time
        df_last = df_hareket[mask_24h]
        
        giris_24h = df_last[df_last['hareket_tipi'] == 'Giriş']['miktar'].sum()
        cikis_24h = df_last[df_last['hareket_tipi'] == 'Çıkış']['miktar'].sum()
        
        return giris_24h, cikis_24h
    except:
        return 0.0, 0.0

# --------------------------------------------------------------------------
# DASHBOARD GÖSTERİMİ
# --------------------------------------------------------------------------

def show_silo_card_detailed(silo_data):
    """Silo Kartı - Mevcut yapını koruduk"""
    with st.container(border=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**{silo_data.get('isim', 'Silo')}**")
            bugday = str(silo_data.get('bugday_cinsi', '-'))
            if bugday == "nan": bugday = "-"
            st.caption(f"🌾 {bugday}")
            
            # Maliyet
            maliyet = float(silo_data.get('maliyet', 0))
            st.markdown(f"💰 **{maliyet:.2f} TL**")
            
        with c2:
            try:
                kap = float(silo_data.get('kapasite', 1))
                mev = float(silo_data.get('mevcut_miktar', 0))
                dol = (mev / kap)
            except: dol = 0
            st.markdown(draw_silo(dol, ""), unsafe_allow_html=True)
            
        st.markdown(f"**{mev:.1f} / {kap:.0f} Ton**")
        
        # Detaylar
        with st.expander("🔍 Analiz"):
            k1, k2 = st.columns(2)
            k1.metric("Prot", f"{float(silo_data.get('protein',0)):.1f}")
            k2.metric("Glut", f"{float(silo_data.get('gluten',0)):.1f}")
            k1.metric("Sedim", f"{float(silo_data.get('sedim',0)):.0f}")
            
            # PDF Butonu
            safe_name = str(silo_data.get('isim', 's')).replace(" ", "_")
            if st.button("📄 Rapor", key=f"pdf_{safe_name}", use_container_width=True):
                # PDF indirme mantığı buraya bağlanacak
                st.info("PDF hazırlanıyor...")

def show_dashboard():
    """YÖNETİCİ KOKPİTİ"""
    
    # Verileri Çek
    df_silo, df_hareket = get_dashboard_data()
    
    if df_silo.empty:
        st.warning("Sistemde tanımlı silo bulunamadı.")
        return

    # --- HESAPLAMALAR ---
    toplam_stok = df_silo['mevcut_miktar'].sum()
    
    # Finansal Değer (Her silonun miktar * maliyeti)
    df_silo['deger'] = df_silo['mevcut_miktar'] * df_silo['maliyet']
    toplam_deger_tl = df_silo['deger'].sum()
    
    # Ağırlıklı Ortalama Maliyet
    ort_maliyet = (toplam_deger_tl / toplam_stok) if toplam_stok > 0 else 0
    
    # Son 24 Saat Hareketleri
    giris_24h, cikis_24h = calculate_last_24h(df_hareket)

    # --- BAŞLIK ---
    st.markdown("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <h2 style="margin:0; color:#1e3a8a;">🏭 Fabrika Kontrol Merkezi</h2>
        <span style="color:#64748b; font-size:0.9rem">Canlı Veri Akışı</span>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # 1. YÖNETİCİ ŞERİDİ (FİNANS - SİMÜLASYON - HAREKET)
    # ==============================================================================
    
    with st.container(border=True):
        col_finans, col_simulasyon, col_hareket = st.columns([1.2, 1.5, 1.2])
        
        # A) FİNANSAL DURUM
        with col_finans:
            st.markdown("### 💰 Finansal Durum")
            st.metric("Toplam Stok Değeri", f"{(toplam_deger_tl/1_000_000):.2f} Milyon ₺")
            st.metric("Ort. Stok Maliyeti", f"{ort_maliyet:.2f} TL/kg")
            
        # B) ÜRETİM SİMÜLASYONU (STOK ÖMRÜ)
        with col_simulasyon:
            st.markdown("### ⏳ Stok Ömrü Hesapla")
            
            # İnteraktif Slider / Input
            gunluk_kirma = st.number_input(
                "Günlük Planlanan Kırma (Ton)", 
                min_value=0, 
                value=250, 
                step=10,
                help="Fabrikanın günlük kırma hedefini buraya girin."
            )
            
            if gunluk_kirma > 0:
                yetecek_gun = toplam_stok / gunluk_kirma
                renk = "normal"
                if yetecek_gun < 7: renk = "inverse" # Kırmızı (Kritik)
                elif yetecek_gun > 20: renk = "normal" # Yeşil (Rahat)
                
                st.metric("Stok Yetebilirlik Süresi", f"{yetecek_gun:.1f} Gün", delta=None, delta_color=renk)
                
                # Görsel Çubuk (Progress Bar)
                st.progress(min(1.0, yetecek_gun / 30)) # 30 günü %100 kabul et
                if yetecek_gun < 5:
                    st.error(f"⚠️ Kritik Seviye! Stok 5 günden az kaldı.")
            else:
                st.info("Hesaplamak için günlük tonaj giriniz.")

        # C) SON 24 SAAT
        with col_hareket:
            st.markdown("### 🚛 Son 24 Saat")
            c1, c2 = st.columns(2)
            c1.metric("Giriş", f"{giris_24h:.0f} Ton", "Mal Kabul")
            c2.metric("Çıkış", f"{cikis_24h:.0f} Ton", "Üretime")
            
            net_fark = giris_24h - cikis_24h
            if net_fark > 0:
                st.caption(f"📈 Depoya +{net_fark:.0f} ton eklendi")
            else:
                st.caption(f"📉 Depodan {abs(net_fark):.0f} ton eksildi")

    st.markdown("---")

    # ==============================================================================
    # 2. SİLO KARTLARI (MEVCUT GÖRÜNÜM)
    # ==============================================================================
    st.subheader(f"🏭 Anlık Silo Durumu (Toplam: {toplam_stok:,.0f} Ton)")
    
    num_silos = len(df_silo)
    cols_per_row = 4
    
    for i in range(0, num_silos, cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < num_silos:
                with cols[j]:
                    show_silo_card_detailed(df_silo.iloc[i + j])
