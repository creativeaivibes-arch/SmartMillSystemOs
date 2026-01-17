import streamlit as st
import pandas as pd
import time
from datetime import datetime
# DİKKAT: Artık get_db_connection yok, fetch_data ve get_conn var
from app.core.database import fetch_data, get_conn
from app.core.error_handling import error_handler, log_debug, log_info, log_warning, ERROR_HANDLING_AVAILABLE
from app.core.utils import turkce_karakter_duzelt
from app.core.styles import card_metric

# PDF rapor fonksiyonları
# (Eğer reports modülünde hata alırsan o dosyayı da güncellememiz gerekebilir ama şimdilik kalsın)
try:
    from app.modules.reports import create_silo_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    # Eğer modül bulunamazsa program çökmesin diye boş fonksiyonlar
    def create_silo_pdf_report(*args): return None
    def turkce_karakter_duzelt_pdf(x): return x

def draw_silo(fill_ratio, name):
    """Silo görseli çiz - Thread-safe version"""
    try:
        fill_ratio = float(fill_ratio)
        fill_ratio = max(0.0, min(1.0, fill_ratio))  # 0-1 arasına sınırla
    except (ValueError, TypeError):
        fill_ratio = 0.0
    
    height = 100
    fill_height = int(height * fill_ratio)
    empty_height = height - fill_height
    
    # Renk hesaplama (daha güvenli)
    try:
        color_val = 255 - int(fill_ratio * 150)
        color_val = max(0, min(255, color_val))  # 0-255 arasına sınırla
        
        if fill_ratio < 0.4:
            fill_color = f"rgb(255, {color_val}, {color_val})"
        elif fill_ratio >= 0.9:
            fill_color = f"rgb({color_val}, 255, {color_val})"
        else:
            fill_color = f"rgb({color_val}, {color_val}, 255)"
    except:
        fill_color = "rgb(200, 200, 200)"  # Varsayılan gri renk
    
    svg = f'''<svg width="60" height="{height + 10}">
        <rect x="10" y="5" width="40" height="{height}" rx="5" ry="5" 
              style="fill: #f0f2f6; stroke: #333; stroke-width:2;"/>
        <rect x="10" y="{5 + empty_height}" width="40" height="{fill_height}" 
              rx="5" ry="5" style="fill: {fill_color}; stroke: none;"/>
        <text x="30" y="{height + 5}" font-size="8" text-anchor="middle" 
              fill="#333">{name}</text>
    </svg>'''
    return svg

@error_handler(context="Silo Verisi Getirme")
def get_silo_data():
    """Silo verilerini güvenli şekilde getir - GOOGLE SHEETS UYUMLU"""
    
    log_debug("Silo verileri getiriliyor (Google Sheets)", "Dashboard")
    
    try:
        # SQL yerine fetch_data kullanıyoruz
        df = fetch_data("silolar")
        
        # Eğer veri boşsa boş DataFrame dön
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])

        # NaN değerleri temizle
        df = df.fillna({
            'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
            'sedim': 0, 'maliyet': 0, 'bugday_cinsi': '', 'mevcut_miktar': 0, 'kapasite': 100
        })
        
        # İsim sırasına göre diz (SQL'deki ORDER BY yerine)
        if 'isim' in df.columns:
            df = df.sort_values('isim')

        log_debug(f"{len(df)} silo verisi getirildi", "Dashboard")
        return df
            
    except Exception as e:
        log_warning(f"Silo verisi çekme hatası: {e}", "Dashboard")
        return pd.DataFrame()

def update_silo_cinsi(silo_isim, yeni_cins):
    """Silo buğday cinsini güncelle - GOOGLE SHEETS UYUMLU"""
    try:
        conn = get_conn()
        # 1. Mevcut veriyi çek
        df = fetch_data("silolar")
        
        if df.empty:
            return False

        # 2. İlgili satırı bul ve güncelle
        # Pandas ile filtreleme yapıyoruz
        mask = df['isim'] == silo_isim
        if mask.any():
            df.loc[mask, 'bugday_cinsi'] = yeni_cins[:50]
            
            # 3. Güncellenmiş tabloyu Google Sheets'e geri yükle
            conn.update(worksheet="silolar", data=df)
            return True
        return False
        
    except Exception as e:
        st.error(f"Güncelleme hatası: {str(e)}")
        return False

