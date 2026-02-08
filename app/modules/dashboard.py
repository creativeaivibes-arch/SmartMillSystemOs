import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# --- CORE VE DATABASE IMPORTLARI ---
from app.core.database import fetch_data, get_conn
from app.core.styles import card_metric
from app.core.error_handling import error_handler, log_warning
from app.core.languages import t  # ✅ DEĞIŞIKLIK: get_text yerine t kullanacağız

# PDF Rapor Fonksiyonları (Senin Orijinal Raporlama Sistemin)
try:
    from app.modules.reports import create_silo_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    def create_silo_pdf_report(*args): return None
    def turkce_karakter_duzelt_pdf(x): return x

# --- AYARLAR (CONFIG) - MAGIC NUMBERS ---
DASHBOARD_CONFIG = {
    'REFRESH_INTERVAL': 300,       # 5 dakika (Cache süresi)
    'RECENT_DAYS': 7,              # Son kaç günün verisi
    'CRITICAL_CAPACITY': 0.95,     # Kırmızı alarm seviyesi (%95)
    'WARNING_CAPACITY': 0.85,      # Sarı alarm seviyesi (%85)
    'LOW_STOCK_CAPACITY': 0.15,    # Düşük stok uyarısı (%15)
    'TARGET_PROTEIN': 11.5         # Hedef protein alt limiti
}

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

# --------------------------------------------------------------------------
# VERİ KATMANI (DATA LAYER) - GÜVENLİ VE HIZLI
# --------------------------------------------------------------------------
def fetch_all_dashboard_data():
    """Tüm verileri tek seferde çeker, temizler ve session_state'e kaydeder"""
    with st.spinner('📊 Veriler güncelleniyor...'):
        try:
            data = {
                'silolar': fetch_data("silolar"),
                'hareketler': fetch_data("hareketler"),
                'uretim_kaydi': fetch_data("uretim_kaydi") 
            }
            
            # --- 1. SİLO VERİSİ KONTROLÜ VE TEMİZLİĞİ ---
            df_silo = data['silolar']
            if not df_silo.empty:
                # Kritik sütunlar yoksa oluştur ve 0 bas (Sütun Varlık Kontrolü)
                critical_cols = ['protein', 'gluten', 'hektolitre', 'maliyet', 'kapasite', 'mevcut_miktar']
                for col in critical_cols:
                    if col not in df_silo.columns:
                        df_silo[col] = 0
                    else:
                        # Sayısal dönüşüm (hatalı verileri 0 yapar)
                        df_silo[col] = pd.to_numeric(df_silo[col], errors='coerce').fillna(0)

                if 'isim' in df_silo.columns:
                    df_silo = df_silo.sort_values('isim')
                data['silolar'] = df_silo

            # --- 2. HAREKET VERİSİ TARİH KONTROLÜ ---
            df_hareket = data['hareketler']
            if not df_hareket.empty:
                if 'tarih' not in df_hareket.columns:
                     df_hareket['tarih'] = datetime.now()
                
                # Tarih formatını zorla, bozuk olanları temizle (Tarih Sütunu Kontrolü)
                df_hareket['tarih'] = pd.to_datetime(df_hareket['tarih'], errors='coerce')
                df_hareket = df_hareket.dropna(subset=['tarih'])
                data['hareketler'] = df_hareket

        except Exception as e:
            st.error(f"Veri işleme hatası: {e}")
            return {}
            
    # Session state'e kaydet
    st.session_state['dashboard_data'] = data
    st.session_state['dashboard_last_update'] = datetime.now()
    
    return data

def get_dashboard_data(force_refresh=False):
    """Veriyi session state'den getirir, yoksa yeni çeker (Cache Mekanizması)"""
    if not force_refresh and 'dashboard_data' in st.session_state:
        last_update = st.session_state.get('dashboard_last_update', datetime.min)
        # Config'den süreyi al
        if (datetime.now() - last_update).total_seconds() < DASHBOARD_CONFIG['REFRESH_INTERVAL']:
            return st.session_state['dashboard_data']
            
    return fetch_all_dashboard_data()

