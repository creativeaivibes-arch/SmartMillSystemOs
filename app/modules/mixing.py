import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
import io
import uuid

# --- DATABASE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn
from app.core.utils import turkce_karakter_duzelt

# KURU BUĞDAY VERİSİNİ ÇEKMEK İÇİN
try:
    from app.modules.wheat import get_kuru_bugday_agirlikli_ortalama
except ImportError:
    def get_kuru_bugday_agirlikli_ortalama(silo_isim): return {}

# RAPORLAMA
try:
    from app.modules.reports import create_pacal_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    def create_pacal_pdf_report(*args, **kwargs): return None
    def turkce_karakter_duzelt_pdf(text): return text

# --- YARDIMCI FONKSİYONLAR ---

def get_silo_data_fresh():
    """Silo verilerini TAZE çeker (Anlık Cins ve Kuru Değerler İçin)"""
    try:
        df = fetch_data("silolar", force_refresh=True)
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])

        df = df.fillna({
            'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
            'sedim': 0, 'maliyet': 0, 'bugday_cinsi': '-', 'mevcut_miktar': 0, 'kapasite': 100
        })
        
        if 'isim' in df.columns:
            df = df.sort_values('isim')

        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_pacal_history():
    try:
        df = fetch_data("mixing_batches") 
        if df.empty: return pd.DataFrame()
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'])
            df = df.sort_values('tarih', ascending=False)
        return df
    except Exception as e:
        return pd.DataFrame()
        
def get_tavli_analiz_agirlikli_ortalama(silo_isim):
    """Silo için tüm tavlı analizlerin tonaj ağırlıklı ortalamasını hesapla"""
    try:
        df = fetch_data("tavli_analiz")
        if df.empty: return None
            
        df = df[df['silo_isim'] == silo_isim]
        if df.empty: return None
        
        # Tüm parametreleri kapsayacak liste
        analiz_parametreleri = [
            'protein', 'rutubet', 'gluten', 'gluten_index',
            'sedim', 'g_sedim', 'fn', 'ffn', 'amilograph', 'kul',
            'su_kaldirma_f', 'gelisme_suresi', 'stabilite', 'yumusama',
            'su_kaldirma_e', 'enerji45', 'direnc45', 'taban45',
            'enerji90', 'direnc90', 'taban90', 'enerji135',
            'direnc135', 'taban135'
        ]
        
        df['analiz_tonaj'] = pd.to_numeric(df['analiz_tonaj'], errors='coerce').fillna(0)
        toplam_tonaj = df['analiz_tonaj'].sum()
        
        if toplam_tonaj <= 0: return None
        
        agirlikli_ortalama = {}
        for param in analiz_parametreleri:
            if param in df.columns:
                df[param] = pd.to_numeric(df[param], errors='coerce').fillna(0)
                try:
                    val = (df['analiz_tonaj'] * df[param]).sum() / toplam_tonaj
                    agirlikli_ortalama[param] = float(val)
                except:
                    agirlikli_ortalama[param] = 0.0
            else:
                agirlikli_ortalama[param] = 0.0
        
        agirlikli_ortalama['toplam_tonaj'] = float(toplam_tonaj)
        agirlikli_ortalama['analiz_sayisi'] = len(df)
        return agirlikli_ortalama
        
    except Exception as e:
        return None

def calculate_pacal_metrics(oranlar, tavli_analizler):
    """Paçal oranlarına göre beklenen TAVLI analiz değerlerini hesaplar."""
    # Varsayılan boş yapı (Tüm anahtarlar 0.0)
    analiz_sonuclari = {
        'protein': 0.0, 'rutubet': 0.0, 'gluten': 0.0, 'gluten_index': 0.0,
        'sedim': 0.0, 'g_sedim': 0.0, 'fn': 0.0, 'ffn': 0.0, 
        'amilograph': 0.0, 'kul': 0.0,
        'su_kaldirma_f': 0.0, 'gelisme_suresi': 0.0, 'stabilite': 0.0, 'yumusama': 0.0,
        'su_kaldirma_e': 0.0, 'enerji45': 0.0, 'direnc45': 0.0, 'taban45': 0.0,
        'enerji90': 0.0, 'direnc90': 0.0, 'taban90': 0.0, 'enerji135': 0.0,
        'direnc135': 0.0, 'taban135': 0.0
    }
    
    analiz_var_mi = False
    
    for isim, oran in oranlar.items():
        if oran > 0 and isim in tavli_analizler:
            analiz_var_mi = True
            analiz_data = tavli_analizler[isim]
            katsayi = oran / 100.0
            
            for param in analiz_sonuclari.keys():
                # Veri varsa ağırlıklı ortalamaya ekle
                val = float(analiz_data.get(param, 0) or 0)
                analiz_sonuclari[param] += val * katsayi
    
    return analiz_sonuclari if analiz_var_mi else None

