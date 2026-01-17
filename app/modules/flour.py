import streamlit as st
import pandas as pd
import time
from datetime import datetime

# --- DATABASE BAĞLANTISI (GOOGLE SHEETS UYUMLU) ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.utils import turkce_karakter_duzelt
from app.core.config import INPUT_LIMITS, TERMS, get_limit

# Rapor modülü (Hata verirse boş geçmesi için önlem)
try:
    from app.modules.reports import create_un_maliyet_pdf_report, download_styled_excel
except ImportError:
    def create_un_maliyet_pdf_report(*args): return None
    def download_styled_excel(*args): st.warning("Excel modülü yüklenemedi")

# --------------------------------------------------------------------------
# 1. SPESİFİKASYON YÖNETİMİ
# --------------------------------------------------------------------------

def save_spec(un_cinsi, parametre, min_val, max_val, hedef_val, tolerans):
    """Spesifikasyon kaydet/güncelle (Google Sheets)"""
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        
        # Yeni kayıt verisi
        new_row = {
            'un_cinsi': un_cinsi, 'parametre': parametre, 
            'min_deger': min_val, 'max_deger': max_val, 
            'hedef_deger': hedef_val, 'tolerans': tolerans, 'aktif': 1
        }
        
        if df.empty:
            return add_data("un_spekleri", new_row)
        
        # Güncelleme mantığı
        mask = (df['un_cinsi'] == un_cinsi) & (df['parametre'] == parametre)
        if mask.any():
            df.loc[mask, ['min_deger', 'max_deger', 'hedef_deger', 'tolerans', 'aktif']] = [min_val, max_val, hedef_val, tolerans, 1]
            conn.update(worksheet="un_spekleri", data=df)
        else:
            add_data("un_spekleri", new_row)
            
        return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

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
    st.markdown("### 🎯 Un Kalite Spesifikasyonları")
    
    df_analiz, df_specs = fetch_data("un_analiz"), fetch_data("un_spekleri")
    
    # Listeleri güvenli şekilde al
    l1 = df_analiz['un_cinsi_marka'].unique().tolist() if not df_analiz.empty and 'un_cinsi_marka' in df_analiz.columns else []
    l2 = df_specs['un_cinsi'].unique().tolist() if not df_specs.empty and 'un_cinsi' in df_specs.columns else []
    all_types = sorted(list(set(l1 + l2)))

    col_sel, col_add = st.columns([2, 1])
    with col_sel:
        secilen_urun = st.selectbox("Düzenlenecek Un Cinsini Seçiniz", ["(Seçiniz/Yeni Ekle)"] + all_types)
    
    if secilen_urun == "(Seçiniz/Yeni Ekle)":
        with col_add:
            yeni = st.text_input("➕ Yeni Un Tanımla").strip()
            if yeni: secilen_urun = yeni
            else: secilen_urun = None

    if not secilen_urun:
        st.info("👆 Lütfen seçim yapınız.")
        d = get_all_specs_dataframe()
        if not d.empty: st.dataframe(d, use_container_width=True, hide_index=True)
        return

    st.divider()
    cur = {}
    if not df_specs.empty:
        for _, r in df_specs[df_specs['un_cinsi'] == secilen_urun].iterrows(): cur[r['parametre']] = r

    groups = {
        "Kimyasal": [("protein", "Protein"), ("rutubet", "Rutubet"), ("kul", "Kül"), ("gluten", "Gluten"), ("gluten_index", "GI"), ("sedim", "Sedim"), ("gecikmeli_sedim", "G.Sedim"), ("fn", "FN"), ("ffn", "FFN"), ("nisasta_zedelenmesi", "Nişasta Z.")],
        "Reoloji": [("su_kaldirma_f", "Su Kld(F)"), ("gelisme_suresi", "Gelişme"), ("stabilite", "Stabilite"), ("yumusama", "Yumuşama"), ("amilograph", "Amilo")]
    }

    with st.form("spec_form"):
        tabs = st.tabs(list(groups.keys()))
        keys = []
        for i, (k, params) in enumerate(groups.items()):
            with tabs[i]:
                for pk, pl in params:
                    c = cur.get(pk, {})
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.markdown(f"**{pl}**")
                    st.number_input("Min", value=float(c.get('min_deger', 0)), key=f"mn_{pk}", step=0.1, label_visibility="collapsed")
                    st.number_input("Hdf", value=float(c.get('hedef_deger', 0)), key=f"tg_{pk}", step=0.1, label_visibility="collapsed")
                    st.number_input("Max", value=float(c.get('max_deger', 0)), key=f"mx_{pk}", step=0.1, label_visibility="collapsed")
                    keys.append(pk)
        
        if st.form_submit_button("💾 Kaydet"):
            cnt = 0
            for k in keys:
                mn, tg, mx = st.session_state.get(f"mn_{k}",0), st.session_state.get(f"tg_{k}",0), st.session_state.get(f"mx_{k}",0)
                if mn > 0 or tg > 0 or mx > 0:
                    if save_spec(secilen_urun, k, mn, mx, tg, 0): cnt += 1
            st.success(f"{cnt} güncellendi"); time.sleep(1); st.rerun()

    if st.session_state.get("user_role") == "admin":
        if st.button("🗑️ Sil"):
            if delete_spec_group(secilen_urun): st.success("Silindi!"); time.sleep(1); st.rerun()

