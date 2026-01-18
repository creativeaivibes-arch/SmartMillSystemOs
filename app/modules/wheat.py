import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np

# --- DATABASE VE CORE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.config import INPUT_LIMITS, TERMS, get_limit
from app.core.error_handling import error_handler, log_info, log_warning, ERROR_HANDLING_AVAILABLE
from app.core.components import render_help_button

# Rapor modülü (Hata önleyici)
try:
    from app.modules.reports import download_styled_excel as shared_download
except ImportError:
    def shared_download(*args): pass

# --------------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR (Dashboard Bağımlılığını Kaldırmak İçin Buraya Eklendi)
# --------------------------------------------------------------------------

def draw_silo(fill_ratio, name):
    """Silo görseli çiz"""
    try:
        fill_ratio = float(fill_ratio)
        fill_ratio = max(0.0, min(1.0, fill_ratio))
    except: fill_ratio = 0.0
    
    height = 100
    fill_height = int(height * fill_ratio)
    empty_height = height - fill_height
    
    try:
        if fill_ratio < 0.2: fill_color = "#EF4444"
        elif fill_ratio < 0.5: fill_color = "#3B82F6"
        elif fill_ratio < 0.8: fill_color = "#10B981"
        else: fill_color = "#F59E0B"
    except: fill_color = "#CBD5E1"
    
    svg = f'''<svg width="60" height="{height + 10}">
        <rect x="10" y="5" width="40" height="{height}" rx="5" ry="5" 
              style="fill: #f0f2f6; stroke: #333; stroke-width:2;"/>
        <rect x="10" y="{5 + empty_height}" width="40" height="{fill_height}" 
              rx="5" ry="5" style="fill: {fill_color}; stroke: none;"/>
        <text x="30" y="{height + 5}" font-size="8" text-anchor="middle" 
              fill="#333">{name}</text>
    </svg>'''
    return svg

def get_silo_data():
    """Silo verilerini getir"""
    try:
        df = fetch_data("silolar")
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])
        # NaN temizliği
        cols = ['protein', 'gluten', 'rutubet', 'hektolitre', 'sedim', 'maliyet', 'mevcut_miktar', 'kapasite']
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'isim' in df.columns:
            df = df.sort_values('isim')
        return df
    except Exception as e:
        st.error(f"Silo verisi hatası: {e}")
        return pd.DataFrame()

# --------------------------------------------------------------------------
# VERİ İŞLEME FONKSİYONLARI (ORİJİNAL MANTIK - GOOGLE SHEETS ADAPTASYONU)
# --------------------------------------------------------------------------

@error_handler(context="Stok Hareketi Loglama")
def log_stok_hareketi(silo_isim, hareket_tipi, miktar, **kwargs):
    """Stok hareketini logla (TÜM PARAMETRELER DAHİL)"""
    try:
        unique_id = int(datetime.now().timestamp() * 1000)
        
        # Orijinal koddaki tüm opsiyonel alanları kapsayan yapı
        data = {
            'id': unique_id,
            'silo_isim': silo_isim,
            'hareket_tipi': hareket_tipi,
            'miktar': abs(float(miktar)),
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            # Analiz Değerleri
            'protein': kwargs.get('protein', 0),
            'gluten': kwargs.get('gluten', 0),
            'rutubet': kwargs.get('rutubet', 0),
            'hektolitre': kwargs.get('hektolitre', 0),
            'sedim': kwargs.get('sedim', 0),
            'maliyet': kwargs.get('maliyet', 0),
            # Lojistik Bilgiler
            'lot_no': kwargs.get('lot_no', ''),
            'tedarikci': kwargs.get('tedarikci', ''),
            'yore': kwargs.get('yore', ''),
            'notlar': kwargs.get('notlar', '')
        }
        return add_data("hareketler", data)
    except Exception as e:
        st.error(f"❌ Hareket kaydı hatası: {str(e)}")
        return False

