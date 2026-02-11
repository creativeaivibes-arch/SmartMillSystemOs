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
        # Analiz tablosunu çek
        df_analiz = fetch_data("un_analiz") 
        
        if not df_analiz.empty:
            # Lot numarasına göre ara (Büyük/Küçük harf duyarsız)
            match = df_analiz[df_analiz.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
            
            if not match.empty:
                record = match.iloc[0]
                chain["found"] = True
                
                # Kayıt Tipi Kontrolü
                islem_tipi = str(record.get('islem_tipi', '')).upper()
                
                if "SEVK" in islem_tipi:
                    # --- A) SEVKİYAT KAYDI BULUNDU ---
                    chain["SHIP"] = record
                    
                    # Bağlantı Noktası: Kaynak Parti No (Üretime Gidiş)
                    kaynak_prd = str(record.get('kaynak_parti_no', ''))
                    if not kaynak_prd or kaynak_prd.lower() == 'nan':
                        kaynak_prd = str(record.get('uretim_lot_no', ''))
                    
                    if kaynak_prd and len(kaynak_prd) > 3:
                        # 1. Üretim kaydını bul
                        df_uretim = fetch_data("uretim_kaydi")
                        if not df_uretim.empty:
                            u_match = df_uretim[df_uretim['parti_no'] == kaynak_prd]
                            if not u_match.empty: chain["PRD"] = u_match.iloc[0]
                            
                        # 2. O üretimin laboratuvar (kontrol) analizini bul
                        l_match = df_analiz[df_analiz['lot_no'] == kaynak_prd]
                        if not l_match.empty: chain["LAB"] = l_match.iloc[0]

                else:
                    # --- B) ÜRETİM/LAB KAYDI BULUNDU ---
                    chain["LAB"] = record
                    
                    # Doğrudan PRD'ye git (Lot no aynıdır)
                    df_uretim = fetch_data("uretim_kaydi")
                    if not df_uretim.empty:
                        u_match = df_uretim[df_uretim['parti_no'] == record.get('lot_no')]
                        if not u_match.empty: chain["PRD"] = u_match.iloc[0]

    except Exception as e:
        st.error(f"Analiz tablosu okunurken hata: {e}")

    # --- ADIM 2: EĞER HALA BULUNAMADIYSA DİREKT ÜRETİM/PAÇAL ARA ---
    
    # PRD Arama (Eğer analizde yoksa)
    if not chain["found"]:
        try:
            df_uretim = fetch_data("uretim_kaydi")
            if not df_uretim.empty:
                match = df_uretim[df_uretim['parti_no'] == search_query]
                if not match.empty:
                    chain["found"] = True
                    chain["PRD"] = match.iloc[0]
        except: pass

    # MIX Arama (Eğer üretimde de yoksa)
    if not chain["found"]:
        try:
            df_mix = fetch_data("mixing_batches")
            if not df_mix.empty:
                match = df_mix[df_mix['batch_id'] == search_query]
                if not match.empty:
                    chain["found"] = True
                    chain["MIX"] = match.iloc[0]
        except: pass

    # --- ADIM 3: ZİNCİRİ TAMAMLA (PRD -> MIX BAĞLANTISI) [GÜNCELLENDİ] ---
    if chain["PRD"] is not None:
        mix_id = ""
        
        # 1. Öncelik: 'mixing_batch_id' sütunu
        val1 = str(chain["PRD"].get('mixing_batch_id', ''))
        if val1 and val1.lower() not in ['nan', 'none', '']:
            mix_id = val1
            
        # 2. Öncelik: 'kullanilan_pacal' sütunu (PRD tablosunda) - SENİN SORUNUNU ÇÖZEN KISIM
        if not mix_id:
            val2 = str(chain["PRD"].get('kullanilan_pacal', ''))
            if val2 and val2.lower() not in ['nan', 'none', '']:
                mix_id = val2
        
        # 3. Öncelik: Lab kaydındaki 'kullanilan_pacal'
        if not mix_id and chain["LAB"] is not None:
             val3 = str(chain["LAB"].get('kullanilan_pacal', ''))
             if val3 and val3.lower() not in ['nan', 'none', '']:
                mix_id = val3

        # Eğer geçerli bir ID bulduysak Paçal tablosunu tara
        if mix_id and mix_id != "BILINMIYOR":
            try:
                df_mix = fetch_data("mixing_batches")
                if not df_mix.empty:
                    # Tam eşleşme ara
                    m_match = df_mix[df_mix['batch_id'] == mix_id]
                    if not m_match.empty: 
                        chain["MIX"] = m_match.iloc[0]
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
    """Sayı formatlama yardımcısı"""
    try: 
        if pd.isna(val) or val == "" or str(val).lower() == "nan": return "-"
        return f"{float(val):.{decimals}f}"
    except: return str(val)

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
        query = st.text_input("🔍 Takip Kodu Giriniz", placeholder="SHIP-..., PRD-..., MIX-...")
    with col_btn:
        st.write("")
        st.write("")
        ara_btn = st.button("🚀 ZİNCİRİ TARA", type="primary", use_container_width=True)

    if ara_btn and query:
        # Cache temizle ki en güncel veriyi görsün
        st.cache_data.clear()
        
        with st.spinner("Veri tabanı taranıyor..."):
            chain = get_trace_chain(query)
        
        if not chain["found"]:
            st.error("❌ Kayıt bulunamadı.")
            return

        st.success(f"✅ Kayıt Bulundu: {query}")
        
        # ======================================================================
        # 0. HALKA: SEVKİYAT BİLGİSİ (SHIP)
        # ======================================================================
        if chain["SHIP"] is not None:
            ship = chain["SHIP"]
            with st.expander("🚚 0. SEVKİYAT / ÇIKIŞ ANALİZİ", expanded=True):
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
        # 1. HALKA: ÜRETİM (Mill Data)
        # ======================================================================
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
                    render_kvkk_row("Bongalite", f"{float(prd.get('bongalite',0)):,.0f}", "Kg")
                    
                    kayip = float(prd.get('kayip', 0))
                    render_kvkk_row("Kayıp Oranı", f"{kayip:.2f}", "%", "red" if kayip > 2 else "black")

        # ======================================================================
        # 3. HALKA: LABORATUVAR (Üretim Kontrolü)
        # ======================================================================
        if chain["LAB"] is not None:
            ship_lot = chain.get("SHIP", {}).get('lot_no') if chain.get("SHIP") is not None else ""
            lab_lot = chain["LAB"].get('lot_no')
            
            # Eğer sevkiyat analiziyle aynı değilse göster
            if ship_lot != lab_lot:
                lab = chain["LAB"]
                with st.expander("🔬 3. ÜRETİM KONTROL ANALİZİ (LAB)", expanded=True):
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
        # 2. HALKA: PAÇAL (Mix Data)
        # ======================================================================
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
            st.warning("⚠️ Bu üretime bağlı Paçal kaydı bulunamadı (Mix ID eksik veya eşleşmiyor).")

    elif ara_btn:
        st.warning("Lütfen kod giriniz.")
