import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# --- DATABASE VE CORE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.utils import turkce_karakter_duzelt
from app.core.config import INPUT_LIMITS, TERMS, get_limit

# Raporlama modülü (Hata önleyici import)
try:
    from app.modules.reports import create_un_maliyet_pdf_report, download_styled_excel
except ImportError:
    def create_un_maliyet_pdf_report(*args): return None
    def download_styled_excel(*args): pass

# -----------------------------------------------------------------------------
# 0. YENİ: MALİYET GEÇMİŞİ ÇEKME FONKSİYONU (STRATEGY İÇİN GEREKLİ)
# -----------------------------------------------------------------------------

def get_un_maliyet_gecmisi():
    """Maliyet geçmişini tarihe göre sıralı şekilde döndürür"""
    df = fetch_data("un_maliyet_hesaplamalari")
    if df.empty:
        return pd.DataFrame()
    
    # Tarih dönüşümü ve sıralama
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
        df = df.sort_values('tarih', ascending=False)
    
    return df

# -----------------------------------------------------------------------------
# 1. SPESİFİKASYON (SPEC) YÖNETİMİ
# -----------------------------------------------------------------------------

def save_spec(un_cinsi, parametre, min_val, max_val, hedef_val, tolerans):
    """Spesifikasyon kaydet/güncelle (Google Sheets)"""
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        
        # Yeni kayıt verisi
        new_row = {
            'un_cinsi': un_cinsi, 'parametre': parametre, 
            'min_deger': float(min_val), 'max_deger': float(max_val), 
            'hedef_deger': float(hedef_val), 'tolerans': float(tolerans), 'aktif': 1
        }
        
        if df.empty:
            return add_data("un_spekleri", new_row)
        
        # Var mı kontrol et (Un Cinsi + Parametre eşleşmesi)
        mask = (df['un_cinsi'] == un_cinsi) & (df['parametre'] == parametre)
        
        if mask.any():
            # Güncelle
            df.loc[mask, ['min_deger', 'max_deger', 'hedef_deger', 'tolerans', 'aktif']] = \
                [float(min_val), float(max_val), float(hedef_val), float(tolerans), 1]
            conn.update(worksheet="un_spekleri", data=df)
            return True
        else:
            # Ekle
            return add_data("un_spekleri", new_row)
            
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def delete_spec_group(un_cinsi):
    """Bir un cinsine ait tüm spekleri sil"""
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        if df.empty: return True
        
        # Silinecek olanlar dışındakileri tut
        df_new = df[df['un_cinsi'] != un_cinsi]
        conn.update(worksheet="un_spekleri", data=df_new)
        return True
    except: return False

def get_all_specs_dataframe():
    """Tüm spekleri rapor için çek"""
    df = fetch_data("un_spekleri")
    if df.empty: return pd.DataFrame()
    
    # Kolon isimlendirme (Görsel uyum için)
    return df.rename(columns={
        'un_cinsi': 'Un Cinsi', 'parametre': 'Parametre',
        'min_deger': 'Min', 'hedef_deger': 'Hedef', 'max_deger': 'Max'
    })

