import streamlit as st
import pandas as pd
import time
from datetime import datetime
from app.core.database import fetch_data
from app.core.error_handling import error_handler, log_debug, log_info, log_warning, ERROR_HANDLING_AVAILABLE
from app.core.utils import turkce_karakter_duzelt
from app.core.styles import card_metric

# PDF rapor fonksiyonları
from app.modules.reports import create_silo_pdf_report, turkce_karakter_duzelt_pdf

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
    """Silo verilerini güvenli şekilde getir - HATA YÖNETİMLİ"""
    
    log_debug("Silo verileri getiriliyor", "Dashboard")
    
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM silolar ORDER BY isim", conn)
            
            # NaN değerleri temizle
            df = df.fillna({
                'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
                'sedim': 0, 'maliyet': 0, 'bugday_cinsi': ''
            })
            
            log_debug(f"{len(df)} silo verisi getirildi", "Dashboard")
            return df
            
    except Exception as e:
        # Decorator yakalayacak
        log_debug("Silo verisi getirme tamamlandı (hata varsa decorator'da)", "Dashboard")
        return pd.DataFrame()

def update_silo_cinsi(silo_isim, yeni_cins):
    """Silo buğday cinsini güncelle"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE silolar SET bugday_cinsi=? WHERE isim=?', 
                     (yeni_cins[:50], silo_isim))  # 50 karakter sınırı
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Güncelleme hatası: {str(e)}")
        return False

def show_silo_card(silo_data):
    """Tek bir silo kartını göster - TAVLI BUĞDAY EKLENDİ ve PDF RAPOR"""
    try:
        with st.container(border=True):
            # Doluluk oranını güvenli hesapla
            try:
                doluluk_orani = float(silo_data['mevcut_miktar']) / float(silo_data['kapasite']) if float(silo_data['kapasite']) > 0 else 0
            except:
                doluluk_orani = 0
            
            st.markdown(f"#### {silo_data['isim']}")
            
            # Maliyet bilgisi
            maliyet = float(silo_data.get('maliyet', 0))
            if maliyet > 0:
                st.markdown(f"**Birim Maliyet:** {maliyet:.2f} TL/KG")
            else:
                st.markdown("**Birim Maliyet:** -")
            
            # Buğday cinsi
            bugday_cinsi = str(silo_data.get('bugday_cinsi', '')).strip()
            if not bugday_cinsi:
                bugday_cinsi = "-"
            st.caption(f"**Cins:** {bugday_cinsi}")
            
            # Tavlı Buğday Stok Bilgisi
            tavli_stok = float(silo_data.get('tavli_bugday_stok', 0))
            st.caption(f"**Tavlı Buğday Stok:** {tavli_stok:.1f} Ton")
            
            # Silo görseli
            st.markdown(draw_silo(doluluk_orani, ""), unsafe_allow_html=True)
            
            # Miktar bilgisi
            st.markdown(f"**{float(silo_data['mevcut_miktar']):.1f} / {float(silo_data['kapasite']):.0f} Ton**")
            
            # Yönetici ise buğday cinsi düzenleme
            if st.session_state.user_role == "admin":
                with st.popover("✏️ Cins Düzenle", use_container_width=True):
                    yeni_cins = st.text_input("Buğday Cinsi", value=bugday_cinsi if bugday_cinsi != "-" else "", 
                                             key=f"cins_{silo_data['isim']}")
                    if st.button("Kaydet", key=f"save_{silo_data['isim']}"):
                        if update_silo_cinsi(silo_data['isim'], yeni_cins):
                            st.success("Kaydedildi!")
                            time.sleep(1)
                            st.rerun()
            
            # PDF RAPOR BUTONU - SADECE İNDİR
            st.divider()
            
            if st.button("📥 PDF Rapor İndir", key=f"pdf_{silo_data['isim']}", 
                       use_container_width=True, type="primary",
                       help="Silo raporunu PDF olarak indir"):
                
                with st.spinner("PDF raporu hazırlanıyor..."):
                    try:
                        # Tavlı analiz ortalamalarını getir
                        from app.modules.mixing import get_tavli_analiz_agirlikli_ortalama
                        tavli_ortalamalari = get_tavli_analiz_agirlikli_ortalama(silo_data['isim'])
                        
                        # Rapor oluştur
                        pdf_bytes = create_silo_pdf_report(silo_data['isim'], silo_data, tavli_ortalamalari)
                        
                        if pdf_bytes:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            silo_name_fixed = turkce_karakter_duzelt_pdf(silo_data['isim'])
                            
                            # Doğrudan indirme butonu göster (Session State kullanarak rerun yapılabilir ama burada gerek yok çünkü button içindeyiz)
                            # Ancak Streamlit button içinde button download çalışmaz.
                            # Bu yüzden download button'u dışarı almak daha iyidir ama dinamik olduğu için session state kullanalım.
                            
                            st.session_state[f'pdf_bytes_{silo_data["isim"]}'] = pdf_bytes
                            st.session_state[f'pdf_name_{silo_data["isim"]}'] = f"SILO_RAPORU_{silo_name_fixed}_{timestamp}.pdf"
                            st.rerun()
                            
                        else:
                            st.error("PDF oluşturulamadı!")
                    except ImportError:
                         st.error("Rapor modülleri yüklenemedi. (Mixing veya Reports modülü eksik olabilir)")
                    except Exception as e:
                        st.error(f"Rapor hatası: {e}")

            # İndirme butonu hazırsa göster
            if f'pdf_bytes_{silo_data["isim"]}' in st.session_state:
                st.download_button(
                    label="💾 İndirmek için Tıklayın",
                    data=st.session_state[f'pdf_bytes_{silo_data["isim"]}'],
                    file_name=st.session_state[f'pdf_name_{silo_data["isim"]}'],
                    mime="application/pdf",
                    key=f"download_ready_{silo_data['isim']}",
                    use_container_width=True
                )
                
    except Exception as e:
        st.error(f"Silo kartı hatası: {str(e)}")

def show_dashboard():
    """Dashboard modülünü göster - PREMIUM UI"""
    
    # Modern Header
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
        <div>
            <h1 style="margin:0; color:#0B4F6C;">🏭 Fabrika Kontrol Merkezi</h1>
            <p style="margin:0; color:#64748B;">Güncel stok ve üretim durumu</p>
        </div>
        <div style="text-align: right;">
            <span style="background-color: #E0F2FE; color: #0369A1; padding: 5px 10px; border-radius: 15px; font-size: 0.8rem; font-weight: 600;">
                Canlı Sistem
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    df = get_silo_data()
    
    if df.empty:
        st.info("👋 Hoşgeldiniz! Sistemde henüz tanımlı silo bulunmuyor.")
        st.warning("👉 Lütfen başlamak için **Yönetim Paneli > Silo Yönetimi** sekmesinden silo tanımlayınız.")
        return
    
    # KPI KARTLARI - SADELEŞTİRİLMİŞ
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
    
    st.markdown("---")
    
    st.markdown("---")
    
    # --- SİLO KARTLARI ---
    st.subheader("🏭 Anlık Silo Durumu")
    
    # Siloları 4'lü grid yapısında göster
    num_silos = len(df)
    for i in range(0, num_silos, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < num_silos:
                with cols[j]:
                    show_silo_card(df.iloc[i + j])

