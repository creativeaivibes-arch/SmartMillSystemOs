import streamlit as st
import pandas as pd
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

from app.core.database import fetch_data, add_data, get_conn
from app.core.utils import turkce_karakter_duzelt
from app.core.config import INPUT_LIMITS, TERMS, get_limit

try:
    from app.modules.reports import create_un_maliyet_pdf_report, download_styled_excel
except ImportError:
    def create_un_maliyet_pdf_report(*args): return None
    def download_styled_excel(*args): pass

def get_un_maliyet_gecmisi():
    """Maliyet geçmişini döndür"""
    df = fetch_data("un_maliyet_hesaplamalari")
    if df.empty:
        return pd.DataFrame()
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
        df = df.sort_values('tarih', ascending=False)
    return df

def save_spec(un_cinsi, parametre, min_val, max_val, hedef_val, tolerans):
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        new_row = {
            'un_cinsi': un_cinsi, 'parametre': parametre, 
            'min_deger': float(min_val), 'max_deger': float(max_val), 
            'hedef_deger': float(hedef_val), 'tolerans': float(tolerans), 'aktif': 1
        }
        if df.empty:
            return add_data("un_spekleri", new_row)
        mask = (df['un_cinsi'] == un_cinsi) & (df['parametre'] == parametre)
        if mask.any():
            df.loc[mask, ['min_deger', 'max_deger', 'hedef_deger', 'tolerans', 'aktif']] = \
                [float(min_val), float(max_val), float(hedef_val), float(tolerans), 1]
            conn.update(worksheet="un_spekleri", data=df)
            return True
        else:
            return add_data("un_spekleri", new_row)
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def delete_spec_group(un_cinsi):
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        if df.empty: return True
        df_new = df[df['un_cinsi'] != un_cinsi]
        conn.update(worksheet="un_spekleri", data=df_new)
        return True
    except: return False

def get_all_specs_dataframe():
    df = fetch_data("un_spekleri")
    if df.empty: return pd.DataFrame()
    return df.rename(columns={
        'un_cinsi': 'Un Cinsi', 'parametre': 'Parametre',
        'min_deger': 'Min', 'hedef_deger': 'Hedef', 'max_deger': 'Max'
    })

def show_spec_yonetimi():
    st.markdown("### 🎯 Un Kalite Spesifikasyonları (Spec)")
    df_analiz = fetch_data("un_analizleri")
    df_spek = fetch_data("un_spekleri")
    un_listesi = set()
    if not df_analiz.empty and 'un_cinsi_marka' in df_analiz.columns:
        un_listesi.update(df_analiz['un_cinsi_marka'].dropna().unique())
    if not df_spek.empty and 'un_cinsi' in df_spek.columns:
        un_listesi.update(df_spek['un_cinsi'].dropna().unique())
    all_types = sorted(list(un_listesi))

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
    current_specs = {}
    if not df_spek.empty:
        df_filtered = df_spek[df_spek['un_cinsi'] == secilen_urun]
        for _, row in df_filtered.iterrows():
            current_specs[row['parametre']] = row

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

def save_un_analiz(lot_no, islem_tipi, **analiz_degerleri):
    try:
        df_check = fetch_data("un_analizleri")
        if not df_check.empty and 'lot_no' in df_check.columns:
            if lot_no in df_check['lot_no'].values:
                return False, f"Bu lot numarası zaten kayıtlı: {lot_no}"
        data = {
            'lot_no': str(lot_no),
            'islem_tipi': islem_tipi,
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            **analiz_degerleri
        }
        if add_data("un_analizleri", data):
            return True, "Kayıt Başarılı"
        return False, "Kayıt Başarısız"
    except Exception as e:
        return False, f"Hata: {str(e)}"

