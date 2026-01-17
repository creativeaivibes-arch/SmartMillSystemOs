import streamlit as st
import pandas as pd
import time
from datetime import datetime
import json

# --- DATABASE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.utils import turkce_karakter_duzelt
from app.core.config import INPUT_LIMITS, TERMS, get_limit

# Rapor modülü hatasını önlemek için try-except
try:
    from app.modules.reports import create_un_maliyet_pdf_report, download_styled_excel
except ImportError:
    def create_un_maliyet_pdf_report(*args): return None
    def download_styled_excel(*args): st.warning("Excel modülü yüklenemedi")

# --- SPESİFİKASYON FONKSİYONLARI ---
def save_spec(un_cinsi, parametre, min_val, max_val, hedef_val, tolerans):
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        new_row = {'un_cinsi': un_cinsi, 'parametre': parametre, 'min_deger': min_val, 'max_deger': max_val, 'hedef_deger': hedef_val, 'tolerans': tolerans, 'aktif': 1}
        
        if df.empty: return add_data("un_spekleri", new_row)
        mask = (df['un_cinsi'] == un_cinsi) & (df['parametre'] == parametre)
        if mask.any():
            df.loc[mask, ['min_deger', 'max_deger', 'hedef_deger', 'tolerans', 'aktif']] = [min_val, max_val, hedef_val, tolerans, 1]
            conn.update(worksheet="un_spekleri", data=df)
        else:
            add_data("un_spekleri", new_row)
        return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}"); return False

def delete_spec_group(un_cinsi):
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        if df.empty: return True
        conn.update(worksheet="un_spekleri", data=df[df['un_cinsi'] != un_cinsi])
        return True
    except: return False

def get_all_specs_dataframe():
    df = fetch_data("un_spekleri")
    if df.empty: return pd.DataFrame()
    return df.rename(columns={'un_cinsi': 'Un Cinsi', 'parametre': 'Parametre', 'min_deger': 'Min', 'hedef_deger': 'Hedef', 'max_deger': 'Max'})[['Un Cinsi', 'Parametre', 'Min', 'Hedef', 'Max']]

def show_spec_yonetimi():
    st.markdown("### 🎯 Un Kalite Spesifikasyonları (Spec)")
    df_analiz, df_specs = fetch_data("un_analiz"), fetch_data("un_spekleri")
    all_types = sorted(list(set((df_analiz['un_cinsi_marka'].unique().tolist() if not df_analiz.empty and 'un_cinsi_marka' in df_analiz.columns else []) + (df_specs['un_cinsi'].unique().tolist() if not df_specs.empty else []))))

    c1, c2 = st.columns([2, 1])
    with c1: secilen = st.selectbox("Un Cinsi Seç", ["(Seç/Ekle)"] + all_types)
    if secilen == "(Seç/Ekle)":
        with c2: 
            yeni = st.text_input("Yeni Cins").strip()
            if yeni: secilen = yeni
            else: secilen = None

    if not secilen:
        st.info("👆 Seçim yapınız.")
        dall = get_all_specs_dataframe()
        if not dall.empty: st.dataframe(dall, use_container_width=True, hide_index=True)
        return

    st.divider()
    cur_specs = {}
    if not df_specs.empty:
        for _, r in df_specs[df_specs['un_cinsi'] == secilen].iterrows(): cur_specs[r['parametre']] = r

    groups = {
        "Kimyasal": [("protein", "Protein"), ("rutubet", "Rutubet"), ("kul", "Kül"), ("gluten", "Gluten"), ("gluten_index", "GI"), ("sedim", "Sedim"), ("gecikmeli_sedim", "G.Sedim"), ("fn", "FN"), ("ffn", "FFN"), ("nisasta_zedelenmesi", "Nişasta Z.")],
        "Farino/Amilo": [("su_kaldirma_f", "Su Kld(F)"), ("gelisme_suresi", "Gelişme"), ("stabilite", "Stabilite"), ("yumusama", "Yumuşama"), ("amilograph", "Amilo")],
        "Extenso": [("enerji45", "E45"), ("direnc45", "D45"), ("taban45", "T45"), ("enerji90", "E90"), ("direnc90", "D90"), ("taban90", "T90"), ("enerji135", "E135"), ("direnc135", "D135"), ("taban135", "T135"), ("su_kaldirma_e", "Su Kld(E)")]
    }

    with st.form("spec_form"):
        tabs = st.tabs(list(groups.keys()))
        keys = []
        for i, (k, params) in enumerate(groups.items()):
            with tabs[i]:
                for pk, pl in params:
                    c = cur_specs.get(pk, {})
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{pl}**")
                    vm = c2.number_input("Min", value=float(c.get('min_deger', 0)), key=f"mn_{pk}", step=0.1)
                    vt = c3.number_input("Hdf", value=float(c.get('hedef_deger', 0)), key=f"tg_{pk}", step=0.1)
                    vx = c4.number_input("Max", value=float(c.get('max_deger', 0)), key=f"mx_{pk}", step=0.1)
                    keys.append(pk)
        
        if st.form_submit_button("💾 Kaydet", type="primary"):
            cnt = 0
            for k in keys:
                if st.session_state[f"mn_{k}"] > 0 or st.session_state[f"tg_{k}"] > 0:
                    if save_spec(secilen, k, st.session_state[f"mn_{k}"], st.session_state[f"mx_{k}"], st.session_state[f"tg_{k}"], 0): cnt += 1
            st.success(f"{cnt} güncellendi"); time.sleep(1); st.rerun()

