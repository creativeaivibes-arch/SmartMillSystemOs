import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
import io
import uuid

# ESKİ IMPORTLAR KALDIRILDI, YENİLERİ EKLENDİ
from app.core.database import fetch_data, add_data, get_conn
from app.core.utils import turkce_karakter_duzelt

# HATAYI GİDERMEK İÇİN DASHBOARD IMPORT'U KALDIRILDI
# from app.modules.dashboard import get_silo_data 

# Rapor modülü yoksa hata vermemesi için try-except bloğu
try:
    from app.modules.reports import create_pacal_pdf_report, turkce_karakter_duzelt_pdf
except ImportError:
    def create_pacal_pdf_report(*args, **kwargs): return None
    def turkce_karakter_duzelt_pdf(text): return text

# --- YENİ EKLENEN FONKSİYON (BAĞIMLILIĞI KALDIRMAK İÇİN) ---
@st.cache_data(ttl=300) 
def get_silo_data():
    """Silo verilerini getir (Dashboard'dan bağımsız çalışması için buraya eklendi)"""
    try:
        df = fetch_data("silolar")
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])

        # NaN temizliği ve Tip Dönüşümü
        df = df.fillna({
            'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
            'sedim': 0, 'maliyet': 0, 'bugday_cinsi': '', 'mevcut_miktar': 0, 'kapasite': 100
        })
        
        if 'isim' in df.columns:
            df = df.sort_values('isim')

        return df
    except Exception as e:
        st.error(f"Silo verisi çekme hatası: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_pacal_history():
    try:
        # Traceability için yeni tabloya geçtik
        df = fetch_data("mixing_batches") 
        
        if df.empty:
            return pd.DataFrame()
            
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'])
            df = df.sort_values('tarih', ascending=False)
            
        return df
    except Exception as e:
        st.error(f"⚠️ Geçmiş yüklenirken hata: {str(e)}")
        return pd.DataFrame()
        
def get_tavli_analiz_agirlikli_ortalama(silo_isim):
    """Silo için tüm tavlı analizlerin tonaj ağırlıklı ortalamasını hesapla - GOOGLE SHEETS UYUMLU"""
    try:
        # 1. Tüm analizleri çek
        df = fetch_data("tavli_analiz")
        
        if df.empty:
            return None
            
        # 2. İlgili siloya göre filtrele (Pandas Filter)
        df = df[df['silo_isim'] == silo_isim]
        
        if df.empty:
            return None
        
        # Analiz parametreleri listesi
        analiz_parametreleri = [
            'protein', 'rutubet', 'gluten', 'gluten_index',
            'sedim', 'g_sedim', 'fn', 'ffn', 'amilograph', 'kul',
            'su_kaldirma_f', 'gelisme_suresi', 'stabilite', 'yumusama',
            'su_kaldirma_e', 'enerji45', 'direnc45', 'taban45',
            'enerji90', 'direnc90', 'taban90', 'enerji135',
            'direnc135', 'taban135'
        ]
        
        # Sayısal değerlere çevir
        df['analiz_tonaj'] = pd.to_numeric(df['analiz_tonaj'], errors='coerce').fillna(0)
        
        # Toplam tonaj
        toplam_tonaj = df['analiz_tonaj'].sum()
        
        if toplam_tonaj <= 0:
            return None
        
        # Ağırlıklı ortalamaları hesapla
        agirlikli_ortalama = {}
        
        for param in analiz_parametreleri:
            if param in df.columns:
                # NaN değerleri 0 olarak değerlendir
                df[param] = pd.to_numeric(df[param], errors='coerce').fillna(0)
                
                # Ağırlıklı ortalama hesapla: Σ(tonaj * değer) / Σ(tonaj)
                try:
                    agirlikli_deger = (df['analiz_tonaj'] * df[param]).sum() / toplam_tonaj
                    agirlikli_ortalama[param] = float(agirlikli_deger)
                except:
                    agirlikli_ortalama[param] = 0.0
            else:
                agirlikli_ortalama[param] = 0.0
        
        # Toplam tonajı da ekle
        agirlikli_ortalama['toplam_tonaj'] = float(toplam_tonaj)
        agirlikli_ortalama['analiz_sayisi'] = len(df)
        
        return agirlikli_ortalama
        
    except Exception as e:
        st.error(f"Ağırlıklı ortalama hesaplama hatası ({silo_isim}): {str(e)}")
        return None

def calculate_pacal_metrics(oranlar, tavli_analizler):
    """Paçal oranlarına göre beklenen analiz değerlerini hesaplar."""
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
        if oran > 0:
            if isim in tavli_analizler:
                analiz_var_mi = True
                analiz_data = tavli_analizler[isim]
                katsayi = oran / 100.0
                
                for param in analiz_sonuclari.keys():
                    if param in analiz_data and analiz_data[param] is not None:
                        try:
                            analiz_sonuclari[param] += float(analiz_data[param]) * katsayi
                        except: pass
    
    if not analiz_var_mi:
        return None
        
    return analiz_sonuclari

def show_pacal_hesaplayici():
    """Paçal Hesaplayıcı modülü - KURU VE TAVLI SNAPSHOT ÖZELLİKLİ"""
    
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📊 Paçal Hesaplayıcı")
    
    try:
        df = get_silo_data()
        if df.empty:
            st.warning("Silo verisi bulunamadı!")
            return
        
        # Sadece içinde mal olan siloları getir
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
        
        # --- HAZIRLIK: Tavlı Verileri Çek ---
        with st.spinner("Analiz verileri hazırlanıyor..."):
            for index, row in dolu_silolar.iterrows():
                analiz = get_tavli_analiz_agirlikli_ortalama(row['isim'])
                if analiz and analiz['toplam_tonaj'] > 0:
                    tavli_analizler[row['isim']] = analiz
                    analiz_durumlari[row['isim']] = {'var': True, 'sayi': analiz['analiz_sayisi']}
                else:
                    analiz_durumlari[row['isim']] = {'var': False}
        
        # --- SOL KOLON: SİLO SEÇİMİ ---
        with col_input:
            st.subheader("🧩 Silo Kullanım Oranları (%)")
            
            for index, row in dolu_silolar.iterrows():
                col_label, col_input_box = st.columns([3, 1])
                
                with col_label:
                    st.write(f"**{row['isim']}**")
                    # Silodaki HAM (Kuru) değerleri göster
                    prot_kuru = float(row.get('protein', 0)) if pd.notnull(row.get('protein')) else 0.0
                    maliyet = float(row.get('maliyet', 0)) if pd.notnull(row.get('maliyet')) else 0.0
                    
                    st.caption(f"Kuru Prot: {prot_kuru:.1f} | Maliyet: {maliyet:.2f} TL")
                    
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
        
        # --- SAĞ KOLON: SONUÇLAR VE KAYIT ---
        with col_result:
            st.subheader("📈 Tahmini Sonuçlar")
            
            if toplam_oran > 0:
                # 1. Kuru (Ham) Paçal ve Maliyet Hesabı
                paçal_maliyeti = 0.0
                kuru_pacal = {'protein': 0.0, 'gluten': 0.0}
                
                for isim, oran in oranlar.items():
                    if oran > 0:
                        silo_row = dolu_silolar[dolu_silolar['isim'] == isim].iloc[0]
                        katsayi = oran / 100.0
                        
                        paçal_maliyeti += float(silo_row.get('maliyet', 0)) * katsayi
                        kuru_pacal['protein'] += float(silo_row.get('protein', 0) or 0) * katsayi
                        kuru_pacal['gluten'] += float(silo_row.get('gluten', 0) or 0) * katsayi
                
                # 2. Tavlı Paçal Hesabı
                analiz_sonuclari = calculate_pacal_metrics(oranlar, tavli_analizler)
                
                if toplam_oran == 100:
                    # Göstergeler
                    c1, c2 = st.columns(2)
                    c1.metric("Maliyet", f"{paçal_maliyeti:.2f} TL")
                    c1.metric("Kuru Protein (Teorik)", f"{kuru_pacal['protein']:.1f}")
                    
                    if analiz_sonuclari:
                        c2.metric("Tavlı Protein (Hesap)", f"{analiz_sonuclari['protein']:.1f}")
                        c2.metric("Tavlı Gluten", f"{analiz_sonuclari['gluten']:.1f}")
                        st.caption(f"Enerji: {analiz_sonuclari.get('enerji135',0):.0f} | Stabilite: {analiz_sonuclari.get('stabilite',0):.1f}")
                    
                    st.divider()
                    
                    # --- KAYIT BÖLÜMÜ (SNAPSHOT) ---
                    st.success("✅ Reçete Kayda Hazır")
                    urun_adi = st.text_input("Reçete Adı (Örn: Lüks Ekmeklik)", placeholder="Ürün adını giriniz")
                    
                    if st.button("💾 PAÇALI KAYDET (FOTOĞRAF ÇEK)", type="primary"):
                        if not urun_adi:
                            st.error("Lütfen reçete adı giriniz.")
                        else:
                            # 1. ID Oluştur
                            date_str = datetime.now().strftime('%Y%m%d')
                            unique_suffix = str(uuid.uuid4())[:4].upper()
                            batch_id = f"MIX-{date_str}-{unique_suffix}"
                            
                            # 2. SNAPSHOT OLUŞTUR (En Kritik Kısım)
                            silo_snapshot = {}
                            for s_isim, s_oran in oranlar.items():
                                if s_oran > 0:
                                    # O anki HAM verileri çek
                                    raw = dolu_silolar[dolu_silolar['isim'] == s_isim].iloc[0]
                                    # O anki TAVLI verileri çek
                                    tavli = tavli_analizler.get(s_isim, {})
                                    
                                    silo_snapshot[s_isim] = {
                                        "oran": s_oran,
                                        "kuru_analiz": {
                                            "protein": float(raw.get('protein', 0) or 0),
                                            "gluten": float(raw.get('gluten', 0) or 0),
                                            "maliyet": float(raw.get('maliyet', 0) or 0),
                                            "cins": str(raw.get('bugday_cinsi', ''))
                                        },
                                        "tavli_analiz_ozet": {
                                            "protein": tavli.get('protein', 0),
                                            "gluten": tavli.get('gluten', 0)
                                        }
                                    }
                            
                            # 3. Kuru Hesaplamayı da Sonuca Ekle
                            final_analiz = analiz_sonuclari.copy() if analiz_sonuclari else {}
                            final_analiz['teorik_kuru_protein'] = kuru_pacal['protein']
                            
                            # 4. Kaydet
                            kayit_verisi = {
                                "batch_id": batch_id,
                                "tarih": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "operator": st.session_state.get('username', 'Sistem'),
                                "urun_adi": urun_adi.strip(),
                                "silo_snapshot_json": json.dumps(silo_snapshot, ensure_ascii=False),
                                "analiz_snapshot_json": json.dumps(final_analiz, ensure_ascii=False),
                                "maliyet": paçal_maliyeti
                            }
                            
                            if add_data("mixing_batches", kayit_verisi):
                                st.cache_data.clear()
                                st.success(f"✅ Paçal Başarıyla Kaydedildi! ID: {batch_id}")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("Kayıt hatası.")
            else:
                st.info("👈 Soldan oranları giriniz.")
                
    except Exception as e:
        st.error(f"Modül Hatası: {e}")
def show_pacal_gecmisi():
    """Paçal Geçmişi - Traceability Uyumlu"""
    st.header("📜 Paçal Arşivi (Traceability)")
    
    df = get_pacal_history()
    
    if df.empty:
        st.info("📭 Henüz kayıtlı paçal bulunmamaktadır.")
        return

    for idx, row in df.iterrows():
        # Başlık
        baslik = f"📦 {row.get('urun_adi','-')} | {row.get('tarih','-')} | ID: {row.get('batch_id','?')}"
        
        with st.expander(baslik):
            c1, c2 = st.columns(2)
            
            # SOL: Silo Detayları (Snapshot)
            with c1:
                st.markdown("**🏗️ Kullanılan Silolar (Kayıt Anındaki Değerler)**")
                try:
                    snapshot = json.loads(row.get('silo_snapshot_json', '{}'))
                    temiz_veri = []
                    
                    for silo, data in snapshot.items():
                        if isinstance(data, dict):
                            # Yeni Format
                            kuru = data.get('kuru_analiz', {})
                            temiz_veri.append({
                                "Silo": silo,
                                "Oran": f"%{data.get('oran',0)}",
                                "Cins": kuru.get('cins', '-'),
                                "Kuru Prot.": kuru.get('protein', '-'),
                                "Maliyet": kuru.get('maliyet', '-')
                            })
                        else:
                            # Eski Format (Sadece oran varsa)
                            temiz_veri.append({"Silo": silo, "Oran": f"%{data}", "Cins": "?"})
                            
                    st.dataframe(pd.DataFrame(temiz_veri), hide_index=True, use_container_width=True)
                except:
                    st.error("Veri çözümlenemedi.")
            
            # SAĞ: Paçal Sonucu
            with c2:
                st.markdown("**🧪 Paçal Özeti**")
                try:
                    analiz = json.loads(row.get('analiz_snapshot_json', '{}'))
                    kuru_p = analiz.get('teorik_kuru_protein', 0)
                    tavli_p = analiz.get('protein', 0)
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Kuru Protein (Ort)", f"{kuru_p:.1f}")
                    m2.metric("Tavlı Protein (Ort)", f"{tavli_p:.1f}")
                    
                    st.caption(f"💰 Maliyet: {row.get('maliyet',0):.2f} TL")
                except:
                    st.write("-")


