def update_tavli_bugday_stok(silo_isim, eklenen_tonaj, islem_tipi="ekle"):
    """Tavlı buğday stokunu güncelle"""
    try:
        conn = get_conn()
        df = fetch_data("silolar")
        if df.empty: return False

        mask = df['isim'] == silo_isim
        if not mask.any(): return False
            
        current = float(df.loc[mask, 'tavli_bugday_stok'].iloc[0]) if pd.notnull(df.loc[mask, 'tavli_bugday_stok'].iloc[0]) else 0.0
        
        if islem_tipi == "ekle":
            yeni_tavli = current + float(eklenen_tonaj)
        elif islem_tipi == "cikar":
            yeni_tavli = max(0, current - float(eklenen_tonaj))
        else: return False
            
        df.loc[mask, 'tavli_bugday_stok'] = yeni_tavli
        conn.update(worksheet="silolar", data=df)
        return True
    except Exception as e:
        st.error(f"Tavlı stok güncelleme hatası: {str(e)}")
        return False

def recalculate_silos_from_logs():
    """Geçmiş hareketleri tarayıp siloları senkronize eder (SQL Mantığı -> Pandas Mantığı)"""
    try:
        conn = get_conn()
        df_silolar = fetch_data("silolar")
        df_hareketler = fetch_data("hareketler")
        
        if df_silolar.empty: return False
        
        # Hareket yoksa çık
        if df_hareketler.empty: 
            return True

        for index, row in df_silolar.iterrows():
            silo_isim = row['isim']
            silo_moves = df_hareketler[df_hareketler['silo_isim'] == silo_isim]
            
            curr_miktar = 0.0
            
            # Girişler ve Çıkışlar
            girisler = silo_moves[silo_moves['hareket_tipi'] == 'Giriş']
            cikislar = silo_moves[silo_moves['hareket_tipi'] == 'Çıkış']
            
            toplam_giris = girisler['miktar'].sum()
            toplam_cikis = cikislar['miktar'].sum()
            
            curr_miktar = max(0, toplam_giris - toplam_cikis)
            
            # AĞIRLIKLI Ortalama (Sadece Girişlerden Hesaplanır)
            if not girisler.empty and toplam_giris > 0:
                try:
                    avg_prot = (girisler['miktar'] * girisler['protein']).sum() / toplam_giris
                    avg_mal = (girisler['miktar'] * girisler['maliyet']).sum() / toplam_giris
                    
                    df_silolar.at[index, 'protein'] = avg_prot
                    df_silolar.at[index, 'maliyet'] = avg_mal
                    # Diğer parametreler de eklenebilir (gluten vb.)
                except: pass

            df_silolar.at[index, 'mevcut_miktar'] = curr_miktar

        conn.update(worksheet="silolar", data=df_silolar)
        return True
    except Exception as e:
        st.error(f"Hesaplama hatası: {str(e)}")
        return False

def add_to_bugday_giris_arsivi(lot_no, **kwargs):
    """Buğday girişini arşive ekle (DETAYLI KAYIT)"""
    try:
        # kwargs içinde orijinal kodundaki tüm parametreler gelecek:
        # tarih, bugday_cinsi, tedarikci, yore, plaka, tonaj, fiyat, silo_isim,
        # hektolitre, protein, rutubet, gluten, gluten_index, sedim, gecikmeli_sedim,
        # sune, kirik_ciliz, yabanci_tane, notlar
        
        data = {'lot_no': lot_no, **kwargs}
        return add_data("bugday_giris_arsivi", data)
    except Exception as e:
        st.error(f"❌ Arşiv hatası: {str(e)}")
        return False

