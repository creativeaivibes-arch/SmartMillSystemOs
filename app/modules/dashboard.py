import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --- CORE VE DATABASE IMPORTLARI ---
from app.core.database import fetch_data, get_conn
from app.core.styles import card_metric
from app.core.error_handling import error_handler, log_warning

# PDF Rapor Fonksiyonları (Senin Orijinal Raporlama Sistemin)
try:
    from app.modules.reports import create_silo_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    def create_silo_pdf_report(*args): return None
    def turkce_karakter_duzelt_pdf(x): return x

# --------------------------------------------------------------------------
# SİLO GÖRSELLEŞTİRME (Senin Orijinal draw_silo Fonksiyonun)
# --------------------------------------------------------------------------
def draw_silo(fill_ratio, name):
    try:
        fill_ratio = float(fill_ratio)
        fill_ratio = max(0.0, min(1.0, fill_ratio))
    except: fill_ratio = 0.0
    
    height = 100
    fill_height = int(height * fill_ratio)
    empty_height = height - fill_height
    
    if fill_ratio < 0.4: fill_color = "rgb(255, 100, 100)"
    elif fill_ratio >= 0.9: fill_color = "rgb(100, 255, 100)"
    else: fill_color = "rgb(100, 100, 255)"
    
    svg = f'''<svg width="60" height="{height + 10}">
        <rect x="10" y="5" width="40" height="{height}" rx="5" ry="5" 
              style="fill: #f0f2f6; stroke: #333; stroke-width:2;"/>
        <rect x="10" y="{5 + empty_height}" width="40" height="{fill_height}" 
              rx="5" ry="5" style="fill: {fill_color}; stroke: none;"/>
        <text x="30" y="{height + 5}" font-size="8" text-anchor="middle" fill="#333">{name}</text>
    </svg>'''
    return svg

@error_handler(context="Dashboard Veri")
def get_dashboard_data():
    try:
        # CACHE EKLE - 30 saniyede bir güncelle (API kota optimizasyonu)
        @st.cache_data(ttl=30)
        def cached_silo_fetch():
            return fetch_data("silolar")
        
        @st.cache_data(ttl=30)
        def cached_hareket_fetch():
            return fetch_data("hareketler")
        
        df_silo = cached_silo_fetch()
        if df_silo.empty:
            df_silo = pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet', 'tavli_bugday_stok'])
        
        df_silo = df_silo.fillna(0)
        if 'isim' in df_silo.columns: df_silo = df_silo.sort_values('isim')
        
        df_hareket = cached_hareket_fetch()
        return df_silo, df_hareket
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

# --------------------------------------------------------------------------
# SİLO KARTI (Senin "Aynı Kalsın" Dediğin Orijinal Kart Yapısı)
# --------------------------------------------------------------------------
def show_silo_card(silo_data):
    with st.container(border=True):
        # Doluluk hesaplama
        kapasite = float(silo_data.get('kapasite', 1))
        mevcut = float(silo_data.get('mevcut_miktar', 0))
        doluluk = mevcut / kapasite if kapasite > 0 else 0
        
        st.markdown(f"#### {silo_data.get('isim', 'Silo')}")
        
        # Maliyet ve Cins Bilgisi
        maliyet = float(silo_data.get('maliyet', 0))
        st.markdown(f"**Birim Maliyet:** {maliyet:.2f} TL/KG")
        
        bugday_cinsi = str(silo_data.get('bugday_cinsi', '-'))
        st.caption(f"**Cins:** {bugday_cinsi}")
        
        # Tavlı Stok Bilgisi
        tavli_stok = float(silo_data.get('tavli_bugday_stok', 0))
        st.caption(f"**Tavlı Buğday Stok:** {tavli_stok:.1f} Ton")
        
        # Orijinal Silo Görseli
        st.markdown(draw_silo(doluluk, ""), unsafe_allow_html=True)
        st.markdown(f"**{mevcut:.1f} / {kapasite:.0f} Ton**")
        
        # Yönetici Cins Düzenleme
        if st.session_state.get('user_role') == "admin":
            with st.popover("✏️ Cins Düzenle", use_container_width=True):
                yeni_cins = st.text_input("Buğday Cinsi", value=bugday_cinsi if bugday_cinsi != "-" else "", key=f"c_{silo_data['isim']}")
                if st.button("Kaydet", key=f"s_{silo_data['isim']}"):
                    # Güncelleme mantığı (fetch_data -> update)
                    conn = get_conn()
                    df_all = fetch_data("silolar")
                    df_all.loc[df_all['isim'] == silo_data['isim'], 'bugday_cinsi'] = yeni_cins
                    conn.update(worksheet="silolar", data=df_all)
                    st.rerun()

        # SENİN İSTEDİĞİN ORİJİNAL PDF RAPOR BUTONU