def show_silo_card(silo_data):
    """Tek bir silo kartını göster"""
    try:
        with st.container(border=True):
            # Doluluk oranını güvenli hesapla
            try:
                kapasite = float(silo_data.get('kapasite', 1))
                mevcut = float(silo_data.get('mevcut_miktar', 0))
                doluluk_orani = mevcut / kapasite if kapasite > 0 else 0
            except:
                doluluk_orani = 0
            
            st.markdown(f"#### {silo_data.get('isim', 'Silo')}")
            
            # Maliyet bilgisi
            try:
                maliyet = float(silo_data.get('maliyet', 0))
            except:
                maliyet = 0
                
            if maliyet > 0:
                st.markdown(f"**Birim Maliyet:** {maliyet:.2f} TL/KG")
            else:
                st.markdown("**Birim Maliyet:** -")
            
            # Buğday cinsi
            bugday_cinsi = str(silo_data.get('bugday_cinsi', '')).strip()
            if not bugday_cinsi or bugday_cinsi == "nan":
                bugday_cinsi = "-"
            st.caption(f"**Cins:** {bugday_cinsi}")
            
            # Tavlı Buğday Stok Bilgisi (Sütun varsa göster)
            tavli_stok = float(silo_data.get('tavli_bugday_stok', 0))
            st.caption(f"**Tavlı Buğday Stok:** {tavli_stok:.1f} Ton")
            
            # Silo görseli
            st.markdown(draw_silo(doluluk_orani, ""), unsafe_allow_html=True)
            
            # Miktar bilgisi
            st.markdown(f"**{mevcut:.1f} / {kapasite:.0f} Ton**")
            
            # Yönetici ise buğday cinsi düzenleme
            # Hata almamak için session state kontrolü
            if st.session_state.get('user_role') == "admin":
                with st.popover("✏️ Cins Düzenle", use_container_width=True):
                    yeni_cins = st.text_input("Buğday Cinsi", value=bugday_cinsi if bugday_cinsi != "-" else "", 
                                            key=f"cins_{silo_data.get('isim', 'x')}")
                    if st.button("Kaydet", key=f"save_{silo_data.get('isim', 'x')}"):
                        if update_silo_cinsi(silo_data['isim'], yeni_cins):
                            st.success("Kaydedildi!")
                            time.sleep(1)
                            st.rerun()
            
            # PDF RAPOR BUTONU
            st.divider()
            
            # Benzersiz key oluştur
            safe_name = str(silo_data.get('isim', 'silo')).replace(" ", "_")
            if st.button("📥 PDF Rapor İndir", key=f"pdf_{safe_name}", 
                        use_container_width=True, type="primary"):
                
                with st.spinner("PDF raporu hazırlanıyor..."):
                    try:
                        # Rapor modülünü burada import etmeyi dene (Circular import önlemek için)
                        from app.modules.mixing import get_tavli_analiz_agirlikli_ortalama
                        
                        tavli_ortalamalari = get_tavli_analiz_agirlikli_ortalama(silo_data['isim'])
                        pdf_bytes = create_silo_pdf_report(silo_data['isim'], silo_data, tavli_ortalamalari)
                        
                        if pdf_bytes:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            silo_name_fixed = turkce_karakter_duzelt_pdf(silo_data['isim'])
                            
                            st.download_button(
                                label="💾 İndirmeyi Başlat",
                                data=pdf_bytes,
                                file_name=f"SILO_RAPORU_{silo_name_fixed}_{timestamp}.pdf",
                                mime="application/pdf",
                                key=f"down_{safe_name}"
                            )
                        else:
                            st.error("PDF oluşturulamadı!")
                    except Exception as e:
                         st.warning(f"Rapor oluşturulamadı: {e}")
                
    except Exception as e:
        st.error(f"Silo kartı hatası: {str(e)}")

def show_dashboard():
    """Dashboard modülünü göster"""
    
    # Modern Header
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
        <div>
            <h1 style="margin:0; color:#0B4F6C;">🏭 Fabrika Kontrol Merkezi</h1>
            <p style="margin:0; color:#64748B;">Güncel stok ve üretim durumu</p>
        </div>
        <div style="text-align: right;">
            <span style="background-color: #E0F2FE; color: #0369A1; padding: 5px 10px; border-radius: 15px; font-size: 0.8rem; font-weight: 600;">
                Canlı Sistem (Cloud)
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    df = get_silo_data()
    
    if df.empty:
        st.info("👋 Hoşgeldiniz! Sistemde henüz tanımlı silo bulunmuyor.")
        return
    
    # KPI KARTLARI
    try:
        toplam_stok = df['mevcut_miktar'].sum()
        toplam_kapasite = df['kapasite'].sum()
        doluluk_orani = (toplam_stok / toplam_kapasite * 100) if toplam_kapasite > 0 else 0
        aktif_silo_sayisi = len(df[df['mevcut_miktar'] > 0])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            card_metric("Toplam Stok", f"{toplam_stok:,.0f} Ton", None, "#0B4F6C")
            
        with col2:
            color = "#10B981" 
            if doluluk_orani > 90: color = "#EF4444" 
            elif doluluk_orani > 70: color = "#F59E0B"
            card_metric("Doluluk Oranı", f"%{doluluk_orani:.1f}", None, color)
            
        with col3:
            card_metric("Aktif Silolar", f"{aktif_silo_sayisi} / {len(df)}", None, "#6366F1")
    except Exception as e:
        st.error(f"Metrik hesaplama hatası: {e}")
    
    st.markdown("---")
    
    # --- SİLO KARTLARI ---
    st.subheader("🏭 Anlık Silo Durumu")
    
    num_silos = len(df)
    for i in range(0, num_silos, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < num_silos:
                with cols[j]:
                    show_silo_card(df.iloc[i + j])
