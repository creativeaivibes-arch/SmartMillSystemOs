import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np

# --- DATABASE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.config import INPUT_LIMITS, TERMS, get_limit
from app.core.error_handling import error_handler, log_info, log_warning, ERROR_HANDLING_AVAILABLE
from app.core.components import render_help_button

# --------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR (BAĞIMSIZLAŞTIRILDI)
# --------------------------------------------------------------------------

def get_silo_data():
    """Silo verilerini getir (Dashboard'dan bağımsız)"""
    try:
        df = fetch_data("silolar")
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])

        # NaN temizliği
        df = df.fillna({
            'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
            'sedim': 0, 'maliyet': 0, 'bugday_cinsi': '', 'mevcut_miktar': 0, 'kapasite': 100
        })
        
        if 'isim' in df.columns:
            df = df.sort_values('isim')

        return df
    except Exception as e:
        st.error(f"Silo verisi çekme hatası: {e}")
        return pd.DataFrame()

def draw_silo_preview(fill_ratio):
    """Silo doluluk görseli (Küçük önizleme için)"""
    try:
        fill_ratio = max(0.0, min(1.0, float(fill_ratio)))
    except: fill_ratio = 0.0
    
    height = 60
    fill_h = int(height * fill_ratio)
    empty_h = height - fill_h
    color = "#3B82F6" if fill_ratio < 0.8 else "#EF4444"
    
    return f'''<svg width="40" height="{height}">
        <rect x="0" y="0" width="40" height="{height}" rx="4" fill="#f1f5f9" stroke="#cbd5e1"/>
        <rect x="0" y="{empty_h}" width="40" height="{fill_h}" rx="4" fill="{color}"/>
    </svg>'''

# --------------------------------------------------------------------------
# LOGLAMA VE VERİTABANI İŞLEMLERİ
# --------------------------------------------------------------------------

@error_handler(context="Stok Hareketi Loglama")
def log_stok_hareketi(silo_isim, hareket_tipi, miktar, **kwargs):
    """Stok hareketini kaydet"""
    try:
        unique_id = int(datetime.now().timestamp() * 1000)
        data = {
            'id': unique_id,
            'silo_isim': silo_isim,
            'hareket_tipi': hareket_tipi,
            'miktar': abs(float(miktar)),
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'protein': kwargs.get('protein', 0),
            'gluten': kwargs.get('gluten', 0),
            'rutubet': kwargs.get('rutubet', 0),
            'hektolitre': kwargs.get('hektolitre', 0),
            'sedim': kwargs.get('sedim', 0),
            'maliyet': kwargs.get('maliyet', 0),
            'lot_no': kwargs.get('lot_no', ''),
            'tedarikci': kwargs.get('tedarikci', ''),
            'yore': kwargs.get('yore', ''),
            'notlar': kwargs.get('notlar', '')
        }
        return add_data("hareketler", data)
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def update_tavli_bugday_stok(silo_isim, tonaj, islem="ekle"):
    """Tavlı buğday stokunu güncelle"""
    try:
        conn = get_conn()
        df = fetch_data("silolar")
        if df.empty: return False
        
        mask = df['isim'] == silo_isim
        if mask.any():
            curr = float(df.loc[mask, 'tavli_bugday_stok'].iloc[0] or 0)
            yeni = (curr + float(tonaj)) if islem == "ekle" else max(0, curr - float(tonaj))
            df.loc[mask, 'tavli_bugday_stok'] = yeni
            conn.update(worksheet="silolar", data=df)
            return True
        return False
    except: return False

def recalculate_silos_from_logs():
    """Siloları hareket kayıtlarından yeniden hesapla (Senkronizasyon)"""
    try:
        conn = get_conn()
        df_silo = fetch_data("silolar")
        df_move = fetch_data("hareketler")
        
        if df_silo.empty: return
        
        for idx, row in df_silo.iterrows():
            silo = row['isim']
            moves = df_move[df_move['silo_isim'] == silo]
            
            # Basit Toplam
            giris = moves[moves['hareket_tipi'] == 'Giriş']['miktar'].sum()
            cikis = moves[moves['hareket_tipi'] == 'Çıkış']['miktar'].sum()
            net = giris - cikis
            
            # Ağırlıklı Ortalama (Sadece Girişlerden)
            girisler = moves[moves['hareket_tipi'] == 'Giriş']
            if not girisler.empty and giris > 0:
                avg_prot = (girisler['miktar'] * girisler['protein']).sum() / giris
                avg_mal = (girisler['miktar'] * girisler['maliyet']).sum() / giris
                
                df_silo.at[idx, 'protein'] = avg_prot
                df_silo.at[idx, 'maliyet'] = avg_mal
            
            df_silo.at[idx, 'mevcut_miktar'] = max(0, net)
            
        conn.update(worksheet="silolar", data=df_silo)
    except: pass

