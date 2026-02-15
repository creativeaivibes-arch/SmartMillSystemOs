import streamlit as st
import pandas as pd
import json
from datetime import datetime
import re


# Veritabanı Erişim
from app.core.database import fetch_data
# Raporlama modülünü güvenli içeri al (PDF için)
try:
    from app.modules.reports import create_traceability_pdf_report
except ImportError:
    def create_traceability_pdf_report(*args): return None
        

# ==============================================================================
# 1. ZİNCİR KURMA MOTORU (BACKEND)
# ==============================================================================
@st.cache_data(ttl=300) 
def load_traceability_databases():
    """Veritabanlarını 5 dakikalığına hafızaya alır, sistemi hızlandırır."""
    df_analiz = pd.DataFrame()
    df_uretim = pd.DataFrame()
    df_mix = pd.DataFrame()
    df_ship = pd.DataFrame() # Sevkiyat tablosu eklendi
    df_enz = pd.DataFrame()  # Enzim tablosu eklendi
    
    try: df_analiz = fetch_data("un_analiz")
    except: pass
    try: df_uretim = fetch_data("uretim_kaydi")
    except: pass
    try: df_mix = fetch_data("mixing_batches")
    except: pass
    try: df_ship = fetch_data("sevkiyat_listesi")
    except: pass
    try: df_enz = fetch_data("enzim_receteleri")
    except: pass
    
    return df_analiz, df_uretim, df_mix, df_ship, df_enz
    
