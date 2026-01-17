import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np

# --- DATABASE IMPORTLARI (GÜNCELLENDİ) ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.config import INPUT_LIMITS, TERMS, get_limit
from app.core.error_handling import error_handler, log_debug, log_info, log_warning, handle_error, ERROR_HANDLING_AVAILABLE
from app.modules.dashboard import get_silo_data, draw_silo
from app.core.components import render_help_button

# --- DATA MANIPULATION FUNCTIONS ---

@error_handler(context="Stok Hareketi Loglama")
def log_stok_hareketi(silo_isim, hareket_tipi, miktar, **kwargs):
    """Stok hareketini logla - GOOGLE SHEETS UYUMLU"""
    log_info(f"Stok hareketi: {silo_isim} - {hareket_tipi} - {miktar}ton", "Stok Yönetimi")
    try:
        # Benzersiz ID oluştur (Update/Delete işlemleri için gerekli)
        unique_id = int(datetime.now().timestamp() * 1000)
        
        # Temel veriler
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

        # Google Sheets'e ekle
        if add_data("hareketler", data):
            log_info(f"Stok hareketi başarıyla loglandı: {silo_isim}", "Stok Yönetimi")
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"❌ Hareket kaydı hatası: {str(e)}")
        return False

def update_tavli_bugday_stok(silo_isim, eklenen_tonaj, islem_tipi="ekle"):
    """Tavlı buğday stokunu güncelle - GOOGLE SHEETS UYUMLU"""
    try:
        conn = get_conn()
        df = fetch_data("silolar")
        
        if df.empty:
            return False

        # İlgili siloyu bul
        mask = df['isim'] == silo_isim
        if not mask.any():
            return False
            
        current = float(df.loc[mask, 'tavli_bugday_stok'].iloc[0]) if pd.notnull(df.loc[mask, 'tavli_bugday_stok'].iloc[0]) else 0.0
        
        # Hesapla
        if islem_tipi == "ekle":
            yeni_tavli = current + float(eklenen_tonaj)
        elif islem_tipi == "cikar":
            yeni_tavli = current - float(eklenen_tonaj)
            if yeni_tavli < 0: yeni_tavli = 0
        else:
            return False
            
        # Güncelle
        df.loc[mask, 'tavli_bugday_stok'] = yeni_tavli
        conn.update(worksheet="silolar", data=df)
        return True
            
    except Exception as e:
        st.error(f"Tavlı stok güncelleme hatası: {str(e)}")
        return False

def recalculate_silos_from_logs():
    """
    Geçmiş hareketleri tarayıp Dashboard'u sıfırdan hesaplar.
    SQL döngüsü yerine Pandas işlemleri kullanılır.
    """
    try:
        conn = get_conn()
        
        # 1. Verileri Çek
        df_silolar = fetch_data("silolar")
        df_hareketler = fetch_data("hareketler")
        
        if df_silolar.empty:
            return False

        # Hareketler boşsa siloları sıfırla ama yapıyı koru
        if df_hareketler.empty:
            # Burası opsiyonel, şimdilik pas geçiyoruz
            return True

        # Tarihe göre sırala (Eskiden yeniye)
        if 'tarih' in df_hareketler.columns:
            df_hareketler['tarih'] = pd.to_datetime(df_hareketler['tarih'])
            df_hareketler = df_hareketler.sort_values('tarih')

        # Her silo için hesaplama yap
        for index, row in df_silolar.iterrows():
            silo_isim = row['isim']
            
            # Bu siloya ait hareketleri filtrele
            silo_moves = df_hareketler[df_hareketler['silo_isim'] == silo_isim]
            
            curr_miktar = 0.0
            curr_vals = {
                'protein': 0.0, 'gluten': 0.0, 'rutubet': 0.0, 
                'hektolitre': 0.0, 'sedim': 0.0, 'maliyet': 0.0
            }
            
            for _, h in silo_moves.iterrows():
                h_tip = h['hareket_tipi']
                h_miktar = float(h['miktar']) if pd.notnull(h['miktar']) else 0.0
                
                if h_tip == 'Giriş':
                    if (curr_miktar + h_miktar) > 0:
                        # Ağırlıklı ortalama
                        for key in curr_vals.keys():
                            h_val = float(h.get(key, 0)) if pd.notnull(h.get(key, 0)) else 0.0
                            curr_vals[key] = ((curr_miktar * curr_vals[key]) + (h_miktar * h_val)) / (curr_miktar + h_miktar)
                        curr_miktar += h_miktar
                    else:
                        # Sıfırdan başlama
                        curr_miktar = h_miktar
                        for key in curr_vals.keys():
                            curr_vals[key] = float(h.get(key, 0)) if pd.notnull(h.get(key, 0)) else 0.0
                            
                elif h_tip == 'Çıkış':
                    curr_miktar -= h_miktar
                    if curr_miktar < 0: curr_miktar = 0
            
            # DataFrame'i güncelle
            df_silolar.at[index, 'mevcut_miktar'] = curr_miktar
            for key, val in curr_vals.items():
                df_silolar.at[index, key] = val

        # Google Sheets'e tek seferde yaz
        conn.update(worksheet="silolar", data=df_silolar)
        return True
            
    except Exception as e:
        st.error(f"Silo yeniden hesaplama hatası: {str(e)}")
        return False