def show_un_analiz_kaydi():
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
        current_specs = {}
        if un_cinsi_marka and not df_spek.empty:
            df_s = df_spek[df_spek['un_cinsi'] == un_cinsi_marka]
            for _, row in df_s.iterrows():
                current_specs[row['parametre']] = row
        def validate_input(key, label, val):
            if key in current_specs:
                spec = current_specs[key]
                s_min, s_max, s_tgt = float(spec['min_deger']), float(spec['max_deger']), float(spec['hedef_deger'])
                st.caption(f"🎯 Hedef: **{s_tgt:.2f}** | Aralık: **{s_min:.2f}-{s_max:.2f}**")
                if val < s_min or (s_max > 0 and val > s_max):
                    st.error(f"❌ Limit Dışı!")
            return val
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
            st.write("**45. Dakika:**")
            e1, e2, e3 = st.columns(3)
            e45_d = e1.number_input("Direnç (45)", value=610.0)
            e45_t = e2.number_input("Taban (45)", value=165.0)
            e45_e = e3.number_input("Enerji (45)", value=110.0)
            st.write("**90. Dakika:**")
            e1, e2, e3 = st.columns(3)
            e90_d = e1.number_input("Direnç (90)", value=900.0)
            e90_t = e2.number_input("Taban (90)", value=125.0)
            e90_e = e3.number_input("Enerji (90)", value=120.0)
            st.write("**135. Dakika:**")
            e1, e2, e3 = st.columns(3)
            e135_d = e1.number_input("Direnç (135)", value=980.0)
            e135_t = e2.number_input("Taban (135)", value=120.0)
            e135_e = e3.number_input("Enerji (135)", value=126.0)
            su_e = st.number_input("Su Kaldırma (Extenso) (%)", value=54.3)
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

def show_un_analiz_kayitlari():
    st.header("📚 Un Analiz Kayıtları")
    df = fetch_data("un_analizleri")
    if df.empty:
        st.info("📭 Henüz kayıtlı analiz bulunmamaktadır.")
        return
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
    st.subheader(f"📊 Toplam Kayıt: {len(df)}")
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
        df = df.sort_values('tarih', ascending=False)
        df['DisplayTarih'] = df['tarih'].dt.strftime('%d/%m/%Y')
    cols = ['DisplayTarih', 'lot_no', 'islem_tipi', 'un_cinsi_marka', 'protein', 'gluten', 'sedim', 'kul']
    cols = [c for c in cols if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True, height=400)
    st.divider()
    if st.button("📥 Excel Olarak İndir"):
        filename = f"un_analiz_{datetime.now().strftime('%Y%m%d')}.xlsx"
        download_styled_excel(df, filename, "Un Analizleri")