# --------------------------------------------------------------------------
# 2. UN ANALİZ KAYDI
# --------------------------------------------------------------------------

def save_un_analiz(lot, tip, **kw):
    try:
        # Lot kontrolü
        df = fetch_data("un_analiz")
        if not df.empty and 'lot_no' in df.columns and str(lot) in df['lot_no'].astype(str).values:
            return False, f"Bu lot ({lot}) zaten kayıtlı!"

        data = {'lot_no': str(lot), 'islem_tipi': tip, 'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), **kw}
        if add_data("un_analiz", data): return True, "Kaydedildi"
        return False, "Hata"
    except Exception as e: return False, str(e)

def show_un_analiz_kaydi():
    if st.session_state.user_role not in ["admin", "operations"]: st.warning("Yetkisiz"); return
    st.header("📝 Un Analiz Kaydı")
    
    c1, c2 = st.columns(2)
    with c1:
        lot = st.text_input("Lot No", value=f"UN-{datetime.now().strftime('%y%m%d%H%M')}")
        tip = st.selectbox("İşlem Tipi", ["ÜRETİM", "SEVKİYAT", "NUMUNE"])
        marka = st.text_input("Un Markası")
        
        # Cins listesi
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

    with c2:
        st.subheader("Değerler")
        def inp(l, k, v=0.0): return st.number_input(l, 0.0, 1000.0, float(v), 0.1)
        
        with st.expander("Analizler", expanded=True):
            pr = inp("Protein", "prot", 11.5)
            ru = inp("Rutubet", "rut", 14.5)
            gl = inp("Gluten", "glut", 28.0)
            gi = inp("GI", "gi", 85.0)
            sd = inp("Sedim", "sed", 40.0)
            fn = inp("FN", "fn", 350.0)
            kl = st.number_input("Kül", 0.0, 2.0, 0.720, 0.001, format="%.3f")
            
    if st.button("Kaydet", type="primary", use_container_width=True):
        if not lot or not cins: st.error("Eksik bilgi"); return
        dt = {'un_cinsi_marka': cins, 'un_markasi': marka, 'uretim_silosu': silo, 'protein': pr, 'rutubet': ru, 'gluten': gl, 'gluten_index': gi, 'sedim': sd, 'fn': fn, 'kul': kl, 'notlar': note}
        ok, msg = save_un_analiz(lot, tip, **dt)
        if ok: st.success("Kaydedildi!"); time.sleep(1); st.rerun()
        else: st.error(msg)

def show_un_analiz_kayitlari():
    st.header("📚 Kayıtlar")
    df = fetch_data("un_analiz")
    if not df.empty:
        if 'tarih' in df.columns: df['tarih'] = pd.to_datetime(df['tarih']).dt.strftime('%d/%m/%Y %H:%M')
        st.dataframe(df.sort_values('tarih', ascending=False), use_container_width=True)
    else: st.info("Kayıt yok")

# --------------------------------------------------------------------------
# 3. MALİYET HESAPLAMA (PDF HATASI DÜZELTİLDİ)
# --------------------------------------------------------------------------

def save_un_maliyet_hesaplama(data, kullanici):
    try:
        # Google Sheets uyumlu kayıt
        row = {
            'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'kullanici': kullanici,
            'id': int(time.time()), # ID üret
            **data # Tüm hesaplama verileri
        }
        
        if add_data("un_maliyet_hesaplamalari", row):
            return True, "Kayıt Başarılı"
        return False, "Kayıt Başarısız"
    except Exception as e:
        return False, str(e)

def get_un_maliyet_gecmisi():
    df = fetch_data("un_maliyet_hesaplamalari")
    if not df.empty and 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
    return df

def show_un_maliyet_hesaplama():
    """Un Maliyet Hesaplama Modülü - PDF FIX"""
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

    # 2. YAN ÜRÜNLER
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
            
            # Kayıt Paketi (DÜZELTME BURADA YAPILDI)
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
                'toplam_gelir': toplam_gelir, 'toplam_gider': toplam_gider,
                'un_tonaj': un_tonaj  # <--- İŞTE EKSİK OLAN PARÇA BU!
            }
            
            st.session_state.un_maliyet_hesaplama_verileri = res
            st.session_state.hesaplama_yapildi = True
            
            # Veritabanına kayıt
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
    st.header("📉 Maliyet Geçmişi")
    df = get_un_maliyet_gecmisi()
    if not df.empty:
        disp_cols = ['tarih', 'ay', 'yil', 'un_cesidi', 'net_kar_50kg', 'fabrika_cikis_maliyet']
        cols = [c for c in disp_cols if c in df.columns]
        st.dataframe(df[cols], use_container_width=True)
    else: st.info("Kayıt yok")
