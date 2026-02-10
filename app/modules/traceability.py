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
        "SHIP": None, # Sevkiyat (Un Analiz tablosundan islem_tipi=SEVKİYAT)
        "LAB": None,  # Laboratuvar (Un Analiz tablosundan islem_tipi=ÜRETİM)
        "PRD": None,  # Üretim (Değirmen Verileri)
        "MIX": None,  # Paçal (Reçete ve Snapshot)
        "ENZ": None   # Enzim (Varsa)
    }
    
    search_query = str(search_query).strip()
    
    # --- ADIM 1: ANALİZ TABLOSUNDAN BAŞLA (Hem Sevkiyat Hem Lab Burada) ---
    try:
        # Tablo adını senin ekran görüntüne göre 'un_analiz' varsayıyorum
        # Eğer kodda 'un_analizleri' kullanıyorsan burayı güncelle.
        df_analiz = fetch_data("un_analiz") 
        
        if not df_analiz.empty:
            # Lot numarasına göre ara
            match = df_analiz[df_analiz.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
            
            if not match.empty:
                record = match.iloc[0]
                chain["found"] = True
                
                # Kayıt Tipi Kontrolü
                islem_tipi = str(record.get('islem_tipi', '')).upper()
                
                if "SEVK" in islem_tipi:
                    # Bu bir Sevkiyat Kaydı
                    chain["SHIP"] = record
                    
                    # BAĞLANTI NOKTASI: Sevkiyatın hangi üretimden geldiğini bul
                    # Google Sheets'te 'kaynak_parti_no' sütunu olmalı!
                    kaynak_prd = str(record.get('kaynak_parti_no', ''))
                    if not kaynak_prd or kaynak_prd == 'nan':
                        # Belki 'uretim_lot_no' diye kaydetmişsindir?
                        kaynak_prd = str(record.get('uretim_lot_no', ''))
                    
                    if kaynak_prd and len(kaynak_prd) > 3:
                        # Üretim kaydına git
                        df_uretim = fetch_data("uretim_kaydi")
                        if not df_uretim.empty:
                            u_match = df_uretim[df_uretim['parti_no'] == kaynak_prd]
                            if not u_match.empty: chain["PRD"] = u_match.iloc[0]
                            
                        # Ayrıca o üretimin laboratuvar analizini de bul
                        l_match = df_analiz[df_analiz['lot_no'] == kaynak_prd]
                        if not l_match.empty: chain["LAB"] = l_match.iloc[0]

                else:
                    # Bu bir Üretim Analizi (Lab)
                    chain["LAB"] = record
                    # Doğrudan PRD'ye git (Lot no aynıdır)
                    df_uretim = fetch_data("uretim_kaydi")
                    if not df_uretim.empty:
                        u_match = df_uretim[df_uretim['parti_no'] == record.get('lot_no')]
                        if not u_match.empty: chain["PRD"] = u_match.iloc[0]

    except Exception as e:
        st.error(f"Analiz tablosu okunurken hata: {e}")

    # --- ADIM 2: EĞER ZİNCİR BULUNAMADIYSA DİREKT ÜRETİM/PAÇAL ARA ---
    
    # PRD Arama
    if not chain["found"]:
        try:
            df_uretim = fetch_data("uretim_kaydi")
            if not df_uretim.empty:
                match = df_uretim[df_uretim['parti_no'] == search_query]
                if not match.empty:
                    chain["found"] = True
                    chain["PRD"] = match.iloc[0]
        except: pass

    # MIX Arama
    if not chain["found"]:
        try:
            df_mix = fetch_data("mixing_batches")
            if not df_mix.empty:
                match = df_mix[df_mix['batch_id'] == search_query]
                if not match.empty:
                    chain["found"] = True
                    chain["MIX"] = match.iloc[0]
        except: pass

    # --- ADIM 3: ZİNCİRİ TAMAMLA (PRD -> MIX) ---
    if chain["PRD"] is not None:
        mix_id = str(chain["PRD"].get('mixing_batch_id', '')) # mill.py ile kaydedilen sütun
        
        # Eğer üretim kaydında mix id yoksa, bazen analiz kaydında 'kullanilan_pacal' diye olabilir
        if (not mix_id or mix_id == 'nan') and chain["LAB"] is not None:
             mix_id = str(chain["LAB"].get('kullanilan_pacal', ''))

        if mix_id and mix_id != "BILINMIYOR":
            try:
                df_mix = fetch_data("mixing_batches")
                if not df_mix.empty:
                    m_match = df_mix[df_mix['batch_id'] == mix_id]
                    if not m_match.empty: chain["MIX"] = m_match.iloc[0]
            except: pass

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
    try: 
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return "-"
        return f"{float(val):.{decimals}f}"
    except: return str(val)

def show_traceability_dashboard():
    """KARA KUTU ANA EKRANI"""
    st.markdown("""
    <div style='background-color: #263238; padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>
        <h1 style='margin:0; font-size: 24px;'>🕵️‍♂️ İZLENEBİLİRLİK (KARA KUTU)</h1>
        <p style='color: #cfd8dc; margin-top:5px; font-size: 14px;'>Sevkiyat ➔ Üretim ➔ Paçal ➔ Buğday</p>
    </div>
    """, unsafe_allow_html=True)

    # --- ARAMA MOTORU ---
    col_search, col_btn = st.columns([3, 1])
    with col_search:
        query = st.text_input("🔍 Takip Kodu Giriniz", placeholder="SHIP-..., PRD-..., MIX-...")
    with col_btn:
        st.write("")
        st.write("")
        ara_btn = st.button("🚀 ZİNCİRİ TARA", type="primary", use_container_width=True)

    if ara_btn and query:
        # Cache temizle ki en güncel veriyi görsün (Quota limitine dikkat!)
        st.cache_data.clear()
        
        with st.spinner("Veri tabanı taranıyor..."):
            chain = get_trace_chain(query)
        
        if not chain["found"]:
            st.error("❌ Kayıt bulunamadı.")
            return

        st.success(f"✅ Kayıt Bulundu: {query}")
        
        # 0. HALKA: SEVKİYAT BİLGİSİ (Varsa)
        if chain["SHIP"] is not None:
            ship = chain["SHIP"]
            with st.expander("🚚 0. SEVKİYAT / ÇIKIŞ ANALİZİ", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    render_kvkk_row("Lot No", ship.get('lot_no'))
                    render_kvkk_row("Ürün", ship.get('un_cinsi_marka') or ship.get('un_markasi'))
                    render_kvkk_row("Tarih", str(ship.get('tarih'))[:16])
                with c2:
                    # Analiz Değerleri (SHIP kaydında da analiz var)
                    st.caption("Çıkış Analiz Değerleri")
                    cols = st.columns(3)
                    cols[0].metric("Protein", fmt(ship.get('protein')))
                    cols[1].metric("Kül", fmt(ship.get('kul'), 3))
                    cols[2].metric("Sedim", fmt(ship.get('sedim'), 0))
                
                # Bağlantı Uyarısı
                kaynak = ship.get('kaynak_parti_no') or ship.get('uretim_lot_no')
                if not kaynak or str(kaynak).lower() == 'nan':
                    st.warning("⚠️ Bu sevkiyat kaydında 'Kaynak Parti No' boş olduğu için geriye gidilemiyor.")
                else:
                    st.info(f"🔗 Kaynak Üretim Lotu: {kaynak}")

        # 1. HALKA: ÜRETİM (Mill Data)
        if chain["PRD"] is not None:
            prd = chain["PRD"]
            with st.expander("🏭 1. ÜRETİM VE DEĞİRMEN VERİLERİ", expanded=True):
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

        # 3. HALKA: LABORATUVAR (Üretim Analizi)
        if chain["LAB"] is not None and chain["LAB"].get('lot_no') != chain.get("SHIP", {}).get('lot_no'):
            lab = chain["LAB"]
            with st.expander("🔬 3. ÜRETİM KONTROL ANALİZİ (LAB)", expanded=True):
                st.markdown(f"**Referans:** {lab.get('lot_no')}")
                t1, t2 = st.tabs(["Kimyasal", "Reoloji"])
                with t1:
                    lc1, lc2, lc3 = st.columns(3)
                    lc1.metric("Protein", fmt(lab.get('protein')))
                    lc2.metric("Kül", fmt(lab.get('kul'), 3))
                    lc3.metric("Gluten", fmt(lab.get('gluten')))
                with t2:
                    lc4, lc5, lc6 = st.columns(3)
                    lc4.metric("Enerji", fmt(lab.get('enerji') or lab.get('enerji135'), 0))
                    lc5.metric("Direnç", fmt(lab.get('direnc') or lab.get('direnc135'), 0))
                    lc6.metric("Stabilite", fmt(lab.get('stabilite')))

        # 2. HALKA: PAÇAL (Mix Data)
        if chain["MIX"] is not None:
            mix = chain["MIX"]
            with st.expander("🌾 2. PAÇAL VE HAMMADDE İÇERİĞİ", expanded=True):
                st.info(f"🔗 **Reçete:** `{mix.get('urun_adi')}`")
                
                try:
                    snapshot = json.loads(mix.get('silo_snapshot_json', '{}'))
                    analiz = json.loads(mix.get('analiz_snapshot_json', '{}'))
                    
                    # Paçal Hedefleri
                    k1, k2, k3 = st.columns(3)
                    k_prot = analiz.get('kuru_protein_ort', analiz.get('teorik_kuru_protein', 0))
                    k1.metric("Kuru Protein", fmt(k_prot))
                    k2.metric("Tavlı Protein", fmt(analiz.get('protein', 0)))
                    k3.metric("Maliyet", f"{float(mix.get('maliyet', 0)):.2f} TL")
                    
                    st.divider()
                    st.markdown("**🏗️ Kullanılan Silolar**")
                    
                    rows = []
                    for silo, data in snapshot.items():
                        if isinstance(data, dict):
                            meta = data.get('meta', {})
                            kuru = data.get('kuru_analiz', {})
                            cins = meta.get('cins') or kuru.get('cins') or "-"
                            
                            rows.append({
                                "Silo": silo,
                                "Oran": f"%{data.get('oran', 0)}",
                                "Cins": cins,
                                "Kuru Prot.": fmt(kuru.get('protein', 0)),
                                "Süne": fmt(kuru.get('sune', 0))
                            })
                        else:
                            rows.append({"Silo": silo, "Oran": f"%{data}"})
                            
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Paçal verisi okunamadı: {e}")

        elif chain["PRD"] is not None:
            st.warning("⚠️ Bu üretime bağlı Paçal kaydı bulunamadı.")

    elif ara_btn:
        st.warning("Lütfen kod giriniz.")
