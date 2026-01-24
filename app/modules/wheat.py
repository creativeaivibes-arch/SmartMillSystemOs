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
    """
    Geçmiş hareketleri tarayıp siloları senkronize eder (SQL Mantığı -> Pandas Mantığı)
    
    ÖNEMLİ: Bu fonksiyon her mal kabul/çıkıştan sonra otomatik çağrılır!
    """
    try:
        # ===== VERİLERİ ÇEK (FORCE REFRESH) =====
        from app.core.database import update_data, clear_cache
        
        # Cache'i temizle ve taze veri al
        clear_cache("silolar")
        clear_cache("hareketler")
        
        df_silolar = fetch_data("silolar", force_refresh=True)
        df_hareketler = fetch_data("hareketler", force_refresh=True)
        
        if df_silolar.empty:
            st.warning("⚠️ Silolar tablosu boş!")
            return False
        
        # Hareket yoksa siloları sıfırla ve çık
        if df_hareketler.empty:
            st.info("ℹ️ Henüz hareket kaydı yok, silolar sıfırlanıyor.")
            df_silolar['mevcut_miktar'] = 0.0
            df_silolar['protein'] = 0.0
            df_silolar['maliyet'] = 0.0
            return update_data("silolar", df_silolar)
        
        # ===== NUMERIC KOLONLARI DÜZELT =====
        numeric_cols = ['miktar', 'protein', 'maliyet', 'gluten', 'rutubet', 'hektolitre', 'sedim']
        for col in numeric_cols:
            if col in df_hareketler.columns:
                df_hareketler[col] = pd.to_numeric(df_hareketler[col], errors='coerce').fillna(0)
        
        # ===== HER SİLO İÇİN HESAPLA =====
        for index, row in df_silolar.iterrows():
            silo_isim = row['isim']
            
            # Bu silonun hareketlerini filtrele
            silo_moves = df_hareketler[df_hareketler['silo_isim'] == silo_isim].copy()
            
            if silo_moves.empty:
                # Hareket yoksa stoğu sıfırla
                df_silolar.at[index, 'mevcut_miktar'] = 0.0
                df_silolar.at[index, 'protein'] = 0.0
                df_silolar.at[index, 'maliyet'] = 0.0
                continue
            
            # ===== GİRİŞ VE ÇIKIŞ AYIR =====
            girisler = silo_moves[silo_moves['hareket_tipi'] == 'Giriş'].copy()
            cikislar = silo_moves[silo_moves['hareket_tipi'] == 'Çıkış'].copy()
            
            # ===== TOPLAM HESAPLA =====
            toplam_giris = girisler['miktar'].sum() if not girisler.empty else 0.0
            toplam_cikis = cikislar['miktar'].sum() if not cikislar.empty else 0.0
            
            mevcut_miktar = max(0, toplam_giris - toplam_cikis)
            
            # ===== AĞIRLIKLI ORTALAMA (Sadece Girişlerden) =====
            if not girisler.empty and toplam_giris > 0:
                try:
                    # Protein ortalaması
                    avg_protein = (girisler['miktar'] * girisler['protein']).sum() / toplam_giris
                    
                    # Maliyet ortalaması
                    avg_maliyet = (girisler['miktar'] * girisler['maliyet']).sum() / toplam_giris
                    
                    # Diğer parametreler (opsiyonel)
                    avg_gluten = (girisler['miktar'] * girisler['gluten']).sum() / toplam_giris if 'gluten' in girisler.columns else 0
                    avg_rutubet = (girisler['miktar'] * girisler['rutubet']).sum() / toplam_giris if 'rutubet' in girisler.columns else 0
                    avg_hektolitre = (girisler['miktar'] * girisler['hektolitre']).sum() / toplam_giris if 'hektolitre' in girisler.columns else 0
                    avg_sedim = (girisler['miktar'] * girisler['sedim']).sum() / toplam_giris if 'sedim' in girisler.columns else 0
                    
                    # Silo tablosunu güncelle
                    df_silolar.at[index, 'protein'] = avg_protein
                    df_silolar.at[index, 'maliyet'] = avg_maliyet
                    
                    # Eğer sütunlar varsa diğerlerini de güncelle
                    if 'gluten' in df_silolar.columns:
                        df_silolar.at[index, 'gluten'] = avg_gluten
                    if 'rutubet' in df_silolar.columns:
                        df_silolar.at[index, 'rutubet'] = avg_rutubet
                    if 'hektolitre' in df_silolar.columns:
                        df_silolar.at[index, 'hektolitre'] = avg_hektolitre
                    if 'sedim' in df_silolar.columns:
                        df_silolar.at[index, 'sedim'] = avg_sedim
                    
                except Exception as calc_err:
                    st.warning(f"⚠️ {silo_isim} için ortalama hesaplanamadı: {calc_err}")
                    # Hesaplama hatası olsa bile miktar güncellensin
                    pass
            else:
                # Giriş yoksa varsayılan değerler
                df_silolar.at[index, 'protein'] = 0.0
                df_silolar.at[index, 'maliyet'] = 0.0
            
            # ===== MEVCUT MİKTARI GÜNCELLE =====
            df_silolar.at[index, 'mevcut_miktar'] = mevcut_miktar
        
        # ===== GOOGLE SHEETS'E KAYDET (YENİ METODUMUZLA) =====
        if update_data("silolar", df_silolar):
            # Başarı mesajı (opsiyonel - çok fazla gösterilirse yorucu olur)
            # st.success("✅ Silo stokları güncellendi!")
            return True
        else:
            st.error("❌ Silo güncellemesi başarısız!")
            return False
        
    except Exception as e:
        st.error(f"❌ Silo hesaplama hatası: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
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
        
        # BOŞLUK KONTROLÜ
        if df_h.empty:
            st.warning("🔍 Hareketler tablosu boş!")
            return pd.DataFrame()
        
        # DEBUG: Sütunları göster (geçici - sonra silebilirsin)
        # st.info(f"Hareketler sütunları: {list(df_h.columns)}")
        # if not df_a.empty:
        #     st.info(f"Arşiv sütunları: {list(df_a.columns)}")
        
        # Arşiv yoksa hareketleri olduğu gibi döndür
        if df_a.empty:
            if 'tarih' in df_h.columns:
                df_h['tarih'] = pd.to_datetime(df_h['tarih'], errors='coerce')
                df_h = df_h.sort_values('tarih', ascending=False)
            return df_h
        
        # ===== LOT_NO KONTROLÜ =====
        if 'lot_no' not in df_h.columns:
            st.error("❌ 'lot_no' sütunu hareketler tablosunda bulunamadı!")
            # lot_no yoksa hareketleri olduğu gibi göster
            return df_h
        
        if 'lot_no' not in df_a.columns:
            st.warning("⚠️ 'lot_no' sütunu arşiv tablosunda bulunamadı!")
            return df_h
        
        # ===== ARŞİVDEN ALINACAK SÜTUNLARI BELİRLE (Mevcut olanları al) =====
        arsiv_kolonlar = ['lot_no']  # lot_no kesin olmalı
        
        # İsteğe bağlı sütunları ekle (varsa)
        optional_cols = [
            'tedarikci', 'yore', 'plaka', 'bugday_cinsi', 
            'sune', 'kirik_ciliz', 'yabanci_tane', 
            'gluten_index', 'gecikmeli_sedim'
        ]
        
        for col in optional_cols:
            if col in df_a.columns:
                arsiv_kolonlar.append(col)
        
        # ===== PANDAS MERGE (LEFT JOIN) =====
        merged = pd.merge(
            df_h, 
            df_a[arsiv_kolonlar], 
            on='lot_no', 
            how='left',  # Sol tablodaki (hareketler) tüm kayıtları koru
            suffixes=('', '_arsiv')
        )
        
        # ===== ÇAKIŞAN SÜTUNLARI BİRLEŞTİR =====
        # Eğer hem hareketler hem arşivde aynı sütun varsa (örn: tedarikci)
        # Hareketlerdeki boşsa arşivden doldur
        for col in ['tedarikci', 'yore', 'bugday_cinsi']:
            if col in merged.columns and f'{col}_arsiv' in merged.columns:
                merged[col] = merged[col].fillna(merged[f'{col}_arsiv'])
                # Gereksiz _arsiv sütununu sil
                merged.drop(f'{col}_arsiv', axis=1, inplace=True)
        
        # ===== TARİH SIRALAMASI =====
        if 'tarih' in merged.columns:
            merged['tarih'] = pd.to_datetime(merged['tarih'], errors='coerce')
            merged = merged.sort_values('tarih', ascending=False)
        
        return merged
        
    except Exception as e:
        st.error(f"❌ Hareket yükleme hatası: {e}")
        import traceback
        st.code(traceback.format_exc())
        return pd.DataFrame()
        
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
        mevcut = float(silo_row.get('mevcut_miktar', 0))
        kapasite = float(silo_row.get('kapasite', 0))
        kalan = kapasite - mevcut
        st.info(f"Kalan Kapasite: {kalan:.1f} Ton")
        
        tarih = st.date_input("Kabul Tarihi *", datetime.now())
        
        # Spec Listesi (Opsiyonel Validation İçin)
        specs_list = []
        df_specs = fetch_data("bugday_spekleri")
        if not df_specs.empty:
            specs_list = df_specs['bugday_cinsi'].unique().tolist()
            
        secilen_standart = st.selectbox("Standart Seçiniz", ["(Standart Yok)"] + specs_list)
        bugday_cinsi = st.text_input("Buğday Cinsi *", placeholder="Örn: Esperia")
        
        current_specs = {}
        if secilen_standart != "(Standart Yok)":
            df_s = df_specs[df_specs['bugday_cinsi'] == secilen_standart]
            for _, row in df_s.iterrows():
                current_specs[row['parametre']] = row

        tedarikci = st.text_input("Tedarikçi/Firma *")
        yore = st.text_input("Yöre/Bölge *")
        plaka = st.text_input("Plaka *")
        notlar = st.text_area("Notlar", key="mal_kabul_notlar")
        
        # Manuel Kantar
        miktar = st.number_input("Gelen Miktar (Ton) *", min_value=27.0, format="%.1f")
        fiyat = st.number_input("Alış Fiyatı (TL) *", min_value=15.0, format="%.2f")

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
            
            sune = st.number_input("Süne (%)", 0.0, 10.0, 0.5)
            validate_val("sune", sune, "Süne")

        with c3:
            kirik_ciliz = st.number_input("Kırık & Cılız (%)", 0.0, 100.0, 3.0)
            validate_val("kirik_ciliz", kirik_ciliz, "Kırık/Cılız")
            
            yabanci_tane = st.number_input("Yabancı Tane (%)", 0.0, 100.0, 3.5)
            validate_val("yabanci_tane", yabanci_tane, "Yabancı Tane")
            
            hasere = st.selectbox("Haşere", ["Yok", "Var"])

    st.divider()
    if st.button("💾 Kaydı Tamamla", type="primary", use_container_width=True):
        # ===== KAPSAMLI VALİDASYON SİSTEMİ =====
        from app.core.config import validate_numeric_input, validate_capacity
        
        validasyon_hatalari = []
        
        # 1. Miktar kontrolü
        valid, msg, _ = validate_numeric_input(miktar, 'tonaj', allow_zero=False, allow_negative=False)
        if not valid:
            validasyon_hatalari.append(f"Miktar: {msg}")
        
        # 2. Fiyat kontrolü
        valid, msg, _ = validate_numeric_input(fiyat, 'fiyat', allow_zero=False, allow_negative=False)
        if not valid:
            validasyon_hatalari.append(f"Fiyat: {msg}")
        
        # 3. Analiz değerleri kontrolü
        analiz_checks = [
            (g_hl, 'hektolitre', 'Hektolitre'),
            (g_rut, 'rutubet', 'Rutubet'),
            (g_prot, 'protein', 'Protein'),
            (g_glut, 'gluten', 'Gluten'),
            (g_index, 'gluten_index', 'Gluten Index'),
            (g_sedim, 'sedim', 'Sedimantasyon'),
            (sune, 'sune', 'Süne'),
        ]
        
        for deger, key, label in analiz_checks:
            if deger > 0:  # Sadece girilmişse kontrol et
                valid, msg, _ = validate_numeric_input(deger, key, allow_zero=True, allow_negative=False)
                if not valid:
                    validasyon_hatalari.append(f"{label}: {msg}")
        
        # 4. Kapasite kontrolü (YENİ YÖNTEM)
        valid, msg, kalan_yeni = validate_capacity(mevcut, kapasite, miktar)
        if not valid:
            validasyon_hatalari.append(msg)
        
        # 5. Zorunlu alanlar
        if not (bugday_cinsi and tedarikci and plaka):
            validasyon_hatalari.append("❌ Buğday cinsi, tedarikçi ve plaka zorunludur!")
        
        # ===== HATA VARSA GÖSTER VE DUR =====
        if validasyon_hatalari:
            st.error("🚫 Lütfen aşağıdaki hataları düzeltin:")
            for hata in validasyon_hatalari:
                st.write(f"- {hata}")
            return
        
        # ===== VALİDASYON BAŞARILI - KAYIT İŞLEMİ =====
        note_final = f"Plaka: {plaka} | {notlar}"
        if hasere == "Var": note_final += " | HAŞERE RİSKİ"
        
        # Kayıt (Stok Hareketi + Arşiv)
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
                
                # Silo stoklarını yeniden hesapla
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
    if df.empty: 
        st.warning("Silo bulunamadı.")
        return
    
    c1, c2 = st.columns(2)
    with c1:
        silo = st.selectbox("Kaynak Silo", df['isim'].tolist())
        row = df[df['isim'] == silo].iloc[0]
        mevcut = float(row['mevcut_miktar'])
        st.metric("Mevcut", f"{mevcut:.1f} Ton")
        
        miktar = st.number_input("Miktar (Ton)", 0.1, max_value=mevcut if mevcut > 0 else 0.1)
        neden = st.selectbox("Neden", ["Üretime Gönderim", "Silo Transferi", "Satış", "Zayi"])
        
        hedef = None
        if neden == "Silo Transferi":
            hedef = st.selectbox("Hedef Silo", [s for s in df['isim'].tolist() if s != silo])
            
    with c2:
        # Önizleme
        yeni = max(0, mevcut - miktar)
        doluluk = yeni / float(row['kapasite']) if float(row['kapasite']) > 0 else 0
        st.markdown(draw_silo(doluluk, f"Kalan: {yeni:.1f}"), unsafe_allow_html=True)
    
    st.divider()
    
    if st.button("📤 Çıkışı Onayla", type="primary", use_container_width=True):
        # ===== VALİDASYON SİSTEMİ =====
        from app.core.config import validate_stock_withdrawal
        
        validasyon_hatalari = []
        
        # 1. Stok çıkış kontrolü
        valid, msg = validate_stock_withdrawal(mevcut, miktar)
        if not valid:
            validasyon_hatalari.append(msg)
        
        # 2. Transfer kontrolü (hedef silo seçilmiş mi?)
        if neden == "Silo Transferi" and not hedef:
            validasyon_hatalari.append("❌ Transfer için hedef silo seçmelisiniz!")
        
        # 3. Transfer hedef kapasite kontrolü
        if neden == "Silo Transferi" and hedef:
            from app.core.config import validate_capacity
            
            hedef_row = df[df['isim'] == hedef].iloc[0]
            hedef_mevcut = float(hedef_row['mevcut_miktar'])
            hedef_kapasite = float(hedef_row['kapasite'])
            
            valid, msg, _ = validate_capacity(hedef_mevcut, hedef_kapasite, miktar)
            if not valid:
                validasyon_hatalari.append(f"Hedef Silo: {msg}")
        
        # ===== HATA VARSA GÖSTER VE DUR =====
        if validasyon_hatalari:
            st.error("🚫 Lütfen aşağıdaki hataları düzeltin:")
            for hata in validasyon_hatalari:
                st.write(f"- {hata}")
            return
        
        # ===== VALİDASYON BAŞARILI - ÇIKIŞ İŞLEMİ =====
        if log_stok_hareketi(silo, "Çıkış", miktar, notlar=neden):
            update_tavli_bugday_stok(silo, miktar, "cikar")
            
            # Transfer ise hedefe giriş yap
            if neden == "Silo Transferi" and hedef:
                log_stok_hareketi(hedef, "Giriş", miktar, 
                                 protein=float(row['protein']), 
                                 maliyet=float(row['maliyet']), 
                                 notlar=f"Transfer: {silo}")
                update_tavli_bugday_stok(hedef, miktar, "ekle")
            
            # Silo stoklarını yeniden hesapla
            recalculate_silos_from_logs()
            
            st.success("✅ İşlem Başarılı!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ Çıkış kaydı oluşturulamadı!")

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
        notlar = st.text_area("Notlar", key="tavli_notlar")

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
        vals['amilograph'] = cc2.number_input("Amilograph", value=1100.0, format="%.2f")
        
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
    """
    Buğday Giriş Arşivi - PROFESYONEL VERSİYON
    - Sayfalandırma (10 kayıt/sayfa)
    - Çoklu filtre sistemi
    - Profesyonel Excel export
    """
    st.header("🗄️ Buğday Giriş Arşivi")
    
    df = get_bugday_arsiv()
    
    if df.empty:
        st.info("📭 Henüz arşiv kaydı bulunmuyor.")
        return
    
    # ===== FİLTRE SİSTEMİ =====
    with st.expander("🔍 Gelişmiş Filtreleme Sistemi", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            # Tarih Aralığı Filtresi
            st.markdown("**📅 Tarih Aralığı**")
            if 'tarih' in df.columns:
                df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
                min_tarih = df['tarih'].min().date() if not df['tarih'].isna().all() else datetime.now().date()
                max_tarih = df['tarih'].max().date() if not df['tarih'].isna().all() else datetime.now().date()
                
                baslangic = st.date_input("Başlangıç", min_tarih, key="arsiv_baslangic")
                bitis = st.date_input("Bitiş", max_tarih, key="arsiv_bitis")
            else:
                baslangic = bitis = datetime.now().date()
        
        with col_f2:
            # Tedarikçi Filtresi
            st.markdown("**🏢 Tedarikçi**")
            tedarikci_list = ["Tümü"] + sorted(df['tedarikci'].dropna().unique().tolist()) if 'tedarikci' in df.columns else ["Tümü"]
            secili_tedarikci = st.selectbox("Seçiniz", tedarikci_list, key="arsiv_tedarikci")
            
            # Buğday Cinsi Filtresi
            st.markdown("**🌾 Buğday Cinsi**")
            cins_list = ["Tümü"] + sorted(df['bugday_cinsi'].dropna().unique().tolist()) if 'bugday_cinsi' in df.columns else ["Tümü"]
            secili_cins = st.selectbox("Seçiniz", cins_list, key="arsiv_cins")
        
        with col_f3:
            # Yöre Filtresi
            st.markdown("**🗺️ Yöre/Bölge**")
            yore_list = ["Tümü"] + sorted(df['yore'].dropna().unique().tolist()) if 'yore' in df.columns else ["Tümü"]
            secili_yore = st.selectbox("Seçiniz", yore_list, key="arsiv_yore")
            
            # Arama Kutusu (Lot No / Plaka)
            st.markdown("**🔎 Hızlı Arama**")
            arama = st.text_input("Lot No / Plaka", placeholder="BUGDAY-241225...", key="arsiv_arama")
    
    # ===== FİLTRE UYGULAMA =====
    df_filtered = df.copy()
    
    # Tarih Filtresi
    if 'tarih' in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered['tarih'].dt.date >= baslangic) & 
            (df_filtered['tarih'].dt.date <= bitis)
        ]
    
    # Tedarikçi Filtresi
    if secili_tedarikci != "Tümü" and 'tedarikci' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['tedarikci'] == secili_tedarikci]
    
    # Buğday Cinsi Filtresi
    if secili_cins != "Tümü" and 'bugday_cinsi' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['bugday_cinsi'] == secili_cins]
    
    # Yöre Filtresi
    if secili_yore != "Tümü" and 'yore' in df_filtered.columns:
        df_filtered = df_filtered[df_filtered['yore'] == secili_yore]
    
    # Arama Filtresi
    if arama:
        arama_mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
        if 'lot_no' in df_filtered.columns:
            arama_mask |= df_filtered['lot_no'].str.contains(arama, case=False, na=False)
        if 'plaka' in df_filtered.columns:
            arama_mask |= df_filtered['plaka'].str.contains(arama, case=False, na=False)
        df_filtered = df_filtered[arama_mask]
    
    # ===== İSTATİSTİK ÖZETİ =====
    if not df_filtered.empty:
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("📊 Toplam Kayıt", len(df_filtered))
        col_s2.metric("🚛 Toplam Tonaj", f"{df_filtered['tonaj'].sum():.1f} Ton" if 'tonaj' in df_filtered.columns else "N/A")
        col_s3.metric("🏢 Tedarikçi Sayısı", df_filtered['tedarikci'].nunique() if 'tedarikci' in df_filtered.columns else 0)
        col_s4.metric("🌾 Buğday Çeşidi", df_filtered['bugday_cinsi'].nunique() if 'bugday_cinsi' in df_filtered.columns else 0)
    
    st.divider()
    
    # ===== TABLO HAZIRLAMA =====
    if df_filtered.empty:
        st.warning("⚠️ Filtre kriterlerine uygun kayıt bulunamadı.")
        return
    
    # Sütun Sıralaması ve Türkçe Başlıklar
    kolon_map = {
        'tarih': 'Tarih',
        'lot_no': 'Lot No',
        'bugday_cinsi': 'Buğday Cinsi',
        'tedarikci': 'Tedarikçi / Firma',
        'yore': 'Yöre / Bölge',
        'plaka': 'Plaka',
        'hektolitre': 'Hektolitre',
        'protein': 'Protein (%)',
        'gluten': 'Gluten (%)',
        'gluten_index': 'Gluten Index',
        'sedim': 'Sedim (ml)',
        'gecikmeli_sedim': 'G. Sedim (ml)',
        'sune': 'Süne (%)',
        'kirik_ciliz': 'Kırık & Cılız (%)',
        'yabanci_tane': 'Yabancı Tane (%)',
        'tonaj': 'Tonaj',
        'fiyat': 'Fiyat (TL)'
    }
    
    # Sadece var olan sütunları seç
    mevcut_kolonlar = [k for k in kolon_map.keys() if k in df_filtered.columns]
    df_display = df_filtered[mevcut_kolonlar].copy()
    
    # Tarih formatı düzelt (sadece gün-ay-yıl)
    if 'tarih' in df_display.columns:
        df_display['tarih'] = df_display['tarih'].dt.strftime('%d.%m.%Y')
    
    # Haşere bilgisi (notlardan çıkar - opsiyonel)
    if 'notlar' in df_filtered.columns:
        df_display['Haşere'] = df_filtered['notlar'].apply(
            lambda x: 'Var' if isinstance(x, str) and 'HAŞ' in x.upper() else 'Yok'
        )
    
    # Türkçe başlıkları uygula
    df_display = df_display.rename(columns=kolon_map)
    
    # ID sütunu ekle (1, 2, 3...)
    df_display.insert(0, 'ID', range(1, len(df_display) + 1))
    
    # ===== SAYFALANDIRMA =====
    sayfa_basi = 10
    toplam_sayfa = (len(df_display) - 1) // sayfa_basi + 1
    
    col_page1, col_page2, col_page3 = st.columns([2, 1, 2])
    with col_page2:
        sayfa = st.number_input(
            f"Sayfa (1-{toplam_sayfa})", 
            min_value=1, 
            max_value=toplam_sayfa, 
            value=1, 
            key="arsiv_sayfa"
        )
    
    # İlgili sayfayı göster
    baslangic_idx = (sayfa - 1) * sayfa_basi
    bitis_idx = min(sayfa * sayfa_basi, len(df_display))
    df_sayfa = df_display.iloc[baslangic_idx:bitis_idx]
    
    # ===== TABLO GÖRÜNÜMÜ =====
    st.dataframe(
        df_sayfa,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Tarih": st.column_config.TextColumn("Tarih", width="medium"),
            "Lot No": st.column_config.TextColumn("Lot No", width="medium"),
            "Protein (%)": st.column_config.NumberColumn("Protein (%)", format="%.2f"),
            "Gluten (%)": st.column_config.NumberColumn("Gluten (%)", format="%.2f"),
            "Hektolitre": st.column_config.NumberColumn("Hektolitre", format="%.1f"),
            "Tonaj": st.column_config.NumberColumn("Tonaj", format="%.1f"),
            "Fiyat (TL)": st.column_config.NumberColumn("Fiyat", format="%.2f ₺")
        }
    )
    
    st.caption(f"Gösterilen: {baslangic_idx + 1}-{bitis_idx} / Toplam: {len(df_filtered)} kayıt")
    
    # ===== EXCEL EXPORT (PROFESYONEL) =====
    st.divider()
    
    if st.button("📥 Excel İndir (Tüm Filtreli Veriler)", type="primary", use_container_width=True):
        export_profesyonel_excel(df_display, "Bugday_Giris_Arsivi")