def add_to_bugday_giris_arsivi(lot_no, tarih, bugday_cinsi, tedarikci, yore, plaka, 
                             tonaj, fiyat, silo_isim, hektolitre, protein, rutubet, gluten, 
                             gluten_index, sedim, gecikmeli_sedim, sune, kirik_ciliz, 
                             yabanci_tane, notlar):
    """Buğday girişini arşive ekle"""
    try:
        # Veri Paketi
        data = {
            'lot_no': lot_no,
            'tarih': str(tarih),
            'bugday_cinsi': bugday_cinsi,
            'tedarikci': tedarikci,
            'yore': yore,
            'plaka': plaka,
            'tonaj': float(tonaj),
            'fiyat': float(fiyat),
            'silo_isim': silo_isim,
            'hektolitre': float(hektolitre),
            'protein': float(protein),
            'rutubet': float(rutubet),
            'gluten': float(gluten),
            'gluten_index': float(gluten_index),
            'sedim': float(sedim),
            'gecikmeli_sedim': float(gecikmeli_sedim),
            'sune': float(sune),
            'kirik_ciliz': float(kirik_ciliz),
            'yabanci_tane': float(yabanci_tane),
            'notlar': notlar
        }
        
        # Lot No kontrolü (Duplicate Check)
        df = fetch_data("bugday_giris_arsivi")
        if not df.empty and 'lot_no' in df.columns:
            if lot_no in df['lot_no'].values:
                st.error(f"❌ Bu lot numarası zaten kayıtlı: {lot_no}")
                return False

        return add_data("bugday_giris_arsivi", data)
            
    except Exception as e:
        st.error(f"❌ Arşiv kaydı hatası: {str(e)}")
        return False

def get_movements():
    """Stok hareketlerini detaylı getir (JOIN işlemi Pandas ile yapılır)"""
    try:
        # İki tabloyu da çek
        df_hareketler = fetch_data("hareketler")
        df_arsiv = fetch_data("bugday_giris_arsivi")
        
        if df_hareketler.empty:
            return pd.DataFrame()
            
        # Eğer Arşiv boşsa sadece hareketleri dön
        if df_arsiv.empty:
            return df_hareketler
            
        # PANDAS MERGE (SQL LEFT JOIN KARŞILIĞI)
        # lot_no üzerinden birleştir
        merged_df = pd.merge(
            df_hareketler, 
            df_arsiv[['lot_no', 'tedarikci', 'yore', 'fiyat', 'plaka', 'bugday_cinsi', 'gluten_index', 'gecikmeli_sedim', 'sune', 'kirik_ciliz', 'yabanci_tane']], 
            on='lot_no', 
            how='left', 
            suffixes=('', '_arsiv')
        )
        
        # COALESCE Mantığı (Eğer hareketlerde boşsa arşivden al)
        # Pandas'ta combine_first veya fillna kullanılır
        for col in ['tedarikci', 'yore']:
            if f'{col}_arsiv' in merged_df.columns:
                merged_df[col] = merged_df[col].fillna(merged_df[f'{col}_arsiv'])
        
        # Fiyat / Maliyet birleştirme
        if 'fiyat' in merged_df.columns:
            merged_df['alis_fiyati'] = merged_df['fiyat'].fillna(merged_df['maliyet'])
        else:
            merged_df['alis_fiyati'] = merged_df['maliyet']
            
        # Tarihe göre sırala
        if 'tarih' in merged_df.columns:
            merged_df['tarih'] = pd.to_datetime(merged_df['tarih'])
            merged_df = merged_df.sort_values('tarih', ascending=False)
            
        # Haşere kontrolü
        if 'notlar' in merged_df.columns:
            merged_df['hasere'] = merged_df['notlar'].apply(lambda x: "Var" if x and "HAŞERE" in str(x).upper() else "Yok")
            
        return merged_df.head(500) # Son 500 kayıt
        
    except Exception as e:
        st.error(f"Stok hareketleri yüklenemedi: {e}")
        return pd.DataFrame()

def get_bugday_arsiv():
    """Buğday giriş arşivini getir"""
    df = fetch_data("bugday_giris_arsivi")
    if not df.empty and 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
    return df

def save_tavli_analiz(silo_isim, analiz_tonaj, **analiz_degerleri):
    """Tavlı buğday analizini kaydet"""
    try:
        data = {
            'silo_isim': silo_isim,
            'analiz_tonaj': float(analiz_tonaj),
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **analiz_degerleri # Geri kalan tüm parametreleri ekle
        }
        
        if add_data("tavli_analiz", data):
            return True, "Analiz başarıyla kaydedildi!"
        else:
            return False, "Kayıt sırasında hata."
            
    except Exception as e:
        return False, f"Kayıt hatası: {str(e)}"

