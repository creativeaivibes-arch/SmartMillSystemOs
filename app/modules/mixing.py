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

# KURU BUĞDAY VERİSİNİ ÇEKMEK İÇİN (Hata önleyici import)
try:
    from app.modules.wheat import get_kuru_bugday_agirlikli_ortalama
except ImportError:
    # Eğer wheat modülü yüklenemezse boş dict dönen dummy fonksiyon
    def get_kuru_bugday_agirlikli_ortalama(silo_isim): return {}

# Rapor modülü yoksa hata vermemesi için try-except bloğu
try:
    from app.modules.reports import create_pacal_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    def create_pacal_pdf_report(*args, **kwargs): return None
    def turkce_karakter_duzelt_pdf(text): return text

# --- CACHE VE DATA FONKSİYONLARI ---
@st.cache_data(ttl=300) 
def get_silo_data():
    """Silo verilerini getir"""
    try:
        df = fetch_data("silolar")
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])

        df = df.fillna({
            'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
            'sedim': 0, 'maliyet': 0, 'bugday_cinsi': '', 'mevcut_miktar': 0, 'kapasite': 100
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
        
        # Analiz parametreleri
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
                if param in analiz_data:
                    try:
                        analiz_sonuclari[param] += float(analiz_data[param]) * katsayi
                    except: pass
    
    return analiz_sonuclari if analiz_var_mi else None

# ==============================================================================
# MODÜL 1: PAÇAL HESAPLAYICI VE KAYITÇI
# ==============================================================================
def show_pacal_hesaplayici():
    """Paçal Hesaplayıcı - TAM SNAPSHOT ÖZELLİKLİ"""
    
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📊 Paçal Hesaplayıcı")
    
    # 1. Silo Verilerini Çek
    df = get_silo_data()
    if df.empty:
        st.warning("Silo verisi bulunamadı!")
        return
    
    # Dolu siloları filtrele
    dolu_silolar = df[df['mevcut_miktar'] > 0].copy()
    if dolu_silolar.empty:
        st.warning("⚠️ Paçal yapmak için dolu silo bulunmamaktadır!")
        return
    
    st.info(f"✅ {len(dolu_silolar)} adet dolu silo bulundu.")
    
    col_input, col_result = st.columns([1, 1], gap="medium")
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
    
    # 3. Sol Kolon: Oran Girişi
    with col_input:
        st.subheader("🧩 Silo Kullanım Oranları (%)")
        
        for index, row in dolu_silolar.iterrows():
            col_label, col_input_box = st.columns([3, 1])
            
            with col_label:
                st.write(f"**{row['isim']}**")
                # Silo kartından temel bilgileri göster
                bugday_cinsi = str(row.get('bugday_cinsi', '')).strip() or "-"
                maliyet = float(row.get('maliyet', 0)) if pd.notnull(row.get('maliyet')) else 0.0
                
                st.caption(f"Cins: {bugday_cinsi} | Maliyet: {maliyet:.2f} TL/KG")
                
                if analiz_durumlari.get(row['isim'], {}).get('var'):
                    st.success(f"✅ Tavlı Analiz Mevcut")
                else:
                    st.warning("⚠️ Tavlı analiz yok")
            
            with col_input_box:
                oran = st.number_input(
                    "Oran %", min_value=0.0, max_value=100.0, value=0.0, step=0.1,
                    key=f"oran_{row['isim']}_{index}", label_visibility="collapsed"
                )
                oranlar[row['isim']] = float(oran)
                toplam_oran += float(oran)
        
        st.metric("Toplam Oran", f"%{toplam_oran:.1f}")
        if toplam_oran != 100:
            st.warning(f"Toplam %100 olmalı. Şu an: %{toplam_oran:.1f}")
    
    # 4. Sağ Kolon: Sonuçlar ve Kayıt
    with col_result:
        st.subheader("📈 Tahmini Sonuçlar")
        
        if toplam_oran > 0:
            # A) Kuru Paçal Ortalamaları (Hektolitre, Protein, Maliyet)
            pacal_maliyeti = 0.0
            kuru_pacal_ozet = {'protein': 0.0, 'gluten': 0.0, 'hektolitre': 0.0}
            
            for isim, oran in oranlar.items():
                if oran > 0:
                    # Silonun o anki KURU ortalamasını çek
                    kuru_analiz = get_kuru_bugday_agirlikli_ortalama(isim)
                    silo_row = dolu_silolar[dolu_silolar['isim'] == isim].iloc[0]
                    katsayi = oran / 100.0
                    
                    # Maliyet
                    maliyet = float(silo_row.get('maliyet', 0))
                    pacal_maliyeti += maliyet * katsayi
                    
                    # Kuru Veriler (Yoksa 0 kabul et)
                    kuru_pacal_ozet['protein'] += float(kuru_analiz.get('protein', 0) or 0) * katsayi
                    kuru_pacal_ozet['gluten'] += float(kuru_analiz.get('gluten', 0) or 0) * katsayi
                    kuru_pacal_ozet['hektolitre'] += float(kuru_analiz.get('hektolitre', 0) or 0) * katsayi
            
            # B) Tavlı Paçal Ortalamaları
            tavli_sonuc = calculate_pacal_metrics(oranlar, tavli_analizler)
            
            if toplam_oran == 100:
                # GÖSTERGELER (DASHBOARD)
                with st.container(border=True):
                    st.markdown("##### 🔬 Paçal Özeti")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Kuru Protein", f"{kuru_pacal_ozet['protein']:.1f}")
                    c1.metric("Kuru Hektolitre", f"{kuru_pacal_ozet['hektolitre']:.1f}")
                    
                    c2.metric("Tavlı Protein", f"{tavli_sonuc.get('protein', 0):.1f}" if tavli_sonuc else "-")
                    c2.metric("Tavlı Gluten", f"{tavli_sonuc.get('gluten', 0):.1f}" if tavli_sonuc else "-")
                    
                    c3.metric("Tahmini Maliyet", f"{pacal_maliyeti:.2f} TL")
                    c3.metric("Tavlı Enerji", f"{tavli_sonuc.get('enerji135', 0):.0f}" if tavli_sonuc else "-")

                st.divider()
                
                # --- KAYIT BÖLÜMÜ (KRİTİK SNAPSHOT NOKTASI) ---
                st.success("✅ Reçete Kayda Hazır")
                urun_adi = st.text_input("Reçete Adı (Örn: Lüks Ekmeklik)", placeholder="Üretilecek Un Cinsini Yazınız")
                
                if st.button("💾 PAÇALI KAYDET (TRACEABILITY)", type="primary", use_container_width=True):
                    if not urun_adi:
                        st.error("Lütfen reçete adı giriniz.")
                    else:
                        try:
                            # 1. Kimlik Oluştur
                            date_str = datetime.now().strftime('%Y%m%d')
                            unique_suffix = str(uuid.uuid4())[:4].upper()
                            batch_id = f"MIX-{date_str}-{unique_suffix}"
                            
                            # 2. SİLO SNAPSHOT AL (Düzeltilen Kısım)
                            silo_snapshot = {}
                            for s_isim, s_oran in oranlar.items():
                                if s_oran > 0:
                                    # Silo ana verisini bul (Maliyet ve Cins için)
                                    raw_silo = dolu_silolar[dolu_silolar['isim'] == s_isim].iloc[0]
                                    
                                    # Kuru Analiz Ortalamasını Çek (wheat.py'den)
                                    kuru_analiz = get_kuru_bugday_agirlikli_ortalama(s_isim)
                                    
                                    # Tavlı Analiz Verisini Al
                                    tavli_analiz = tavli_analizler.get(s_isim, {})
                                    
                                    # Hepsini paketle
                                    silo_snapshot[s_isim] = {
                                        "oran": s_oran,
                                        "meta": {
                                            # Cins ve Maliyeti buraya sabitliyoruz
                                            "cins": str(raw_silo.get('bugday_cinsi', '-')), 
                                            "maliyet": float(raw_silo.get('maliyet', 0))
                                        },
                                        "kuru_analiz": kuru_analiz,
                                        "tavli_analiz": tavli_analiz
                                    }
                            
                            # 3. Paçal Sonuçlarını Paketle
                            final_analiz_ozet = tavli_sonuc.copy() if tavli_sonuc else {}
                            final_analiz_ozet.update({
                                "kuru_protein_ort": kuru_pacal_ozet['protein'],
                                "kuru_gluten_ort": kuru_pacal_ozet['gluten'],
                                "kuru_hektolitre_ort": kuru_pacal_ozet['hektolitre']
                            })
                            
                            # 4. Veritabanına Yaz
                            kayit_verisi = {
                                "batch_id": batch_id,
                                "tarih": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "operator": st.session_state.get('username', 'Unknown'),
                                "urun_adi": urun_adi.strip(),
                                "silo_snapshot_json": json.dumps(silo_snapshot, ensure_ascii=False),
                                "analiz_snapshot_json": json.dumps(final_analiz_ozet, ensure_ascii=False),
                                "maliyet": pacal_maliyeti
                            }
                            
                            if add_data("mixing_batches", kayit_verisi):
                                st.cache_data.clear()
                                st.success(f"✅ Paçal Kaydedildi! ID: {batch_id}")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("Kayıt veritabanı hatası.")
                                
                        except Exception as e:
                            st.error(f"Kayıt Hatası: {e}")
            else:
                st.info("ℹ️ Toplam oranı %100 yapınız.")
        else:
            st.info("👈 Soldan oranları giriniz.")

# ==============================================================================
# MODÜL 2: PAÇAL GEÇMİŞİ (ZENGİN ÖZET GÖRÜNÜMÜ)
# ==============================================================================
def show_pacal_gecmisi():
    """Paçal Geçmişi - Zengin Özet ve Traceability Bağlantısı"""
    st.header("📜 Paçal Arşivi (Traceability)")
    
    df = get_pacal_history()
    
    if df.empty:
        st.info("📭 Henüz kayıtlı paçal bulunmamaktadır.")
        return

    for idx, row in df.iterrows():
        # Kart Başlığı
        baslik = f"📦 {row.get('urun_adi','-')} | {row.get('tarih','-')} | ID: {row.get('batch_id','?')}"
        
        with st.expander(baslik):
            # JSON verilerini çözümle
            try:
                snapshot = json.loads(row.get('silo_snapshot_json', '{}'))
                analiz = json.loads(row.get('analiz_snapshot_json', '{}'))
            except:
                st.error("Veri paketi bozuk.")
                continue

            # 1. BÖLÜM: PAÇAL ÖZETİ (HEDEF KALİTE)
            st.markdown("#### 🧪 Paçal Özeti (Hesaplanan Ortalamalar)")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            # Kuru Değerler
            k_prot = analiz.get('kuru_protein_ort', analiz.get('teorik_kuru_protein', 0))
            k_hl = analiz.get('kuru_hektolitre_ort', 0)
            
            # Tavlı Değerler
            t_prot = analiz.get('protein', 0)
            t_stab = analiz.get('stabilite', 0)
            t_enerji = analiz.get('enerji135', 0)
            
            kpi1.metric("Kuru Protein", f"{k_prot:.1f}")
            kpi2.metric("Tavlı Protein", f"{t_prot:.1f}")
            kpi3.metric("Tavlı Enerji (135)", f"{t_enerji:.0f}")
            kpi4.metric("Ort. Maliyet", f"{row.get('maliyet',0):.2f} TL")
            
            st.divider()
            
            # 2. BÖLÜM: KULLANILAN SİLOLAR (TABLO)
            st.markdown("#### 🏗️ Kullanılan Silolar (Reçete)")
            
            silo_listesi = []
            for silo_adi, data in snapshot.items():
                if isinstance(data, dict):
                    # VERİ AYIKLAMA (Düzeltilen Kısım)
                    meta = data.get('meta', {})
                    kuru = data.get('kuru_analiz', {})
                    
                    # 1. Cinsi bul (Önce meta'ya bak, yoksa kuru analize bak)
                    cins = meta.get('cins', kuru.get('cins', '-'))
                    if not cins: cins = "-"
                    
                    # 2. Maliyeti bul
                    maliyet = meta.get('maliyet', kuru.get('maliyet', 0))
                    
                    # 3. Kuru Proteini bul
                    k_prot_silo = kuru.get('protein', 0)
                    
                    silo_listesi.append({
                        "Silo Adı": silo_adi,
                        "Oran": f"%{data.get('oran', 0)}",
                        "Buğday Cinsi": cins,
                        "Kuru Protein": f"{k_prot_silo:.1f}",
                        "Maliyet": f"{maliyet:.2f} TL"
                    })
                else:
                    # Eski versiyon kayıtlar için (Hata vermesin)
                    silo_listesi.append({"Silo Adı": silo_adi, "Oran": f"%{data}", "Buğday Cinsi": "-", "Kuru Protein": "-", "Maliyet": "-"})
            
            st.dataframe(pd.DataFrame(silo_listesi), hide_index=True, use_container_width=True)
            
            # 3. BÖLÜM: DETAY (KARA KUTU YÖNLENDİRMESİ)
            st.info(f"ℹ️ Bu paçalı oluşturan siloların detaylı Farinograph, Extensograph ve Süne analizleri **Traceability (Kara Kutu)** modülünde `{row.get('batch_id')}` kodu ile saklanmaktadır.")