def get_movements():
    """Stok hareketlerini detaylı getir (Arşiv ile JOIN işlemi)"""
    try:
        df_h = fetch_data("hareketler")
        df_a = fetch_data("bugday_giris_arsivi")
        
        if df_h.empty: return pd.DataFrame()
        if df_a.empty: return df_h
        
        # Pandas Merge (SQL LEFT JOIN yerine)
        # Hareket tablosunda olmayan detaylar (Süne, Yabancı Tane vb.) Arşivden gelir
        merged = pd.merge(
            df_h, 
            df_a[['lot_no', 'tedarikci', 'yore', 'plaka', 'bugday_cinsi', 'sune', 'kirik_ciliz', 'yabanci_tane', 'gluten_index', 'gecikmeli_sedim']], 
            on='lot_no', 
            how='left', 
            suffixes=('', '_arsiv')
        )
        
        # Çakışan sütunlarda boşlukları doldur
        for col in ['tedarikci', 'yore']:
            if f'{col}_arsiv' in merged.columns:
                merged[col] = merged[col].fillna(merged[f'{col}_arsiv'])
        
        if 'tarih' in merged.columns:
            merged['tarih'] = pd.to_datetime(merged['tarih'])
            merged = merged.sort_values('tarih', ascending=False)
            
        return merged
    except Exception as e:
        st.error(f"Hareket yükleme hatası: {e}")
        return pd.DataFrame()

def get_bugday_arsiv():
    """Arşiv verisi"""
    df = fetch_data("bugday_giris_arsivi")
    if not df.empty and 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
    return df

# --- TAVLI ANALİZLERİ (TEMPERED WHEAT) ---

def save_tavli_analiz(silo_isim, analiz_tonaj, **analiz_degerleri):
    try:
        data = {
            'silo_isim': silo_isim, 
            'analiz_tonaj': float(analiz_tonaj),
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **analiz_degerleri
        }
        return add_data("tavli_analiz", data), "Kaydedildi"
    except Exception as e: return False, str(e)

def get_tavli_analizler(silo_isim=None):
    df = fetch_data("tavli_analiz")
    if df.empty: return pd.DataFrame()
    if silo_isim: df = df[df['silo_isim'] == silo_isim]
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
    return df
def get_kuru_bugday_agirlikli_ortalama(silo_isim):
    """
    Bir silodaki KURU BUĞDAY analizlerinin ağırlıklı ortalamasını hesaplar.
    Mal kabul girişlerinden (hareketler tablosu) veriler alınır.
    
    Returns:
        dict: Ağırlıklı ortalama analiz değerleri
    """
    try:
        # Hareketler tablosundan bu silonun GİRİŞ kayıtlarını al
        df_hareketler = fetch_data("hareketler")
        if df_hareketler.empty:
            return {}
        
        # Sadece bu silonun girişleri
        df_silo = df_hareketler[
            (df_hareketler['silo_isim'] == silo_isim) & 
            (df_hareketler['hareket_tipi'] == 'Giriş')
        ].copy()
        
        if df_silo.empty:
            return {}
        
        # Tonaj sütunu kontrolü
        if 'miktar' not in df_silo.columns:
            return {}
        
        # Numeric dönüşüm
        numeric_cols = ['miktar', 'hektolitre', 'protein', 'rutubet', 'gluten', 
                       'gluten_index', 'sedim', 'gecikmeli_sedim']
        
        for col in numeric_cols:
            if col in df_silo.columns:
                df_silo[col] = pd.to_numeric(df_silo[col], errors='coerce').fillna(0)
        
        toplam_tonaj = df_silo['miktar'].sum()
        
        if toplam_tonaj == 0:
            return {}
        
        # Ağırlıklı ortalama hesapla
        ortalama = {}
        analiz_cols = ['hektolitre', 'protein', 'rutubet', 'gluten', 
                      'gluten_index', 'sedim', 'gecikmeli_sedim']
        
        for col in analiz_cols:
            if col in df_silo.columns:
                # (miktar * değer).sum() / toplam_miktar
                agirlikli_toplam = (df_silo['miktar'] * df_silo[col]).sum()
                ortalama[col] = agirlikli_toplam / toplam_tonaj if toplam_tonaj > 0 else 0
        
        return ortalama
        
    except Exception as e:
        st.error(f"Kuru buğday ortalama hesaplama hatası: {e}")
        return {}
# --- SPEC YÖNETİMİ ---