def get_trace_chain(search_query):
    """
    Girilen Lot/ID'den başlayıp SAHA GERÇEKLİĞİNE göre tüm zinciri kurar.
    Sistem Köprüsü: SHIP -> LAB -> MIX <- PRD (Mill)
    """
    chain = {
        "found": False, "SHIP": None, "LAB": None, "PRD": None, "MIX": None, "ENZ": None
    }
    
    # Güvenli arama için regex karakterlerini escape et
    search_query = str(search_query).strip()
    
    # Cache'li database'leri kullan (5 dakika hafızada kalır)
    df_analiz, df_uretim, df_mix, df_ship, df_enz = load_traceability_databases()
    
    
    # --- ADIM 1: GİRDİYİ BUL (Herhangi bir halkadan başlanabilir) ---
    
    # A) Analiz Tablosunda Ara (Sevkiyat veya Lab)
    if not df_analiz.empty:
        # Sadece ilgili sütunlarda ara (3x daha hızlı)
        match = df_analiz[df_analiz.astype(str).apply(
            lambda x: x.str.contains(search_query, case=False, regex=False)
        ).any(axis=1)]
        if not match.empty:
            record = match.iloc[0]
            chain["found"] = True
            islem_tipi = str(record.get('islem_tipi', '')).upper()
            
            if "SEVK" in islem_tipi:
                chain["SHIP"] = record
                # KÖPRÜ 1: Sevkiyat (SHIP) -> Üretim Analizi (LAB)
                lab_ref = str(record.get('kaynak_parti_no') or record.get('uretim_lot_no') or '')
                if lab_ref and lab_ref.lower() != 'nan':
                    l_match = df_analiz[df_analiz['lot_no'] == lab_ref]
                    if not l_match.empty: chain["LAB"] = l_match.iloc[0]
            else:
                chain["LAB"] = record

    # B) Üretim (Değirmen) Tablosunda Ara (Direkt girildiyse)
    if not chain["found"] and not df_uretim.empty:
        match = df_uretim[df_uretim['parti_no'].astype(str).str.contains(search_query, case=False, regex=False)]
        if not match.empty:
            chain["found"] = True
            chain["PRD"] = match.iloc[0]

    # C) Paçal Tablosunda Ara (Direkt girildiyse)
    if not chain["found"] and not df_mix.empty:
        match = df_mix[df_mix['batch_id'].astype(str).str.contains(search_query, case=False, regex=False)]
        if not match.empty:
            chain["found"] = True
            chain["MIX"] = match.iloc[0]


    # --- ADIM 2: EKSİK HALKALARI TAMAMLA (KÖPRÜLERİ GEÇ) ---

    # KÖPRÜ 2: Laboratuvar (LAB) -> Paçal (MIX)
    # Lab analiz formunda kaynağa (kaynak_parti_no) MIX-... kaydediliyor.
    if chain["LAB"] is not None and chain["MIX"] is None:
        mix_ref = str(chain["LAB"].get('kaynak_parti_no') or chain["LAB"].get('kullanilan_pacal') or '')
        if mix_ref and "MIX" in mix_ref.upper() and not df_mix.empty:
            m_match = df_mix[df_mix['batch_id'].astype(str).str.contains(mix_ref, case=False, regex=False)]
            if not m_match.empty: chain["MIX"] = m_match.iloc[0]

    # KÖPRÜ 3: Değirmen Üretim (PRD) -> Paçal (MIX)
    # Değirmen formunda kaynağa (kullanilan_pacal) MIX-... kaydediliyor.
    if chain["PRD"] is not None and chain["MIX"] is None:
        mix_ref = str(chain["PRD"].get('kullanilan_pacal') or chain["PRD"].get('mixing_batch_id') or '')
        if mix_ref and "MIX" in mix_ref.upper() and not df_mix.empty:
            
            if not m_match.empty: chain["MIX"] = m_match.iloc[0]

    # KÖPRÜ 4: Paçal (MIX) -> Değirmen Üretim (PRD) (Merkez İstasyon Dönüşü)
    # Elimizde Paçal (MIX) varsa, bu paçalın girdiği DEĞİRMEN ÜRETİMİNİ (PRD) bul.
    if chain["MIX"] is not None and chain["PRD"] is None and not df_uretim.empty:
        mix_id = str(chain["MIX"].get('batch_id', ''))
        if mix_id:
            u_match = df_uretim[df_uretim['kullanilan_pacal'].astype(str).str.contains(mix_id, case=False, regex=False)]
            if not u_match.empty:
                # Aynı paçalla birden fazla üretim yapıldıysa en son yapılanı alır
                chain["PRD"] = u_match.sort_values('tarih', ascending=False).iloc[0]

    # KÖPRÜ 5: Eğer Değirmen(PRD) var ama Laboratuvar(LAB) yoksa
    if chain["PRD"] is not None and chain["LAB"] is None and not df_analiz.empty:
        # MIX üzerinden kardeşi olan Laboratuvar analizini bul
        if chain["MIX"] is not None:
             mix_id = str(chain["MIX"].get('batch_id', ''))
             l_match = df_analiz[
                 (df_analiz['kaynak_parti_no'].astype(str).str.contains(mix_id, case=False, regex=False)) & 
                 (df_analiz['islem_tipi'] == 'ÜRETİM')
             ]
             if not l_match.empty:
                 chain["LAB"] = l_match.sort_values('tarih', ascending=False).iloc[0]
    # KÖPRÜ 6: Paçal (MIX) -> Enzim Reçetesi (ENZ)
    if chain["MIX"] is not None and chain["ENZ"] is None:
        mix_id = str(chain["MIX"].get('batch_id', ''))
        if mix_id:
            try:
                df_enz = fetch_data("enzim_receteleri")
                if not df_enz.empty:
                    # uretim_kodu sütununa kaydetmiştik, orada arıyoruz
                    e_match = df_enz[df_enz['uretim_kodu'].astype(str).str.contains(mix_id, case=False, regex=False)]
                    if not e_match.empty:
                        chain["ENZ"] = e_match.sort_values('tarih', ascending=False).iloc[0]
            except Exception as e:
                pass
    return chain
    