# --------------------------------------------------------------------------
# SİLO KARTI (ÇOK DİLLİ HALE GETİRİLDİ) ✅
# --------------------------------------------------------------------------
def show_silo_card(silo_data):
    with st.container(border=True):
        # Doluluk hesaplama
        kapasite = float(silo_data.get('kapasite', 1))
        mevcut = float(silo_data.get('mevcut_miktar', 0))
        doluluk = mevcut / kapasite if kapasite > 0 else 0
        
        st.markdown(f"#### {silo_data.get('isim', 'Silo')}")
        
        # ✅ ÇEVİRİ: Birim Maliyet
        maliyet = float(silo_data.get('maliyet', 0))
        st.markdown(f"**{t('dash_unit_cost')}:** {maliyet:.2f} {t('lbl_currency')}")
        
        # ✅ ÇEVİRİ: Cins
        bugday_cinsi = str(silo_data.get('bugday_cinsi', '-'))
        st.caption(f"**{t('lbl_variety')}:** {bugday_cinsi}")
        
        # ✅ ÇEVİRİ: Tavlı Buğday Stok
        tavli_stok = float(silo_data.get('tavli_bugday_stok', 0))
        st.caption(f"**{t('lbl_tempered_stock')}:** {tavli_stok:.1f} Ton")
        
        # Orijinal Silo Görseli
        st.markdown(draw_silo(doluluk, ""), unsafe_allow_html=True)
        st.markdown(f"**{mevcut:.1f} / {kapasite:.0f} Ton**")
        
        # ✅ ÇEVİRİ: Yönetici Cins Düzenleme
        if st.session_state.get('user_role') == "admin":
            with st.popover(f"✏️ {t('btn_edit_variety')}", use_container_width=True):
                yeni_cins = st.text_input(
                    t('label_variety'), 
                    value=bugday_cinsi if bugday_cinsi != "-" else "", 
                    key=f"c_{silo_data['isim']}"
                )
                if st.button(t('btn_submit'), key=f"s_{silo_data['isim']}"):
                    # Güncelleme mantığı (fetch_data -> update)
                    conn = get_conn()
                    df_all = fetch_data("silolar")
                    df_all.loc[df_all['isim'] == silo_data['isim'], 'bugday_cinsi'] = yeni_cins
                    conn.update(worksheet="silolar", data=df_all)
                    st.rerun()

        # ✅ ÇEVİRİ: PDF RAPOR BUTONU
        st.divider()
        safe_name = str(silo_data.get('isim', 'silo')).replace(" ", "_")
        if st.button(
            t('btn_download_pdf'), 
            key=f"pdf_{safe_name}", 
            use_container_width=True, 
            type="primary"
        ):
            with st.spinner("Rapor hazırlanıyor..."):
                try:
                    from app.modules.mixing import get_tavli_analiz_agirlikli_ortalama
                    from app.modules.wheat import get_kuru_bugday_agirlikli_ortalama
                    
                    tavli_ort = get_tavli_analiz_agirlikli_ortalama(silo_data['isim'])
                    kuru_ort = get_kuru_bugday_agirlikli_ortalama(silo_data['isim'])
                    
                    pdf_bytes = create_silo_pdf_report(
                        silo_data['isim'], 
                        silo_data, 
                        tavli_ort, 
                        kuru_ort
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
                    st.error(f"Rapor oluşturma hatası: {e}")

# --------------------------------------------------------------------------
# ANA DASHBOARD EKRANI (ÇOK DİLLİ HALE GETİRİLDİ) ✅
# --------------------------------------------------------------------------
def show():
    """Ana Dashboard Görünümü - Modern ve Temiz Tasarım"""
    
    # ===== HEADER VE YENİLEME BUTONU =====
    col_h1, col_h2 = st.columns([3, 1])
    
    with col_h1:
        # ✅ ÇEVİRİ: Başlık
        st.title(t('dash_header'))
    
    with col_h2:
        # ✅ ÇEVİRİ: Yenile Butonu
        if st.button(f"🔄 {t('btn_refresh')}", use_container_width=True):
            get_dashboard_data(force_refresh=True)
            st.rerun()
    
    # Veri çekme
    data = get_dashboard_data()
    
    if not data:
        st.error("⚠️ Veri yüklenemedi. Lütfen bağlantıyı kontrol edin.")
        return
    
    df_silo = data.get('silolar', pd.DataFrame())
    df_hareket = data.get('hareketler', pd.DataFrame())
    
    if df_silo.empty:
        st.warning("📭 Gösterilecek silo verisi bulunamadı.")
        return
    
    # ===== 1. ÖZET METRİKLER (KPI KARTLARI) =====
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        toplam_stok = df_silo['mevcut_miktar'].sum()
        st.metric(
            label="📦 Toplam Stok", 
            value=f"{toplam_stok:,.0f} Ton"
        )
    
    with col2:
        # ✅ ÇEVİRİ: Stok Değeri
        stok_degeri = (df_silo['mevcut_miktar'] * df_silo['maliyet']).sum()
        st.metric(
            label=f"💰 {t('dash_stock_value')}", 
            value=f"{stok_degeri:,.0f} {t('lbl_currency').split('/')[0]}"
        )
    
    with col3:
        # ✅ ÇEVİRİ: Ortalama Maliyet
        if toplam_stok > 0:
            ort_maliyet = stok_degeri / toplam_stok
            st.metric(
                label=f"💵 {t('dash_avg_cost')}", 
                value=f"{ort_maliyet:.2f} {t('lbl_currency')}"
            )
        else:
            st.metric(label=f"💵 {t('dash_avg_cost')}", value="0.00")
    
    with col4:
        # ✅ ÇEVİRİ: Stok Ömrü (Kalan Süre)
        gunluk_kirma = 150  # Config'den alınabilir
        kalan_gun = int(toplam_stok / gunluk_kirma) if gunluk_kirma > 0 else 0
        st.metric(
            label=f"⏳ {t('dash_stock_life')}", 
            value=f"{kalan_gun} Gün"
        )
    
    st.divider()
    
    # ===== 2. AKILLI UYARI SİSTEMİ =====
    # ✅ ÇEVİRİ: Uyarı Sistemi Başlığı
    st.subheader(t('dash_alert_title'))
    
    uyarilar = []
    
    for idx, silo in df_silo.iterrows():
        kapasite = float(silo.get('kapasite', 1))
        mevcut = float(silo.get('mevcut_miktar', 0))
        doluluk_oran = mevcut / kapasite if kapasite > 0 else 0
        protein = float(silo.get('protein', 0))
        
        # Kapasite Uyarıları
        if doluluk_oran >= DASHBOARD_CONFIG['CRITICAL_CAPACITY']:
            uyarilar.append({
                'tip': 'critical',
                'mesaj': f"🔴 **{silo['isim']}**: Kapasite doldu! (%{doluluk_oran*100:.0f})"
            })
        elif doluluk_oran >= DASHBOARD_CONFIG['WARNING_CAPACITY']:
            uyarilar.append({
                'tip': 'warning',
                'mesaj': f"🟡 **{silo['isim']}**: Kapasite yüksek (%{doluluk_oran*100:.0f})"
            })
        elif doluluk_oran <= DASHBOARD_CONFIG['LOW_STOCK_CAPACITY']:
            # ✅ ÇEVİRİ: Düşük Stok Uyarısı
            uyarilar.append({
                'tip': 'info',
                'mesaj': f"🔵 **{silo['isim']}**: {t('msg_stock_low')} (%{doluluk_oran*100:.0f})"
            })
        
        # Protein Uyarısı
        if protein > 0 and protein < DASHBOARD_CONFIG['TARGET_PROTEIN']:
            uyarilar.append({
                'tip': 'warning',
                'mesaj': f"🟡 **{silo['isim']}**: Düşük protein ({protein:.1f}%)"
            })
    
    # Uyarıları göster
    if uyarilar:
        col_u1, col_u2 = st.columns(2)
        
        critical_warnings = [u for u in uyarilar if u['tip'] == 'critical']
        other_warnings = [u for u in uyarilar if u['tip'] != 'critical']
        
        with col_u1:
            if critical_warnings:
                for uyari in critical_warnings:
                    st.error(uyari['mesaj'])
        
        with col_u2:
            if other_warnings:
                for uyari in other_warnings:
                    if uyari['tip'] == 'warning':
                        st.warning(uyari['mesaj'])
                    else:
                        st.info(uyari['mesaj'])
        
        if not critical_warnings and not other_warnings:
            st.success("🟢 Tüm sistemler normal - Kritik durum yok")
    else:
        st.success("🟢 Tüm sistemler normal - Kritik durum yok")

    st.divider()

    # ===== 3. TREND GRAFİĞİ + KALİTE SKORKART =====
    col_trend, col_quality = st.columns([2, 1])
    
    with col_trend:
        # ✅ ÇEVİRİ: Stok Hareketi Başlığı
        st.subheader(t('dash_stock_move_7d'))
        
        if not df_hareket.empty and 'tarih' in df_hareket.columns:
            # Son 7 günü filtrele
            son_7gun = df_hareket[df_hareket['tarih'] >= (datetime.now() - timedelta(days=DASHBOARD_CONFIG['RECENT_DAYS']))].copy()
            
            if not son_7gun.empty:
                # Günlük toplam giriş/çıkış
                son_7gun['gun'] = son_7gun['tarih'].dt.date
                
                gunluk_giris = son_7gun[son_7gun['hareket_tipi'] == 'Giriş'].groupby('gun')['miktar'].sum().reset_index()
                gunluk_giris.columns = ['Tarih', 'Giriş']
                
                gunluk_cikis = son_7gun[son_7gun['hareket_tipi'] == 'Çıkış'].groupby('gun')['miktar'].sum().reset_index()
                gunluk_cikis.columns = ['Tarih', 'Çıkış']
                
                # Merge
                gunluk = pd.merge(gunluk_giris, gunluk_cikis, on='Tarih', how='outer').fillna(0)
                gunluk['Net'] = gunluk['Giriş'] - gunluk['Çıkış']
                gunluk = gunluk.sort_values('Tarih')
                
                # Tarih formatını düzelt (sadece gün.ay)
                gunluk['Tarih_Formatli'] = pd.to_datetime(gunluk['Tarih']).dt.strftime('%d.%m')
                
                # Plotly grafiği
                try:
                    import plotly.graph_objects as go
                    
                    fig = go.Figure()
                    
                    # ✅ ÇEVİRİ: Grafik Legend
                    fig.add_trace(go.Bar(
                        x=gunluk['Tarih_Formatli'],
                        y=gunluk['Giriş'],
                        name=t('dash_input'),
                        marker_color='#4CAF50'
                    ))
                    
                    fig.add_trace(go.Bar(
                        x=gunluk['Tarih_Formatli'],
                        y=gunluk['Çıkış'],
                        name=t('dash_output'),
                        marker_color='#F44336'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=gunluk['Tarih_Formatli'],
                        y=gunluk['Net'],
                        name='Net Değişim',
                        mode='lines+markers',
                        line=dict(color='#2196F3', width=3),
                        marker=dict(size=8)
                    ))
                    
                    fig.update_layout(
                        barmode='group',
                        height=250,
                        margin=dict(l=20, r=20, t=20, b=20),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        xaxis_title="",
                        yaxis_title="Tonaj"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                except ImportError:
                    # Fallback: Basit metrik gösterimi
                    st.info("📊 Grafik için plotly kütüphanesi gerekli")
                    col_g1, col_g2, col_g3 = st.columns(3)
                    col_g1.metric("Toplam Giriş", f"{gunluk['Giriş'].sum():.1f} T")
                    col_g2.metric("Toplam Çıkış", f"{gunluk['Çıkış'].sum():.1f} T")
                    col_g3.metric("Net", f"{gunluk['Net'].sum():+.1f} T")
            else:
                st.info("📭 Son 7 günde hareket kaydı yok")
        else:
            st.info("📭 Henüz stok hareketi kaydı bulunmuyor")
    
    with col_quality:
        st.subheader("🧪 Kalite Profili")
        
        with st.container(border=True):
            # Ağırlıklı ortalama kalite parametreleri
            toplam_tonaj = df_silo['mevcut_miktar'].sum()
            
            if toplam_tonaj > 0:
                # Protein ortalaması
                avg_protein = (df_silo['mevcut_miktar'] * df_silo['protein']).sum() / toplam_tonaj
                # Gluten ortalaması (eğer varsa)
                avg_gluten = (df_silo['mevcut_miktar'] * df_silo['gluten']).sum() / toplam_tonaj if 'gluten' in df_silo.columns else 0
                # Hektolitre ortalaması (eğer varsa)
                avg_hektolitre = (df_silo['mevcut_miktar'] * df_silo['hektolitre']).sum() / toplam_tonaj if 'hektolitre' in df_silo.columns else 0
                
                # Protein skoru (10-15 arası ideal)
                protein_skor = min(100, max(0, (avg_protein - 10) / 5 * 100)) if avg_protein > 0 else 0
                
                st.metric("Ort. Protein", f"{avg_protein:.2f}%")
                st.progress(protein_skor / 100)
                
                if avg_gluten > 0:
                    gluten_skor = min(100, max(0, (avg_gluten - 20) / 15 * 100))
                    st.metric("Ort. Gluten", f"{avg_gluten:.2f}%")
                    st.progress(gluten_skor / 100)
                
                if avg_hektolitre > 0:
                    hekto_skor = min(100, max(0, (avg_hektolitre - 70) / 15 * 100))
                    st.metric("Ort. Hektolitre", f"{avg_hektolitre:.1f}")
                    st.progress(hekto_skor / 100)
                
                # Genel skor
                genel_skor = protein_skor
                if genel_skor >= 80:
                    st.success(f"📊 Genel Skor: {genel_skor:.0f}/100 (MÜKEMMEL)")
                elif genel_skor >= 60:
                    st.info(f"📊 Genel Skor: {genel_skor:.0f}/100 (İYİ)")
                else:
                    st.warning(f"📊 Genel Skor: {genel_skor:.0f}/100 (ORTA)")
            else:
                st.info("📭 Henüz stok bulunmuyor")

    st.divider()

    # ===== 5. ANLIK SİLO DURUMU =====
    # ✅ ÇEVİRİ: Anlık Silo Durumu Başlığı
    st.subheader(t('dash_live_status'))
    
    # Veri setindeki silo sayısını al
    num_silos = len(df_silo)
    
    if num_silos > 0:
        # Siloları 4'lü sütunlar halinde diz
        for i in range(0, num_silos, 4):
            cols = st.columns(4)
            for j in range(4):
                if i + j < num_silos:
                    with cols[j]:
                        # Tekil silo kartını çağır
                        show_silo_card(df_silo.iloc[i + j])
    else:
        st.info("📭 Gösterilecek aktif silo verisi bulunamadı.")
