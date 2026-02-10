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
    """
    DASHBOARD ÖNBELLEK İPTALİ (DÜZELTİLDİ)
    Artık 5 dakika beklemez, Admin panelindeki değişikliği anında görür.
    """
    # Eski zamanlayıcı (if ... timer < 300) kodunu sildik.
    # Doğrudan güncel veriyi çekmesini söylüyoruz.
    return fetch_all_dashboard_data()
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
    """
    OPTIMAL DASHBOARD - PROFESYONEL VERSİYON (REVİZE EDİLMİŞ)
    - Finansal özet
    - Akıllı uyarı sistemi
    - Trend grafiği
    - Kalite skorkart
    - Silo kartları
    """
    
    # 1. ÜST KONTROL PANELİ (YENİLE BUTONU VE BAŞLIK)
    col_title, col_refresh, col_info = st.columns([6, 1, 2])
    
    with col_title:
        st.markdown("<h2 style='color:#0B4F6C; margin:0;'>🏭 Fabrika Kontrol Merkezi</h2>", unsafe_allow_html=True)
    
    with col_refresh:
        # Manuel Yenileme Butonu
        if st.button("🔄 Yenile", use_container_width=True):
            st.cache_data.clear() # Streamlit cache temizle
            get_dashboard_data(force_refresh=True) # Session cache yenile
            st.success("Güncellendi!")
            time.sleep(0.5)
            st.rerun()
            
    with col_info:
        # Son güncelleme bilgisini göster
        if 'dashboard_last_update' in st.session_state:
            last_up = st.session_state['dashboard_last_update'].strftime('%H:%M:%S')
            st.caption(f"🕒 Son Güncelleme: {last_up}")
    
    st.divider()

    # 2. VERİLERİ GETİR (YENİ SÖZLÜK YAPISINDAN AYIKLA)
    data = get_dashboard_data()
    
    # Yeni sistemden gelen veriyi eski değişken isimlerine ata
    # Böylece alt satırlardaki kodlar bozulmaz.
    df_silo = data.get('silolar', pd.DataFrame())
    df_hareket = data.get('hareketler', pd.DataFrame())
    
    # Veri Kontrolü
    if df_silo.empty:
        st.warning("⚠️ Henüz silo tanımlanmamış veya veri çekilemedi. Yönetim Paneli'nden silo ekleyin.")
        return

    # ===== 3. ÜST YÖNETİCİ ŞERİDİ (FİNANS + STOK ÖMRÜ + 24 SAAT) =====
    with st.container(border=True):
        col_fin, col_sim, col_24h = st.columns([1, 1.5, 1])
        
        toplam_stok = df_silo['mevcut_miktar'].sum()
        toplam_deger = (df_silo['mevcut_miktar'] * df_silo['maliyet'] * 1000).sum()
        
        with col_fin:
            st.markdown("### 💰 Finans")
            st.metric("Stok Değeri", f"{toplam_deger/1_000_000:.2f}M ₺")
            avg_maliyet = (toplam_deger / (toplam_stok * 1000)) if toplam_stok > 0 else 0
            st.metric("Ort. Maliyet", f"{avg_maliyet:.2f} TL/Kg")
            
        with col_sim:
            st.markdown("### ⏳ Stok Ömrü")
            gunluk = st.number_input("Günlük Kırma (Ton)", value=80, step=10, key="dashboard_gunluk_kirma")
            if gunluk > 0:
                omur = toplam_stok / gunluk
                st.metric("Kalan Süre", f"{omur:.1f} Gün")
                st.progress(min(1.0, omur/30))
            else:
                st.metric("Kalan Süre", "N/A")
                
        with col_24h:
            st.markdown("### 🚛 Son 24 Saat")
            # Son 24 saatteki hareketler
            if not df_hareket.empty and 'tarih' in df_hareket.columns:
                try:
                    df_hareket['tarih'] = pd.to_datetime(df_hareket['tarih'], errors='coerce')
                    son_24h = df_hareket[df_hareket['tarih'] >= (datetime.now() - timedelta(hours=24))]
                    
                    giris_24h = son_24h[son_24h['hareket_tipi'] == 'Giriş']['miktar'].sum()
                    cikis_24h = son_24h[son_24h['hareket_tipi'] == 'Çıkış']['miktar'].sum()
                    
                    st.metric("Giriş", f"{giris_24h:.1f} T", delta=f"+{giris_24h:.1f}")
                    st.metric("Çıkış", f"{cikis_24h:.1f} T", delta=f"-{cikis_24h:.1f}")
                except:
                     st.metric("Veri Hatası", "-")
            else:
                st.metric("Hareket Yok", "-")

    st.divider()

    # ===== 2. AKILLI UYARI SİSTEMİ (ÜST KISIM) =====
    st.subheader("⚠️ Akıllı Uyarı Sistemi")
    
    uyarilar = []
    
    for _, silo in df_silo.iterrows():
        kapasite = float(silo.get('kapasite', 1))
        mevcut = float(silo.get('mevcut_miktar', 0))
        
        if kapasite > 0:
            doluluk = mevcut / kapasite
            
            # Taşma riski
            if doluluk > 0.95:
                uyarilar.append({
                    'tip': 'critical',
                    'mesaj': f"🔴 **{silo['isim']}**: Kapasite %{doluluk*100:.0f} - TAŞMA RİSKİ!"
                })
            elif doluluk > 0.85:
                uyarilar.append({
                    'tip': 'warning',
                    'mesaj': f"🟡 **{silo['isim']}**: Kapasite %{doluluk*100:.0f} - Yakında dolacak"
                })
            
            # Düşük stok uyarısı
            if doluluk < 0.15 and mevcut > 0:
                uyarilar.append({
                    'tip': 'info',
                    'mesaj': f"🔵 **{silo['isim']}**: Stok azalıyor (%{doluluk*100:.0f})"
                })
        
        # Kalite uyarıları
        protein = float(silo.get('protein', 0))
        if protein > 0 and protein < 11.5:
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
        st.subheader("📈 Son 7 Günlük Stok Hareketi")
        
        if not df_hareket.empty and 'tarih' in df_hareket.columns:
            # Son 7 günü filtrele
            son_7gun = df_hareket[df_hareket['tarih'] >= (datetime.now() - timedelta(days=7))].copy()
            
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
                    
                    fig.add_trace(go.Bar(
                        x=gunluk['Tarih_Formatli'],
                        y=gunluk['Giriş'],
                        name='Giriş',
                        marker_color='#4CAF50'
                    ))
                    
                    fig.add_trace(go.Bar(
                        x=gunluk['Tarih_Formatli'],
                        y=gunluk['Çıkış'],
                        name='Çıkış',
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

    # ===== 5. ANLIK SİLO DURUMU (YENİ VERİ YAPISI İLE) =====
    st.subheader("🏭 Anlık Silo Durumu")
    
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