# ==============================================================================
# 2. GÖRSELLEŞTİRME (FRONTEND)
# ==============================================================================
def render_kvkk_row(label, value, unit="", color="black"):
    """Basit veri satırı"""
    if pd.isna(value) or value == "" or str(value).lower() == "nan":
        value = "-"
        unit = ""
    
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #f0f0f0; padding: 4px 0;">
        <span style="font-weight: 600; color: #555;">{label}</span>
        <span style="color: {color}; font-weight: 500;">{value} <span style="font-size:0.8em; color:#888;">{unit}</span></span>
    </div>
    """, unsafe_allow_html=True)

def fmt(val, decimals=1):
    """Sayı formatlama yardımcısı"""
    try: 
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return "-"
        return f"{float(val):.{decimals}f}"
    except: return str(val)

def show_traceability_dashboard():
    """KARA KUTU ANA EKRANI VE AKILLI FİLTRE PANELİ"""
    st.markdown("""
    <div style='background-color: #263238; padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>
        <h1 style='margin:0; font-size: 24px;'>🕵️‍♂️ İZLENEBİLİRLİK (KARA KUTU)</h1>
        <p style='color: #cfd8dc; margin-top:5px; font-size: 14px;'>Sevkiyat ➔ Lab ➔ Enzim ➔ Üretim ➔ Paçal ➔ Buğday</p>
    </div>
    """, unsafe_allow_html=True)

    # ==============================================================================
    # ⚡ HIZLI ERİŞİM VE AKILLI FİLTRE PANELİ
    # ==============================================================================
    st.markdown("### ⚡ Son Aktiviteler ve Hızlı Tarama")
    
    # Veritabanlarını sessizce çek
    df_analiz = pd.DataFrame()
    df_uretim = pd.DataFrame()
    df_enzim = pd.DataFrame()
    df_mix = pd.DataFrame()
    
    try: df_analiz = fetch_data("un_analiz")
    except: pass
    try: df_uretim = fetch_data("uretim_kaydi")
    except: pass
    try: df_enzim = fetch_data("enzim_receteleri")
    except: pass
    try: df_mix = fetch_data("mixing_batches")
    except: pass

    # Yardımcı Fonksiyon: Liste Hazırlama
    def hazirla(df, lot_col, label_cols, filter_col=None, filter_val=None):
        if df.empty or lot_col not in df.columns: return []
        temp_df = df.copy()
        if filter_col and filter_val and filter_col in temp_df.columns:
            temp_df = temp_df[temp_df[filter_col].astype(str).str.contains(filter_val, case=False, na=False, regex=False)]
        if 'tarih' in temp_df.columns:
            temp_df['tarih'] = pd.to_datetime(temp_df['tarih'], errors='coerce')
            temp_df = temp_df.sort_values('tarih', ascending=False)
        
        liste = []
        for _, row in temp_df.head(10).iterrows(): # SADECE SON 10 KAYIT
            lot = str(row.get(lot_col, ''))
            if not lot or lot.lower() == 'nan': continue
            
            tarih = row['tarih'].strftime('%d.%m %H:%M') if pd.notnull(row.get('tarih')) else "-"
            ekstra = " - ".join([str(row.get(c, '')) for c in label_cols if pd.notnull(row.get(c)) and str(row.get(c)) != 'nan'])
            
            liste.append(f"{lot} | {tarih} | {ekstra}")
        return liste

    # Sekmeler
    t1, t2, t3, t4, t5 = st.tabs(["🚚 Sevkiyatlar", "🔬 Lab Analizleri", "💊 Enzimler", "🏭 Üretimler", "🌾 Paçallar"])
    
    secilen_hizli_kod = None
    
    with t1:
        liste = hazirla(df_analiz, 'lot_no', ['musteri_adi', 'un_cinsi_marka'], 'islem_tipi', 'SEVK')
        if liste:
            secim = st.selectbox("Son 10 Sevkiyat Kaydı", ["Seçiniz..."] + liste, key="hizli_sevk")
            if secim != "Seçiniz...": secilen_hizli_kod = secim.split(' | ')[0].strip()
        else: st.info("Kayıt yok.")
            
    with t2:
        liste = hazirla(df_analiz, 'lot_no', ['un_markasi'], 'islem_tipi', 'ÜRETİM')
        if liste:
            secim = st.selectbox("Son 10 Üretim Analizi (PRD)", ["Seçiniz..."] + liste, key="hizli_lab")
            if secim != "Seçiniz...": secilen_hizli_kod = secim.split(' | ')[0].strip()
        else: st.info("Kayıt yok.")
            
    with t3:
        liste = hazirla(df_enzim, 'enzim_id', ['uretim_kodu'])
        if liste:
            secim = st.selectbox("Son 10 Enzim Reçetesi", ["Seçiniz..."] + liste, key="hizli_enz")
            if secim != "Seçiniz...": secilen_hizli_kod = secim.split(' | ')[0].strip()
        else: st.info("Kayıt yok.")
            
    with t4:
        liste = hazirla(df_uretim, 'parti_no', ['vardiya', 'kullanilan_pacal'])
        if liste:
            secim = st.selectbox("Son 10 Değirmen Üretimi", ["Seçiniz..."] + liste, key="hizli_prd")
            if secim != "Seçiniz...": secilen_hizli_kod = secim.split(' | ')[0].strip()
        else: st.info("Kayıt yok.")
            
    with t5:
        liste = hazirla(df_mix, 'batch_id', ['urun_adi'])
        if liste:
            secim = st.selectbox("Son 10 Paçal Reçetesi", ["Seçiniz..."] + liste, key="hizli_mix")
            if secim != "Seçiniz...": secilen_hizli_kod = secim.split(' | ')[0].strip()
        else: st.info("Kayıt yok.")

    st.divider()

    # ==============================================================================
    # MANUEL ARAMA MOTORU (Alternatif)
    # ==============================================================================
    st.markdown("**Veya Geçmiş Bir Kodu Manuel Arayın:**")
    col_search, col_btn = st.columns([3, 1])
    
    # Eğer yukarıdan bir şey seçildiyse input kutusuna otomatik yazsın
    default_query = secilen_hizli_kod if secilen_hizli_kod else ""
    
    with col_search:
        query = st.text_input("🔍 Takip Kodu Giriniz", value=default_query, placeholder="SHIP-..., PRD-..., MIX-...")
    with col_btn:
        st.write("")
        st.write("")
        ara_btn = st.button("🚀 ZİNCİRİ TARA", type="primary", width='stretch')
    if ara_btn and query:
        # Cache temizle ki en güncel veriyi görsün
        st.cache_data.clear()
        
        with st.spinner("Veri tabanı taranıyor..."):
            chain = get_trace_chain(query)
        
        if not chain["found"]:
            st.error("❌ Kayıt bulunamadı.")
            return

        st.success(f"✅ Kayıt Bulundu: {query}")
        
        # --- PDF RAPOR BUTONU (GİRİNTİ DÜZELTİLDİ) ---
        st.divider()
        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.info("💡 Bu partinin (Lot) tüm hikayesini PDF olarak indirebilirsiniz.")
        with col_btn:
            # Rapor Fonksiyonunu Çağır
            try:
                pdf_data = create_traceability_pdf_report(chain)
                if pdf_data:
                    st.download_button(
                        label="📄 Raporu İndir",
                        data=pdf_data,
                        file_name=f"izlenebilirlik_{query}.pdf",
                        mime="application/pdf",
                        width='stretch',
                        type="primary"
                    )
                else:
                    st.warning("PDF oluşturulamadı")
            except Exception as e:
                st.error(f"PDF Hatası: {e}")
        st.divider()
        # ======================================================================
        # 1. HALKA: SEVKİYAT BİLGİSİ (SHIP)
        # ======================================================================
        if chain["SHIP"] is not None:
            ship = chain["SHIP"]
            with st.expander("🚚 1. SEVKİYAT BİLGİLERİ / ÇIKIŞ ANALİZ SONUÇLARI", expanded=True):
                # --- A. TEMEL BİLGİLER ---
                c1, c2 = st.columns(2)
                with c1:
                    render_kvkk_row("Lot No", ship.get('lot_no'))
                    # Müşteri adı
                    musteri = ship.get('musteri_adi') or ship.get('musteri') or ship.get('cari_adi')
                    render_kvkk_row("Müşteri", musteri)
                    # Plaka
                    render_kvkk_row("Plaka", ship.get('plaka'))
                    
                with c2:
                    # Ürün adı
                    urun = ship.get('un_cinsi_marka') or ship.get('un_markasi') or ship.get('urun_adi')
                    render_kvkk_row("Ürün", urun)
                    # Tarih
                    render_kvkk_row("Tarih", str(ship.get('tarih'))[:16])
                
                # Bağlantı Uyarısı
                kaynak = ship.get('kaynak_parti_no') or ship.get('uretim_lot_no')
                if not kaynak or str(kaynak).lower() == 'nan':
                    st.warning("⚠️ Bu sevkiyat kaydında 'Kaynak Parti No' (Üretim Lotu) boş olduğu için geriye gidilemiyor.")
                else:
                    st.info(f"🔗 Kaynak Üretim Lotu: {kaynak}")

                st.divider()
                
                # --- B. DETAYLI ANALİZ (FULL SPEKTRUM) ---
                st.markdown("##### 🧪 Çıkış Analiz Değerleri (Full)")
                
                t1, t2, t3 = st.tabs(["⚗️ Kimyasal", "📈 Farinograph", "📊 Extensograph"])
                
                with t1:
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Protein", fmt(ship.get('protein')))
                    k2.metric("Kül", fmt(ship.get('kul'), 3))
                    k3.metric("Rutubet", fmt(ship.get('rutubet')))
                    k4.metric("Gluten", fmt(ship.get('gluten')))
                    
                    k5, k6, k7, k8 = st.columns(4)
                    k5.metric("G. İndeks", fmt(ship.get('gluten_index'), 0))
                    k6.metric("Sedim", fmt(ship.get('sedim'), 0))
                    k7.metric("G. Sedim", fmt(ship.get('gecikmeli_sedim') or ship.get('g_sedim'), 0))
                    k8.metric("FN", fmt(ship.get('fn'), 0))
                    
                    k9, k10, k11, k12 = st.columns(4)
                    k9.metric("FFN", fmt(ship.get('ffn'), 0))

                with t2:
                    f1, f2 = st.columns(2)
                    f1.metric("Su Kal. (F)", fmt(ship.get('su_kaldirma_f')))
                    f1.metric("Gelişme", fmt(ship.get('gelisme_suresi')))
                    f2.metric("Stabilite", fmt(ship.get('stabilite')))
                    f2.metric("Yumuşama", fmt(ship.get('yumusama'), 0))

                with t3:
                    st.markdown("**45. Dakika**")
                    ex1, ex2, ex3 = st.columns(3)
                    ex1.metric("Enerji (45)", fmt(ship.get('enerji45'), 0))
                    ex2.metric("Direnç (45)", fmt(ship.get('direnc45'), 0))
                    ex3.metric("Uzama (45)", fmt(ship.get('uzama45'), 0))
                    
                    st.markdown("**90. Dakika**")
                    ex4, ex5, ex6 = st.columns(3)
                    ex4.metric("Enerji (90)", fmt(ship.get('enerji90'), 0))
                    ex5.metric("Direnç (90)", fmt(ship.get('direnc90'), 0))
                    ex6.metric("Uzama (90)", fmt(ship.get('uzama90'), 0))
                    
                    st.markdown("**135. Dakika**")
                    ex7, ex8, ex9 = st.columns(3)
                    e135 = ship.get('enerji135') or ship.get('enerji')
                    d135 = ship.get('direnc135') or ship.get('direnc')
                    u135 = ship.get('uzama135') or ship.get('uzama')
                    ex7.metric("Enerji (135)", fmt(e135, 0))
                    ex8.metric("Direnç (135)", fmt(d135, 0))
                    ex9.metric("Uzama (135)", fmt(u135, 0))
        # ======================================================================
        # 2. HALKA: LABORATUVAR (Üretim Kontrolü)
        # ======================================================================
        if chain["LAB"] is not None:
            ship_lot = chain.get("SHIP", {}).get('lot_no') if chain.get("SHIP") is not None else ""
            lab_lot = chain["LAB"].get('lot_no')
            
            # Eğer sevkiyat analiziyle aynı değilse göster
            if ship_lot != lab_lot:
                lab = chain["LAB"]
                with st.expander("🔬 2. ÜRETİM KONTROL ANALİZİ (LAB)", expanded=True):
                    st.markdown(f"**Referans:** `{lab.get('lot_no')}` | **Tarih:** {str(lab.get('tarih'))[:16]}")
                    
                    lt1, lt2, lt3 = st.tabs(["⚗️ Kimyasal", "📈 Farinograph", "📊 Extensograph"])
                    
                    with lt1:
                        k1, k2, k3, k4 = st.columns(4)
                        k1.metric("Protein", fmt(lab.get('protein')))
                        k2.metric("Kül", fmt(lab.get('kul'), 3))
                        k3.metric("Rutubet", fmt(lab.get('rutubet')))
                        k4.metric("Gluten", fmt(lab.get('gluten')))
                        
                        k5, k6, k7, k8 = st.columns(4)
                        k5.metric("G. İndeks", fmt(lab.get('gluten_index'), 0))
                        k6.metric("Sedim", fmt(lab.get('sedim'), 0))
                        k7.metric("G. Sedim", fmt(lab.get('gecikmeli_sedim') or lab.get('g_sedim'), 0))
                        k8.metric("FN", fmt(lab.get('fn'), 0))
                        
                        k9, k10 = st.columns([1,3])
                        k9.metric("FFN", fmt(lab.get('ffn'), 0))

                    with lt2:
                        f1, f2 = st.columns(2)
                        f1.metric("Su Kal. (F)", fmt(lab.get('su_kaldirma_f')))
                        f1.metric("Gelişme", fmt(lab.get('gelisme_suresi')))
                        f2.metric("Stabilite", fmt(lab.get('stabilite')))
                        f2.metric("Yumuşama", fmt(lab.get('yumusama'), 0))

                    with lt3:
                        st.markdown("**45. Dakika**")
                        ex1, ex2, ex3 = st.columns(3)
                        ex1.metric("Enerji (45)", fmt(lab.get('enerji45'), 0))
                        ex2.metric("Direnç (45)", fmt(lab.get('direnc45'), 0))
                        ex3.metric("Uzama (45)", fmt(lab.get('uzama45'), 0))
                        
                        st.markdown("**90. Dakika**")
                        ex4, ex5, ex6 = st.columns(3)
                        ex4.metric("Enerji (90)", fmt(lab.get('enerji90'), 0))
                        ex5.metric("Direnç (90)", fmt(lab.get('direnc90'), 0))
                        ex6.metric("Uzama (90)", fmt(lab.get('uzama90'), 0))
                        
                        st.markdown("**135. Dakika**")
                        ex7, ex8, ex9 = st.columns(3)
                        e135 = lab.get('enerji135') or lab.get('enerji')
                        d135 = lab.get('direnc135') or lab.get('direnc')
                        u135 = lab.get('uzama135') or lab.get('uzama')
                        ex7.metric("Enerji (135)", fmt(e135, 0))
                        ex8.metric("Direnç (135)", fmt(d135, 0))
                        ex9.metric("Uzama (135)", fmt(u135, 0))
        # ======================================================================
        # 3. HALKA: ENZİM REÇETESİ (ENZ) (PAÇALA BAĞLI)
        # ======================================================================
        if chain["ENZ"] is not None:
            enz = chain["ENZ"]
            with st.expander("💊 3. ENZİM VE KATKI REÇETESİ (ENZ)", expanded=True):
                st.info(f"🔗 **Bağlı Paçal:** `{enz.get('uretim_kodu')}` | **Kimlik:** `{enz.get('enzim_id')}`")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Hedef Un", f"{float(enz.get('un_ton', 0)):.1f} Ton")
                c2.metric("Buğday Hızı", f"{float(enz.get('bugday_hiz', 0)):.0f} kg/s")
                c3.metric("Akış Hızı", f"{float(enz.get('dozaj_akis', 0)):.0f} gr/dk")
                
                st.divider()
                
                try:
                    enz_verisi = json.loads(enz.get('enzim_verisi_json', '[]'))
                    if enz_verisi:
                        st.markdown("**🧪 Reçete İçeriği**")
                        cols = st.columns(len(enz_verisi))
                        for idx, item in enumerate(enz_verisi):
                            cols[idx].metric(item.get('ad', '-'), f"{item.get('doz', 0)} gr/çuv")
                    else:
                        st.warning("Reçete içeriği boş.")
                except Exception as e:
                    st.error(f"Reçete içeriği okunamadı: {e}")

        # ======================================================================
        # 4. HALKA: ÜRETİM (Mill Data)
        # ======================================================================
        if chain["PRD"] is not None:
            prd = chain["PRD"]
            with st.expander("🏭 4. ÜRETİM VE DEĞİRMEN VERİLERİ", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("##### ⚙️ Operasyon")
                    render_kvkk_row("Parti No", prd.get('parti_no'))
                    render_kvkk_row("Tarih", str(prd.get('tarih'))[:16])
                    render_kvkk_row("Vardiya", f"{prd.get('vardiya')} ({prd.get('sorumlu')})")
                    render_kvkk_row("Kırılan", f"{float(prd.get('kirilan_bugday',0)):,.0f} Kg")
                    render_kvkk_row("Tav Süresi", prd.get('tav_suresi'), "Saat")

                with c2:
                    st.markdown("##### 📉 Randıman")
                    r_top = float(prd.get('toplam_randiman', 0))
                    render_kvkk_row("TOPLAM RANDIMAN", f"{r_top:.2f}", "%", "green" if r_top>74 else "orange")
                    st.divider()
                    render_kvkk_row("Un-1", f"{float(prd.get('un_1',0)):,.0f}", "Kg")
                    render_kvkk_row("Un-2", f"{float(prd.get('un_2',0)):,.0f}", "Kg")
                    render_kvkk_row("Kepek", f"{float(prd.get('kepek',0)):,.0f}", "Kg")
                    render_kvkk_row("Bongalite", f"{float(prd.get('bongalite',0)):,.0f}", "Kg")
                    
                    kayip = float(prd.get('kayip', 0))
                    render_kvkk_row("Kayıp Oranı", f"{kayip:.2f}", "%", "red" if kayip > 2 else "black")     

        
        # ======================================================================
        # 5. HALKA: PAÇAL (MIX) - FULL DETAY VE ALT SEKMELİ YAPI
        # ======================================================================
        if chain["MIX"] is not None:
            mix = chain["MIX"]
            with st.expander("🌾 5. PAÇAL VE HAMMADDE İÇERİĞİ (MIX)", expanded=True):
                st.info(f"🔗 **Reçete:** `{mix.get('urun_adi')}` | **ID:** `{mix.get('batch_id')}`")
                
                try:
                    snapshot = json.loads(mix.get('silo_snapshot_json', '{}'))
                    analiz = json.loads(mix.get('analiz_snapshot_json', '{}'))
                    
                    # --- AKILLI KURTARMA (FALLBACK) ---
                    # Eğer kuru protein veya maliyet 0.00 gelirse, oranlardan canlı hesapla
                    k_prot = float(analiz.get('kuru_protein_ort') or analiz.get('teorik_kuru_protein') or 0.0)
                    if k_prot == 0.0:
                        for s_isim, s_data in snapshot.items():
                            if isinstance(s_data, dict):
                                o = float(s_data.get('oran', 0))
                                p = float(s_data.get('kuru_analiz', {}).get('protein', 0) or 0)
                                k_prot += p * (o / 100)

                    # --- 1. PAÇAL HEDEFLERİ ---
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Hedef Kuru Protein", fmt(k_prot))
                    k2.metric("Hedef Tavlı Protein", fmt(analiz.get('protein', 0)))
                    k3.metric("Ortalama Maliyet", f"{float(mix.get('maliyet', 0)):.2f} TL")
                    
                    st.divider()
                    
                    # --- 2. KULLANILAN SİLOLAR (SADE ÖZET TABLO) ---
                    st.markdown("##### 🏗️ Kullanılan Silolar (Reçete Özeti)")
                    
                    rows = []
                    gecerli_silolar = {}
                    for silo, data in snapshot.items():
                        if isinstance(data, dict):
                            oran = float(data.get('oran', 0))
                            if oran > 0:
                                meta = data.get('meta', {})
                                kuru = data.get('kuru_analiz', {})
                                cins = meta.get('cins') or kuru.get('cins') or "-"
                                
                                # Akıllı Maliyet Çekimi
                                maliyet = float(meta.get('maliyet') or kuru.get('maliyet') or 0.0)
                                
                                rows.append({
                                    "Silo": silo,
                                    "Oran": f"%{oran}",
                                    "Cins": cins,
                                    "Maliyet": f"{maliyet:.2f} TL"
                                })
                                gecerli_silolar[silo] = data
                        else:
                            rows.append({"Silo": silo, "Oran": f"%{data}", "Cins": "-", "Maliyet": "-"})
                            
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
                    
                    # --- 3. SİLO DETAYLARI (SEKMELİ / TAB YAPI) ---
                    if gecerli_silolar:
                        st.divider()
                        st.markdown("##### 🔬 Silo Analiz Detayları)")
                        
                        silo_isimleri = [f"🏭 {s} (%{d.get('oran')})" for s, d in gecerli_silolar.items()]
                        silo_tablari = st.tabs(silo_isimleri)
                        
                        for idx, (silo, data) in enumerate(gecerli_silolar.items()):
                            with silo_tablari[idx]:
                                kuru = data.get('kuru_analiz', {})
                                tavli = data.get('tavli_analiz', {})
                                
                                col_kuru, col_tavli = st.columns([1, 1.4], gap="medium")
                                
                                # ==========================================
                                # SOL KUTU: KURU BUĞDAY (3 Sütunlu Liste)
                                # ==========================================
                                with col_kuru:
                                    st.markdown("<h6 style='color:#b45309;'>🌾 KURU BUĞDAY ANALİZLERİ</h6>", unsafe_allow_html=True)
                                    with st.container(border=True):
                                        ck1, ck2, ck3 = st.columns(3)
                                        
                                        # 1. Sütun
                                        ck1.markdown(f"**Hektolitre:** {fmt(kuru.get('hektolitre'))}")
                                        ck1.markdown(f"**Gluten:** {fmt(kuru.get('gluten'))}")
                                        ck1.markdown(f"**G. Sedim:** {fmt(kuru.get('gecikmeli_sedim') or kuru.get('g_sedim'), 0)}")
                                        ck1.markdown(f"**Yabancı T.:** {fmt(kuru.get('yabanci_madde') or kuru.get('yabanci'))}")
                                        
                                        # 2. Sütun
                                        ck2.markdown(f"**Protein:** {fmt(kuru.get('protein'))}")
                                        ck2.markdown(f"**G. İndeks:** {fmt(kuru.get('gluten_index'), 0)}")
                                        ck2.markdown(f"**Süne:** {fmt(kuru.get('sune'))}")
                                        
                                        # 3. Sütun
                                        ck3.markdown(f"**Rutubet:** {fmt(kuru.get('rutubet'))}")
                                        ck3.markdown(f"**Sedim:** {fmt(kuru.get('sedim'), 0)}")
                                        ck3.markdown(f"**Kırık/Cılız:** {fmt(kuru.get('kirik_ciliz') or kuru.get('kirik'))}")
                                
                                # ==========================================
                                # SAĞ KUTU: TAVLI BUĞDAY (Alt Sekmeli)
                                # ==========================================
                                with col_tavli:
                                    st.markdown("<h6 style='color:#0369a1;'>💧 TAVLI BUĞDAY ANALİZLERİ</h6>", unsafe_allow_html=True)
                                    with st.container(border=True):
                                        t_kimya, t_farino, t_extenso = st.tabs(["⚗️ Kimyasal", "📈 Farinograph", "📊 Extensograph"])
                                        
                                        with t_kimya:
                                            ct1, ct2, ct3 = st.columns(3)
                                            ct1.markdown(f"**Protein:** {fmt(tavli.get('protein'))}")
                                            ct2.markdown(f"**Rutubet:** {fmt(tavli.get('rutubet'))}")
                                            ct3.markdown(f"**Gluten:** {fmt(tavli.get('gluten'))}")
                                            
                                            ct1.markdown(f"**G. İndeks:** {fmt(tavli.get('gluten_index'), 0)}")
                                            ct2.markdown(f"**Sedim:** {fmt(tavli.get('sedim'), 0)}")
                                            ct3.markdown(f"**G. Sedim:** {fmt(tavli.get('gecikmeli_sedim') or tavli.get('g_sedim'), 0)}")
                                            
                                            ct1.markdown(f"**FN:** {fmt(tavli.get('fn'), 0)}")
                                            ct2.markdown(f"**FFN:** {fmt(tavli.get('ffn'), 0)}")
                                            ct3.markdown(f"**Amilograph:** {fmt(tavli.get('amilograph'), 0)}")

                                        with t_farino:
                                            cf1, cf2 = st.columns(2)
                                            cf1.markdown(f"**Su Kaldırma:** {fmt(tavli.get('su_kaldirma_f'))}")
                                            cf1.markdown(f"**Gelişme Süresi:** {fmt(tavli.get('gelisme_suresi'))}")
                                            
                                            cf2.markdown(f"**Stabilite:** {fmt(tavli.get('stabilite'))}")
                                            cf2.markdown(f"**Yumuşama:** {fmt(tavli.get('yumusama'), 0)}")

                                        with t_extenso:
                                            st.markdown(f"**Su Kaldırma (E):** {fmt(tavli.get('su_kaldirma_e'))}")
                                            st.markdown("---")
                                            ce1, ce2, ce3 = st.columns(3)
                                            
                                            ce1.caption("45. Dakika")
                                            ce1.markdown(f"Direnç: {fmt(tavli.get('direnc45'), 0)}")
                                            ce1.markdown(f"Taban: {fmt(tavli.get('taban45'), 0)}")
                                            ce1.markdown(f"Enerji: {fmt(tavli.get('enerji45'), 0)}")
                                            
                                            ce2.caption("90. Dakika")
                                            ce2.markdown(f"Direnç: {fmt(tavli.get('direnc90'), 0)}")
                                            ce2.markdown(f"Taban: {fmt(tavli.get('taban90'), 0)}")
                                            ce2.markdown(f"Enerji: {fmt(tavli.get('enerji90'), 0)}")
                                            
                                            ce3.caption("135. Dakika")
                                            ce3.markdown(f"Direnç: {fmt(tavli.get('direnc135'), 0)}")
                                            ce3.markdown(f"Taban: {fmt(tavli.get('taban135'), 0)}")
                                            ce3.markdown(f"Enerji: {fmt(tavli.get('enerji135'), 0)}")
                                
                except Exception as e:
                    st.error(f"Paçal verisi okunamadı: {e}")

        elif chain["PRD"] is not None:
            st.warning("⚠️ Bu üretime bağlı Paçal kaydı bulunamadı (Mix ID eksik veya eşleşmiyor).")