def save_bugday_spec(bugday_cinsi, parametre, min_val, max_val, hedef_val):
    try:
        conn = get_conn()
        df = fetch_data("bugday_spekleri")
        new_row = {
            'bugday_cinsi': bugday_cinsi, 'parametre': parametre, 
            'min_deger': min_val, 'max_deger': max_val, 'hedef_deger': hedef_val, 'aktif': 1
        }
        
        if df.empty: return add_data("bugday_spekleri", new_row)
        
        # Upsert Logic
        mask = (df['bugday_cinsi'] == bugday_cinsi) & (df['parametre'] == parametre)
        if mask.any():
            df.loc[mask, ['min_deger', 'max_deger', 'hedef_deger']] = [min_val, max_val, hedef_val]
            conn.update(worksheet="bugday_spekleri", data=df)
        else:
            add_data("bugday_spekleri", new_row)
        return True
    except: return False

def get_all_bugday_specs_dataframe():
    df = fetch_data("bugday_spekleri")
    return df if not df.empty else pd.DataFrame()

def delete_bugday_spec_group(cins):
    try:
        conn = get_conn()
        df = fetch_data("bugday_spekleri")
        if df.empty: return True
        df = df[df['bugday_cinsi'] != cins]
        conn.update(worksheet="bugday_spekleri", data=df)
        return True
    except: return False

# --------------------------------------------------------------------------
# UI EKRANLARI - %100 ORİJİNAL KAPSAM (EKSİKSİZ)
# --------------------------------------------------------------------------

