import streamlit as st
import pandas as pd
import time
from datetime import datetime
import sqlite3
import json

from app.core.database import get_db_connection
from app.core.utils import turkce_karakter_duzelt
from app.core.config import INPUT_LIMITS, TERMS, get_limit
# Rapor modülü importu (Döngüsel hatayı önlemek için gerekirse try-except eklenebilir)
try:
    from app.modules.reports import create_un_maliyet_pdf_report, download_styled_excel
except ImportError:
    # Eğer rapor modülü henüz yoksa hata vermesin, fonksiyonu boş geçsin
    def create_un_maliyet_pdf_report(*args): return None
    def download_styled_excel(*args): st.warning("Excel modülü yüklenemedi")

# --------------------------------------------------------------------------
# 1. SPESİFİKASYON YÖNETİMİ
# --------------------------------------------------------------------------

def save_spec(un_cinsi, parametre, min_val, max_val, hedef_val, tolerans):
    """Spesifikasyon kaydet/güncelle"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Önce tabloyu kontrol et
            c.execute("SELECT id FROM un_spekleri WHERE un_cinsi=? AND parametre=?", (un_cinsi, parametre))
            exists = c.fetchone()
            
            if exists:
                c.execute("""UPDATE un_spekleri 
                           SET min_deger=?, max_deger=?, hedef_deger=?, tolerans=?, aktif=1 
                           WHERE id=?""", 
                           (min_val, max_val, hedef_val, tolerans, exists[0]))
            else:
                c.execute("""INSERT INTO un_spekleri (un_cinsi, parametre, min_deger, max_deger, hedef_deger, tolerans) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                           (un_cinsi, parametre, min_val, max_val, hedef_val, tolerans))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def delete_spec_group(un_cinsi):
    """Bir un cinsine ait tüm spekleri sil"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM un_spekleri WHERE un_cinsi=?", (un_cinsi,))
            conn.commit()
            return True
    except Exception as e:
        return False

def get_all_specs_dataframe():
    """Tüm spekleri rapor için çek"""
    try:
        with get_db_connection() as conn:
            df = pd.read_sql("""
                SELECT un_cinsi as "Un Cinsi", 
                       parametre as "Parametre", 
                       min_deger as "Min", 
                       hedef_deger as "Hedef", 
                       max_deger as "Max" 
                FROM un_spekleri 
                ORDER BY un_cinsi, parametre
            """, conn)
            return df
    except:
        return pd.DataFrame()

def show_spec_yonetimi():
    """Un Kalite Spesifikasyon Yönetimi"""
    st.markdown("### 🎯 Un Kalite Spesifikasyonları (Spec)")
    
    # Un Cinsi Seçimi
    try:
        with get_db_connection() as conn:
            un_cinsleri = pd.read_sql("SELECT DISTINCT un_cinsi_marka FROM un_analiz WHERE un_cinsi_marka IS NOT NULL", conn)
            spek_cinsleri = pd.read_sql("SELECT DISTINCT un_cinsi FROM un_spekleri", conn)
            all_types = sorted(list(set(un_cinsleri['un_cinsi_marka'].tolist() + spek_cinsleri['un_cinsi'].tolist())))
    except:
        all_types = []

    col_sel, col_add = st.columns([2, 1])
    with col_sel:
        secilen_urun = st.selectbox("Düzenlenecek Un Cinsini Seçiniz", ["(Seçiniz/Yeni Ekle)"] + all_types)
    
    if secilen_urun == "(Seçiniz/Yeni Ekle)":
        with col_add:
            yeni_isim = st.text_input("➕ Yeni Un Tanımla", placeholder="Örn: Tam Buğday Unu").strip()
            if yeni_isim: secilen_urun = yeni_isim
            else: secilen_urun = None

    if not secilen_urun:
        st.info("👆 Lütfen bir un cinsi seçin.")
        st.divider()
        df_all = get_all_specs_dataframe()
        if not df_all.empty: st.dataframe(df_all, use_container_width=True, hide_index=True)
        return

    st.divider()
    
    current_specs = {}
    try:
        with get_db_connection() as conn:
            df_specs = pd.read_sql("SELECT * FROM un_spekleri WHERE un_cinsi=?", conn, params=(secilen_urun,))
            for _, row in df_specs.iterrows(): current_specs[row['parametre']] = row
    except: pass

    # Parametre Grupları
    param_groups = {
        "Kimyasal Analizler": [("protein", "Protein (%)"), ("rutubet", "Rutubet (%)"), ("kul", "Kül (%)"), ("gluten", "Gluten (%)"), ("gluten_index", "Gluten Index"), ("sedim", "Sedim (ml)"), ("gecikmeli_sedim", "Gecikmeli Sedim (ml)"), ("fn", "Düşme Sayısı (FN)"), ("ffn", "F.F.N"), ("nisasta_zedelenmesi", "Nişasta Zedelenmesi")],
        "Farinograph & Amilograph": [("su_kaldirma_f", "Su Kaldırma (Farino) (%)"), ("gelisme_suresi", "Gelişme Süresi (dk)"), ("stabilite", "Stabilite (dk)"), ("yumusama", "Yumuşama Derecesi (FU)"), ("amilograph", "Amilograph (AU)")],
        "Extensograph": [("enerji45", "Enerji (45 dk)"), ("direnc45", "Direnç (45 dk)"), ("taban45", "Uzama/Taban (45 dk)"), ("enerji90", "Enerji (90 dk)"), ("direnc90", "Direnç (90 dk)"), ("taban90", "Uzama/Taban (90 dk)"), ("enerji135", "Enerji (135 dk)"), ("direnc135", "Direnç (135 dk)"), ("taban135", "Uzama/Taban (135 dk)"), ("su_kaldirma_e", "Su Kaldırma (Extenso) (%)")]
    }

    # Form
    st.markdown(f"### 🛠️ Düzenleme: {secilen_urun}")
    with st.form("spec_editor_full"):
        tabs = st.tabs(list(param_groups.keys()))
        input_keys = [] 
        
        for idx, (group, params) in enumerate(param_groups.items()):
            with tabs[idx]:
                for p_key, p_label in params:
                    cur = current_specs.get(p_key, {})
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{p_label}**")
                    st.number_input("Min", value=float(cur.get('min_deger', 0.0)), key=f"min_{p_key}", step=0.1, label_visibility="collapsed")
                    st.number_input("Hedef", value=float(cur.get('hedef_deger', 0.0)), key=f"tgt_{p_key}", step=0.1, label_visibility="collapsed")
                    st.number_input("Max", value=float(cur.get('max_deger', 0.0)), key=f"max_{p_key}", step=0.1, label_visibility="collapsed")
                    input_keys.append(p_key)
        
        st.divider()
        if st.form_submit_button("💾 Kaydet / Güncelle", type="primary"):
            saved_count = 0
            for p_key in input_keys:
                s_min, s_tgt, s_max = st.session_state.get(f"min_{p_key}", 0.0), st.session_state.get(f"tgt_{p_key}", 0.0), st.session_state.get(f"max_{p_key}", 0.0)
                if s_min > 0 or s_tgt > 0 or s_max > 0:
                    if save_spec(secilen_urun, p_key, s_min, s_max, s_tgt, 0): saved_count += 1
            if saved_count > 0: st.success(f"✅ {saved_count} parametre güncellendi."); time.sleep(1); st.rerun()
            else: st.warning("Değişiklik yok.")

    # Silme Butonu
    if st.session_state.get("user_role") == "admin":
        st.divider()
        if st.button("🗑️ Bu Tanımı Sil", type="secondary"):
            if delete_spec_group(secilen_urun): st.success("Silindi!"); time.sleep(1); st.rerun()

# --------------------------------------------------------------------------
# 2. UN ANALİZ KAYDI
# --------------------------------------------------------------------------

def save_un_analiz(lot_no, islem_tipi, **analiz_degerleri):
    """Un analizini kaydet"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Kolon kontrolleri
            c.execute("PRAGMA table_info(un_analiz)")
            mevcut = [col[1] for col in c.fetchall()]
            for col in ['un_cinsi_marka', 'un_markasi']:
                if col not in mevcut: c.execute(f"ALTER TABLE un_analiz ADD COLUMN {col} TEXT")
            conn.commit()
            
            # Veri Hazırlığı
            columns = ['lot_no', 'islem_tipi', 'tarih']
            values = [lot_no, islem_tipi, datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
            
            fields = ['un_cinsi_marka', 'un_markasi', 'uretim_silosu', 'protein', 'rutubet', 'gluten', 'gluten_index', 'sedim', 'gecikmeli_sedim', 'fn', 'ffn', 'amilograph', 'nisasta_zedelenmesi', 'kul', 'su_kaldirma_f', 'gelisme_suresi', 'stabilite', 'yumusama', 'su_kaldirma_e', 'direnc45', 'direnc90', 'direnc135', 'taban45', 'taban90', 'taban135', 'enerji45', 'enerji90', 'enerji135', 'notlar']
            
            for f in fields:
                if f in analiz_degerleri:
                    columns.append(f)
                    values.append(analiz_degerleri[f])
            
            placeholders = ', '.join(['?'] * len(values))
            cols_str = ', '.join(columns)
            c.execute(f"INSERT INTO un_analiz ({cols_str}) VALUES ({placeholders})", values)
            conn.commit()
            return True, "Kaydedildi"
            
    except sqlite3.IntegrityError: return False, f"Bu lot zaten kayıtlı: {lot_no}"
    except Exception as e: return False, str(e)

def show_un_analiz_kaydi():
    """Un Analiz Kayıt Ekranı"""
    if st.session_state.user_role not in ["admin", "operations"]:
        st.warning("⛔ Yetkisiz Erişim"); return
        
    st.header("📝 Un Analiz Kaydı")
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📋 Bilgiler")
        lot_no = st.text_input("Lot No", value=f"UN-{datetime.now().strftime('%y%m%d%H%M%S')}")
        islem_tipi = st.selectbox("İşlem Tipi", ["ÜRETİM", "SEVKİYAT", "NUMUNE", "ŞİKAYET", "İADE"])
        un_markasi = st.text_input("Un Markası (Ticari)")
        
        # Un Cinsi Seçimi
        try:
            with get_db_connection() as conn:
                u = pd.read_sql("SELECT DISTINCT un_cinsi_marka FROM un_analiz WHERE un_cinsi_marka IS NOT NULL", conn)
                s = pd.read_sql("SELECT DISTINCT un_cinsi FROM un_spekleri", conn)
                ts = sorted(list(set(u['un_cinsi_marka'].tolist() + s['un_cinsi'].tolist())))
        except: ts = []
            
        c1, c2 = st.columns([2, 1])
        with c1: sel_type = st.selectbox("Un Cinsi", ["(Seçiniz)"] + ts + ["(Yeni)"])
        if sel_type == "(Yeni)": 
            with c2: un_cinsi_marka = st.text_input("Yeni Cins Adı").strip()
        elif sel_type != "(Seçiniz)": un_cinsi_marka = sel_type
        else: un_cinsi_marka = ""

        # Silo
        uretim_silosu = None
        if islem_tipi == "ÜRETİM":
            try:
                with get_db_connection() as conn:
                    sl = pd.read_sql("SELECT silo_adi FROM uretim_silolari WHERE aktif=1", conn)['silo_adi'].tolist()
                    uretim_silosu = st.selectbox("Üretim Silosu", ["(Seçiniz)"] + sl)
                    if uretim_silosu == "(Seçiniz)": uretim_silosu = None
            except: pass
        
        notlar = st.text_area("Notlar")

    with col2:
        st.subheader("🧪 Değerler")
        # Spec Kontrol
        specs = {}
        if un_cinsi_marka:
            try:
                with get_db_connection() as conn:
                    df_s = pd.read_sql("SELECT * FROM un_spekleri WHERE un_cinsi=?", conn, params=(un_cinsi_marka,))
                    for _, r in df_s.iterrows(): specs[r['parametre']] = r
            except: pass

        def val_in(lbl, key, d=0.0, mx=100.0, stp=0.1):
            val = st.number_input(lbl, 0.0, float(mx), float(d), float(stp))
            if key in specs:
                s = specs[key]
                st.caption(f"🎯 {s['hedef_deger']} | ↔️ {s['min_deger']}-{s['max_deger']}")
                if val < s['min_deger'] or (s['max_deger'] > 0 and val > s['max_deger']): st.error("Limit Dışı!")
            return val

        with st.expander("Temel Analizler", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                prot = val_in("Protein (%)", "protein", 11.5, 20.0)
                rut = val_in("Rutubet (%)", "rutubet", 14.5, 20.0)
                glut = val_in("Gluten (%)", "gluten", 28.0, 50.0)
            with c2:
                idx = val_in("G. Index", "gluten_index", 85.0, 100.0, 1.0)
                sed = val_in("Sedim", "sedim", 40.0, 100.0, 1.0)
                fn = val_in("FN", "fn", 350.0, 1000.0, 1.0)

        with st.expander("Diğer"):
            gs = val_in("G. Sedim", "gecikmeli_sedim", 50.0, 100.0, 1.0)
            ffn = val_in("FFN", "ffn", 380.0, 1000.0, 1.0)
            kul = st.number_input("Kül", 0.0, 2.0, 0.720, 0.001, format="%.3f")
            ami = val_in("Amilo", "amilograph", 650.0, 2000.0, 1.0)
            nis = val_in("Nişasta Z.", "nisasta_zedelenmesi", 15.0, 50.0)

    if st.button("✅ Kaydet", type="primary", use_container_width=True):
        if not lot_no or not islem_tipi or not un_cinsi_marka:
            st.error("Zorunlu alanlar eksik!"); return
        
        data = {
            'uretim_silosu': uretim_silosu, 'un_cinsi_marka': un_cinsi_marka, 'un_markasi': un_markasi,
            'protein': prot, 'rutubet': rut, 'gluten': glut, 'gluten_index': idx,
            'sedim': sed, 'gecikmeli_sedim': gs, 'fn': fn, 'ffn': ffn, 'amilograph': ami,
            'nisasta_zedelenmesi': nis, 'kul': kul, 'notlar': notlar
        }
        ok, msg = save_un_analiz(lot_no, islem_tipi, **data)
        if ok: st.success("Kaydedildi!"); time.sleep(1); st.rerun()
        else: st.error(msg)

def show_un_analiz_kayitlari():
    st.header("📚 Un Analiz Kayıtları")
    try:
        with get_db_connection() as conn:
            df = pd.read_sql("SELECT * FROM un_analiz ORDER BY tarih DESC LIMIT 100", conn)
    except: df = pd.DataFrame()
    
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        download_styled_excel(df, f"analizler_{datetime.now().strftime('%Y%m%d')}.xlsx")
    else: st.info("Kayıt yok.")

# --------------------------------------------------------------------------
# 3. MALİYET HESAPLAMA (Gelişmiş - Yan Ürünlü)
# --------------------------------------------------------------------------

def save_un_maliyet_hesaplama(data, kullanici):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            cols = ['tarih', 'kullanici']
            vals = [datetime.now().strftime('%Y-%m-%d %H:%M:%S'), kullanici]
            
            # İzin verilen alanlar
            allowed = ['un_cesidi', 'bugday_pacal_maliyeti', 'aylik_kirilan_bugday', 'un_randimani', 
                      'un_satis_fiyati', 'un2_orani', 'bongalite_orani', 'kepek_orani', 'razmol_orani', 
                      'belge_geliri', 'un2_fiyati', 'bongalite_fiyati', 'kepek_fiyati', 'razmol_fiyati', 
                      'ton_bugday_elektrik', 'elektrik_gideri', 'personel_maasi', 'bakim_maliyeti', 
                      'mutfak_gideri', 'finans_gideri', 'nakliye', 'satis_pazarlama', 'pp_cuval', 
                      'katki_maliyeti', 'net_kar_50kg', 'fabrika_cikis_maliyet', 'net_kar_toplam', 
                      'toplam_gelir', 'toplam_gider', 'notlar', 'kirik_tonaj', 'kirik_fiyat', 
                      'basak_tonaj', 'basak_fiyat', 'diger_giderler', 'ay', 'yil']
            
            for k, v in data.items():
                if k in allowed:
                    cols.append(k)
                    vals.append(v)
            
            ph = ', '.join(['?'] * len(vals))
            cl = ', '.join(cols)
            c.execute(f"INSERT INTO un_maliyet_hesaplamalari ({cl}) VALUES ({ph})", vals)
            conn.commit()
            return True, "Kayıt Başarılı"
    except Exception as e: return False, str(e)

def get_un_maliyet_gecmisi():
    try:
        with get_db_connection() as conn:
            return pd.read_sql("SELECT * FROM un_maliyet_hesaplamalari ORDER BY tarih DESC LIMIT 50", conn)
    except: return pd.DataFrame()

def show_un_maliyet_hesaplama():
    """Un Maliyet Hesaplama Modülü - TAM KAPSAMLI"""
    st.header("🧮 Un Maliyet Hesaplama")
    
    if 'hesaplama_yapildi' not in st.session_state: st.session_state.hesaplama_yapildi = False
    
    # Filtreler
    c1, c2 = st.columns(2)
    with c1: ay = st.selectbox("Ay", ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"], index=datetime.now().month-1)
    with c2: yil = st.selectbox("Yıl", list(range(2026, 2037)))

    # --- 3 KOLONLU GİRİŞ ALANI ---
    col1, col2, col3 = st.columns(3, gap="medium")
    
    # 1. TEMEL BİLGİLER
    with col1:
        st.markdown("#### 📋 TEMEL BİLGİLER")
        un_cesidi = st.text_input("Un Çeşidi *", value="Ekmeklik")
        bugday_pacal = st.number_input("Buğday Paçal (TL/KG) *", 14.60, step=0.01, format="%.2f")
        aylik_kirilan = st.number_input("Aylık Kırılan (Ton) *", 3000.0, step=10.0)
        randiman = st.number_input("Un Randımanı (%) *", 70.0, step=0.1)
        satis_fiyat = st.number_input("Un Satış Fiyatı (50KG) *", 980.0, step=1.0)
        belge = st.number_input("Belge Geliri (50KG)", 0.0)

    # 2. YAN ÜRÜNLER (Senin aradığın kısım burası)
    with col2:
        st.markdown("#### 📊 YAN ÜRÜN ORANLARI (%)")
        c_y1, c_y2 = st.columns(2)
        un2_or = c_y1.number_input("2. Un Oranı", 7.0, step=0.1)
        bon_or = c_y2.number_input("Bongalite", 1.5, step=0.1)
        kep_or = c_y1.number_input("Kepek", 9.0, step=0.1)
        raz_or = c_y2.number_input("Razmol", 11.0, step=0.1)
        
        st.markdown("#### 💰 YAN ÜRÜN FİYATLARI (TL)")
        un2_fy = c_y1.number_input("2. Un Fiyat", 17.00, step=0.1)
        bon_fy = c_y2.number_input("Bongalite Fiyat", 11.60, step=0.1)
        kep_fy = c_y1.number_input("Kepek Fiyat", 8.90, step=0.1)
        raz_fy = c_y2.number_input("Razmol Fiyat", 9.10, step=0.1)
        
        st.markdown("#### 🌾 EK GELİRLER")
        c_e1, c_e2 = st.columns(2)
        kirik_t = c_e1.number_input("Kırık (Kg)", 0.0)
        basak_t = c_e2.number_input("Başak (Kg)", 0.0)
        kirik_f = c_e1.number_input("Kırık TL", 0.0)
        basak_f = c_e2.number_input("Başak TL", 0.0)

    # 3. GİDERLER
    with col3:
        st.markdown("#### 🏢 AYLIK SABİT GİDERLER")
        personel = st.number_input("Personel", 1200000.0, step=1000.0)
        bakim = st.number_input("Bakım", 100000.0, step=1000.0)
        mutfak = st.number_input("Mutfak", 50000.0, step=1000.0)
        finans = st.number_input("Finans", 0.0, step=1000.0)
        diger = st.number_input("Diğer", 0.0, step=1000.0)
        
        st.markdown("#### ⚡ ELEKTRİK")
        el_ton = st.number_input("1 Ton Elk. (TL)", 500.0)
        st.caption(f"Aylık: {el_ton * aylik_kirilan:,.0f} TL")
        
        st.markdown("#### 🛒 ÇUVAL BAŞI GİDER")
        c_g1, c_g2 = st.columns(2)
        nakliye = c_g1.number_input("Nakliye", 20.0)
        pazar = c_g2.number_input("Pazarlama", 20.5)
        cuval = c_g1.number_input("Çuval", 15.0)
        katki = c_g2.number_input("Katkı/Enzim", 9.0)

    st.divider()
    
    if st.button("🧮 HESAPLA ve KAYDET", type="primary", use_container_width=True):
        if not un_cesidi: st.error("Un çeşidi giriniz"); return
        
        try:
            # HESAPLAMALAR
            un_tonaj = aylik_kirilan * (randiman / 100)
            cuval_say = (un_tonaj * 1000) / 50 if un_tonaj > 0 else 1
            
            # Gelirler
            g_un = cuval_say * satis_fiyat
            g_yan = (aylik_kirilan * 1000) * ((un2_or*un2_fy + bon_or*bon_fy + kep_or*kep_fy + raz_or*raz_fy)/100)
            g_ek = (kirik_t * kirik_f) + (basak_t * basak_f) + (belge * cuval_say)
            toplam_gelir = g_un + g_yan + g_ek
            
            # Giderler
            gid_bugday = bugday_pacal * aylik_kirilan * 1000
            gid_cuval = (nakliye + pazar + cuval + katki) * cuval_say
            gid_sabit = personel + bakim + mutfak + finans + diger + (el_ton * aylik_kirilan)
            toplam_gider = gid_bugday + gid_cuval + gid_sabit
            
            # Karlılık
            kar_toplam = toplam_gelir - toplam_gider
            kar_cuval = kar_toplam / cuval_say if cuval_say > 0 else 0
            fab_cikis = satis_fiyat - kar_cuval
            
            res = {
                'ay': ay, 'yil': yil, 'un_cesidi': un_cesidi,
                'bugday_pacal_maliyeti': bugday_pacal, 'aylik_kirilan_bugday': aylik_kirilan,
                'un_randimani': randiman, 'un_satis_fiyati': satis_fiyat,
                'un2_orani': un2_or, 'bongalite_orani': bon_or, 'kepek_orani': kep_or, 'razmol_orani': raz_or,
                'un2_fiyati': un2_fy, 'bongalite_fiyati': bon_fy, 'kepek_fiyati': kep_fy, 'razmol_fiyati': raz_fy,
                'belge_geliri': belge, 'kirik_tonaj': kirik_t, 'kirik_fiyat': kirik_f, 
                'basak_tonaj': basak_t, 'basak_fiyat': basak_f,
                'personel_maasi': personel, 'bakim_maliyeti': bakim, 'mutfak_gideri': mutfak,
                'finans_gideri': finans, 'diger_giderler': diger, 'ton_bugday_elektrik': el_ton,
                'elektrik_gideri': el_ton * aylik_kirilan,
                'nakliye': nakliye, 'satis_pazarlama': pazar, 'pp_cuval': cuval, 'katki_maliyeti': katki,
                'net_kar_50kg': kar_cuval, 'fabrika_cikis_maliyet': fab_cikis, 'net_kar_toplam': kar_toplam,
                'toplam_gelir': toplam_gelir, 'toplam_gider': toplam_gider
            }
            
            st.session_state.un_maliyet_hesaplama_verileri = res
            st.session_state.hesaplama_yapildi = True
            
            ok, msg = save_un_maliyet_hesaplama(res, st.session_state.get('username', '-'))
            if ok: st.success("✅ Hesaplandı ve Kaydedildi!"); time.sleep(1); st.rerun()
            else: st.warning(f"Hesaplandı ama kaydedilemedi: {msg}")
            
        except Exception as e: st.error(f"Hata: {e}")

    if st.session_state.hesaplama_yapildi and st.session_state.un_maliyet_hesaplama_verileri:
        d = st.session_state.un_maliyet_hesaplama_verileri
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Net Kar (50kg)", f"{d['net_kar_50kg']:,.2f} TL")
        c2.metric("🏭 Fabrika Çıkış", f"{d['fabrika_cikis_maliyet']:,.2f} TL")
        c3.metric("💵 Toplam Kar", f"{d['net_kar_toplam']:,.2f} TL")
        
        if st.button("📄 PDF Rapor"):
            pdf = create_un_maliyet_pdf_report(d)
            if pdf: st.download_button("İndir", pdf, "maliyet.pdf", "application/pdf")

def show_un_maliyet_gecmisi():
    """Geçmiş Kayıtlar"""
    st.header("📉 Maliyet Geçmişi")
    df = get_un_maliyet_gecmisi()
    if not df.empty:
        # Görünümü sadeleştir
        disp_cols = ['tarih', 'ay', 'yil', 'un_cesidi', 'net_kar_50kg', 'fabrika_cikis_maliyet']
        cols = [c for c in disp_cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
    else: st.info("Kayıt yok")