def save_un_maliyet(data):
    """Maliyet hesaplamasını kaydet"""
    try:
        data['tarih'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data['kullanici'] = st.session_state.get('username', 'Sistem')
        return add_data("un_maliyet_hesaplamalari", data)
    except: 
        return False

def show_un_maliyet_hesaplama():
    """Un Maliyet Hesaplama - SADECE HESAPLAMA"""
    st.header("🧮 Un Maliyet Hesaplama")
    
    # Para birimi
    currency = "TL"
    
    # AY/YIL FİLTRELEME
    col_filter1, col_filter2 = st.columns(2)    
    with col_filter1:
        ay_listesi = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", 
                     "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
        secilen_ay = st.selectbox("Hesaplama Ayı", ay_listesi, index=datetime.now().month - 1)
    
    with col_filter2:
        yil_listesi = list(range(2024, 2037))
        secilen_yil = st.selectbox("Hesaplama Yılı", yil_listesi, index=2)
    
    st.divider()
    st.subheader(f"Un Maliyeti Hesapla - {secilen_ay} {secilen_yil}")
    
    # ÜÇ KOLONLU LAYOUT
    col1, col2, col3 = st.columns(3, gap="medium")
    
    with col1:
        st.markdown("#### 📋 TEMEL BİLGİLER")
        un_cesidi = st.text_input("Un Çeşidi *", value="Ekmeklik", placeholder="Örn: Ekmeklik, Pizza")
        bugday_maliyet = st.number_input("Buğday Paçal (TL/KG) *", min_value=0.0, value=14.60, step=0.01, format="%.2f")
        aylik_kirilan = st.number_input("Aylık Kırılan (Ton) *", min_value=0.0, value=3000.0, step=0.1, format="%.1f")
        randiman = st.number_input("Randıman (%) *", min_value=0.0, max_value=100.0, value=70.0, step=0.1, format="%.1f")
        satis_fiyati = st.number_input("Satış Fiyatı (50 KG) *", min_value=0.0, value=980.00, step=0.01, format="%.2f")
        belge = st.number_input("Belge Geliri (50 KG)", min_value=0.0, value=0.00, step=0.01, format="%.2f")

    with col2:
        st.markdown("#### 📊 YAN ÜRÜN ORANLARI (%)")
        col_oran1, col_oran2 = st.columns(2)
        with col_oran1:
            st.caption("Un Oranı")
            r_un2 = st.number_input("2. Un", min_value=0.0, value=7.0, step=0.1, format="%.1f", label_visibility="collapsed", key="r_un2")
            st.caption("Bongalite")
            r_bon = st.number_input("Bongalite %", min_value=0.0, value=1.5, step=0.1, format="%.1f", label_visibility="collapsed", key="r_bon")
        with col_oran2:
            st.caption("Kepek Oranı")
            r_kep = st.number_input("Kepek", min_value=0.0, value=9.0, step=0.1, format="%.1f", label_visibility="collapsed", key="r_kep")
            st.caption("Razmol Oranı")
            r_raz = st.number_input("Razmol", min_value=0.0, value=11.0, step=0.1, format="%.1f", label_visibility="collapsed", key="r_raz")
        
        st.markdown("#### 💰 YAN ÜRÜN FİYATLARI")
        col_fiyat1, col_fiyat2 = st.columns(2)
        with col_fiyat1:
            st.caption("Un Fiyat")
            p_un2 = st.number_input("2. Un TL", min_value=0.0, value=17.00, step=0.01, format="%.2f", label_visibility="collapsed", key="p_un2")
            st.caption("Bongalite Fiyat")
            p_bon = st.number_input("Bon. TL", min_value=0.0, value=11.60, step=0.01, format="%.2f", label_visibility="collapsed", key="p_bon")
        with col_fiyat2:
            st.caption("Kepek Fiyat")
            p_kep = st.number_input("Kepek TL", min_value=0.0, value=8.90, step=0.01, format="%.2f", label_visibility="collapsed", key="p_kep")
            st.caption("Razmol Fiyat")
            p_raz = st.number_input("Razmol TL", min_value=0.0, value=9.10, step=0.01, format="%.2f", label_visibility="collapsed", key="p_raz")
        
        st.markdown("#### 🌾 EK GELİRLER")
        col_ek1, col_ek2 = st.columns(2)
        with col_ek1:
            st.caption("Satılan Kırık (Kg)")
            kirik_tonaj = st.number_input("Kırık Kg", min_value=0.0, value=0.0, step=10.0, label_visibility="collapsed", key="kirik_tonaj")
            st.caption("Satılan Başak (Kg)")
            basak_tonaj = st.number_input("Başak Kg", min_value=0.0, value=0.0, step=10.0, label_visibility="collapsed", key="basak_tonaj")
        with col_ek2:
            st.caption("Kırık Fiyat (TL)")
            kirik_fiyat = st.number_input("Kırık TL", min_value=0.0, value=0.0, step=0.01, label_visibility="collapsed", key="kirik_fiyat")
            st.caption("Başak Fiyat (TL)")
            basak_fiyat = st.number_input("Başak TL", min_value=0.0, value=0.0, step=0.01, label_visibility="collapsed", key="basak_fiyat")

    with col3:
        st.markdown("#### 🏢 AYLIK SABİT GİDERLER")
        g_personel = st.number_input("Personel Maaşı", min_value=0.0, value=1200000.0, step=1000.0, format="%.2f")
        g_bakim = st.number_input("Bakım Maliyeti", min_value=0.0, value=100000.0, step=1000.0, format="%.2f")
        g_mutfak = st.number_input("Mutfak (Kantin)", min_value=0.0, value=50000.0, step=1000.0, format="%.2f")
        g_finans = st.number_input("Finans (Banka)", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
        g_diger = st.number_input("Diğer Giderler", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
        
        st.markdown("#### ⚡ ELEKTRİK")
        g_elektrik_birim = st.number_input("1 Ton Buğday Elektrik (TL)", min_value=0.0, value=500.00, step=0.01)
        elektrik_aylik = g_elektrik_birim * aylik_kirilan
        st.caption(f"Aylık Elektrik: {elektrik_aylik:,.0f} {currency}")
        
        st.markdown("#### 🛒 ÇUVAL BAŞI GİDERLER")
        col_cg1, col_cg2 = st.columns(2)
        with col_cg1:
            st.caption("Nakliye")
            g_nakliye = st.number_input("Nakliye Gider", min_value=0.0, value=20.00, step=0.5, label_visibility="collapsed", key="g_nakliye")
            st.caption("Pazarlama")
            g_pazarlama = st.number_input("Pazarlama Gider", min_value=0.0, value=20.50, step=0.5, label_visibility="collapsed", key="g_pazarlama")
        with col_cg2:
            st.caption("PP Çuval")
            g_cuval = st.number_input("PP Çuval Gider", min_value=0.0, value=15.00, step=0.5, label_visibility="collapsed", key="g_cuval")
            st.caption("Enzim/Katkı")
            g_katki = st.number_input("Katkı Gider", min_value=0.0, value=9.00, step=0.5, label_visibility="collapsed", key="g_katki")

    st.divider()
    if st.button("🧮 HESAPLA VE KAYDET", type="primary", use_container_width=True):
        un_tonaj = aylik_kirilan * (randiman / 100)
        cuval_sayisi = (un_tonaj * 1000) / 50
        
        # Gelirler
        gelir_un = cuval_sayisi * satis_fiyati
        gelir_un2 = (aylik_kirilan * 1000) * (r_un2 / 100) * p_un2
        gelir_bon = (aylik_kirilan * 1000) * (r_bon / 100) * p_bon
        gelir_kep = (aylik_kirilan * 1000) * (r_kep / 100) * p_kep
        gelir_raz = (aylik_kirilan * 1000) * (r_raz / 100) * p_raz
        gelir_belge = belge * cuval_sayisi
        gelir_kirik = kirik_tonaj * kirik_fiyat
        gelir_basak = basak_tonaj * basak_fiyat
        toplam_gelir = gelir_un + gelir_un2 + gelir_bon + gelir_kep + gelir_raz + gelir_belge + gelir_kirik + gelir_basak
        
        # Giderler
        gider_bugday = bugday_maliyet * aylik_kirilan * 1000
        gider_elektrik = elektrik_aylik
        gider_sabit = g_personel + g_bakim + g_mutfak + g_finans + g_diger
        gider_nakliye = g_nakliye * cuval_sayisi
        gider_pazarlama = g_pazarlama * cuval_sayisi
        gider_cuval = g_cuval * cuval_sayisi
        gider_katki = g_katki * cuval_sayisi
        toplam_gider = gider_bugday + gider_elektrik + gider_sabit + gider_nakliye + gider_pazarlama + gider_cuval + gider_katki
        
        # Kar
        net_kar = toplam_gelir - toplam_gider
        net_kar_cuval = net_kar / cuval_sayisi if cuval_sayisi > 0 else 0
        maliyet_fabrika = satis_fiyati - net_kar_cuval
        
        st.success("✅ Hesaplama Tamamlandı!")
        m1, m2, m3 = st.columns(3)
        m1.metric("Net Kar (50kg)", f"{net_kar_cuval:.2f} TL")
        m2.metric("Fabrika Maliyet", f"{maliyet_fabrika:.2f} TL")
        m3.metric("Toplam Kar", f"{net_kar:,.0f} TL")
        
        data = {
            'ay': secilen_ay, 'yil': secilen_yil, 'un_cesidi': un_cesidi, 
            'bugday_pacal_maliyeti': bugday_maliyet, 'aylik_kirilan_bugday': aylik_kirilan,
            'un_randimani': randiman, 'un_satis_fiyati': satis_fiyati, 'belge_geliri': belge,
            'un2_orani': r_un2, 'un2_fiyati': p_un2, 'bongalite_orani': r_bon, 'bongalite_fiyati': p_bon,
            'kepek_orani': r_kep, 'kepek_fiyati': p_kep, 'razmol_orani': r_raz, 'razmol_fiyati': p_raz,
            'kirik_tonaj': kirik_tonaj, 'kirik_fiyat': kirik_fiyat, 'basak_tonaj': basak_tonaj, 'basak_fiyat': basak_fiyat,
            'ton_bugday_elektrik': g_elektrik_birim, 'elektrik_gideri': gider_elektrik,
            'personel_maasi': g_personel, 'bakim_maliyeti': g_bakim, 'mutfak_gideri': g_mutfak,
            'finans_gideri': g_finans, 'diger_giderler': g_diger,
            'nakliye': g_nakliye, 'satis_pazarlama': g_pazarlama, 'pp_cuval': g_cuval, 'katki_maliyeti': g_katki,
            'net_kar_50kg': net_kar_cuval, 'net_kar_kg': net_kar_cuval / 50,
            'fabrika_cikis_maliyet': maliyet_fabrika, 'net_kar_toplam': net_kar,
            'toplam_gelir': toplam_gelir, 'toplam_gider': toplam_gider
        }
        
        if save_un_maliyet(data):
            st.success(f"💾 Kayıt Başarılı: {secilen_ay} {secilen_yil}")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error("❌ Kayıt Başarısız!")
    
    def show_un_maliyet_gecmisi():
    """Maliyet Geçmişi - Dashboard Tasarımı"""
    st.header("📊 Un Maliyet Geçmişi & Trendler")
    
    df = get_un_maliyet_gecmisi()
    
    if df.empty:
        st.info("📭 Henüz maliyet hesaplaması kaydı bulunmamaktadır.")
        st.info("💡 İlk hesaplamayı yapmak için 'Un Maliyet Hesaplama' menüsüne gidin.")
        return
    
    # Özet Göstergeler
    st.subheader("📈 Özet Göstergeler")
    son_kayit = df.iloc[0]
    ort_kar = df['net_kar_50kg'].mean() if 'net_kar_50kg' in df.columns else 0
    ort_maliyet = df['fabrika_cikis_maliyet'].mean() if 'fabrika_cikis_maliyet' in df.columns else 0
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Son Kayıt: Net Kar (50kg)", f"{son_kayit.get('net_kar_50kg', 0):.2f} TL",
                  delta=f"{son_kayit.get('net_kar_50kg', 0) - ort_kar:.2f} TL" if ort_kar > 0 else None)
    with kpi2:
        st.metric("Son Kayıt: Fabrika Maliyet", f"{son_kayit.get('fabrika_cikis_maliyet', 0):.2f} TL",
                  delta=f"{son_kayit.get('fabrika_cikis_maliyet', 0) - ort_maliyet:.2f} TL" if ort_maliyet > 0 else None,
                  delta_color="inverse")
    with kpi3:
        st.metric("Son Kayıt: Toplam Kar", f"{son_kayit.get('net_kar_toplam', 0):,.0f} TL")
    with kpi4:
        st.metric("Toplam Kayıt Sayısı", f"{len(df)} Hesaplama")
    
    st.divider()
    
    # Grafikler
    st.subheader("📉 Trend Grafikleri")
    if 'tarih' in df.columns:
        df['tarih_str'] = df['tarih'].dt.strftime('%d/%m/%Y')
    
    tab1, tab2, tab3 = st.tabs(["💰 Karlılık Trendi", "📊 Maliyet-Satış Karşılaştırma", "📈 Aylık Performans"])
    
    with tab1:
        if 'net_kar_50kg' in df.columns and 'tarih_str' in df.columns:
            fig1 = px.line(df, x='tarih_str', y='net_kar_50kg', title="Çuval Başına Net Kar Trendi",
                          labels={'tarih_str': 'Tarih', 'net_kar_50kg': 'Net Kar (TL/50kg)'}, markers=True)
            fig1.update_layout(hovermode='x unified')
            st.plotly_chart(fig1, use_container_width=True)
    
    with tab2:
        if 'fabrika_cikis_maliyet' in df.columns and 'un_satis_fiyati' in df.columns:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df['tarih_str'], y=df['fabrika_cikis_maliyet'], mode='lines+markers',
                                     name='Fabrika Maliyet', line=dict(color='red')))
            fig2.add_trace(go.Scatter(x=df['tarih_str'], y=df['un_satis_fiyati'], mode='lines+markers',
                                     name='Satış Fiyatı', line=dict(color='green')))
            fig2.update_layout(title="Maliyet vs Satış Fiyatı", xaxis_title="Tarih", yaxis_title="Fiyat (TL/50kg)", hovermode='x unified')
            st.plotly_chart(fig2, use_container_width=True)
    
    with tab3:
        if 'net_kar_toplam' in df.columns and 'tarih_str' in df.columns:
            fig3 = px.bar(df, x='tarih_str', y='net_kar_toplam', title="Dönemsel Toplam Kar",
                         labels={'tarih_str': 'Tarih', 'net_kar_toplam': 'Toplam Kar (TL)'},
                         color='net_kar_toplam', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig3, use_container_width=True)
    
    st.divider()
    
    # Detaylı Tablo
    st.subheader("📋 Detaylı Kayıtlar")
    display_cols = ['tarih_str', 'un_cesidi', 'net_kar_50kg', 'fabrika_cikis_maliyet',
                    'un_satis_fiyati', 'net_kar_toplam', 'aylik_kirilan_bugday', 'kullanici']
    display_cols = [c for c in display_cols if c in df.columns]
    
    df_display = df[display_cols].copy()
    df_display.columns = ['Tarih', 'Un Çeşidi', 'Net Kar (50kg)', 'Fabrika Maliyet',
                          'Satış Fiyatı', 'Toplam Kar', 'Kırılan Buğday (Ton)', 'Kullanıcı'][:len(display_cols)]
    
    st.dataframe(df_display, use_container_width=True, hide_index=True, height=400)
    
    st.divider()
    if st.button("📥 Tüm Geçmişi Excel Olarak İndir", type="primary"):
        filename = f"un_maliyet_gecmisi_{datetime.now().strftime('%Y%m%d')}.xlsx"
        download_styled_excel(df, filename, "Maliyet Geçmişi")