def show_mal_kabul():
    """Mal Kabul Ekranı - Tüm Analiz Parametreleri Dahil"""
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("Yetkisiz")
        return

    st.header("🚜 Mal Kabul ve Stok Girişi")
    lot_no = f"BUGDAY-{datetime.now().strftime('%y%m%d%H%M%S')}"
    
    col1, col2 = st.columns([1, 1.5], gap="large")
    
    with col1:
        st.subheader("📋 Temel Bilgiler")
        st.info(f"**Otomatik Lot No:** `{lot_no}`")
        
        df_silo = get_silo_data()
        if df_silo.empty: 
            st.warning("Silo tanımlayınız.")
            return
            
        secilen_silo = st.selectbox("Depolanacak Silo *", df_silo['isim'].tolist())
        
        # Kapasite Kontrolü
        silo_row = df_silo[df_silo['isim'] == secilen_silo].iloc[0]
        kalan = float(silo_row.get('kapasite', 0)) - float(silo_row.get('mevcut_miktar', 0))
        st.info(f"Kalan Kapasite: {kalan:.1f} Ton")
        
        tarih = st.date_input("Kabul Tarihi *", datetime.now())
        
        # Spec Listesi (Opsiyonel Validation İçin)
        specs_list = []
        df_specs = fetch_data("bugday_spekleri")
        if not df_specs.empty:
            specs_list = df_specs['bugday_cinsi'].unique().tolist()
            
        secilen_standart = st.selectbox("Standart Seçiniz", ["(Standart Yok)"] + specs_list)
        bugday_cinsi = st.text_input("Buğday Cinsi *", placeholder="Örn: Bezostaya")
        
        current_specs = {}
        if secilen_standart != "(Standart Yok)":
            df_s = df_specs[df_specs['bugday_cinsi'] == secilen_standart]
            for _, row in df_s.iterrows():
                current_specs[row['parametre']] = row

        tedarikci = st.text_input("Tedarikçi/Firma *")
        yore = st.text_input("Yöre/Bölge *")
        plaka = st.text_input("Plaka *")
        notlar = st.text_area("Notlar")
        
        # Manuel Kantar
        miktar = st.number_input("Gelen Miktar (Ton) *", min_value=0.1, format="%.1f")
        fiyat = st.number_input("Alış Fiyatı (TL) *", min_value=0.1, format="%.2f")

    with col2:
        st.subheader("🧪 Laboratuvar Analiz Değerleri")
        
        # Validasyon Helper
        def validate_val(key, val, label):
            if key in current_specs:
                spec = current_specs[key]
                s_min, s_max = float(spec.get('min_deger', 0)), float(spec.get('max_deger', 999))
                if val < s_min or (s_max > 0 and val > s_max):
                    st.error(f"❌ {label} Sınır Dışı! (Max: {s_max:.1f})")
                elif key == "sune" and val > s_max and s_max > 0:
                     st.error(f"⚠️ Yüksek Süne! Max: {s_max:.1f}")

        # 3 Kolonlu Detaylı Giriş (Orijinal Yapı)
        c1, c2, c3 = st.columns(3)
        
        with c1:
            g_hl = st.number_input("Hektolitre", 0.0, 100.0, 78.0)
            validate_val("hektolitre", g_hl, "Hektolitre")
            
            g_rut = st.number_input("Rutubet (%)", 0.0, 20.0, 13.5)
            validate_val("rutubet", g_rut, "Rutubet")
            
            g_prot = st.number_input("Protein (%)", 0.0, 20.0, 12.0)
            validate_val("protein", g_prot, "Protein")
            
            g_glut = st.number_input("Gluten (%)", 0.0, 50.0, 28.0)
            validate_val("gluten", g_glut, "Gluten")

        with c2:
            g_index = st.number_input("Gluten Index", 0.0, 100.0, 90.0)
            validate_val("gluten_index", g_index, "G.Index")
            
            g_sedim = st.number_input("Sedim (ml)", 0.0, 100.0, 30.0)
            validate_val("sedim", g_sedim, "Sedim")
            
            g_g_sedim = st.number_input("Gecikmeli Sedim (ml)", 0.0, 100.0, 35.0)
            validate_val("gecikmeli_sedim", g_g_sedim, "G.Sedim")
            
            sune = st.number_input("Süne (%)", 0.0, 10.0, 0.0)
            validate_val("sune", sune, "Süne")

        with c3:
            kirik_ciliz = st.number_input("Kırık & Cılız (%)", 0.0, 100.0, 2.0)
            validate_val("kirik_ciliz", kirik_ciliz, "Kırık/Cılız")
            
            yabanci_tane = st.number_input("Yabancı Tane (%)", 0.0, 100.0, 2.5)
            validate_val("yabanci_tane", yabanci_tane, "Yabancı Tane")
            
            hasere = st.selectbox("Haşere", ["Yok", "Var"])

    st.divider()
    if st.button("💾 Kaydı Tamamla", type="primary", use_container_width=True):
        # 1. Kapasite Kontrolü
        if miktar > kalan:
            st.error(f"❌ Kapasite AŞIMI! Sadece {kalan:.1f} ton yer var.")
            return
        
        # 2. Zorunlu Alanlar
        if not (bugday_cinsi and tedarikci and plaka):
            st.error("Lütfen zorunlu alanları doldurun.")
            return

        note_final = f"Plaka: {plaka} | {notlar}"
        if hasere == "Var": note_final += " | HAŞERE RİSKİ"
        
        # 3. Kayıt (Stok Hareketi + Arşiv)
        ok_log = log_stok_hareketi(
            secilen_silo, "Giriş", miktar,
            protein=g_prot, gluten=g_glut, rutubet=g_rut, hektolitre=g_hl,
            sedim=g_sedim, maliyet=fiyat, lot_no=lot_no,
            tedarikci=tedarikci, yore=yore, notlar=note_final
        )
        
        if ok_log:
            # Arşive tüm detayları ekle
            ok_arc = add_to_bugday_giris_arsivi(
                lot_no, tarih=str(tarih), bugday_cinsi=bugday_cinsi,
                tedarikci=tedarikci, yore=yore, plaka=plaka,
                tonaj=miktar, fiyat=fiyat, silo_isim=secilen_silo,
                hektolitre=g_hl, protein=g_prot, rutubet=g_rut,
                gluten=g_glut, gluten_index=g_index, sedim=g_sedim,
                gecikmeli_sedim=g_g_sedim, sune=sune, kirik_ciliz=kirik_ciliz,
                yabanci_tane=yabanci_tane, notlar=note_final
            )
            
            if ok_arc:
                st.success("✅ Kayıt Başarılı!")
                recalculate_silos_from_logs()
                time.sleep(1)
                st.rerun()
            else:
                st.error("Arşiv kaydında hata oluştu.")
        else:
            st.error("Stok kaydında hata oluştu.")