def export_profesyonel_excel(df, dosya_adi="Arsiv"):
    """
    Profesyonel Excel Export (SADECE XLSX)
    - Renkli başlıklar
    - Hücre kenarlıkları
    - Otomatik sütun genişliği
    """
    try:
        from io import BytesIO
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
        from openpyxl.utils.dataframe import dataframe_to_rows
        
        # Yeni workbook oluştur
        wb = Workbook()
        ws = wb.active
        ws.title = "Arşiv"
        
        # DataFrame'i satır satır ekle
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=value)
                
                # Kenarlık tanımla
                border = Border(
                    left=Side(style='thin', color='000000'),
                    right=Side(style='thin', color='000000'),
                    top=Side(style='thin', color='000000'),
                    bottom=Side(style='thin', color='000000')
                )
                cell.border = border
                
                # Başlık satırı ise (1. satır)
                if r_idx == 1:
                    cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
                    cell.font = Font(bold=True, color="FFFFFF", size=11)
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                else:
                    # Veri hücreleri
                    cell.alignment = Alignment(vertical='center')
        
        # Sütun genişliklerini ayarla
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = min(max_length + 3, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # BytesIO buffer'a kaydet
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        
        # Download butonu
        st.download_button(
            label="📄 Excel Dosyasını İndir (.xlsx)",
            data=output.getvalue(),
            file_name=f"{dosya_adi}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="secondary",
            use_container_width=True
        )
        
        st.success("✅ Excel dosyası hazır!")
        
    except ImportError:
        st.error("❌ openpyxl kütüphanesi eksik! requirements.txt'e ekleyin.")
    except Exception as e:
        st.error(f"❌ Excel oluşturma hatası: {e}")

def show_bugday_spec_yonetimi():
    """Buğday Spesifikasyon Yönetimi - GELİŞTİRİLMİŞ TASARIM"""
    st.header("📏 Buğday Kalite Standartları")
    
    tab1, tab2 = st.tabs(["➕ Yeni Standart Ekle", "📋 Mevcut Standartlar"])
    
    with tab1:
        st.subheader("Yeni Standart Tanımla")
        
        # Parametre mapping (ikon + Türkçe)
        PARAMETRE_MAP = {
            "protein": {"label": "🧬 Protein", "birim": "%"},
            "gluten": {"label": "🌾 Gluten", "birim": "%"},
            "rutubet": {"label": "💧 Rutubet", "birim": "%"},
            "hektolitre": {"label": "📊 Hektolitre", "birim": "kg/hl"},
            "sedim": {"label": "🔬 Sedimantasyon", "birim": "ml"},
            "gluten_index": {"label": "⚗️ Gluten Index", "birim": "%"},
            "sune": {"label": "🐛 Süne", "birim": "%"},
            "kirik_ciliz": {"label": "💔 Kırık & Cılız", "birim": "%"},
            "yabanci_tane": {"label": "🌿 Yabancı Tane", "birim": "%"}
        }
        
        col1, col2 = st.columns(2)
        with col1:
            cins = st.text_input("**🏷️ Buğday Cinsi** *", placeholder="Örn: Bezostaya-1")
        
        with col2:
            param_labels = [f"{v['label']}" for k, v in PARAMETRE_MAP.items()]
            param_keys = list(PARAMETRE_MAP.keys())
            selected_label = st.selectbox("**🔬 Kalite Parametresi** *", param_labels)
            param = param_keys[param_labels.index(selected_label)]
            birim = PARAMETRE_MAP[param]['birim']
        
        # Değer girişleri - KART TASARIMI
        st.markdown("#### 📐 Standart Değerler")
        with st.container(border=True):
            col3, col4, col5 = st.columns(3)
            min_val = col3.number_input(f"**Minimum** ({birim})", 0.0, format="%.2f", help="Kabul edilebilir en düşük değer")
            max_val = col4.number_input(f"**Maximum** ({birim})", 0.0, format="%.2f", help="Kabul edilebilir en yüksek değer")
            hedef_val = col5.number_input(f"**Hedef** ({birim})", 0.0, format="%.2f", help="İdeal hedef değer")
        
        st.divider()
        if st.button("💾 Standart Kaydet", type="primary", use_container_width=True):
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
            
            PARAMETRE_MAP = {
                "protein": {"label": "🧬 Protein", "birim": "%"},
                "gluten": {"label": "🌾 Gluten", "birim": "%"},
                "rutubet": {"label": "💧 Rutubet", "birim": "%"},
                "hektolitre": {"label": "📊 Hektolitre", "birim": "kg/hl"},
                "sedim": {"label": "🔬 Sedimantasyon", "birim": "ml"},
                "gluten_index": {"label": "⚗️ Gluten Index", "birim": "%"},
                "sune": {"label": "🐛 Süne", "birim": "%"},
                "kirik_ciliz": {"label": "💔 Kırık & Cılız", "birim": "%"},
                "yabanci_tane": {"label": "🌿 Yabancı Tane", "birim": "%"}
            }
            
            for cins in cinsler:
                with st.expander(f"🌾 **{cins}**", expanded=False):
                    cins_df = df_specs[df_specs['bugday_cinsi'] == cins].copy()
                    
                    # Parametreleri Türkçe etiketle
                    cins_df['Parametre'] = cins_df['parametre'].apply(
                        lambda x: PARAMETRE_MAP.get(x, {"label": x})['label']
                    )
                    
                    # Gösterim için yeniden düzenle
                    display_df = cins_df[['Parametre', 'min_deger', 'max_deger', 'hedef_deger']].copy()
                    display_df.columns = ['Parametre', 'Min', 'Max', 'Hedef']
                    
                    st.dataframe(
                        display_df, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "Parametre": st.column_config.TextColumn("Parametre", width="medium"),
                            "Min": st.column_config.NumberColumn("Min", format="%.2f"),
                            "Max": st.column_config.NumberColumn("Max", format="%.2f"),
                            "Hedef": st.column_config.NumberColumn("Hedef ⭐", format="%.2f")
                        }
                    )
                    
                    # Silme butonu - ONAY İLE
                    col_a, col_b = st.columns([3, 1])
                    with col_b:
                        if st.button(f"🗑️ Sil", key=f"del_{cins}", type="secondary", use_container_width=True):
                            if f"confirm_delete_{cins}" not in st.session_state:
                                st.session_state[f"confirm_delete_{cins}"] = True
                                st.warning(f"⚠️ '{cins}' standardını silmek istediğinize emin misiniz?")
                                st.rerun()
                    
                    # Onay mesajı gösterildiyse
                    if st.session_state.get(f"confirm_delete_{cins}", False):
                        col_x, col_y = st.columns(2)
                        with col_x:
                            if st.button("✅ Evet, Sil", key=f"confirm_yes_{cins}", type="primary"):
                                if delete_bugday_spec_group(cins):
                                    st.success(f"✅ {cins} silindi")
                                    del st.session_state[f"confirm_delete_{cins}"]
                                    time.sleep(1)
                                    st.rerun()
                        with col_y:
                            if st.button("❌ İptal", key=f"confirm_no_{cins}"):
                                del st.session_state[f"confirm_delete_{cins}"]
                                st.rerun()
        else:
            st.info("📭 Henüz standart tanımlanmamış")
            st.markdown("""
            **💡 İpucu:** Yeni bir standart eklemek için yukarıdaki **'Yeni Standart Ekle'** sekmesini kullanın.
            """)