def add_to_bugday_giris_arsivi(lot_no, **kwargs):
    """Arşiv Kaydı"""
    try:
        data = {'lot_no': lot_no, **kwargs}
        return add_data("bugday_giris_arsivi", data)
    except: return False

# --------------------------------------------------------------------------
# EKRANLAR (UI)
# --------------------------------------------------------------------------

def show_mal_kabul():
    """Mal Kabul Ekranı"""
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("Yetkisiz erişim")
        return

    st.header("🚜 Mal Kabul ve Stok Girişi")
    lot_no = f"BUGDAY-{datetime.now().strftime('%y%m%d%H%M%S')}"
    
    col1, col2 = st.columns([1, 1.5], gap="large")
    
    with col1:
        st.info(f"**Otomatik Lot:** `{lot_no}`")
        df_silo = get_silo_data()
        
        if df_silo.empty:
            st.error("Silo bulunamadı! Önce silo tanımlayın.")
            return
            
        silo = st.selectbox("Depolanacak Silo *", df_silo['isim'].tolist())
        
        # Kapasite Bilgisi
        silo_row = df_silo[df_silo['isim'] == silo].iloc[0]
        bos_yer = float(silo_row['kapasite']) - float(silo_row['mevcut_miktar'])
        st.caption(f"Boş Kapasite: {bos_yer:.1f} Ton")
        
        tarih = st.date_input("Tarih", datetime.now())
        bugday_cinsi = st.text_input("Buğday Cinsi *")
        tedarikci = st.text_input("Tedarikçi *")
        yore = st.text_input("Yöre")
        plaka = st.text_input("Plaka *")
        
        c_kantar1, c_kantar2 = st.columns(2)
        miktar = c_kantar1.number_input("Miktar (Ton) *", min_value=0.1, format="%.1f")
        fiyat = c_kantar2.number_input("Birim Fiyat (TL) *", min_value=0.1, format="%.2f")
        
        notlar = st.text_area("Notlar")

    with col2:
        st.subheader("🧪 Laboratuvar Değerleri")
        
        c1, c2, c3 = st.columns(3)
        prot = c1.number_input("Protein", 12.0)
        glut = c2.number_input("Gluten", 28.0)
        hl = c3.number_input("Hektolitre", 78.0)
        
        rut = c1.number_input("Rutubet", 13.5)
        sedim = c2.number_input("Sedim", 30.0)
        g_sedim = c3.number_input("G. Sedim", 35.0)
        
        sune = c1.number_input("Süne (%)", 0.0)
        index = c2.number_input("G. Index", 90.0)
        hasere = c3.checkbox("🦗 Haşere Var mı?")
    
    st.divider()
    
    if st.button("💾 Kaydı Tamamla", type="primary", use_container_width=True):
        if not bugday_cinsi or not tedarikci or not plaka:
            st.error("Zorunlu alanları doldurun (Cins, Tedarikçi, Plaka)")
            return
            
        note_final = f"Plaka: {plaka} | {notlar}"
        if hasere: note_final += " | HAŞERE RİSKİ"
        
        # 1. Stok Hareketi
        ok1 = log_stok_hareketi(silo, "Giriş", miktar, protein=prot, gluten=glut, rutubet=rut, 
                               hektolitre=hl, sedim=sedim, maliyet=fiyat, lot_no=lot_no,
                               tedarikci=tedarikci, yore=yore, notlar=note_final)
        
        # 2. Arşiv
        ok2 = add_to_bugday_giris_arsivi(lot_no, tarih=str(tarih), bugday_cinsi=bugday_cinsi,
                                        tedarikci=tedarikci, yore=yore, plaka=plaka, tonaj=miktar,
                                        fiyat=fiyat, silo_isim=silo, protein=prot, gluten=glut,
                                        rutubet=rut, hektolitre=hl, sedim=sedim, sune=sune, notlar=note_final)
        
        if ok1 and ok2:
            st.success("✅ Giriş Başarılı!")
            recalculate_silos_from_logs() # Siloları güncelle
            time.sleep(1)
            st.rerun()
        else:
            st.error("Kayıt sırasında hata oluştu.")