# ==============================================================================
# MODÜL 1: PAÇAL HESAPLAYICI VE KAYITÇI
# ==============================================================================
def show_pacal_hesaplayici():
    """Paçal Hesaplayıcı"""
    
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📊 Paçal Hesaplayıcı")
    
    # 1. Silo Verilerini Çek (TAZE)
    df = get_silo_data_fresh()
    if df.empty:
        st.warning("Silo verisi bulunamadı!")
        return
    
    dolu_silolar = df[df['mevcut_miktar'] > 0].copy()
    if dolu_silolar.empty:
        st.warning("⚠️ Paçal yapmak için dolu silo bulunmamaktadır!")
        return
    
    st.info(f"✅ {len(dolu_silolar)} adet dolu silo bulundu.")
    
    col_input, col_result = st.columns([1, 1.2], gap="medium")
    oranlar = {}
    toplam_oran = 0.0
    
    tavli_analizler = {}
    analiz_durumlari = {}
    
    # 2. Analiz Verilerini Hazırla
    with st.spinner("Analiz verileri hazırlanıyor..."):
        for index, row in dolu_silolar.iterrows():
            analiz = get_tavli_analiz_agirlikli_ortalama(row['isim'])
            if analiz and analiz['toplam_tonaj'] > 0:
                tavli_analizler[row['isim']] = analiz
                analiz_durumlari[row['isim']] = {'var': True, 'sayi': analiz['analiz_sayisi']}
            else:
                analiz_durumlari[row['isim']] = {'var': False}
    
    # --- SOL: GİRİŞ ---
    with col_input:
        st.subheader("🧩 Silo Oranları")
        for index, row in dolu_silolar.iterrows():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{row['isim']}**")
                cins = str(row.get('bugday_cinsi', '-'))
                st.caption(f"Cins: {cins}")
                if analiz_durumlari.get(row['isim'], {}).get('var'):
                    st.success("✅ Tavlı Verisi Var", icon="✅")
                else:
                    st.warning("⚠️ Tavlı Verisi Yok", icon="⚠️")
            with c2:
                val = st.number_input(f"%", 0.0, 100.0, 0.0, 0.1, key=f"oran_{index}", label_visibility="collapsed")
                oranlar[row['isim']] = val
                toplam_oran += val
        
        st.metric("Toplam", f"%{toplam_oran:.1f}")
        if toplam_oran != 100: st.warning("Toplam %100 olmalı.")

    # --- SAĞ: SONUÇLAR ---
    with col_result:
        st.subheader("📈 Tahmini Paçal Sonuçları")
        
        if toplam_oran > 0:
            pacal_maliyeti = 0.0
            kuru_ozet = {'protein': 0.0, 'rutubet': 0.0, 'gluten': 0.0}
            
            for isim, oran in oranlar.items():
                if oran > 0:
                    silo_row = dolu_silolar[dolu_silolar['isim'] == isim].iloc[0]
                    katsayi = oran / 100.0
                    
                    # Maliyet
                    pacal_maliyeti += float(silo_row.get('maliyet', 0)) * katsayi
                    
                    # Kuru Veri Çekme (HİBRİT YÖNTEM: Önce Hareketlerden, Yoksa Karttan)
                    kuru_data = get_kuru_bugday_agirlikli_ortalama(isim)
                    
                    # Kuru Protein
                    kp = float(kuru_data.get('protein', 0) or 0)
                    if kp == 0: kp = float(silo_row.get('protein', 0) or 0) # Yedek
                    kuru_ozet['protein'] += kp * katsayi
                    
                    # Kuru Rutubet
                    kr = float(kuru_data.get('rutubet', 0) or 0)
                    if kr == 0: kr = float(silo_row.get('rutubet', 0) or 0) # Yedek
                    kuru_ozet['rutubet'] += kr * katsayi

            # Tavlı Hesaplama
            tavli_sonuc = calculate_pacal_metrics(oranlar, tavli_analizler)
            
            if toplam_oran == 100:
                with st.container(border=True):
                    # ÖZET KARTLAR
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Ort. Maliyet", f"{pacal_maliyeti:.2f} TL")
                    k2.metric("Kuru Protein", f"{kuru_ozet['protein']:.1f}")
                    k3.metric("Kuru Rutubet", f"{kuru_ozet['rutubet']:.1f}")
                    
                    if tavli_sonuc:
                        st.divider()
                        st.markdown("**🔬 Detaylı Paçal Ortalamaları**")
                        
                        tt1, tt2, tt3 = st.tabs(["Kimyasal", "Farino", "Extenso"])
                        
                        with tt1:
                            c1, c2 = st.columns(2)
                            c1.metric("Tavlı Protein", f"{tavli_sonuc.get('protein',0):.1f}")
                            c1.metric("Gluten", f"{tavli_sonuc.get('gluten',0):.1f}")
                            c2.metric("Sedim", f"{tavli_sonuc.get('sedim',0):.0f}")
                            c2.metric("G. İndeks", f"{tavli_sonuc.get('gluten_index',0):.0f}")
                            st.caption(f"FN: {tavli_sonuc.get('fn',0):.0f} | FFN: {tavli_sonuc.get('ffn',0):.0f}")
                            
                        with tt2:
                            c1, c2 = st.columns(2)
                            c1.metric("Su Kal. (F)", f"{tavli_sonuc.get('su_kaldirma_f',0):.1f}")
                            c1.metric("Stabilite", f"{tavli_sonuc.get('stabilite',0):.1f}")
                            c2.metric("Gelişme", f"{tavli_sonuc.get('gelisme_suresi',0):.1f}")
                            c2.metric("Yumuşama", f"{tavli_sonuc.get('yumusama',0):.0f}")
                            
                        with tt3:
                            c1, c2 = st.columns(2)
                            c1.metric("Enerji (135)", f"{tavli_sonuc.get('enerji135',0):.0f}")
                            c2.metric("Direnç (135)", f"{tavli_sonuc.get('direnc135',0):.0f}")
                            st.caption(f"Taban (135): {tavli_sonuc.get('taban135',0):.0f}")

                # --- KAYIT ---
                st.divider()
                urun_adi = st.text_input("Reçete Adı", placeholder="Lüks Ekmeklik vb.")
                
                if st.button("💾 PAÇALI KAYDET", type="primary", use_container_width=True):
                    if urun_adi:
                        try:
                            # ID Oluştur
                            batch_id = f"MIX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
                            
                            # Snapshot Hazırla
                            silo_snapshot = {}
                            for s, o in oranlar.items():
                                if o > 0:
                                    # Verileri Garantiye Al
                                    raw = dolu_silolar[dolu_silolar['isim'] == s].iloc[0]
                                    k_analiz = get_kuru_bugday_agirlikli_ortalama(s)
                                    t_analiz = tavli_analizler.get(s, {})
                                    
                                    # Cins Bilgisi (Yedekli)
                                    cins = str(raw.get('bugday_cinsi', ''))
                                    if not cins or cins == 'nan': cins = "-"
                                    
                                    silo_snapshot[s] = {
                                        "oran": o,
                                        "meta": { "cins": cins, "maliyet": float(raw.get('maliyet', 0)) },
                                        "kuru_analiz": k_analiz,
                                        "tavli_analiz": t_analiz
                                    }
                            
                            # Sonuçları Hazırla (Tüm Detayları İçeren JSON)
                            final_analiz = tavli_sonuc.copy() if tavli_sonuc else {}
                            final_analiz.update({
                                "kuru_protein_ort": kuru_ozet['protein'],
                                "kuru_rutubet_ort": kuru_ozet['rutubet']
                            })
                            
                            # Kaydet
                            data = {
                                "batch_id": batch_id,
                                "tarih": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "operator": st.session_state.get('username', 'Sistem'),
                                "urun_adi": urun_adi,
                                "silo_snapshot_json": json.dumps(silo_snapshot, ensure_ascii=False),
                                "analiz_snapshot_json": json.dumps(final_analiz, ensure_ascii=False),
                                "maliyet": pacal_maliyeti
                            }
                            
                            if add_data("mixing_batches", data):
                                st.cache_data.clear()
                                st.success(f"✅ Kaydedildi! ID: {batch_id}")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("Veritabanı hatası!")
                        except Exception as e:
                            st.error(f"Hata: {e}")
                    else:
                        st.error("İsim giriniz.")