def show_stok_cikis():
    """Stok Çıkışı Ekranı"""
    st.header("📉 Stok Çıkışı (Üretim/Transfer)")
    df = get_silo_data()
    if df.empty: return
    
    c1, c2 = st.columns(2)
    with c1:
        silo = st.selectbox("Kaynak Silo", df['isim'].tolist())
        row = df[df['isim'] == silo].iloc[0]
        mevcut = float(row['mevcut_miktar'])
        st.metric("Mevcut", f"{mevcut:.1f} Ton")
        
        miktar = st.number_input("Miktar (Ton)", 0.1, max_value=mevcut if mevcut>0 else 0.1)
        neden = st.selectbox("Neden", ["Üretime Gönderim", "Silo Transferi", "Satış", "Zayi"])
        
        hedef = None
        if neden == "Silo Transferi":
            hedef = st.selectbox("Hedef Silo", [s for s in df['isim'].tolist() if s != silo])
            
    with c2:
        # Önizleme
        yeni = max(0, mevcut - miktar)
        doluluk = yeni / float(row['kapasite']) if float(row['kapasite']) > 0 else 0
        st.markdown(draw_silo(doluluk, f"Kalan: {yeni:.1f}"), unsafe_allow_html=True)

    if st.button("📤 Çıkışı Onayla", type="primary"):
        if log_stok_hareketi(silo, "Çıkış", miktar, notlar=neden):
            update_tavli_bugday_stok(silo, miktar, "cikar")
            
            # Transfer ise hedefe giriş yap
            if neden == "Silo Transferi" and hedef:
                log_stok_hareketi(hedef, "Giriş", miktar, protein=float(row['protein']), 
                                 maliyet=float(row['maliyet']), notlar=f"Transfer: {silo}")
                update_tavli_bugday_stok(hedef, miktar, "ekle")
            
            recalculate_silos_from_logs()
            st.success("İşlem Başarılı")
            time.sleep(1)
            st.rerun()