st.divider()
safe_name = str(silo_data.get('isim', 'silo')).replace(" ", "_")
if st.button("📥 PDF Rapor İndir", key=f"pdf_{safe_name}", use_container_width=True, type="primary"):
    with st.spinner("Rapor hazırlanıyor..."):
        try:
            from app.modules.mixing import get_tavli_analiz_agirlikli_ortalama
            from app.modules.wheat import get_kuru_bugday_agirlikli_ortalama  # YENİ!
            
            tavli_ort = get_tavli_analiz_agirlikli_ortalama(silo_data['isim'])
            kuru_ort = get_kuru_bugday_agirlikli_ortalama(silo_data['isim'])  # YENİ!
            
            pdf_bytes = create_silo_pdf_report(
                silo_data['isim'], 
                silo_data, 
                tavli_ort, 
                kuru_ort  # YENİ PARAMETRE!
            )
            
            if pdf_bytes:
                st.download_button(
                    label="💾 İndirmeyi Başlat",
                    data=pdf_bytes,
                    file_name=f"SILO_RAPORU_{turkce_karakter_duzelt_pdf(silo_data['isim'])}.pdf",
                    mime="application/pdf",
                    key=f"dl_{safe_name}"
                )
        except Exception as e:
            st.error(f"Rapor hatası: {e}")

# --------------------------------------------------------------------------
# ANA DASHBOARD
# --------------------------------------------------------------------------
def show_dashboard():
    df_silo, df_hareket = get_dashboard_data()
    if df_silo.empty:
        st.warning("Silo bulunamadı.")
        return

    # --- ÜST YÖNETİCİ ŞERİDİ (KATILDIĞIN ÖNERİLER) ---
    st.markdown("<h2 style='color:#0B4F6C;'>🏭 Fabrika Kontrol Merkezi</h2>", unsafe_allow_html=True)
    
    with st.container(border=True):
        col_fin, col_sim, col_24h = st.columns([1, 1.5, 1])
        toplam_stok = df_silo['mevcut_miktar'].sum()
        toplam_deger = (df_silo['mevcut_miktar'] * df_silo['maliyet'] * 1000).sum()
        
        with col_fin:
            st.markdown("### 💰 Finans")
            st.metric("Stok Değeri", f"{toplam_deger/1_000_000:.2f}M ₺")
            avg_maliyet = (toplam_deger / (toplam_stok * 1000)) if toplam_stok > 0 else 0
            st.metric("Ort. Maliyet", f"{avg_maliyet:.2f} TL")
            
        with col_sim:
            st.markdown("### ⏳ Stok Ömrü")
            gunluk = st.number_input("Günlük Kırma (Ton)", value=80, step=10)
            if gunluk > 0:
                omur = toplam_stok / gunluk
                st.metric("Kalan Süre", f"{omur:.1f} Gün")
                st.progress(min(1.0, omur/30))
                
        with col_24h:
            st.markdown("### 🚛 24 Saat")
            # Basit son 24 saat filtresi logic'i buraya eklenebilir
            st.metric("Toplam Stok", f"{toplam_stok:,.0f} Ton")

    st.divider()

    # --- SİLO KARTLARI (KAPSAMI VE GÖRÜNÜMÜ KORUNAN BÖLÜM) ---
    st.subheader("🏭 Anlık Silo Durumu")
    num_silos = len(df_silo)
    for i in range(0, num_silos, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < num_silos:
                with cols[j]:
                    show_silo_card(df_silo.iloc[i + j])