# --------------------------------------------------------------------------
# BUĞDAY YÖNETİM MERKEZİ (YENİ EKLENEN ANA FONKSİYON)
# --------------------------------------------------------------------------
def show_wheat_yonetimi():
    """
    Buğday Operasyon Merkezi
    Tüm giriş, analiz, paçal ve stok süreçlerinin yönetildiği ana ekran.
    """
    
    # 1. Başlık Alanı (Yeşil/Tarım Teması)
    st.markdown("""
    <div style='background-color: #E8F5E9; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #2E7D32;'>
        <h2 style='color: #1B5E20; margin:0;'>🌾 Buğday Operasyon Merkezi</h2>
        <p style='color: #4CAF50; margin:0; font-size: 14px;'>Hammadde Giriş, Kalite Yönetimi, Paçal ve Stok Takibi</p>
    </div>
    """, unsafe_allow_html=True)

    # 2. Yatay Menü (Senin belirlediğin yapı)
    secim = st.radio(
        "Modül Seçiniz:",
        [
            "🚛 Giriş & Kalite Operasyonları", 
            "⚗️ Paçal (Blend) Yönetimi", 
            "📤 Stok Çıkışı", 
            "📂 Veri Tabanı & İzlenebilirlik"
        ],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.markdown("---")

    # 3. Yönlendirmeler ve Sekmeler
    
    # --- A) GİRİŞ & KALİTE ---
    if secim == "🚛 Giriş & Kalite Operasyonları":
        # İç Sekmeler
        tab1, tab2, tab3 = st.tabs(["📐 Spek & Hedefler", "📥 Hammadde Giriş", "🧪 Tavlı Analiz Girişi"])
        
        with tab1:
            with st.container(border=True):
                show_bugday_spec_yonetimi()
        
        with tab2:
            with st.container(border=True):
                show_mal_kabul()
                
        with tab3:
            with st.container(border=True):
                show_tavli_analiz()

    # --- B) PAÇAL (BLEND) YÖNETİMİ ---
    elif secim == "⚗️ Paçal (Blend) Yönetimi":
        try:
            import app.modules.calculations as calculations
            
            tab_p1, tab_p2 = st.tabs(["🧮 Paçal Hesaplayıcı", "📜 Paçal Geçmişi"])
            
            with tab_p1:
                with st.container(border=True):
                    if hasattr(calculations, 'show_pacal_hesaplayici'):
                        calculations.show_pacal_hesaplayici()
                    else:
                        st.warning("⚠️ Paçal Hesaplayıcı modülü bulunamadı.")
            
            with tab_p2:
                with st.container(border=True):
                    if hasattr(calculations, 'show_pacal_gecmisi'):
                        calculations.show_pacal_gecmisi()
                    else:
                        st.warning("⚠️ Paçal Geçmişi modülü bulunamadı.")
                        
        except ImportError:
            st.error("⚠️ 'app.modules.calculations' modülü yüklenemedi!")
        except Exception as e:
            st.error(f"⚠️ Bir hata oluştu: {e}")

    # --- C) STOK ÇIKIŞI ---
    elif secim == "📤 Stok Çıkışı":
        with st.container(border=True):
            show_stok_cikis()

    # --- D) VERİ TABANI & İZLENEBİLİRLİK ---
    elif secim == "📂 Veri Tabanı & İzlenebilirlik":
        tab_db1, tab_db2 = st.tabs(["📒 Giriş Arşivi", "🔄 Stok Hareketleri"])
        
        with tab_db1:
            with st.container(border=True):
                show_bugday_giris_arsivi()
                
        with tab_db2:
            with st.container(border=True):
                show_stok_hareketleri()