def get_tavli_analizler(silo_isim=None):
    """Tavlı analiz kayıtlarını getir"""
    df = fetch_data("tavli_analiz")
    
    if df.empty:
        return pd.DataFrame()
        
    if silo_isim:
        df = df[df['silo_isim'] == silo_isim]
        
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
        
    return df.head(100)

# --- QUALITY SPECIFICATION MANAGEMENT ---

def save_bugday_spec(bugday_cinsi, parametre, min_val, max_val, hedef_val):
    """Buğday spesifikasyonunu kaydet/güncelle (Upsert)"""
    try:
        conn = get_conn()
        df = fetch_data("bugday_spekleri")
        
        # Yeni satır verisi
        new_row = {
            'bugday_cinsi': bugday_cinsi,
            'parametre': parametre,
            'min_deger': min_val,
            'max_deger': max_val,
            'hedef_deger': hedef_val,
            'aktif': 1
        }
        
        # Eğer tablo boşsa direkt ekle
        if df.empty:
            return add_data("bugday_spekleri", new_row)
            
        # Var mı kontrol et (Pandas ile)
        mask = (df['bugday_cinsi'] == bugday_cinsi) & (df['parametre'] == parametre)
        
        if mask.any():
            # Güncelle
            df.loc[mask, ['min_deger', 'max_deger', 'hedef_deger', 'aktif']] = [min_val, max_val, hedef_val, 1]
            conn.update(worksheet="bugday_spekleri", data=df)
        else:
            # Ekle
            add_data("bugday_spekleri", new_row)
            
        return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def delete_bugday_spec_group(bugday_cinsi):
    """Bir buğday cinsine ait tüm spekleri sil"""
    try:
        conn = get_conn()
        df = fetch_data("bugday_spekleri")
        if df.empty: return True
        
        # Filtrele (Silinecekler HARİÇ olanları tut)
        df_new = df[df['bugday_cinsi'] != bugday_cinsi]
        
        # Tüm tabloyu güncelle (Overwrite)
        conn.update(worksheet="bugday_spekleri", data=df_new)
        return True
    except Exception:
        return False

def get_all_bugday_specs_dataframe():
    """Tüm buğday speklerini rapor için çek"""
    df = fetch_data("bugday_spekleri")
    if df.empty: return pd.DataFrame()
    
    # İsimlendirme
    df = df.rename(columns={
        'bugday_cinsi': 'Buğday Cinsi',
        'parametre': 'Parametre',
        'min_deger': 'Min',
        'hedef_deger': 'Hedef',
        'max_deger': 'Max'
    })
    return df

