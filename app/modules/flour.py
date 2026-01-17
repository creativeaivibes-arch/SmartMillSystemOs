import streamlit as st
import pandas as pd
import time
from datetime import datetime
import json

# --- GÜNCELLENMİŞ IMPORTLAR ---
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
    """Spesifikasyon kaydet/güncelle (Upsert) - Google Sheets"""
    try:
        conn = get_conn()
        df = fetch_data("un_spekleri")
        
        # Yeni satır verisi
        new_row = {
            'un_cinsi': un_cinsi,
            'parametre': parametre,
            'min_deger': min_val,
            'max_deger': max_val,
            'hedef_deger': hedef_val,
            'tolerans': tolerans,
            'aktif': 1
        }
        
        if df.empty:
            return add_data("un_spekleri", new_row)
            
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
        df_new = df[df['un_cinsi'] != un_cinsi]
        conn.update(worksheet="un_spekleri", data=df_new)
        return True
    except Exception:
        return False

def get_all_specs_dataframe():
    df = fetch_data("un_spekleri")
    if df.empty: return pd.DataFrame()
    df = df.sort_values(['un_cinsi', 'parametre'])
    return df.rename(columns={'un_cinsi': 'Un Cinsi', 'parametre': 'Parametre', 'min_deger': 'Min', 'hedef_deger': 'Hedef', 'max_deger': 'Max'})[['Un Cinsi', 'Parametre', 'Min', 'Hedef', 'Max']]