# --- UN ANALİZ ---
def save_un_analiz(lot, tip, **kw):
    try:
        data = {'lot_no': str(lot), 'islem_tipi': tip, 'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), **kw}
        if add_data("un_analiz", data): return True, "OK"
        return False, "Hata"
    except Exception as e: return False, str(e)

def show_un_analiz_kaydi():
    if st.session_state.get('user_role') not in ["admin", "operations"]: return
    st.header("📝 Un Analiz Kaydı")
    
    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        lot = st.text_input("Lot No", value=f"UN-{datetime.now().strftime('%y%m%d%H%M')}")
        tip = st.selectbox("Tip", ["ÜRETİM", "SEVKİYAT", "NUMUNE"])
        marka = st.text_input("Marka")
        
        df_sp = fetch_data("un_spekleri")
        specs = df_sp['un_cinsi'].unique().tolist() if not df_sp.empty else []
        cins = st.selectbox("Cins", ["(Seç)"] + specs + ["(Yeni)"])
        if cins == "(Yeni)": cins = st.text_input("Yeni Cins")
        elif cins == "(Seç)": cins = ""
        
        silo = None
        if tip == "ÜRETİM":
            df_s = fetch_data("uretim_silolari")
            sls = df_s[df_s['aktif']==1]['silo_adi'].tolist() if not df_s.empty else []
            silo = st.selectbox("Silo", [""]+sls)
        
        note = st.text_area("Not")

    with col2:
        st.subheader("Değerler")
        # Helper input
        def inp(l, k, v=0.0, m=100.0): return st.number_input(l, 0.0, m, float(v), 0.1)
        
        with st.expander("Temel", expanded=True):
            pr = inp("Protein", "prot", 11.5)
            ru = inp("Rutubet", "rut", 14.5)
            gl = inp("Gluten", "glut", 28.0)
            gi = inp("G.Index", "gi", 85.0)
            sd = inp("Sedim", "sed", 40.0)
            fn = inp("FN", "fn", 350.0, 1000.0)
        
        with st.expander("Diğer"):
            gs = inp("G.Sedim", "gs", 50.0)
            ff = inp("FFN", "ff", 380.0, 1000.0)
            kl = st.number_input("Kül", 0.0, 2.0, 0.720, 0.001, format="%.3f")
            am = inp("Amilo", "am", 650.0, 2000.0)
            nz = inp("Nişasta Z.", "nz", 15.0)
            sk = inp("Su Kld", "sk", 57.0)
            
    if st.button("Kaydet", type="primary", use_container_width=True):
        if not lot or not cins: st.error("Eksik bilgi"); return
        dt = {'un_cinsi_marka': cins, 'un_markasi': marka, 'uretim_silosu': silo, 'protein': pr, 'rutubet': ru, 'gluten': gl, 'gluten_index': gi, 'sedim': sd, 'gecikmeli_sedim': gs, 'fn': fn, 'ffn': ff, 'kul': kl, 'amilograph': am, 'nisasta_zedelenmesi': nz, 'su_kaldirma_f': sk, 'notlar': note}
        ok, msg = save_un_analiz(lot, tip, **dt)
        if ok: st.success("Kaydedildi!"); time.sleep(1); st.rerun()
        else: st.error(msg)

def show_un_analiz_kayitlari():
    st.header("📚 Kayıtlar")
    df = fetch_data("un_analiz")
    if not df.empty:
        if 'tarih' in df.columns: df['tarih'] = pd.to_datetime(df['tarih']).dt.strftime('%d/%m/%Y %H:%M')
        st.dataframe(df.sort_values('tarih', ascending=False), use_container_width=True)
        download_styled_excel(df, "analizler.xlsx")
    else: st.info("Kayıt yok")

# --- MALIYET HESAPLAMA ---
def show_un_maliyet_hesaplama():
    """Un Maliyet Hesaplama Modülü - TAM EKRAN"""
    st.header("🧮 Un Maliyet Hesaplama")
    
    if 'un_maliyet_hesaplama_verileri' not in st.session_state: st.session_state.un_maliyet_hesaplama_verileri = None
    if 'hesaplama_yapildi' not in st.session_state: st.session_state.hesaplama_yapildi = False
    
    # Filtreler
    c1, c2 = st.columns(2)
    with c1: ay = st.selectbox("Ay", ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"], index=datetime.now().month-1)
    with c2: yil = st.selectbox("Yıl", range(2025, 2036))

    # --- INPUTLAR ---
    col1, col2, col3 = st.columns(3, gap="medium")
    
    with col1:
        st.markdown("#### 📋 Temel Bilgiler")
        un_cesidi = st.text_input("Un Çeşidi *", value="Ekmeklik")
        bugday_pacal = st.number_input("Buğday Paçal (TL/KG) *", value=14.60, step=0.01)
        aylik_kirilan = st.number_input("Aylık Kırılan (Ton) *", value=3000.0, step=10.0)
        randiman = st.number_input("Un Randımanı (%) *", value=70.0, step=0.1)
        satis_fiyat = st.number_input("Un Satış Fiyatı (50KG) *", value=980.0, step=1.0)
        belge = st.number_input("Belge Geliri", value=0.0)

    with col2:
        st.markdown("#### 📊 Yan Ürünler")
        c_y1, c_y2 = st.columns(2)
        un2_or = c_y1.number_input("Un2 %", 7.0)
        bon_or = c_y2.number_input("Bon %", 1.5)
        kep_or = c_y1.number_input("Kep %", 9.0)
        raz_or = c_y2.number_input("Raz %", 11.0)
        
        st.markdown("#### 💰 Yan Ürün Fiyat")
        un2_fy = c_y1.number_input("Un2 TL", 17.0)
        bon_fy = c_y2.number_input("Bon TL", 11.6)
        kep_fy = c_y1.number_input("Kep TL", 8.9)
        raz_fy = c_y2.number_input("Raz TL", 9.1)
        
        st.markdown("#### 🌾 Ek Gelir (Ton)")
        kirik_t = c_y1.number_input("Kırık T", 0.0)
        basak_t = c_y2.number_input("Başak T", 0.0)
        kirik_f = c_y1.number_input("Kırık TL", 0.0)
        basak_f = c_y2.number_input("Başak TL", 0.0)

    with col3:
        st.markdown("#### 🏢 Sabit Giderler")
        personel = st.number_input("Personel", 1200000.0, step=1000.0)
        bakim = st.number_input("Bakım", 100000.0, step=1000.0)
        mutfak = st.number_input("Mutfak", 50000.0, step=1000.0)
        finans = st.number_input("Finans", 0.0, step=1000.0)
        diger = st.number_input("Diğer", 0.0, step=1000.0)
        
        st.markdown("#### ⚡ Elektrik")
        el_ton = st.number_input("1 Ton Elk (TL)", 500.0)
        
        st.markdown("#### 🛒 Çuval Başı")
        c_g1, c_g2 = st.columns(2)
        nakliye = c_g1.number_input("Nakliye", 20.0)
        pazar = c_g2.number_input("Pazar", 20.5)
        cuval = c_g1.number_input("Çuval", 15.0)
        katki = c_g2.number_input("Katkı", 9.0)

    st.divider()
    if st.button("🧮 HESAPLA ve KAYDET", type="primary", use_container_width=True):
        if not un_cesidi: st.error("Un çeşidi girin"); return
        
        try:
            # Hesaplama
            un_tonaj = aylik_kirilan * (randiman / 100)
            cuval_say = (un_tonaj * 1000) / 50
            if cuval_say == 0: cuval_say = 1
            
            gelir_un = cuval_say * satis_fiyat
            gelir_yan = (aylik_kirilan*1000) * ((un2_or*un2_fy + bon_or*bon_fy + kep_or*kep_fy + raz_or*raz_fy)/100)
            gelir_ek = (kirik_t*1000*kirik_f) + (basak_t*1000*basak_f) + (belge*cuval_say)
            toplam_gelir = gelir_un + gelir_yan + gelir_ek
            
            gider_bugday = bugday_pacal * aylik_kirilan * 1000
            gider_cuval = (nakliye + pazar + cuval + katki) * cuval_say
            gider_sabit = personel + bakim + mutfak + finans + diger + (el_ton * aylik_kirilan)
            toplam_gider = gider_bugday + gider_cuval + gider_sabit
            
            kar_toplam = toplam_gelir - toplam_gider
            kar_cuval = kar_toplam / cuval_say
            fabrika_cikis = satis_fiyat - kar_cuval
            
            res = {
                'ay': ay, 'yil': yil, 'un_cesidi': un_cesidi,
                'net_kar_50kg': kar_cuval, 'fabrika_cikis_maliyet': fabrika_cikis, 'net_kar_toplam': kar_toplam,
                'aylik_kirilan_bugday': aylik_kirilan, 'un_randimani': randiman, 'un_satis_fiyati': satis_fiyat,
                'personel_maasi': personel, 'elektrik_gideri': el_ton * aylik_kirilan
            }
            
            st.session_state.un_maliyet_hesaplama_verileri = res
            st.session_state.hesaplama_yapildi = True
            
            # Kayıt
            kayit = {'tarih': datetime.now().strftime('%Y-%m-%d %H:%M'), 'kullanici': st.session_state.get('username', '-'), 'id': int(time.time()), **res}
            if add_data("un_maliyet_hesaplamalari", kayit): st.success("Hesaplandı ve Kaydedildi!"); time.sleep(1); st.rerun()
            else: st.error("Kayıt hatası")
            
        except Exception as e: st.error(f"Hata: {e}")

    if st.session_state.hesaplama_yapildi:
        d = st.session_state.un_maliyet_hesaplama_verileri
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Net Kar (50kg)", f"{d['net_kar_50kg']:,.2f} TL")
        c2.metric("Fabrika Çıkış", f"{d['fabrika_cikis_maliyet']:,.2f} TL")
        c3.metric("Toplam Kar", f"{d['net_kar_toplam']:,.2f} TL")
        if st.button("📄 PDF İndir"):
            pdf = create_un_maliyet_pdf_report(d)
            if pdf: st.download_button("İndir", pdf, "maliyet.pdf", "application/pdf")

def show_un_maliyet_gecmisi():
    st.header("📉 Geçmiş")
    df = fetch_data("un_maliyet_hesaplamalari")
    if not df.empty: st.dataframe(df, use_container_width=True)
    else: st.info("Boş")
