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
    """Paçal Hesaplayıcı modülü"""
    
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📊 Paçal Hesaplayıcı")
    
    try:
        df = get_silo_data()
        if df.empty:
            st.warning("Silo verisi bulunamadı!")
            return
        
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
        
        with st.spinner("Tonaj ağırlıklı analiz ortalamaları hesaplanıyor..."):
            for index, row in dolu_silolar.iterrows():
                analiz = get_tavli_analiz_agirlikli_ortalama(row['isim'])
                if analiz and analiz['toplam_tonaj'] > 0:
                    tavli_analizler[row['isim']] = analiz
                    analiz_durumlari[row['isim']] = {
                        'var': True,
                        'tonaj': analiz['toplam_tonaj'],
                        'sayi': analiz['analiz_sayisi']
                    }
                else:
                    analiz_durumlari[row['isim']] = {'var': False}
        
        with col_input:
            st.subheader("🧩 Silo Kullanım Oranları (%)")
            
            for index, row in dolu_silolar.iterrows():
                col_label, col_input_box = st.columns([3, 1])
                
                with col_label:
                    st.write(f"**{row['isim']}**")
                    bugday_cinsi = str(row.get('bugday_cinsi', '')).strip() or "-"
                    # Güvenli float dönüşümü
                    maliyet = float(row.get('maliyet', 0)) if pd.notnull(row.get('maliyet')) else 0.0
                    mevcut = float(row['mevcut_miktar']) if pd.notnull(row['mevcut_miktar']) else 0.0
                    
                    st.caption(f"Cins: {bugday_cinsi} | Maliyet: {maliyet:.2f} TL/KG | Mevcut: {mevcut:.1f} Ton")
                    
                    durum = analiz_durumlari.get(row['isim'], {'var': False})
                    if durum['var']:
                        st.success(f"📊 {durum['sayi']} analiz, {durum['tonaj']:.1f} Ton")
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
            
            if toplam_oran > 100:
                st.error("⚠️ Toplam oran %100'ü geçemez!")
            elif toplam_oran < 100:
                st.warning(f"⚠️ Toplam oran %100 olmalı. Eksik: %{100-toplam_oran:.1f}")
        
        with col_result:
            st.subheader("📈 Paçal Sonuçları")
            
            if toplam_oran > 0:
                paçal_maliyeti = 0.0
                sifir_maliyetli_silolar = [] # <--- YENİ: Hatalı silo takibi
                
                for isim, oran in oranlar.items():
                    if oran > 0:
                        silo_verisi = dolu_silolar[dolu_silolar['isim'] == isim]
                        if not silo_verisi.empty:
                            # Maliyeti çek, yoksa 0 al
                            maliyet = float(silo_verisi.iloc[0].get('maliyet', 0))
                            
                            # Eğer maliyet 0 veya negatifse listeye not et
                            if maliyet <= 0:
                                sifir_maliyetli_silolar.append(isim)
                                
                            paçal_maliyeti += maliyet * (oran / 100)
                
                # UYARI MEKANİZMASI: Eğer 0 TL'lik silo varsa kullanıcıyı uyar
                if sifir_maliyetli_silolar:
                     st.warning(f"⚠️ Dikkat: {', '.join(sifir_maliyetli_silolar)} silosunun maliyeti 0 TL görünüyor. Paçal maliyeti gerçekte daha yüksek olabilir!")
                
                # Hesaplama
                analiz_sonuclari = calculate_pacal_metrics(oranlar, tavli_analizler)
                
                analiz_var_mi = analiz_sonuclari is not None
                
                if analiz_var_mi:
                     # Kullanılan analiz tonajı
                    kullanilan_silolar = [isim for isim, oran in oranlar.items() if oran > 0]
                    analiz_sonuclari['kullanilan_silo_sayisi'] = len(kullanilan_silolar)

                    toplam_analiz_tonaji = 0
                    for isim in kullanilan_silolar:
                        if isim in tavli_analizler:
                            toplam_analiz_tonaji += tavli_analizler[isim]['toplam_tonaj']
                    analiz_sonuclari['toplam_analiz_tonaji'] = toplam_analiz_tonaji
                
                if toplam_oran == 100:
                    st.success("✅ Paçal hesaplaması tamamlandı!")
                    st.metric("💰 Paçal Maliyeti", f"{paçal_maliyeti:.2f} TL/KG")
                    
                    if analiz_var_mi:
                        st.subheader("📊 Analiz Sonuçları")
                        
                        tab1, tab2, tab3 = st.tabs(["🧪 Kimyasal", "📈 Farinograph", "📊 Extensograph"])
                        
                        with tab1:
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Protein", f"{analiz_sonuclari['protein']:.1f}%")
                            c1.metric("Rutubet", f"{analiz_sonuclari['rutubet']:.1f}%")
                            c1.metric("Gluten", f"{analiz_sonuclari['gluten']:.1f}%")
                            c1.metric("Amilograph", f"{analiz_sonuclari.get('amilograph', 0):.0f} AU")
                            
                            c2.metric("Gluten Index", f"{analiz_sonuclari['gluten_index']:.0f}")
                            c2.metric("Sedim", f"{analiz_sonuclari['sedim']:.1f} ml")
                            c2.metric("G. Sedim", f"{analiz_sonuclari['g_sedim']:.1f} ml")
                            
                            c3.metric("F.N", f"{analiz_sonuclari['fn']:.0f}")
                            c3.metric("F.F.N", f"{analiz_sonuclari['ffn']:.0f}")
                            c3.metric("Kül", f"{analiz_sonuclari['kul']:.2f}%")
                            
                        with tab2:
                            c1, c2 = st.columns(2)
                            c1.metric("Su Kaldırma", f"%{analiz_sonuclari['su_kaldirma_f']:.1f}")
                            c1.metric("Gelişme Süresi", f"{analiz_sonuclari['gelisme_suresi']:.1f} dk")
                            c2.metric("Stabilite", f"{analiz_sonuclari['stabilite']:.1f} dk")
                            c2.metric("Yumuşama", f"{analiz_sonuclari['yumusama']:.0f} B.U")
                            
                        with tab3:
                            st.caption("Extensograph (45 - 90 - 135 dk)")
                            t1, t2, t3 = st.columns(3)
                            with t1:
                                st.markdown("**45 Dakika**")
                                st.write(f"Enerji: {analiz_sonuclari['enerji45']:.0f}")
                                st.write(f"Direnç: {analiz_sonuclari['direnc45']:.0f}")
                                st.write(f"Uzama: {analiz_sonuclari['taban45']:.0f}")
                            with t2:
                                st.markdown("**90 Dakika**")
                                st.write(f"Enerji: {analiz_sonuclari['enerji90']:.0f}")
                                st.write(f"Direnç: {analiz_sonuclari['direnc90']:.0f}")
                                st.write(f"Uzama: {analiz_sonuclari['taban90']:.0f}")
                            with t3:
                                st.markdown("**135 Dakika**")
                                st.write(f"Enerji: {analiz_sonuclari['enerji135']:.0f}")
                                st.write(f"Direnç: {analiz_sonuclari['direnc135']:.0f}")
                                st.write(f"Uzama: {analiz_sonuclari['taban135']:.0f}")
                        
                        st.divider()
                        
                        urun_adi = st.text_input("Üretim Adı / Kod")
                        
                        st.success("✅ Reçete Kayda Hazır")
                        urun_adi = st.text_input("Reçete Adı (Örn: Lüks Ekmeklik)", placeholder="Üretilecek Un Cinsini Yazınız")
                        if st.button("💾 PAÇALI KAYDET (TRACEABILITY)", type="primary"):
                            if not urun_adi:
                                st.error("Lütfen bir isim giriniz.")
                            else:
                                try:
                                    # 1. Benzersiz Traceability ID Oluştur (MIX-2026...)
                                    date_str = datetime.now().strftime('%Y%m%d')
                                    unique_suffix = str(uuid.uuid4())[:4].upper()
                                    batch_id = f"MIX-{date_str}-{unique_suffix}"
                                    # 2. SNAPSHOT AL (Silonun O Anki Durumunu Dondur)
                                    silo_snapshot = {}
                                    for s_isim, s_oran in oranlar.items():
                                        if s_oran > 0:
                                            silo_snapshot[s_isim] = {
                                                "oran": s_oran,
                                                "analiz_degerleri": tavli_analizler.get(s_isim, {})
                                            } 
                                    # 3. Veritabanı Formatı
                                    kayit_verisi = {
                                        "batch_id": batch_id,
                                        "tarih": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        "operator": st.session_state.get('username', 'Unknown'),
                                        "urun_adi": urun_adi.strip(),
                                        "silo_snapshot_json": json.dumps(silo_snapshot, ensure_ascii=False),
                                        "analiz_snapshot_json": json.dumps(analiz_sonuclari, ensure_ascii=False),
                                        "maliyet": paçal_maliyeti
                                    }
                                    # 4. Yeni Tabloya Kaydet
                                    if add_data("mixing_batches", kayit_verisi):
                                        st.cache_data.clear()
                                        st.success(f"✅ Paçal İzlenebilirlik Sistemine Kaydedildi! ID: {batch_id}")
                                        time.sleep(1.5)
                                        st.rerun()
                                    else:
                                        st.error("Veritabanı hatası oluştu.")
                                except Exception as e:
                                    st.error(f"Kayıt Hatası: {e}")
                else:
                    st.info("ℹ️ Toplam oranı %100 yapınca sonuçlar görünecek")
            else:
                st.info("👈 Oranları ayarlayın")
    except Exception as e:
        st.error(f"Hata: {e}")