# ==============================================================================
# MODÜL 2: PAÇAL GEÇMİŞİ (PROFESYONEL GÖRÜNÜM)
# ==============================================================================
def show_pacal_gecmisi():
    """Paçal Geçmişi - İSTENEN DETAYLI GÖRÜNÜM"""
    st.header("📜 Paçal Arşivi (Traceability)")
    
    df = get_pacal_history()
    if df.empty:
        st.info("Kayıt yok.")
        return

    for idx, row in df.iterrows():
        baslik = f"📦 {row.get('urun_adi','-')} | {row.get('tarih','-')} | ID: {row.get('batch_id','?')}"
        
        with st.expander(baslik):
            try:
                snap = json.loads(row.get('silo_snapshot_json', '{}'))
                analiz = json.loads(row.get('analiz_snapshot_json', '{}'))
            except:
                st.error("Veri okunamadı."); continue

            # --- 1. ÜST ÖZET (MALİYET) ---
            st.metric("💰 Ortalama Maliyet", f"{row.get('maliyet', 0):.2f} TL")
            st.divider()

            # --- 2. KULLANILAN SİLOLAR TABLOSU (SADE) ---
            st.markdown("##### 🏗️ Kullanılan Silolar")
            silo_rows = []
            for s, d in snap.items():
                if isinstance(d, dict):
                    # Verileri Güvenli Çek
                    meta = d.get('meta', {})
                    kuru = d.get('kuru_analiz', {})
                    
                    # Cins bulma (Önce meta, sonra kuru analiz, sonra '-')
                    cins = meta.get('cins') or kuru.get('cins') or "-"
                    
                    silo_rows.append({
                        "Silo Adı": s,
                        "Oran": f"%{d.get('oran', 0)}",
                        "Buğday Cinsi": cins
                    })
                else:
                    silo_rows.append({"Silo Adı": s, "Oran": f"%{d}", "Buğday Cinsi": "-"})
            
            st.dataframe(pd.DataFrame(silo_rows), hide_index=True, use_container_width=True)
            
            st.divider()
            
            # --- 3. DETAYLI ANALİZLER (SEKMELİ YAPI) ---
            st.markdown("##### 🧪 Paçal Özeti (Hesaplanan Ortalamalar)")
            
            t1, t2, t3 = st.tabs(["⚗️ Kimyasal Analizler", "📈 Farinograph", "📊 Extensograph"])
            
            # Helper: Değer varsa formatla, yoksa '-'
            def fmt(val, decimals=1):
                try: return f"{float(val):.{decimals}f}"
                except: return "-"

            with t1:
                # Kuru Protein Gösterimi (Özel İstek)
                kuru_prot = analiz.get('kuru_protein_ort', analiz.get('teorik_kuru_protein', 0))
                
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Protein (Ort):** {fmt(analiz.get('protein', 0))}") # Tavlı
                c1.caption(f"*(Kuru Protein Ort: {fmt(kuru_prot)})*") # Kuru detay
                
                c2.markdown(f"**Rutubet (Ort):** {fmt(analiz.get('rutubet', 0))}")
                c3.markdown(f"**Gluten (Ort):** {fmt(analiz.get('gluten', 0))}")
                
                c4, c5, c6 = st.columns(3)
                c4.markdown(f"**Gluten Index:** {fmt(analiz.get('gluten_index', 0), 0)}")
                c5.markdown(f"**Sedim (Ort):** {fmt(analiz.get('sedim', 0), 0)}")
                c6.markdown(f"**G. Sedim:** {fmt(analiz.get('g_sedim', 0), 0)}")
                
                c7, c8, c9 = st.columns(3)
                c7.markdown(f"**FN (Ort):** {fmt(analiz.get('fn', 0), 0)}")
                c8.markdown(f"**FFN (Ort):** {fmt(analiz.get('ffn', 0), 0)}")
                c9.markdown(f"**Amilograph:** {fmt(analiz.get('amilograph', 0), 0)}")

            with t2:
                f1, f2 = st.columns(2)
                f1.markdown(f"**Su Kal. (F):** {fmt(analiz.get('su_kaldirma_f', 0))}")
                f1.markdown(f"**Gelişme Süresi:** {fmt(analiz.get('gelisme_suresi', 0))}")
                
                f2.markdown(f"**Stabilite:** {fmt(analiz.get('stabilite', 0))}")
                f2.markdown(f"**Yumuşama:** {fmt(analiz.get('yumusama', 0), 0)}")

            with t3:
                st.markdown(f"**Su Kaldırma (E):** {fmt(analiz.get('su_kaldirma_e', 0))}")
                st.markdown("---")
                
                ec1, ec2, ec3 = st.columns(3)
                ec1.caption("45. Dakika")
                ec1.markdown(f"Direnç: {fmt(analiz.get('direnc45', 0), 0)}")
                ec1.markdown(f"Taban: {fmt(analiz.get('taban45', 0), 0)}")
                ec1.markdown(f"Enerji: {fmt(analiz.get('enerji45', 0), 0)}")
                
                ec2.caption("90. Dakika")
                ec2.markdown(f"Direnç: {fmt(analiz.get('direnc90', 0), 0)}")
                ec2.markdown(f"Taban: {fmt(analiz.get('taban90', 0), 0)}")
                ec2.markdown(f"Enerji: {fmt(analiz.get('enerji90', 0), 0)}")
                
                ec3.caption("135. Dakika")
                ec3.markdown(f"Direnç: {fmt(analiz.get('direnc135', 0), 0)}")
                ec3.markdown(f"Taban: {fmt(analiz.get('taban135', 0), 0)}")
                ec3.markdown(f"Enerji: {fmt(analiz.get('enerji135', 0), 0)}")
