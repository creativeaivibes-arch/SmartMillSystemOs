import streamlit as st
import pandas as pd
import json
from datetime import datetime

# Veritabanı Erişim
from app.core.database import fetch_data

# ==============================================================================
# 1. ZİNCİR KURMA MOTORU (BACKEND)
# ==============================================================================
def get_trace_chain(search_query):
    """
    Girilen Lot/ID'den başlayıp geriye doğru tüm zinciri kurar.
    """
    chain = {
        "found": False,
        "SHIP": None, # Sevkiyat
        "LAB": None,  # Laboratuvar (Un Analizi)
        "PRD": None,  # Üretim (Değirmen Verileri)
        "MIX": None,  # Paçal (Reçete ve Snapshot)
        "ENZ": None   # Enzim (Varsa)
    }
    
    search_query = str(search_query).strip()
    
    # --- ADIM 1: ARAMA MOTORU (Tüm Tabloları Tara) ---
    
    # A) Üretim Kayıtlarında Ara (PRD-...)
    if not chain["found"]:
        try:
            df_uretim = fetch_data("uretim_kaydi")
            if not df_uretim.empty:
                match = df_uretim[df_uretim.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
                if not match.empty:
                    chain["found"] = True
                    chain["PRD"] = match.iloc[0]
        except: pass

    # B) Paçal Kayıtlarında Ara (MIX-...)
    if not chain["found"]:
        try:
            df_mix = fetch_data("mixing_batches")
            if not df_mix.empty:
                match = df_mix[df_mix['batch_id'].astype(str) == search_query]
                if not match.empty:
                    chain["found"] = True
                    chain["MIX"] = match.iloc[0]
        except: pass

    # C) Sevkiyat Listesinde Ara (SHIP/IRSALIYE)
    if not chain["found"]:
        try:
            df_ship = fetch_data("sevkiyat_listesi")
            if not df_ship.empty:
                match = df_ship[df_ship.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
                if not match.empty:
                    chain["found"] = True
                    chain["SHIP"] = match.iloc[0]
                    # Sevkiyattan Üretime Köprü
                    if 'uretim_lot_no' in chain["SHIP"]:
                        lot_ref = str(chain["SHIP"]['uretim_lot_no'])
                        if lot_ref:
                            df_uretim = fetch_data("uretim_kaydi")
                            if not df_uretim.empty:
                                u_match = df_uretim[df_uretim['parti_no'] == lot_ref]
                                if not u_match.empty: chain["PRD"] = u_match.iloc[0]
        except: pass

    # D) Un Analizlerinde Ara (LAB-...) - DÜZELTİLEN KISIM
    if not chain["found"]:
        try:
            # HATA BURADAYDI: 'un_analizleri' -> 'un_analiz' OLARAK DÜZELTİLDİ
            df_lab_search = fetch_data("un_analiz") 
            
            if not df_lab_search.empty and 'lot_no' in df_lab_search.columns:
                match = df_lab_search[df_lab_search['lot_no'].astype(str) == search_query]
                if not match.empty:
                    chain["found"] = True
                    chain["LAB"] = match.iloc[0]
                    # Lab analizinden üretime geçiş
                    uretim_ref = str(chain["LAB"].get('lot_no', ''))
                    df_uretim = fetch_data("uretim_kaydi")
                    if not df_uretim.empty:
                        u_match = df_uretim[df_uretim['parti_no'] == uretim_ref]
                        if not u_match.empty: chain["PRD"] = u_match.iloc[0]
        except: pass

    # --- ADIM 2: ZİNCİRİ TAMAMLA (Eksik halkaları doldur) ---
    
    if chain["PRD"] is not None:
        # 1. Paçalı Bul
        mix_id = str(chain["PRD"].get('mixing_batch_id', ''))
        if mix_id and mix_id != "BILINMIYOR":
            try:
                df_mix = fetch_data("mixing_batches")
                if not df_mix.empty:
                    m_match = df_mix[df_mix['batch_id'] == mix_id]
                    if not m_match.empty: chain["MIX"] = m_match.iloc[0]
            except: pass
        
        # 2. Lab Analizini Bul - DÜZELTİLEN KISIM
        if chain["LAB"] is None:
            try:
                # HATA BURADAYDI: 'un_analizleri' -> 'un_analiz' OLARAK DÜZELTİLDİ
                df_lab = fetch_data("un_analiz")
                
                if not df_lab.empty:
                    parti_no = str(chain["PRD"].get('parti_no', ''))
                    l_match = df_lab[df_lab['lot_no'] == parti_no]
                    if not l_match.empty: chain["LAB"] = l_match.iloc[0]
            except: pass

    return chain

# ==============================================================================
# 2. GÖRSELLEŞTİRME (FRONTEND)
# ==============================================================================
def render_kvkk_row(label, value, unit="", color="black"):
    """Basit veri satırı"""
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #f0f0f0; padding: 4px 0;">
        <span style="font-weight: 600; color: #555;">{label}</span>
        <span style="color: {color}; font-weight: 500;">{value} <span style="font-size:0.8em; color:#888;">{unit}</span></span>
    </div>
    """, unsafe_allow_html=True)

def show_traceability_dashboard():
    """KARA KUTU ANA EKRANI"""
    st.markdown("""
    <div style='background-color: #263238; padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>
        <h1 style='margin:0; font-size: 24px;'>🕵️‍♂️ İZLENEBİLİRLİK (KARA KUTU)</h1>
        <p style='color: #cfd8dc; margin-top:5px; font-size: 14px;'>Sevkiyat ➔ Üretim ➔ Paçal ➔ Buğday (Geriye Dönük Tam Takip)</p>
    </div>
    """, unsafe_allow_html=True)

    # --- ARAMA MOTORU ---
    col_search, col_btn = st.columns([3, 1])
    with col_search:
        query = st.text_input("🔍 Takip Kodu Giriniz", placeholder="Parti No (PRD-...), Paçal ID (MIX-...) veya Lot No")
    with col_btn:
        st.write("")
        st.write("")
        ara_btn = st.button("🚀 ZİNCİRİ TARA", type="primary", use_container_width=True)

    if ara_btn and query:
        with st.spinner("Veri tabanı taranıyor, bağlantılar kuruluyor..."):
            chain = get_trace_chain(query)
        
        if not chain["found"]:
            st.error("❌ Kayıt bulunamadı. Lütfen kodu kontrol edin veya ilgili tabloların (un_analiz, sevkiyat_listesi vb.) dolu olduğundan emin olun.")
            return

        st.success("✅ Zincir Başarıyla Kuruldu!")
        
        # 0. HALKA: SEVKİYAT BİLGİSİ (Varsa)
        if chain["SHIP"] is not None:
            ship = chain["SHIP"]
            with st.expander("🚚 0. SEVKİYAT BİLGİSİ (ÇIKIŞ)", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    render_kvkk_row("Lot No", ship.get('lot_no'))
                    render_kvkk_row("Müşteri", ship.get('musteri_adi'))
                    render_kvkk_row("Plaka", ship.get('plaka'))
                with c2:
                    tarih_val = str(ship.get('tarih'))[:16]
                    render_kvkk_row("Tarih", tarih_val)
                    render_kvkk_row("Miktar", ship.get('miktar'), "Kg")
                    render_kvkk_row("Ürün", ship.get('urun_adi'))

        # 1. HALKA: ÜRETİM & DEĞİRMEN (Mill Data)
        if chain["PRD"] is not None:
            prd = chain["PRD"]
            with st.expander("🏭 1. ÜRETİM VE DEĞİRMEN VERİLERİ (PRD)", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("##### ⚙️ Operasyonel Bilgiler")
                    render_kvkk_row("Parti No", prd.get('parti_no'))
                    try:
                        t_prd = pd.to_datetime(prd.get('tarih')).strftime('%d.%m.%Y %H:%M')
                    except: t_prd = str(prd.get('tarih'))
                    render_kvkk_row("Tarih", t_prd)
                    render_kvkk_row("Vardiya", f"{prd.get('vardiya')} ({prd.get('sorumlu')})")
                    render_kvkk_row("Hat", prd.get('uretim_hatti'))
                    st.divider()
                    render_kvkk_row("Kırılan Buğday", f"{float(prd.get('kirilan_bugday',0)):,.0f}", "Kg")
                    render_kvkk_row("Tav Süresi", prd.get('tav_suresi'), "Saat")
                    render_kvkk_row("B1 Rutubet", prd.get('nem_orani'), "%")

                with c2:
                    st.markdown("##### 📉 Randıman Analizi")
                    r_toplam = float(prd.get('toplam_randiman', 0))
                    color_r = "green" if r_toplam > 74 else "orange"
                    
                    render_kvkk_row("TOPLAM RANDIMAN", f"{r_toplam:.2f}", "%", color_r)
                    st.divider()
                    render_kvkk_row("Un-1 Çıkan", f"{float(prd.get('un_1',0)):,.0f}", "Kg")
                    render_kvkk_row("Un-2 Çıkan", f"{float(prd.get('un_2',0)):,.0f}", "Kg")
                    render_kvkk_row("Kepek", f"{float(prd.get('kepek',0)):,.0f}", "Kg")
                    render_kvkk_row("Bongalite", f"{float(prd.get('bongalite',0)):,.0f}", "Kg")
                    
                    kayip = float(prd.get('kayip', 0))
                    render_kvkk_row("Kayıp Oranı", f"{kayip:.2f}", "%", "red" if kayip > 2 else "black")

        # 2. HALKA: PAÇAL VE BUĞDAY (Mix & Wheat Data)
        if chain["MIX"] is not None:
            mix = chain["MIX"]
            with st.expander("🌾 2. PAÇAL VE HAMMADDE İÇERİĞİ (MIX)", expanded=True):
                st.info(f"🔗 **Bağlı Reçete:** `{mix.get('urun_adi')}` | **ID:** `{mix.get('batch_id')}`")
                
                try:
                    snapshot = json.loads(mix.get('silo_snapshot_json', '{}'))
                    analiz = json.loads(mix.get('analiz_snapshot_json', '{}'))
                    
                    # A. PAÇAL HEDEF DEĞERLERİ
                    st.markdown("##### 🧪 Paçalın Teorik Analiz Değerleri (Hesaplanan)")
                    k1, k2, k3, k4 = st.columns(4)
                    
                    k_prot = analiz.get('kuru_protein_ort', analiz.get('teorik_kuru_protein', 0))
                    k1.metric("Kuru Protein", f"{float(k_prot):.1f}")
                    k2.metric("Tavlı Protein", f"{float(analiz.get('protein', 0)):.1f}")
                    k3.metric("Tavlı Enerji", f"{float(analiz.get('enerji135', 0)):.0f}")
                    k4.metric("Maliyet", f"{float(mix.get('maliyet', 0)):.2f} TL")
                    
                    st.divider()
                    
                    # B. SİLO DETAYLARI
                    st.markdown("##### 🏗️ Kullanılan Silolar ve O Anki Analizleri")
                    
                    rows = []
                    for silo, data in snapshot.items():
                        if isinstance(data, dict):
                            meta = data.get('meta', {})
                            kuru = data.get('kuru_analiz', {})
                            tavli = data.get('tavli_analiz', {})
                            
                            cins = meta.get('cins') or kuru.get('cins') or "-"
                            
                            rows.append({
                                "Silo": silo,
                                "Oran": f"%{data.get('oran', 0)}",
                                "Cins": cins,
                                "Kuru Prot.": f"{float(kuru.get('protein', 0) or 0):.1f}",
                                "Süne": f"{float(kuru.get('sune', 0) or 0):.1f}",
                                "Hektolitre": f"{float(kuru.get('hektolitre', 0) or 0):.1f}",
                                "Tavlı Enerji": f"{float(tavli.get('enerji135', 0) or 0):.0f}"
                            })
                        else:
                            rows.append({"Silo": silo, "Oran": f"%{data}"})
                            
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Paçal verisi okunurken hata: {e}")

        elif chain["PRD"] is not None:
            st.warning("⚠️ Bu üretime bağlı Paçal (MIX) kaydı bulunamadı.")

        # 3. HALKA: LABORATUVAR (Final Ürün Analizi)
        if chain["LAB"] is not None:
            lab = chain["LAB"]
            with st.expander("🔬 3. FİNAL ÜRÜN ANALİZİ (LAB)", expanded=True):
                st.markdown(f"**Numune:** {lab.get('numune_adi')} | **Tarih:** {lab.get('tarih')}")
                
                # Değerleri güvenli çekme
                def safe_val(key): return lab.get(key, '-')

                t1, t2 = st.tabs(["Kimyasal", "Reoloji"])
                with t1:
                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric("Protein", safe_val('protein'))
                    lc2.metric("Kül", safe_val('kul'))
                    lc3.metric("Renk", safe_val('renk'))
                with t2:
                    lc4, lc5, lc6 = st.columns(3)
                    lc4.metric("Enerji", safe_val('enerji135') if safe_val('enerji135') != '-' else safe_val('enerji'))
                    lc5.metric("Direnç", safe_val('direnc135') if safe_val('direnc135') != '-' else safe_val('direnc'))
                    lc6.metric("Stabilite", safe_val('stabilite'))
        
        elif chain["found"]:
            st.info("ℹ️ Bu partiye ait laboratuvar sonucu henüz girilmemiş veya eşleşmemiş.")

    elif ara_btn:
        st.warning("Lütfen bir arama kodu giriniz.")