def show_tavli_analiz():
    """Tavlı Buğday Analizi - TAM VE EKSİKSİZ Parametreler"""
    st.header("🧪 Tavlı Buğday Analiz Kaydı")
    df = get_silo_data()
    if df.empty: 
        st.warning("Silo bulunamadı")
        return
    
    c1, c2 = st.columns(2)
    with c1:
        silo = st.selectbox("Silo Seç", df['isim'].tolist())
        row = df[df['isim'] == silo].iloc[0]
        mevcut = float(row.get('mevcut_miktar', 0))
        
        # Tavlı stok kontrolü - Sütun adını kontrol et
        tavli_col = 'tavli_bugday_stok' if 'tavli_bugday_stok' in df.columns else 'tavli_stok'
        tavli = float(row.get(tavli_col, 0)) if pd.notnull(row.get(tavli_col, 0)) else 0.0
        
        kalan = max(0, mevcut - tavli)
        st.info(f"Mevcut: {mevcut:.1f} | Tavlı: {tavli:.1f} | Eklenebilir: {kalan:.1f}")
        
        tonaj = st.number_input("Analiz Tonajı", 0.1, max_value=max(kalan, 1000.0), value=min(kalan, 10.0) if kalan > 0 else 10.0)
    
    with c2:
        tarih = st.date_input("Tarih", datetime.now())
        notlar = st.text_area("Notlar")

    # Tabs - TAM VERSİYON
    tab1, tab2, tab3 = st.tabs(["🧪 Kimyasal", "📈 Farinograph", "📊 Extensograph"])
    vals = {}
    
    with tab1:
        cc1, cc2 = st.columns(2)
        vals['protein'] = cc1.number_input("Protein (%)", value=float(row.get('protein', 12.0)), format="%.2f")
        vals['rutubet'] = cc1.number_input("Rutubet (%)", value=15.0, format="%.2f")
        vals['gluten'] = cc1.number_input("Gluten (%)", value=float(row.get('gluten', 28.0)), format="%.2f")
        vals['gluten_index'] = cc1.number_input("Gluten Index", value=95.0, format="%.2f")
        
        vals['sedim'] = cc2.number_input("Sedim (ml)", value=50.0, format="%.2f")
        vals['g_sedim'] = cc2.number_input("G. Sedim (ml)", value=60.0, format="%.2f")
        vals['fn'] = cc2.number_input("FN", value=300.0, format="%.2f")
        vals['ffn'] = cc2.number_input("FFN", value=400.0, format="%.2f")
        
    with tab2:
        cc1, cc2 = st.columns(2)
        vals['su_kaldirma_f'] = cc1.number_input("Su Kaldırma (Farino) (%)", value=58.0, format="%.2f")
        vals['gelisme_suresi'] = cc1.number_input("Gelişme Süresi (dk)", value=3.0, format="%.2f")
        vals['stabilite'] = cc2.number_input("Stabilite (dk)", value=8.0, format="%.2f")
        vals['yumusama'] = cc2.number_input("Yumuşama (FU)", value=70.0, format="%.2f")
        
    with tab3:
        st.subheader("📊 Extensograph Analizleri (Detaylı)")
        vals['su_kaldirma_e'] = st.number_input("Su Kaldırma (Extenso) (%)", value=58.0, format="%.2f")
        
        # 45 DAKİKA
        with st.expander("📊 45. Dakika:", expanded=True):
            cols45 = st.columns(3)
            vals['direnc45'] = cols45[0].number_input("Direnç (45)", value=610.0, format="%.2f", key="d45")
            vals['taban45'] = cols45[1].number_input("Taban (45)", value=165.0, format="%.2f", key="t45")
            vals['enerji45'] = cols45[2].number_input("Enerji (45)", value=110.0, format="%.2f", key="e45")
        
        # 90 DAKİKA
        with st.expander("📊 90. Dakika:", expanded=True):
            cols90 = st.columns(3)
            vals['direnc90'] = cols90[0].number_input("Direnç (90)", value=900.0, format="%.2f", key="d90")
            vals['taban90'] = cols90[1].number_input("Taban (90)", value=125.0, format="%.2f", key="t90")
            vals['enerji90'] = cols90[2].number_input("Enerji (90)", value=120.0, format="%.2f", key="e90")
        
        # 135 DAKİKA
        with st.expander("📊 135. Dakika:", expanded=True):
            cols135 = st.columns(3)
            vals['direnc135'] = cols135[0].number_input("Direnç (135)", value=980.0, format="%.2f", key="d135")
            vals['taban135'] = cols135[1].number_input("Taban (135)", value=120.0, format="%.2f", key="t135")
            vals['enerji135'] = cols135[2].number_input("Enerji (135)", value=126.0, format="%.2f", key="e135")

    st.divider()
    if st.button("💾 Kaydet", type="primary", use_container_width=True):
        if tonaj > kalan + 0.1:
            st.error(f"❌ Kapasite hatası: Sadece {kalan:.1f} ton eklenebilir!")
            return
        
        # 1. Tavlı analiz kaydet
        ok, msg = save_tavli_analiz(silo, tonaj, **vals, notlar=notlar, tarih=str(tarih))
        
        if ok:
            # 2. Tavlı stoku güncelle - DÜZELTİLMİŞ VERSİYON
            try:
                conn = get_conn()
                df_update = fetch_data("silolar")
                
                # DEBUG: Mevcut sütunları göster
                st.info(f"📊 Silolar tablosundaki sütunlar: {list(df_update.columns)}")
                
                if not df_update.empty:
                    mask = df_update['isim'] == silo
                    
                    if mask.any():
                        # Sütun adını kontrol et - TÜM OLASILIKLARı KAPSAYAN VERSİYON
                        tavli_col = None
                        for col_name in ['tavli_bugday_stok', 'tavli_stok', 'tavli_bugday', 'tavlı_stok']:
                            if col_name in df_update.columns:
                                tavli_col = col_name
                                break
                        
                        # Eğer sütun yoksa oluştur
                        if tavli_col is None:
                            st.warning("⚠️ Tavlı stok sütunu bulunamadı, 'tavli_bugday_stok' oluşturuluyor...")
                            df_update['tavli_bugday_stok'] = 0.0
                            tavli_col = 'tavli_bugday_stok'
                        
                        st.info(f"🔍 Kullanılan sütun adı: **{tavli_col}**")
                        
                        # Mevcut tavlı stoku al
                        current_tavli = float(df_update.loc[mask, tavli_col].iloc[0]) if pd.notnull(df_update.loc[mask, tavli_col].iloc[0]) else 0.0
                        
                        # Yeni tavlı stok hesapla
                        yeni_tavli = current_tavli + float(tonaj)
                        
                        # Güncelle
                        df_update.loc[mask, tavli_col] = yeni_tavli
                        conn.update(worksheet="silolar", data=df_update)
                        
                        st.success(f"✅ Tavlı analiz kaydedildi! Tavlı Stok: {current_tavli:.1f} → {yeni_tavli:.1f} Ton")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Silo bulunamadı!")
                else:
                    st.error("Silo verisi yüklenemedi!")
                    
            except Exception as e:
                st.error(f"❌ Stok güncelleme hatası: {str(e)}")
                st.error(f"🔍 Debug: {type(e).__name__}")
        else:
            st.error(f"❌ Kayıt hatası: {msg}")