def show_spec_yonetimi():
    st.markdown("### 🎯 Un Kalite Spesifikasyonları (Spec)")
    
    df_analiz = fetch_data("un_analiz")
    df_specs = fetch_data("un_spekleri")
    
    analiz_cinsleri = df_analiz['un_cinsi_marka'].unique().tolist() if not df_analiz.empty and 'un_cinsi_marka' in df_analiz.columns else []
    spec_cinsleri = df_specs['un_cinsi'].unique().tolist() if not df_specs.empty and 'un_cinsi' in df_specs.columns else []
    all_types = sorted(list(set(analiz_cinsleri + spec_cinsleri)))

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
    if not df_specs.empty:
        df_filtered = df_specs[df_specs['un_cinsi'] == secilen_urun]
        for _, row in df_filtered.iterrows(): current_specs[row['parametre']] = row

    param_groups = {
        "Kimyasal Analizler": [("protein", "Protein (%)"), ("rutubet", "Rutubet (%)"), ("kul", "Kül (%)"), ("gluten", "Gluten (%)"), ("gluten_index", "Gluten Index"), ("sedim", "Sedim (ml)"), ("gecikmeli_sedim", "Gecikmeli Sedim (ml)"), ("fn", "Düşme Sayısı (FN)"), ("ffn", "F.F.N"), ("nisasta_zedelenmesi", "Nişasta Zedelenmesi")],
        "Farinograph": [("su_kaldirma_f", "Su Kaldırma (Farino) (%)"), ("gelisme_suresi", "Gelişme Süresi (dk)"), ("stabilite", "Stabilite (dk)"), ("yumusama", "Yumuşama Derecesi (FU)"), ("amilograph", "Amilograph (AU)")],
        "Extensograph": [("enerji45", "Enerji (45 dk)"), ("direnc45", "Direnç (45 dk)"), ("taban45", "Uzama/Taban (45 dk)"), ("enerji90", "Enerji (90 dk)"), ("direnc90", "Direnç (90 dk)"), ("taban90", "Uzama/Taban (90 dk)"), ("enerji135", "Enerji (135 dk)"), ("direnc135", "Direnç (135 dk)"), ("taban135", "Uzama/Taban (135 dk)"), ("su_kaldirma_e", "Su Kaldırma (Extenso) (%)")]
    }

    with st.form("spec_editor"):
        tabs = st.tabs(list(param_groups.keys()))
        input_keys = []
        for idx, (group, params) in enumerate(param_groups.items()):
            with tabs[idx]:
                for p_key, p_label in params:
                    cur = current_specs.get(p_key, {})
                    val_min, val_tgt, val_max = float(cur.get('min_deger', 0.0)), float(cur.get('hedef_deger', 0.0)), float(cur.get('max_deger', 0.0))
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    with c1: st.markdown(f"**{p_label}**")
                    with c2: st.number_input("Min", value=val_min, key=f"min_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    with c3: st.number_input("Hedef", value=val_tgt, key=f"tgt_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    with c4: st.number_input("Max", value=val_max, key=f"max_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    input_keys.append(p_key)
        
        if st.form_submit_button("💾 Kaydet", type="primary"):
            saved = 0
            for p_key in input_keys:
                s_min, s_tgt, s_max = st.session_state.get(f"min_{p_key}", 0.0), st.session_state.get(f"tgt_{p_key}", 0.0), st.session_state.get(f"max_{p_key}", 0.0)
                if s_min > 0 or s_tgt > 0 or s_max > 0:
                    if save_spec(secilen_urun, p_key, s_min, s_max, s_tgt, 0): saved += 1
            if saved > 0: st.success(f"✅ {saved} parametre güncellendi."); time.sleep(1); st.rerun()
            else: st.warning("Değişiklik yok.")

    st.divider()
    if st.session_state.get("user_role") == "admin":
        if st.button("🗑️ Bu Tanımı Sil"):
            if delete_spec_group(secilen_urun): st.success("Silindi!"); time.sleep(1); st.rerun()

# --- ANALİZ KAYIT FONKSİYONLARI ---
def save_un_analiz(lot_no, islem_tipi, **analiz_degerleri):
    try:
        df = fetch_data("un_analiz")
        if not df.empty and 'lot_no' in df.columns and str(lot_no) in df['lot_no'].astype(str).values:
            return False, f"Bu lot zaten kayıtlı: {lot_no}"
        
        data = {'lot_no': str(lot_no), 'islem_tipi': islem_tipi, 'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), **analiz_degerleri}
        if add_data("un_analiz", data): return True, "Kaydedildi"
        return False, "Hata"
    except Exception as e: return False, str(e)

def get_un_analiz_kayitlari():
    df = fetch_data("un_analiz")
    if not df.empty and 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
    return df.head(100)

def show_un_analiz_kaydi():
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("Erişim engellendi."); return
    
    st.header("📝 Un Analiz Kaydı")
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📋 Bilgiler")
        auto_lot = f"UN-{datetime.now().strftime('%y%m%d%H%M%S')}"
        lot_no = st.text_input("Lot No", value=auto_lot)
        islem_tipi = st.selectbox("İşlem Tipi", ["ÜRETİM", "SEVKİYAT", "NUMUNE", "ŞİKAYET", "İADE"])
        un_markasi = st.text_input("Un Markası (Ticari)")
        
        df_specs = fetch_data("un_spekleri")
        specs = df_specs['un_cinsi'].unique().tolist() if not df_specs.empty else []
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1: sel_type = st.selectbox("Un Cinsi", ["(Listeden Seç)"] + sorted(specs) + ["(Yeni)"])
        if sel_type == "(Yeni)": 
            with col_t2: un_cinsi = st.text_input("Yeni Cins").strip()
        elif sel_type != "(Listeden Seç)": un_cinsi = sel_type
        else: un_cinsi = ""

        uretim_silosu = None
        if islem_tipi == "ÜRETİM":
            df_silo = fetch_data("uretim_silolari")
            silos = df_silo[df_silo['aktif']==1]['silo_adi'].tolist() if not df_silo.empty else []
            uretim_silosu = st.selectbox("Üretim Silosu", ["(Seçiniz)"] + silos)
            if uretim_silosu == "(Seçiniz)": uretim_silosu = None
        
        notlar = st.text_area("Notlar")

    with col2:
        st.subheader("🧪 Değerler")
        specs_dict = {}
        if un_cinsi and not df_specs.empty:
            df_s = df_specs[df_specs['un_cinsi'] == un_cinsi]
            for _, r in df_s.iterrows(): specs_dict[r['parametre']] = r
        
        def val_in(label, key, min_v, max_v, step=0.1, def_v=0.0):
            val = st.number_input(label, min_value=min_v, max_value=max_v, step=step, value=def_v)
            if key in specs_dict:
                s = specs_dict[key]
                s_min, s_max, s_tgt = float(s['min_deger']), float(s['max_deger']), float(s['hedef_deger'])
                st.caption(f"🎯 {s_tgt} | ↔️ {s_min}-{s_max}")
                if val < s_min or (s_max > 0 and val > s_max): st.error("Limit Dışı!")
            return val

        with st.expander("Temel Analizler", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                prot = val_in("Protein (%)", "protein", 0.0, 20.0, 0.1, 11.5)
                rut = val_in("Rutubet (%)", "rutubet", 0.0, 20.0, 0.1, 14.5)
                glut = val_in("Gluten (%)", "gluten", 0.0, 50.0, 0.1, 28.0)
            with c2:
                g_idx = val_in("Gluten Index", "gluten_index", 0.0, 100.0, 1.0, 85.0)
                sedim = val_in("Sedim (ml)", "sedim", 0.0, 100.0, 1.0, 40.0)
                fn = val_in("FN", "fn", 0.0, 1000.0, 1.0, 350.0)

        with st.expander("Diğer Analizler"):
            c1, c2 = st.columns(2)
            with c1:
                g_sedim = val_in("Gecikmeli Sedim", "gecikmeli_sedim", 0.0, 100.0, 1.0, 50.0)
                ffn = val_in("FFN", "ffn", 0.0, 1000.0, 1.0, 380.0)
                kul = val_in("Kül (%)", "kul", 0.0, 2.0, 0.001, 0.720)
            with c2:
                amilo = val_in("Amilograph", "amilograph", 0.0, 2000.0, 1.0, 650.0)
                nisasta = val_in("Nişasta Zed.", "nisasta_zedelenmesi", 0.0, 50.0, 0.1, 15.0)

    if st.button("✅ Kaydet", type="primary", use_container_width=True):
        if not lot_no or not islem_tipi or not un_cinsi:
            st.error("Zorunlu alanları doldurun!")
            return
        
        data = {
            'uretim_silosu': uretim_silosu, 'un_cinsi_marka': un_cinsi, 'un_markasi': un_markasi,
            'protein': prot, 'rutubet': rut, 'gluten': glut, 'gluten_index': g_idx,
            'sedim': sedim, 'gecikmeli_sedim': g_sedim, 'fn': fn, 'ffn': ffn,
            'amilograph': amilo, 'nisasta_zedelenmesi': nisasta, 'kul': kul, 'notlar': notlar
        }
        ok, msg = save_un_analiz(lot_no, islem_tipi, **data)
        if ok: st.success("Kaydedildi!"); time.sleep(1); st.rerun()
        else: st.error(msg)

def show_un_analiz_kayitlari():
    st.header("📚 Un Analiz Kayıtları")
    df = get_un_analiz_kayitlari()
    if df.empty: st.info("Kayıt yok."); return
    
    # Tarih formatı
    if 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih']).dt.strftime('%d/%m/%Y %H:%M')
        
    st.dataframe(df, use_container_width=True)
    st.divider()
    download_styled_excel(df, f"un_analiz_{datetime.now().strftime('%Y%m%d')}.xlsx")

# --- MALİYET HESAPLAMA (EKSİKSİZ VERSİYON) ---
def save_un_maliyet_hesaplama(data, user):
    try:
        row = {'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'kullanici': user, 'id': int(datetime.now().timestamp()), **data}
        if add_data("un_maliyet_hesaplamalari", row): return True, "Kaydedildi"
        return False, "Hata"
    except Exception as e: return False, str(e)

def get_un_maliyet_gecmisi():
    df = fetch_data("un_maliyet_hesaplamalari")
    if not df.empty and 'tarih' in df.columns:
        df['tarih'] = pd.to_datetime(df['tarih'])
        df = df.sort_values('tarih', ascending=False)
    return df

def show_un_maliyet_hesaplama():
    """Un Maliyet Hesaplama Modülü"""
    st.header("🧮 Un Maliyet Hesaplama")
    
    if 'un_maliyet_hesaplama_verileri' not in st.session_state: st.session_state.un_maliyet_hesaplama_verileri = None
    if 'hesaplama_yapildi' not in st.session_state: st.session_state.hesaplama_yapildi = False
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        aylar = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
        secilen_ay = st.selectbox("Ay", aylar, index=datetime.now().month-1)
    with col_filter2:
        secilen_yil = st.selectbox("Yıl", list(range(2026, 2037)))

    # --- INPUT ALANLARI (ARTIK TAMAMEN BURADA) ---
    col1, col2, col3 = st.columns(3, gap="medium")
    
    with col1:
        st.markdown("#### 📋 Temel Bilgiler")
        un_cesidi = st.text_input("Un Çeşidi *", value="Ekmeklik")
        bugday_pacal_maliyeti = st.number_input("Buğday Paçal Maliyeti (TL/KG) *", value=14.60, step=0.01, format="%.2f")
        aylik_kirilan_bugday = st.number_input("Aylık Kırılan Buğday (Ton) *", value=3000.0, step=10.0)
        un_randimani = st.number_input("Un Randımanı (%) *", value=70.0, step=0.1)
        un_satis_fiyati = st.number_input("Un Satış Fiyatı (50 KG) *", value=980.00, step=1.0)
        belge_geliri = st.number_input("Belge Geliri (50 KG)", value=0.00, step=0.1)

    with col2:
        st.markdown("#### 📊 Yan Ürünler")
        c1, c2 = st.columns(2)
        with c1:
            un2_orani = st.number_input("2. Un Oranı (%)", value=7.0, step=0.1)
            bongalite_orani = st.number_input("Bongalite (%)", value=1.5, step=0.1)
        with c2:
            kepek_orani = st.number_input("Kepek (%)", value=9.0, step=0.1)
            razmol_orani = st.number_input("Razmol (%)", value=11.0, step=0.1)
        
        st.markdown("#### 💰 Yan Ürün Fiyatları")
        c3, c4 = st.columns(2)
        with c3:
            un2_fiyati = st.number_input("2. Un Fiyat", value=17.00, step=0.1)
            bongalite_fiyati = st.number_input("Bongalite Fiyat", value=11.60, step=0.1)
        with c4:
            kepek_fiyati = st.number_input("Kepek Fiyat", value=8.90, step=0.1)
            razmol_fiyati = st.number_input("Razmol Fiyat", value=9.10, step=0.1)
            
        st.markdown("#### 🌾 Ek Gelirler (Ton)")
        c5, c6 = st.columns(2)
        with c5:
            kirik_tonaj = st.number_input("Kırık (Ton)", value=0.0)
            basak_tonaj = st.number_input("Başak (Ton)", value=0.0)
        with c6:
            kirik_fiyat = st.number_input("Kırık (TL)", value=0.0)
            basak_fiyat = st.number_input("Başak (TL)", value=0.0)

    with col3:
        st.markdown("#### 🏢 Giderler (Aylık)")
        personel_maasi = st.number_input("Personel", value=1200000.0, step=1000.0)
        bakim_maliyeti = st.number_input("Bakım", value=100000.0, step=1000.0)
        mutfak_gideri = st.number_input("Mutfak", value=50000.0, step=1000.0)
        finans_gideri = st.number_input("Finans", value=0.0, step=1000.0)
        diger_giderler = st.number_input("Diğer", value=0.0, step=1000.0)
        
        st.markdown("#### ⚡ Elektrik")
        ton_bugday_elektrik = st.number_input("1 Ton Buğday Elektrik (TL)", value=500.0)
        elektrik_gideri_aylik = ton_bugday_elektrik * aylik_kirilan_bugday
        st.caption(f"Aylık Elektrik: {elektrik_gideri_aylik:,.0f} TL")
        
        st.markdown("#### 🛒 Çuval Başı Gider")
        c7, c8 = st.columns(2)
        with c7:
            nakliye = st.number_input("Nakliye", value=20.0)
            satis_pazarlama = st.number_input("Pazarlama", value=20.5)
        with c8:
            pp_cuval = st.number_input("Çuval", value=15.0)
            katki_maliyeti = st.number_input("Katkı", value=9.0)

    st.divider()
    if st.button("🧮 HESAPLA", type="primary", use_container_width=True):
        if not un_cesidi: st.error("Un çeşidi giriniz!"); return
        
        try:
            # Hesaplama Mantığı
            un_tonaj = aylik_kirilan_bugday * (un_randimani / 100)
            cuval_sayisi = (un_tonaj * 1000) / 50
            
            # Gelirler
            un_geliri = cuval_sayisi * un_satis_fiyati
            yan_urun_geliri = (aylik_kirilan_bugday * 1000) * (
                (un2_orani/100 * un2_fiyati) + (bongalite_orani/100 * bongalite_fiyati) +
                (kepek_orani/100 * kepek_fiyati) + (razmol_orani/100 * razmol_fiyati)
            )
            belge_geliri_toplam = belge_geliri * cuval_sayisi
            ek_gelir = (kirik_tonaj * 1000 * kirik_fiyat) + (basak_tonaj * 1000 * basak_fiyat)
            
            toplam_gelir = un_geliri + yan_urun_geliri + belge_geliri_toplam + ek_gelir
            
            # Giderler
            bugday_maliyeti = bugday_pacal_maliyeti * aylik_kirilan_bugday * 1000
            cuval_basi_gider_toplam = (nakliye + satis_pazarlama + pp_cuval + katki_maliyeti) * cuval_sayisi
            sabit_giderler = personel_maasi + bakim_maliyeti + mutfak_gideri + finans_gideri + diger_giderler + elektrik_gideri_aylik
            
            toplam_gider = bugday_maliyeti + cuval_basi_gider_toplam + sabit_giderler
            
            net_kar_toplam = toplam_gelir - toplam_gider
            net_kar_50kg = net_kar_toplam / cuval_sayisi if cuval_sayisi > 0 else 0
            fabrika_cikis = un_satis_fiyati - net_kar_50kg
            
            veriler = {
                'ay': secilen_ay, 'yil': secilen_yil, 'un_cesidi': un_cesidi,
                'net_kar_50kg': net_kar_50kg, 'fabrika_cikis_maliyet': fabrika_cikis, 'net_kar_toplam': net_kar_toplam,
                'aylik_kirilan_bugday': aylik_kirilan_bugday, 'un_randimani': un_randimani,
                'un_satis_fiyati': un_satis_fiyati, 'elektrik_gideri': elektrik_gideri_aylik,
                'personel_maasi': personel_maasi, 'bakim_maliyeti': bakim_maliyeti,
                'nakliye': nakliye, 'pp_cuval': pp_cuval, 'katki_maliyeti': katki_maliyeti,
                'bugday_pacal_maliyeti': bugday_pacal_maliyeti
            }
            
            st.session_state.un_maliyet_hesaplama_verileri = veriler
            st.session_state.hesaplama_yapildi = True
            
            kullanici = st.session_state.get('username', 'Bilinmeyen')
            ok, msg = save_un_maliyet_hesaplama(veriler, kullanici)
            
            if ok: st.success("✅ Hesaplandı ve Kaydedildi!"); time.sleep(1); st.rerun()
            else: st.warning(f"Hesaplandı ama kayıt edilemedi: {msg}")
            
        except Exception as e:
            st.error(f"Hesaplama hatası: {e}")

    # Sonuç Gösterimi
    if st.session_state.hesaplama_yapildi and st.session_state.un_maliyet_hesaplama_verileri:
        res = st.session_state.un_maliyet_hesaplama_verileri
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Net Kar (50kg)", f"{res['net_kar_50kg']:,.2f} TL")
        c2.metric("🏭 Fabrika Çıkış", f"{res['fabrika_cikis_maliyet']:,.2f} TL")
        c3.metric("💵 Toplam Kar", f"{res['net_kar_toplam']:,.2f} TL")
        
        if st.button("📄 PDF İndir"):
            pdf = create_un_maliyet_pdf_report(res)
            if pdf:
                st.download_button("📥 İndir", data=pdf, file_name="maliyet.pdf", mime="application/pdf")
            else:
                st.error("PDF oluşturulamadı.")

def show_un_maliyet_gecmisi():
    st.header("📉 Maliyet Geçmişi")
    df = get_un_maliyet_gecmisi()
    if df.empty: st.info("Kayıt yok."); return
    
    st.dataframe(df, use_container_width=True)