def show_pacal_gecmisi():
    """Paçal Geçmişi - Traceability Uyumlu Yeni Versiyon"""
    st.header("📜 Paçal Arşivi (Traceability)")
    
    df = get_pacal_history()
    
    if df.empty:
        st.info("📭 Henüz kayıtlı paçal bulunmamaktadır (mixing_batches boş).")
        return

    # Tablo Gösterimi
    for idx, row in df.iterrows():
        # Başlıkta ID ve İsim Göster
        with st.expander(f"📦 {row.get('urun_adi','-')} | {row.get('tarih','-')} | ID: {row.get('batch_id','?')}"):
            c1, c2 = st.columns(2)
            
            # Sol: Silo Detayları (Snapshot Çözümleme)
            with c1:
                st.caption("🏗️ Paçalın Yapıldığı Anki Silo Değerleri")
                try:
                    snapshot = json.loads(row.get('silo_snapshot_json', '{}'))
                    temiz_veri = []
                    
                    for silo, data in snapshot.items():
                        # Yeni format kontrolü
                        if isinstance(data, dict):
                            oran = data.get('oran', 0)
                            prot = data.get('analiz_degerleri', {}).get('protein', '-')
                            temiz_veri.append({"Silo": silo, "Oran": f"%{oran}", "Protein (O An)": prot})
                        else:
                            # Eski kayıtlar patlamasın diye
                            temiz_veri.append({"Silo": silo, "Oran": f"%{data}", "Protein": "?"})
                            
                    st.dataframe(pd.DataFrame(temiz_veri), hide_index=True)
                except:
                    st.error("Veri okunamadı.")
            
            # Sağ: Sonuç Analizleri
            with c2:
                st.caption("🧪 Hedeflenen Paçal Sonucu")
                try:
                    analiz = json.loads(row.get('analiz_snapshot_json', '{}'))
                    # Hızlıca 3 kritik değeri gösterelim
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Protein", f"{analiz.get('protein',0):.1f}")
                    m1.metric("Gluten", f"{analiz.get('gluten',0):.1f}")
                    m3.metric("Maliyet", f"{row.get('maliyet',0):.2f} TL")
                except:
                    st.write("-")