def show_spec_yonetimi():
    """Un Kalite Spesifikasyon Yönetimi (Tam Kapsamlı)"""
    st.markdown("### 🎯 Un Kalite Spesifikasyonları (Spec)")
    
    # 1. Un Cinsi Listesini Hazırla
    df_analiz = fetch_data("un_analizleri")
    df_spek = fetch_data("un_spekleri")
    
    un_listesi = set()
    if not df_analiz.empty and 'un_cinsi_marka' in df_analiz.columns:
        un_listesi.update(df_analiz['un_cinsi_marka'].dropna().unique())
    if not df_spek.empty and 'un_cinsi' in df_spek.columns:
        un_listesi.update(df_spek['un_cinsi'].dropna().unique())
        
    all_types = sorted(list(un_listesi))

    # Üst Bar: Seçim
    col_sel, col_add = st.columns([2, 1])
    with col_sel:
        secilen_urun = st.selectbox("Düzenlenecek Un Cinsini Seçiniz", ["(Seçiniz/Yeni Ekle)"] + all_types)
    
    if secilen_urun == "(Seçiniz/Yeni Ekle)":
        with col_add:
            yeni_isim = st.text_input("➕ Yeni Un Tanımla", placeholder="Örn: Tam Buğday Unu").strip()
            if yeni_isim: secilen_urun = yeni_isim
            else: secilen_urun = None

    if not secilen_urun:
        st.info("👆 Lütfen düzenlemek veya oluşturmak için bir un cinsi seçin.")
        st.divider()
        st.caption("📋 Sistemde Kayıtlı Tüm Spekler")
        df_all = get_all_specs_dataframe()
        if not df_all.empty: st.dataframe(df_all, use_container_width=True, hide_index=True)
        return

    st.divider()
    
    # Mevcut Spekleri Çek (Dictionary Formatına Çevir)
    current_specs = {}
    if not df_spek.empty:
        df_filtered = df_spek[df_spek['un_cinsi'] == secilen_urun]
        for _, row in df_filtered.iterrows():
            current_specs[row['parametre']] = row

    # --- Orijinal Kodundaki Parametre Grupları ---
    param_groups = {
        "Kimyasal Analizler": [
            ("protein", "Protein (%)"), ("rutubet", "Rutubet (%)"), ("kul", "Kül (%)"),
            ("gluten", "Gluten (%)"), ("gluten_index", "Gluten Index"), ("sedim", "Sedim (ml)"),
            ("gecikmeli_sedim", "Gecikmeli Sedim (ml)"), ("fn", "Düşme Sayısı (FN)"),
            ("ffn", "F.F.N"), ("nisasta_zedelenmesi", "Nişasta Zedelenmesi")
        ],
        "Farinograph & Amilograph": [
            ("su_kaldirma_f", "Su Kaldırma (Farino) (%)"), ("gelisme_suresi", "Gelişme Süresi (dk)"),
            ("stabilite", "Stabilite (dk)"), ("yumusama", "Yumuşama Derecesi (FU)"),
            ("amilograph", "Amilograph (AU)")
        ],
        "Extensograph": [
            ("enerji45", "Enerji (45 dk)"), ("direnc45", "Direnç (45 dk)"), ("taban45", "Uzama/Taban (45 dk)"),
            ("enerji90", "Enerji (90 dk)"), ("direnc90", "Direnç (90 dk)"), ("taban90", "Uzama/Taban (90 dk)"),
            ("enerji135", "Enerji (135 dk)"), ("direnc135", "Direnç (135 dk)"), ("taban135", "Uzama/Taban (135 dk)"),
            ("su_kaldirma_e", "Su Kaldırma (Extenso) (%)")
        ]
    }

    # --- DÜZENLEME FORMU ---
    st.markdown(f"### 🛠️ Düzenleme: {secilen_urun}")
    
    with st.form("spec_editor_comprehensive"):
        tabs = st.tabs(list(param_groups.keys()))
        input_keys = [] 
        
        for idx, (group_name, params) in enumerate(param_groups.items()):
            with tabs[idx]:
                for p_key, p_label in params:
                    cur = current_specs.get(p_key, {})
                    val_min = float(cur.get('min_deger', 0.0))
                    val_tgt = float(cur.get('hedef_deger', 0.0))
                    val_max = float(cur.get('max_deger', 0.0))
                    
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    with c1: st.markdown(f"**{p_label}**")
                    with c2: st.number_input("Min", value=val_min, key=f"min_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    with c3: st.number_input("Hedef", value=val_tgt, key=f"tgt_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    with c4: st.number_input("Max", value=val_max, key=f"max_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    
                    input_keys.append(p_key)
        
        st.divider()
        if st.form_submit_button("💾 Kaydet / Güncelle", type="primary", use_container_width=True):
            saved_count = 0
            for p_key in input_keys:
                s_min = st.session_state.get(f"min_{p_key}", 0.0)
                s_tgt = st.session_state.get(f"tgt_{p_key}", 0.0)
                s_max = st.session_state.get(f"max_{p_key}", 0.0)
                
                if s_min > 0 or s_tgt > 0 or s_max > 0:
                    if save_spec(secilen_urun, p_key, s_min, s_max, s_tgt, 0):
                        saved_count += 1
            
            if saved_count > 0:
                st.success(f"✅ {saved_count} parametre güncellendi.")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("⚠️ Değer girilmedi.")

    # --- ÖZET VE SİLME ---
    st.divider()
    col_h, col_d = st.columns([3, 1])
    col_h.subheader(f"📋 '{secilen_urun}' Tanımlı Spekleri")
    
    if st.session_state.get("user_role") == "admin":
        if col_d.button("🗑️ Bu Tanımı Sil", key="del_spec_main", type="secondary"):
            if delete_spec_group(secilen_urun):
                st.success("Silindi!")
                time.sleep(1)
                st.rerun()
    
    if not df_spek.empty:
        df_view = df_spek[df_spek['un_cinsi'] == secilen_urun][['parametre', 'min_deger', 'hedef_deger', 'max_deger']]
        if not df_view.empty:
            st.dataframe(df_view, use_container_width=True, hide_index=True)
        else:
            st.info("Kayıtlı değer yok.")

# -----------------------------------------------------------------------------
# 2. ANALİZ KAYDI (GÜVENLİ VE TAM SÜRÜM)
# -----------------------------------------------------------------------------

def save_un_analiz(lot_no, islem_tipi, **analiz_degerleri):
    """Un analizini kaydet - Google Sheets"""
    try:
        # Lot kontrolü
        df_check = fetch_data("un_analizleri")
        if not df_check.empty and 'lot_no' in df_check.columns:
            if lot_no in df_check['lot_no'].values:
                return False, f"Bu lot numarası zaten kayıtlı: {lot_no}"

        # Veri Paketi Hazırla
        data = {
            'lot_no': str(lot_no),
            'islem_tipi': islem_tipi,
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **analiz_degerleri # Tüm dinamik parametreleri ekle
        }
        
        if add_data("un_analizleri", data):
            return True, "Kayıt Başarılı"
        return False, "Kayıt Başarısız"
    except Exception as e:
        return False, f"Hata: {str(e)}"

def show_un_analiz_kaydi():
    """Un Analiz Kaydı (Orijinal Kodundaki Tüm Alanlar Korundu)"""
    
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("⛔ Yetkisiz Erişim")
        return
        
    st.header("📝 Un Analiz Kaydı")
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📋 Numune Bilgileri")
        auto_lot = f"UN-{datetime.now().strftime('%y%m%d%H%M%S')}"
        st.info(f"**Otomatik Lot:** `{auto_lot}`")
        
        lot_no = st.text_input("Lot Numarası *", value=auto_lot)
        analiz_tarihi = st.date_input("Analiz Tarihi", datetime.now())
        islem_tipi = st.selectbox("İşlem Tipi *", ["ÜRETİM", "SEVKİYAT", "NUMUNE", "ŞİKAYET", "İADE"])
        un_markasi = st.text_input("Un Markası (Ticari)", placeholder="Örn: Pırlanta")
        
        # Un Cinsi Seçimi
        df_spek = fetch_data("un_spekleri")
        if not df_spek.empty:
            type_list = sorted(df_spek['un_cinsi'].unique().tolist())
        else:
            type_list = []
            
        c_sel, c_new = st.columns([2, 1])
        with c_sel:
            selected_type = st.selectbox("Un Cinsi (Spec) *", ["(Seçiniz)"] + type_list + ["(Yeni)"])
        
        if selected_type == "(Yeni)":
            un_cinsi_marka = c_new.text_input("Yeni Cins").strip()
        elif selected_type != "(Seçiniz)":
            un_cinsi_marka = selected_type
        else:
            un_cinsi_marka = ""

        # Üretim Silosu Yönetimi (Google Sheets Uyumlu)
        uretim_silosu = None
        if islem_tipi == "ÜRETİM":
            df_silo = fetch_data("uretim_silolari")
            if not df_silo.empty:
                silo_list = ["(Belirtilmemiş)"] + df_silo['silo_adi'].tolist()
                uretim_silosu = st.selectbox("Üretim Silosu *", silo_list)
            else:
                st.warning("Tanımlı üretim silosu yok.")
                
        notlar = st.text_area("Notlar")
    
    with col2:
        st.subheader("🧪 Analiz Değerleri")
        
        # Spec Kontrolü için Veri Çekme
        current_specs = {}
        if un_cinsi_marka and not df_spek.empty:
            df_s = df_spek[df_spek['un_cinsi'] == un_cinsi_marka]
            for _, row in df_s.iterrows():
                current_specs[row['parametre']] = row

        # Validasyon Fonksiyonu
        def validate_input(key, label, val):
            if key in current_specs:
                spec = current_specs[key]
                s_min, s_max, s_tgt = float(spec['min_deger']), float(spec['max_deger']), float(spec['hedef_deger'])
                st.caption(f"🎯 Hedef: **{s_tgt:.2f}** | Aralık: **{s_min:.2f}-{s_max:.2f}**")
                if val < s_min or (s_max > 0 and val > s_max):
                    st.error(f"❌ Limit Dışı!")
            return val

        # --- ORİJİNAL EXPANDER YAPISI ---
        
        with st.expander("🧪 KİMYASAL ANALİZLER (Zorunlu)", expanded=True):
            k1, k2 = st.columns(2)
            with k1:
                protein = validate_input("protein", "Protein", st.number_input("Protein (%)", 0.0, 20.0, 11.5, 0.1))
                rutubet = validate_input("rutubet", "Rutubet", st.number_input("Rutubet (%)", 0.0, 20.0, 14.5, 0.1))
                gluten = validate_input("gluten", "Gluten", st.number_input("Gluten (%)", 0.0, 50.0, 28.0, 0.1))
                gluten_index = validate_input("gluten_index", "GI", st.number_input("Gluten Index", 0.0, 100.0, 85.0, 1.0))
            with k2:
                sedim = validate_input("sedim", "Sedim", st.number_input("Sedim (ml)", 0.0, 100.0, 40.0, 1.0))
                g_sedim = validate_input("gecikmeli_sedim", "G.Sedim", st.number_input("Gecikmeli Sedim", 0.0, 100.0, 50.0, 1.0))
                fn = validate_input("fn", "FN", st.number_input("Düşme Sayısı (FN)", 0.0, 999.0, 350.0, 1.0))
                ffn = st.number_input("F.F.N", 0.0, 999.0, 380.0, 1.0)

        with st.expander("🔬 DİĞER KİMYASAL ANALİZLER", expanded=False):
            k3, k4 = st.columns(2)
            with k3:
                amilo = validate_input("amilograph", "Amilo", st.number_input("Amilograph (AU)", 0.0, value=650.0))
                nisasta = st.number_input("Nişasta Zedelenmesi", 0.0, value=15.0)
            with k4:
                kul = validate_input("kul", "Kül", st.number_input("Kül (%)", 0.0, value=0.720, step=0.001, format="%.3f"))

        with st.expander("📈 FARINOGRAPH ANALİZLERİ", expanded=False):
            f1, f2 = st.columns(2)
            with f1:
                f_su = st.number_input("Su Kaldırma (%)", 0.0, value=57.0)
                f_gelisme = st.number_input("Gelişme Süresi (dk)", 0.0, value=1.8)
            with f2:
                f_stab = st.number_input("Stabilite (dk)", 0.0, value=2.3)
                f_yumus = st.number_input("Yumuşama (FU)", 0.0, value=100.0)

        with st.expander("📊 EXTENSOGRAPH ANALİZLERİ (Detaylı)", expanded=False):
            st.info("Bu veriler senin orijinal kodundan korunmuştur.")
            # 45 dk
            st.write("**45. Dakika:**")
            e1, e2, e3 = st.columns(3)
            e45_d = e1.number_input("Direnç (45)", value=610.0)
            e45_t = e2.number_input("Taban (45)", value=165.0)
            e45_e = e3.number_input("Enerji (45)", value=110.0)
            
            # 90 dk
            st.write("**90. Dakika:**")
            e1, e2, e3 = st.columns(3)
            e90_d = e1.number_input("Direnç (90)", value=900.0)
            e90_t = e2.number_input("Taban (90)", value=125.0)
            e90_e = e3.number_input("Enerji (90)", value=120.0)
            
            # 135 dk
            st.write("**135. Dakika:**")
            e1, e2, e3 = st.columns(3)
            e135_d = e1.number_input("Direnç (135)", value=980.0)
            e135_t = e2.number_input("Taban (135)", value=120.0)
            e135_e = e3.number_input("Enerji (135)", value=126.0)
            
            su_e = st.number_input("Su Kaldırma (Extenso) (%)", value=54.3)

    # --- KAYDET ---
    st.divider()
    if st.button("✅ Un Analizini Kaydet", type="primary", use_container_width=True):
        if not lot_no or not un_cinsi_marka:
            st.error("Lot No ve Un Cinsi zorunludur.")
            return
            
        analiz_data = {
            'un_cinsi_marka': un_cinsi_marka, 'un_markasi': un_markasi, 'uretim_silosu': uretim_silosu,
            'protein': protein, 'rutubet': rutubet, 'gluten': gluten, 'gluten_index': gluten_index,
            'sedim': sedim, 'gecikmeli_sedim': g_sedim, 'fn': fn, 'ffn': ffn,
            'amilograph': amilo, 'nisasta_zedelenmesi': nisasta, 'kul': kul,
            'su_kaldirma_f': f_su, 'gelisme_suresi': f_gelisme, 'stabilite': f_stab, 'yumusama': f_yumus,
            'su_kaldirma_e': su_e,
            'direnc45': e45_d, 'taban45': e45_t, 'enerji45': e45_e,
            'direnc90': e90_d, 'taban90': e90_t, 'enerji90': e90_e,
            'direnc135': e135_d, 'taban135': e135_t, 'enerji135': e135_e,
            'notlar': notlar
        }
        
        ok, msg = save_un_analiz(lot_no, islem_tipi, **analiz_data)
        if ok:
            st.success("✅ Kayıt Başarılı!")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"❌ {msg}")

# -----------------------------------------------------------------------------
# 3. ANALİZ ARŞİVİ (GELİŞTİRİLMİŞ VERSİYON)
# -----------------------------------------------------------------------------

def show_un_analiz_kayitlari():
    """Un Analiz Arşivi - Dashboard Tasarımı"""
    st.header("📚 Un Analiz Kayıtları")
    df = fetch_data("un_analizleri")
    
    if df.empty:
        st.info("📭 Henüz kayıtlı analiz bulunmamaktadır.")
        return

    # --- Üretim Silosu Yönetimi (Expander) ---
    if st.session_state.get('user_role') in ["admin", "operations"]:
        with st.expander("⚙️ Üretim Siloları Yönetimi", expanded=False):
            df_silo = fetch_data("uretim_silolari")
            if not df_silo.empty:
                st.dataframe(df_silo[['silo_adi']], use_container_width=True, hide_index=True)
            
            c1, c2 = st.columns([2, 1])
            yeni_silo = c1.text_input("Yeni Silo Adı", key="new_silo_name")
            if c2.button("➕ Ekle", key="add_silo_btn"):
                if yeni_silo:
                    add_data("uretim_silolari", {'silo_adi': yeni_silo, 'aktif': 1})
                    st.success("Eklendi")
                    time.sleep(0.5)
                    st.rerun()

    # --- TABLO GÖSTERİMİ ---
    st.subheader(f"📊 Toplam Kayıt: {len(df)}")
    
    # Tarih Dönüşümü (Güvenli)
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
        df = df.sort_values('tarih', ascending=False)
        df['DisplayTarih'] = df['tarih'].dt.strftime('%d/%m/%Y')
    
    # Sütun seçimi
    cols = ['DisplayTarih', 'lot_no', 'islem_tipi', 'un_cinsi_marka', 'protein', 'gluten', 'sedim', 'kul']
    cols = [c for c in cols if c in df.columns]
    
    st.dataframe(df[cols], use_container_width=True, hide_index=True, height=400)
    
    st.divider()
    if st.button("📥 Excel