def show_stok_cikis():
    """Stok Çıkış Ekranı"""
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("Yetkisiz erişim")
        return

    st.header("📉 Stok Çıkışı (Üretim/Transfer)")
    df = get_silo_data()
    
    if df.empty:
        st.warning("Silo yok.")
        return
        
    col1, col2 = st.columns([1, 1])
    
    with col1:
        silo = st.selectbox("Kaynak Silo", df['isim'].tolist())
        row = df[df['isim'] == silo].iloc[0]
        mevcut = float(row['mevcut_miktar'])
        
        st.metric("Mevcut Stok", f"{mevcut:.1f} Ton")
        
        miktar = st.number_input("Çıkış Miktarı", min_value=0.1, max_value=mevcut if mevcut > 0 else 0.1)
        neden = st.selectbox("Neden", ["Üretime Gönderim", "Silo Transferi", "Satış", "Zayi"])
        
        hedef = None
        if neden == "Silo Transferi":
            hedef = st.selectbox("Hedef Silo", [s for s in df['isim'].tolist() if s != silo])
            
    with col2:
        st.markdown("### Önizleme")
        yeni_stok = max(0, mevcut - miktar)
        kapasite = float(row['kapasite'])
        doluluk = yeni_stok / kapasite if kapasite > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.metric("Kalan", f"{yeni_stok:.1f} Ton")
        c2.markdown(draw_silo_preview(doluluk), unsafe_allow_html=True)
        
    if st.button("📤 Çıkışı Onayla", type="primary"):
        if miktar <= 0 or miktar > mevcut:
            st.error("Geçersiz miktar")
            return
            
        note = f"{neden}"
        ok = log_stok_hareketi(silo, "Çıkış", miktar, notlar=note)
        
        # Transfer ise hedefe giriş yap
        if ok and neden == "Silo Transferi" and hedef:
            log_stok_hareketi(hedef, "Giriş", miktar, notlar=f"Transfer: {silo} silosundan", 
                             protein=row['protein'], maliyet=row['maliyet'])
            
        if ok:
            st.success("İşlem Başarılı!")
            recalculate_silos_from_logs()
            time.sleep(1)
            st.rerun()

def show_tavli_analiz():
    """Tavlı Buğday Analizi"""
    st.header("💧 Tavlı Buğday Analizi")
    df = get_silo_data()
    
    silo = st.selectbox("Silo Seç", df['isim'].tolist())
    row = df[df['isim'] == silo].iloc[0]
    
    c1, c2 = st.columns(2)
    mevcut = float(row['mevcut_miktar'])
    tavli_stok = float(row.get('tavli_bugday_stok', 0))
    
    c1.metric("Kuru Stok", f"{mevcut:.1f} Ton")
    c2.metric("Mevcut Tavlı", f"{tavli_stok:.1f} Ton")
    
    tonaj = st.number_input("Analiz Yapılan Miktar (Ton)", min_value=1.0)
    
    with st.expander("Analiz Sonuçları", expanded=True):
        c1, c2 = st.columns(2)
        prot = c1.number_input("Protein", value=float(row['protein']))
        rut = c2.number_input("Rutubet", 16.5) # Tavlı olduğu için yüksek varsayılır
        # Diğer parametreler buraya eklenebilir...
        
    if st.button("Kaydet"):
        # Basit kayıt (Detaylı tavlı tablosu yoksa notlara yazalım veya ayrı tablo açalım)
        # Şimdilik tavlı stok miktarını güncelliyoruz
        update_tavli_bugday_stok(silo, tonaj, "ekle")
        st.success("Tavlı stok güncellendi!")
        time.sleep(1)
        st.rerun()

# --- DİĞER MODÜLLER İÇİN GEREKLİ FONKSİYONLAR ---
# Bu dosyayı import eden diğer modüllerin kırılmaması için boş fonksiyonlar veya yönlendirmeler
def show_stok_hareketleri():
    st.info("Hareket geçmişi bu sayfada hazırlanıyor...")

def show_bugday_giris_arsivi():
    st.info("Arşiv kayıtları burada listelenecek...")

def show_bugday_spec_yonetimi():
    st.info("Spec yönetimi...")