def show_bugday_spec_yonetimi():
    """Buğday Kalite Spesifikasyon Yönetimi"""
    st.markdown("### 🌾 Buğday Kalite Spesifikasyonları")
    
    # 1. Cins Seçimi
    df_specs = fetch_data("bugday_spekleri")
    if not df_specs.empty:
        all_types = sorted(df_specs['bugday_cinsi'].unique().tolist())
    else:
        all_types = []

    col_sel, col_add = st.columns([2, 1])
    
    with col_sel:
        secilen_cins = st.selectbox("Düzenlenecek Buğday Cinsini Seçiniz", ["(Seçiniz/Yeni Ekle)"] + all_types)
    
    yeni_isim_girisi = ""
    if secilen_cins == "(Seçiniz/Yeni Ekle)":
        with col_add:
            yeni_isim_girisi = st.text_input("➕ Yeni Cins Tanımla", placeholder="Örn: Genel Standart, Bezostaya").strip()
            if yeni_isim_girisi:
                secilen_cins = yeni_isim_girisi
            else:
                secilen_cins = None

    if not secilen_cins:
        st.info("👆 Lütfen düzenlemek veya oluşturmak için bir buğday cinsi seçin.")
        st.divider()
        st.caption("📋 Mevcut Tanımlar")
        df_all = get_all_bugday_specs_dataframe()
        if not df_all.empty:
            st.dataframe(df_all, use_container_width=True, hide_index=True)
        return

    st.divider()
    
    # Mevcut Spekleri Çek
    current_specs = {}
    if not df_specs.empty:
        df_filtered = df_specs[df_specs['bugday_cinsi'] == secilen_cins]
        for _, row in df_filtered.iterrows():
            current_specs[row['parametre']] = row

    # Parametre Listesi
    parametreler = [
        ("hektolitre", "Hektolitre (kg/hl)"),
        ("rutubet", "Rutubet (%)"),
        ("protein", "Protein (%)"),
        ("gluten", "Gluten (%)"),
        ("gluten_index", "Gluten Index"),
        ("sedim", "Sedim (ml)"),
        ("gecikmeli_sedim", "Gecikmeli Sedim (ml)"),
        ("sune", "Süne (%)"),
        ("kirik_ciliz", "Kırık & Cılız (%)"),
        ("yabanci_tane", "Yabancı Tane (%)")
    ]

    st.markdown(f"### 🛠️ Düzenleme: {secilen_cins}")
    
    with st.form("bugday_spec_form"):
        # Grid Layout
        cols = st.columns(2)
        input_keys = []
        
        for i, (p_key, p_label) in enumerate(parametreler):
            col = cols[i % 2]
            with col:
                st.markdown(f"**{p_label}**")
                c1, c2, c3 = st.columns(3)
                
                cur = current_specs.get(p_key, {})
                val_min = float(cur.get('min_deger', 0.0))
                val_tgt = float(cur.get('hedef_deger', 0.0))
                val_max = float(cur.get('max_deger', 0.0))
                
                with c1:
                    st.number_input("Min", value=val_min, key=f"b_min_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                with c2:
                    st.number_input("Hedef", value=val_tgt, key=f"b_tgt_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                with c3:
                    st.number_input("Max", value=val_max, key=f"b_max_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                
                input_keys.append(p_key)

        st.divider()
        col_submit, col_info = st.columns([1, 2])
        with col_submit:
            submit_btn = st.form_submit_button("💾 Kaydet / Güncelle", type="primary", use_container_width=True)
        with col_info:
            st.caption("ℹ️ Sadece 0'dan büyük değer girilen parametreler kaydedilir.")

        if submit_btn:
            saved_count = 0
            for p_key in input_keys:
                s_min = st.session_state.get(f"b_min_{p_key}", 0.0)
                s_tgt = st.session_state.get(f"b_tgt_{p_key}", 0.0)
                s_max = st.session_state.get(f"b_max_{p_key}", 0.0)
                
                if s_min > 0 or s_tgt > 0 or s_max > 0:
                    if save_bugday_spec(secilen_cins, p_key, s_min, s_max, s_tgt):
                        saved_count += 1
            
            if saved_count > 0:
                st.success(f"✅ {secilen_cins} için {saved_count} parametre güncellendi.")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Değişiklik yapılmadı.")

    # Özet ve Silme
    st.divider()
    col_header, col_delete = st.columns([3, 1])
    with col_header:
        st.subheader(f"📋 '{secilen_cins}' Tanımlı Değerleri")
    
    with col_delete:
        if st.session_state.get("user_role") == "admin":
            if st.button("🗑️ Bu Tanımı Sil", key="del_bugday_spec", type="secondary"):
                if delete_bugday_spec_group(secilen_cins):
                    st.success("Tanım silindi!")
                    time.sleep(1)
                    st.rerun()

    df_spec_view = get_all_bugday_specs_dataframe() 
    if not df_spec_view.empty:
        # Sadece seçili olanı filtrele
        df_selected = df_spec_view[df_spec_view["Buğday Cinsi"] == secilen_cins]
        if not df_selected.empty:
            st.dataframe(df_selected, use_container_width=True, hide_index=True)
        else:
            st.info("Kayıtlı değer yok.")

# --- UI FUNCTIONS (Kısıtlamasız, aynen korundu) ---

@error_handler(context="Buğday Kabul Sistemi")
def show_mal_kabul():
    """Mal Kabul (Giriş) modülü"""
    # ... (Mevcut logic aynen kalıyor, sadece fonksiyon çağrıları yukarıdaki yeni fonksiyonları kullanacak)
    if ERROR_HANDLING_AVAILABLE:
        log_info("Mal Kabul modülü açıldı", "Buğday Girişi")
    
    # Rol kontrolü
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("🚜 Mal Kabul ve Stok Girişi")
    
    lot_no = f"BUGDAY-{datetime.now().strftime('%y%m%d%H%M%S')}"
    
    col1, col2 = st.columns([1, 1.5], gap="large")
    
    with col1:
        st.subheader("📋 Temel Bilgiler")
        st.info(f"**Otomatik Lot No:** `{lot_no}`")
        
        df = get_silo_data()
        if df.empty:
            st.warning("⚠️ Sistemde tanımlı silo bulunamadı!")
            st.info("👉 Lütfen **Yönetim Paneli > Silo Yönetimi** menüsünden silo tanımlayınız.")
            return
        
        secilen_silo_isim = st.selectbox("Depolanacak Silo *", df['isim'].tolist())
        
        # Kapasite Kontrolü
        try:
            silo_row = df[df['isim'] == secilen_silo_isim].iloc[0]
            kalan_kapasite = float(silo_row.get('kapasite', 0)) - float(silo_row.get('mevcut_miktar', 0))
        except:
            kalan_kapasite = 0

        if kalan_kapasite < 0: 
            kalan_kapasite = 0

        st.info(f"ℹ️ Bu siloda kalan boş yer: {kalan_kapasite:.1f} Ton")

        tarih = st.date_input("Kabul Tarihi *", datetime.now())

        # Buğday Cinsi Seçimi
        specs_list = []
        df_specs = fetch_data("bugday_spekleri")
        if not df_specs.empty:
            specs_list = sorted(df_specs['bugday_cinsi'].unique().tolist())
        
        # Standart Seçimi
        secilen_standart = st.selectbox("Standart Seçiniz", ["(Standart Yok)"] + specs_list)
        
        # Buğday Cinsi (Manuel Giriş)
        bugday_cinsi = st.text_input("Buğday Cinsi *", placeholder="Örn: Bezostaya", max_chars=50)
        
        # Spec Verilerini Çek
        current_specs = {}
        if secilen_standart != "(Standart Yok)":
            df_s = df_specs[df_specs['bugday_cinsi'] == secilen_standart]
            for _, row in df_s.iterrows():
                current_specs[row['parametre']] = row

        tedarikci = st.text_input("Tedarikçi/Firma *", max_chars=100)
        yore = st.text_input("Yöre/Bölge *", max_chars=50)
        plaka = st.text_input("Plaka *", max_chars=20)
        notlar = st.text_area("Notlar", height=80, max_chars=200)

        # Kantar
        gelen_miktar = st.number_input("Gelen Miktar (Ton) *", min_value=0.0, step=0.1, format="%.1f")
        gelen_fiyat = st.number_input(f"Alış Fiyatı ({TERMS.get('fiyat', 'TL')}) *", min_value=0.0, step=0.01, format="%.2f")
    
    with col2:
        st.subheader("🧪 Laboratuvar Analiz Değerleri")
        
        def validate_val(key, val, label):
            if key in current_specs:
                spec = current_specs[key]
                s_min = float(spec.get('min_deger', 0))
                s_max = float(spec.get('max_deger', 999))
                s_tgt = float(spec.get('hedef_deger', 0))
                
                if s_tgt > 0:
                    st.caption(f"🎯 Hedef: {s_tgt:.1f} | Aralık: {s_min:.1f} - {s_max:.1f}")
                
                if val < s_min or (s_max > 0 and val > s_max):
                    st.error(f"❌ {label} Sınır Dışı! (Max: {s_max:.1f})")
                elif key == "sune" and val > s_max and s_max > 0:
                     st.error(f"⚠️ Yüksek Süne! Max: {s_max:.1f}")

        col_a1, col_a2, col_a3 = st.columns(3)
        limit = lambda k, p: get_limit(k, p)
        
        with col_a1:
            g_hl = st.number_input(TERMS["hektolitre"], min_value=0.0, max_value=100.0, value=limit("hektolitre", "default"), step=limit("hektolitre", "step"))
            validate_val("hektolitre", g_hl, "Hektolitre")
            
            g_rut = st.number_input(TERMS["rutubet"], min_value=0.0, max_value=20.0, value=limit("rutubet", "default"), step=limit("rutubet", "step"))
            validate_val("rutubet", g_rut, "Rutubet")
            
            g_prot = st.number_input(TERMS["protein"], min_value=0.0, max_value=20.0, value=limit("protein", "default"), step=limit("protein", "step"))
            validate_val("protein", g_prot, "Protein")
            
            g_glut = st.number_input(TERMS["gluten"], min_value=0.0, max_value=50.0, value=limit("gluten", "default"), step=limit("gluten", "step"))
            validate_val("gluten", g_glut, "Gluten")
        
        with col_a2:
            g_index = st.number_input(TERMS["gluten_index"], min_value=0.0, max_value=100.0, value=limit("gluten_index", "default"), step=limit("gluten_index", "step"))
            validate_val("gluten_index", g_index, "G.Index")
            
            g_sedim = st.number_input(TERMS["sedim"], min_value=0.0, max_value=100.0, value=limit("sedim", "default"), step=limit("sedim", "step"))
            validate_val("sedim", g_sedim, "Sedim")
                                    
            g_g_sedim = st.number_input(TERMS["gecikmeli_sedim"], min_value=0.0, max_value=100.0, value=60.0, step=0.1)
            validate_val("gecikmeli_sedim", g_g_sedim, "G.Sedim")
                                     
            sune = st.number_input(TERMS["sune"], min_value=0.0, max_value=10.0, value=limit("sune", "default"), step=limit("sune", "step"))
            validate_val("sune", sune, "Süne")
        
        with col_a3:
            kirik_ciliz = st.number_input("Kırık & Cılız (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.1)
            validate_val("kirik_ciliz", kirik_ciliz, "Kırık/Cılız")
            
            yabanci_tane = st.number_input(TERMS["yabanci_tane"], min_value=0.0, max_value=100.0, value=2.5, step=0.1)
            validate_val("yabanci_tane", yabanci_tane, "Yabancı Tane")
            
            hasere = st.selectbox("Haşere", ["Yok", "Var"], index=0)
    
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        if st.button("💾 Kaydı Tamamla", type="primary", use_container_width=True):
            if gelen_miktar > kalan_kapasite:
                st.error(f"❌ KAPASİTE AŞIMI! Seçtiğiniz siloda sadece {kalan_kapasite:.1f} ton boş yer var.")
                return

            if gelen_miktar <= 0:
                st.error("⚠️ Miktar 0'dan büyük olmalıdır!")
                return
                
            if not (bugday_cinsi and tedarikci and yore and plaka):
                 st.error("⚠️ Lütfen tüm zorunlu alanları (Cins, Tedarikçi, Yöre, Plaka) doldurunuz.")
                 return

            notlar_tam = f"Plaka: {plaka} | {notlar}" if notlar else f"Plaka: {plaka}"
            if hasere == "Var":
                notlar_tam += " | HAŞERE UYARISI: Var"
            
            # 1. Stok hareketi
            if log_stok_hareketi(
                silo_isim=secilen_silo_isim,
                hareket_tipi="Giriş",
                miktar=gelen_miktar,
                protein=g_prot,
                gluten=g_glut,
                rutubet=g_rut,
                hektolitre=g_hl,
                sedim=g_sedim,
                maliyet=gelen_fiyat,
                lot_no=lot_no,
                tedarikci=tedarikci,
                yore=yore,
                notlar=notlar_tam
            ):
                # 2. Arşiv kaydı
                if add_to_bugday_giris_arsivi(
                    lot_no=lot_no,
                    tarih=tarih,
                    bugday_cinsi=bugday_cinsi,
                    tedarikci=tedarikci,
                    yore=yore,
                    plaka=plaka,
                    tonaj=gelen_miktar,
                    fiyat=gelen_fiyat,
                    silo_isim=secilen_silo_isim,
                    hektolitre=g_hl,
                    protein=g_prot,
                    rutubet=g_rut,
                    gluten=g_glut,
                    gluten_index=g_index,
                    sedim=g_sedim,
                    gecikmeli_sedim=g_g_sedim,
                    sune=sune,
                    kirik_ciliz=kirik_ciliz,
                    yabanci_tane=yabanci_tane,
                    notlar=notlar_tam
                ):
                    st.success(f"✅ Buğday kabulü başarıyla kaydedildi! Lot: {lot_no}")
                    recalculate_silos_from_logs()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("❌ Arşive kayıt yapılamadı!")
            else:
                st.error("❌ Stok hareketi kaydedilemedi!")

def show_stok_cikis():
    """Stok Çıkış (Yıkama) modülü"""
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📉 Üretime/Yıkamaya Stok Çıkışı")
    
    df = get_silo_data()
    if df.empty:
        st.error("Silo verisi yüklenemedi!")
        return
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📦 Çıkış Bilgileri")
        secilen_silo_isim = st.selectbox("Kaynak Silo *", df['isim'].tolist())
        silo_bilgisi = df[df['isim'] == secilen_silo_isim].iloc[0]
        mevcut_stok = float(silo_bilgisi['mevcut_miktar'])
        
        st.metric("Mevcut Stok", f"{mevcut_stok:.1f} Ton")
        
        cikacak_miktar = st.number_input("Çıkış Miktarı (Ton) *", min_value=0.0, max_value=float(mevcut_stok) if mevcut_stok > 0 else 0.0, step=0.1)
        
        cikis_nedeni = st.selectbox("Çıkış Nedeni *", ["Üretime Gönderim", "Silo Transferi", "Satış", "Numune", "Diğer"])
        
        hedef_silo = None
        if cikis_nedeni == "Silo Transferi":
            diger_silolar = [s for s in df['isim'].tolist() if s != secilen_silo_isim]
            hedef_silo = st.selectbox("➡️ Hedef Silo (Transfer)", diger_silolar)
            
        notlar = st.text_area("Notlar", height=100, max_chars=500)
    
    with col2:
        st.subheader("📊 Çıkış Önizlemesi")
        if mevcut_stok <= 0:
            st.warning("⚠️ Seçilen siloda stok bulunmamaktadır!")
            st.stop()
            
        if cikacak_miktar > 0:
            yeni_stok = mevcut_stok - cikacak_miktar
            kapasite = float(silo_bilgisi.get('kapasite', 1))
            doluluk_orani = (yeni_stok / kapasite * 100) if kapasite > 0 else 0
            
            with st.container(border=True):
                st.markdown("##### Çıkış Sonrası Durum (Kaynak)")
                col_info1, col_info2 = st.columns(2)
                col_info1.metric("Mevcut", f"{mevcut_stok:.1f} Ton")
                col_info2.metric("Çıkış", f"-{cikacak_miktar:.1f} Ton", delta_color="inverse")
                
                st.divider()
                col_new1, col_new2 = st.columns(2)
                col_new1.metric("Yeni Stok", f"{yeni_stok:.1f} Ton")
                col_new2.metric("Yeni Doluluk", f"%{doluluk_orani:.1f}")
                
                st.markdown(draw_silo(doluluk_orani/100, ""), unsafe_allow_html=True)
                
            if hedef_silo:
                st.success(f"➡️ **{hedef_silo}** silosuna +{cikacak_miktar:.1f} Ton eklenecek.")
        else:
            st.info("👈 Çıkış miktarı giriniz")
            
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        btn_text = "📤 Transferi Başlat" if cikis_nedeni == "Silo Transferi" else "📤 Stok Çıkışını Kaydet"
        if st.button(btn_text, type="primary", use_container_width=True):
            if cikacak_miktar <= 0:
                st.error("❌ Çıkış miktarı 0'dan büyük olmalıdır!")
                return
            
            tam_notlar = f"{cikis_nedeni}"
            if notlar.strip(): tam_notlar += f" | {notlar}"
            
            # 1. KAYNAK SİLODAN ÇIKIŞ
            if log_stok_hareketi(secilen_silo_isim, "Çıkış", cikacak_miktar, notlar=tam_notlar):
                update_tavli_bugday_stok(secilen_silo_isim, cikacak_miktar, "cikar")
                
                # 2. HEDEF SİLOYA GİRİŞ (TRANSFER)
                if cikis_nedeni == "Silo Transferi" and hedef_silo:
                    from app.modules.mixing import get_tavli_analiz_agirlikli_ortalama
                    # (Bu fonksiyonun da GSheets uyumlu olması lazım, değilse hata verir)
                    
                    log_stok_hareketi(
                        silo_isim=hedef_silo,
                        hareket_tipi="Giriş",
                        miktar=cikacak_miktar,
                        protein=float(silo_bilgisi.get('protein', 0)),
                        notlar=f"Transfer Girişi: {secilen_silo_isim} silosundan"
                    )
                    update_tavli_bugday_stok(hedef_silo, cikacak_miktar, "ekle")
                
                recalculate_silos_from_logs()
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ Stok hareketi kaydedilemedi!")

def show_tavli_analiz():
    """Tavlı Buğday Analiz modülü"""
    st.header("🧪 Tavlı Buğday Analiz Kaydı")
    
    df = get_silo_data()
    if df.empty:
        st.error("Silo verisi yüklenemedi!")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        secilen_silo_isim = st.selectbox("Silo Seçin *", df['isim'].tolist())
        silo_info = df[df['isim'] == secilen_silo_isim].iloc[0]
        mevcut_miktar = float(silo_info['mevcut_miktar']) if not pd.isna(silo_info['mevcut_miktar']) else 0.0
        
        tavli_stok = float(silo_info.get('tavli_bugday_stok', 0))
        kalan_kapasite = max(0.0, mevcut_miktar - tavli_stok)
        
        st.info(f"Mevcut: {mevcut_miktar:.1f} Ton | Tavlı Stok: {tavli_stok:.1f} Ton | 🟢 Eklenebilir: {kalan_kapasite:.1f} Ton")
        
        analiz_tonaj = st.number_input("Analiz Tonajı (Ton) *", min_value=0.1, value=min(27.0, kalan_kapasite) if kalan_kapasite > 0 else 0.0, step=0.1)
        
        if analiz_tonaj > kalan_kapasite:
            st.warning(f"⚠️ Dikkat: Girilen tonaj ({analiz_tonaj}), kalan kapasiteden ({kalan_kapasite:.1f}) fazla!")
    
    with col2:
        tarih = st.date_input("Analiz Tarihi *", datetime.now())
        notlar = st.text_area("Notlar", height=60, max_chars=500)
    
    st.divider()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🧪 Kimyasal Analizler", "📈 Farinograph", "📊 Extensograph"])
    analiz_degerleri = {}
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            analiz_degerleri['protein'] = st.number_input("Protein (%)", value=float(silo_info.get('protein', 12.0)), step=0.1)
            analiz_degerleri['rutubet'] = st.number_input("Rutubet (%)", value=15.0, step=0.1)
            analiz_degerleri['gluten'] = st.number_input("Gluten (%)", value=float(silo_info.get('gluten', 28.0)), step=0.1)
            analiz_degerleri['gluten_index'] = st.number_input("Gluten Index", value=95.0, step=1.0)
        with c2:
            analiz_degerleri['sedim'] = st.number_input("Sedim (ml)", value=50.0, step=0.1)
            analiz_degerleri['g_sedim'] = st.number_input("Gecikmeli Sedim", value=60.0, step=0.1)
            analiz_degerleri['fn'] = st.number_input("F.N.", value=250.0, step=1.0)
            analiz_degerleri['ffn'] = st.number_input("F.F.N.", value=400.0, step=1.0)
            
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            analiz_degerleri['su_kaldirma_f'] = st.number_input("Su Kaldırma (%)", value=58.0, step=0.1)
            analiz_degerleri['gelisme_suresi'] = st.number_input("Gelişme Süresi", value=3.0, step=0.1)
        with c2:
            analiz_degerleri['stabilite'] = st.number_input("Stabilite", value=8.0, step=0.1)
            analiz_degerleri['yumusama'] = st.number_input("Yumuşama", value=70.0, step=1.0)
            
    with tab3:
        analiz_degerleri['su_kaldirma_e'] = st.number_input("Su Kaldırma (E) (%)", value=58.0, step=0.1)
        # Diğer extensograph verileri... (Kısaltıldı)

    st.divider()
    if st.button("💾 Tavlı Analizi Kaydet", type="primary"):
        if analiz_tonaj <= 0:
            st.error("❌ Analiz tonajı pozitif olmalı")
            return
        
        success, msg = save_tavli_analiz(secilen_silo_isim, analiz_tonaj, **analiz_degerleri, notlar=notlar)
        if success:
            update_tavli_bugday_stok(secilen_silo_isim, analiz_tonaj, "ekle")
            st.success(f"✅ Analiz kaydedildi! Tavlı stok güncellendi.")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"❌ {msg}")
    
    # Geçmiş Analizler
    st.subheader("📜 Geçmiş Tavlı Analizler")
    df_gecmis = get_tavli_analizler(secilen_silo_isim)
    if not df_gecmis.empty:
        # Görüntüleme ayarları
        st.dataframe(df_gecmis, use_container_width=True, hide_index=True)
    else:
        st.info("Kayıt yok")

def download_styled_excel(df, filename, sheet_name="Rapor"):
    """Wrapper for shared function"""
    try:
        from app.modules.reports import download_styled_excel as shared_download
        shared_download(df, filename, sheet_name)
    except:
        st.warning("Excel indirme modülü yüklenemedi.")

# --- STOK HAREKETLERİ DÜZENLEME ---

def update_stok_hareketi(hareket_id, yeni_veriler):
    """Stok hareketini ve bağlı kayıtları güncelle - GOOGLE SHEETS UYUMLU"""
    try:
        conn = get_conn()
        hareket_id = int(hareket_id)
        
        # 1. Hareketler tablosunu çek
        df_h = fetch_data("hareketler")
        if df_h.empty: return False, "Tablo boş"
        
        # İlgili satırı bul
        mask = df_h['id'] == hareket_id
        if not mask.any(): return False, "Kayıt bulunamadı"
        
        idx = df_h[mask].index[0]
        eski_tip = df_h.at[idx, 'hareket_tipi']
        eski_lot = df_h.at[idx, 'lot_no']
        
        # Güncelle
        for key, val in yeni_veriler.items():
            if key in df_h.columns:
                df_h.at[idx, key] = val
        
        conn.update(worksheet="hareketler", data=df_h)
        
        # 2. Arşiv Senkronizasyonu (Giriş ise)
        if eski_tip == "Giriş" and eski_lot:
            df_a = fetch_data("bugday_giris_arsivi")
            if not df_a.empty:
                mask_a = df_a['lot_no'] == eski_lot
                if mask_a.any():
                    # Mapping
                    mapping = {
                        'miktar': 'tonaj', 'maliyet': 'fiyat',
                        'protein': 'protein', 'rutubet': 'rutubet', 
                        'gluten': 'gluten', 'sedim': 'sedim'
                    }
                    idx_a = df_a[mask_a].index[0]
                    for h_key, a_key in mapping.items():
                        if h_key in yeni_veriler:
                            df_a.at[idx_a, a_key] = yeni_veriler[h_key]
                    conn.update(worksheet="bugday_giris_arsivi", data=df_a)

        # 3. Yeniden Hesapla
        recalculate_silos_from_logs()
        return True, "Güncellendi"
        
    except Exception as e:
        return False, f"Hata: {e}"

def delete_stok_hareketi(hareket_id):
    """Stok hareketini sil - GOOGLE SHEETS UYUMLU"""
    try:
        conn = get_conn()
        hareket_id = int(hareket_id)
        
        # 1. Hareketler
        df_h = fetch_data("hareketler")
        if df_h.empty: return False, "Tablo boş"
        
        mask = df_h['id'] == hareket_id
        if not mask.any(): return False, "Kayıt yok"
        
        row = df_h[mask].iloc[0]
        lot_no = row['lot_no']
        tip = row['hareket_tipi']
        
        # Sil (Filtreleyerek)
        df_h = df_h[~mask]
        conn.update(worksheet="hareketler", data=df_h)
        
        # 2. Arşivden sil (Giriş ise)
        if tip == "Giriş" and lot_no:
            df_a = fetch_data("bugday_giris_arsivi")
            if not df_a.empty:
                df_a = df_a[df_a['lot_no'] != lot_no]
                conn.update(worksheet="bugday_giris_arsivi", data=df_a)
        
        # 3. Hesapla
        recalculate_silos_from_logs()
        return True, "Silindi"
        
    except Exception as e:
        return False, f"Hata: {e}"

def show_stok_hareketleri():
    """Stok Hareketleri ve Düzenleme Ekranı"""
    st.header("📋 Stok Hareket Kayıtları")
    
    df = get_movements()
    if df.empty:
        st.info("Henüz kayıt bulunmamaktadır.")
        return

    is_admin = st.session_state.get('user_role') == 'admin'
    
    # Görüntüleme
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    if is_admin:
        st.divider()
        st.subheader("Düzenleme / Silme")
        hareket_id = st.number_input("İşlem Yapılacak ID", step=1)
        
        if st.button("🗑️ Kaydı Sil"):
            success, msg = delete_stok_hareketi(hareket_id)
            if success:
                st.success(msg)
                time.sleep(1)
                st.rerun()
            else:
                st.error(msg)

def show_bugday_giris_arsivi():
    """Buğday Giriş Arşivi - Raporlama"""
    st.header("🗄️ Buğday Giriş Arşivi")
    
    df = get_bugday_arsiv()
    if df.empty:
        st.info("Kayıt yok.")
        return
        
    st.dataframe(df, use_container_width=True)
    
    st.divider()
    download_styled_excel(df, f"arsiv_{datetime.now().strftime('%Y%m%d')}.xlsx")