def show_stok_hareketleri():
    """Stok Hareketleri Listesi"""
    st.header("📋 Stok Hareketleri")
    df = get_movements()
    if not df.empty:
        # Görünümü düzenle
        cols = ['tarih', 'lot_no', 'hareket_tipi', 'silo_isim', 'miktar', 'tedarikci', 'protein', 'sedim']
        # Varsa al, yoksa geç
        cols = [c for c in cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
    else:
        st.info("Kayıt yok")


def show_bugday_giris_arsivi():
    """Arşiv Ekranı"""
    st.header("🗄️ Giriş Arşivi")
    df = get_bugday_arsiv()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        # Excel İndir Butonu
        try:
            shared_download(df, "bugday_arsiv.xlsx")
        except:
            pass
    else:
        st.info("Kayıt yok")


def show_bugday_spec_yonetimi():
    """Buğday Spesifikasyon Yönetimi"""
    st.header("📐 Buğday Kalite Standartları")
    
    tab1, tab2 = st.tabs(["➕ Yeni Standart Ekle", "📋 Mevcut Standartlar"])
    
    with tab1:
        st.subheader("Yeni Standart Tanımla")
        
        col1, col2 = st.columns(2)
        with col1:
            cins = st.text_input("Buğday Cinsi *", placeholder="Örn: Bezostaya-1")
        
        with col2:
            param = st.selectbox("Parametre *", [
                "protein", "gluten", "rutubet", "hektolitre", 
                "sedim", "gluten_index", "sune", "kirik_ciliz", "yabanci_tane"
            ])
        
        col3, col4, col5 = st.columns(3)
        min_val = col3.number_input("Min Değer", 0.0, format="%.2f")
        max_val = col4.number_input("Max Değer", 0.0, format="%.2f")
        hedef_val = col5.number_input("Hedef Değer", 0.0, format="%.2f")
        
        if st.button("💾 Standart Kaydet", type="primary"):
            if cins and param:
                if save_bugday_spec(cins, param, min_val, max_val, hedef_val):
                    st.success("✅ Standart kaydedildi!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Lütfen tüm zorunlu alanları doldurun")
    
    with tab2:
        df_specs = get_all_bugday_specs_dataframe()
        if not df_specs.empty:
            # Cinslere göre grupla
            cinsler = df_specs['bugday_cinsi'].unique()
            
            for cins in cinsler:
                with st.expander(f"📦 {cins}", expanded=False):
                    cins_df = df_specs[df_specs['bugday_cinsi'] == cins]
                    st.dataframe(cins_df[['parametre', 'min_deger', 'max_deger', 'hedef_deger']], 
                               use_container_width=True, hide_index=True)
                    
                    if st.button(f"🗑️ {cins} Standardını Sil", key=f"del_{cins}"):
                        if delete_bugday_spec_group(cins):
                            st.success(f"✅ {cins} silindi")
                            time.sleep(1)
                            st.rerun()
        else:
            st.info("Henüz standart tanımlanmamış")
