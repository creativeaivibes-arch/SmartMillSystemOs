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
    """Silo verilerini TAZE çeker"""
    try:
        df = fetch_data("silolar", force_refresh=True)
        if df.empty:
            return pd.DataFrame(columns=['isim', 'kapasite', 'mevcut_miktar', 'bugday_cinsi', 'maliyet'])

        if 'bugday_cinsi' not in df.columns: df['bugday_cinsi'] = "-"

        df = df.fillna({
            'protein': 0, 'gluten': 0, 'rutubet': 0, 'hektolitre': 0,
            'sedim': 0, 'maliyet': 0, 'bugday_cinsi': '-', 'mevcut_miktar': 0, 'kapasite': 100
        })
        
        df['bugday_cinsi'] = df['bugday_cinsi'].astype(str).str.strip()
        df['bugday_cinsi'] = df['bugday_cinsi'].replace(['nan', 'None', ''], '-')
        
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
                val = float(analiz_data.get(param, 0) or 0)
                analiz_sonuclari[param] += val * katsayi
    
    return analiz_sonuclari if analiz_var_mi else None

# Helper: Değer formatlama
def fmt(val, decimals=1):
    try: 
        if val == 0 or val is None: return "-"
        return f"{float(val):.{decimals}f}"
    except: return "-"

# ==============================================================================
# YENİ FONKSİYONLAR: GÜNCELLEME VE SİLME
# ==============================================================================

def update_pacal_record(batch_id, new_data):
    """Paçal kaydını Google Sheets'te günceller"""
    try:
        conn = get_conn()
        worksheet = conn.worksheet("mixing_batches")
        df = pd.DataFrame(worksheet.get_all_records())
        
        if df.empty:
            return False
        
        # Batch ID'ye göre satırı bul
        row_idx = df[df['batch_id'] == batch_id].index
        
        if len(row_idx) == 0:
            return False
        
        # Satır numarasını al (Google Sheets 1'den başlar ve header var)
        sheet_row = row_idx[0] + 2
        
        # Güncellenecek kolonları bul ve güncelle
        headers = worksheet.row_values(1)
        
        for key, value in new_data.items():
            if key in headers:
                col_idx = headers.index(key) + 1
                worksheet.update_cell(sheet_row, col_idx, value)
        
        st.cache_data.clear()
        return True
        
    except Exception as e:
        st.error(f"Güncelleme hatası: {e}")
        return False

def delete_pacal_record(batch_id):
    """Paçal kaydını Google Sheets'ten siler"""
    try:
        conn = get_conn()
        worksheet = conn.worksheet("mixing_batches")
        df = pd.DataFrame(worksheet.get_all_records())
        
        if df.empty:
            return False
        
        # Batch ID'ye göre satırı bul
        row_idx = df[df['batch_id'] == batch_id].index
        
        if len(row_idx) == 0:
            return False
        
        # Satır numarasını al (Google Sheets 1'den başlar ve header var)
        sheet_row = row_idx[0] + 2
        
        # Satırı sil
        worksheet.delete_rows(sheet_row)
        
        st.cache_data.clear()
        return True
        
    except Exception as e:
        st.error(f"Silme hatası: {e}")
        return False

# ==============================================================================
# MODÜL 1: PAÇAL HESAPLAYICI VE KAYITÇI
# ==============================================================================
def show_pacal_hesaplayici():
    """Paçal Hesaplayıcı - EŞİTLENMİŞ ARAYÜZ"""
    
    if st.session_state.get('user_role') not in ["admin", "operations", "quality"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📊 Paçal Hesaplayıcı")
    
    # 1. Silo Verilerini Çek
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
                cins = str(row.get('bugday_cinsi', '')).strip() or "-"
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

    # --- SAĞ: SONUÇLAR (GÜNCELLENMİŞ DETAYLI GÖRÜNÜM) ---
    with col_result:
        st.subheader("📈 Tahmini Sonuçlar (Paçal Ort.)")
        
        if toplam_oran > 0:
            pacal_maliyeti = 0.0
            kuru_ozet = {'protein': 0.0, 'rutubet': 0.0, 'gluten': 0.0}
            
            for isim, oran in oranlar.items():
                if oran > 0:
                    silo_row = dolu_silolar[dolu_silolar['isim'] == isim].iloc[0]
                    katsayi = oran / 100.0
                    
                    # Maliyet
                    pacal_maliyeti += float(silo_row.get('maliyet', 0)) * katsayi
                    
                    # HİBRİT KURU VERİ ÇEKME (Protein 0.00 Çözümü)
                    kuru_data = get_kuru_bugday_agirlikli_ortalama(isim)
                    
                    # Protein: Logdan çek, yoksa Silo Kartından çek
                    k_prot = float(kuru_data.get('protein', 0) or 0)
                    if k_prot == 0: 
                        k_prot = float(silo_row.get('protein', 0) or 0)
                    
                    kuru_ozet['protein'] += k_prot * katsayi
                    kuru_ozet['gluten'] += float(kuru_data.get('gluten', 0) or 0) * katsayi
                    kuru_ozet['rutubet'] += float(kuru_data.get('rutubet', 0) or 0) * katsayi

            # Tavlı Hesaplama
            tavli_sonuc = calculate_pacal_metrics(oranlar, tavli_analizler)
            
            if toplam_oran == 100:
                with st.container(border=True):
                    # 1. ÜST ÖZET KARTLAR (Arşivle Eşitlendi)
                    k1, k2, k3 = st.columns(3)
                    k1.metric("💰 Ort. Maliyet", f"{pacal_maliyeti:.2f} TL")
                    k2.metric("🌾 Kuru Protein", f"{kuru_ozet['protein']:.1f}")
                    
                    # Tavlı Protein (Varsa)
                    if tavli_sonuc:
                        k3.metric("🧪 Tavlı Protein", f"{tavli_sonuc.get('protein', 0):.1f}")
                    else:
                        k3.metric("🧪 Tavlı Protein", "-")

                    # 2. DETAYLI SEKMELER (Arşivle Birebir Aynı Yapı)
                    if tavli_sonuc:
                        st.divider()
                        
                        tt1, tt2, tt3 = st.tabs(["⚗️ Kimyasal", "📈 Farinograph", "📊 Extensograph"])
                        
                        with tt1:
                            c1, c2, c3 = st.columns(3)
                            c1.markdown(f"**Protein:** {fmt(tavli_sonuc.get('protein', 0))}")
                            c2.markdown(f"**Rutubet:** {fmt(tavli_sonuc.get('rutubet', 0))}")
                            c3.markdown(f"**Gluten:** {fmt(tavli_sonuc.get('gluten', 0))}")
                            
                            c4, c5, c6 = st.columns(3)
                            c4.markdown(f"**G. İndeks:** {fmt(tavli_sonuc.get('gluten_index', 0), 0)}")
                            c5.markdown(f"**Sedim:** {fmt(tavli_sonuc.get('sedim', 0), 0)}")
                            c6.markdown(f"**G. Sedim:** {fmt(tavli_sonuc.get('g_sedim', 0), 0)}")
                            
                            c7, c8, c9 = st.columns(3)
                            c7.markdown(f"**FN:** {fmt(tavli_sonuc.get('fn', 0), 0)}")
                            c8.markdown(f"**FFN:** {fmt(tavli_sonuc.get('ffn', 0), 0)}")
                            c9.markdown(f"**Amilograph:** {fmt(tavli_sonuc.get('amilograph', 0), 0)}")

                        with tt2:
                            f1, f2 = st.columns(2)
                            f1.markdown(f"**Su Kal. (F):** {fmt(tavli_sonuc.get('su_kaldirma_f', 0))}")
                            f1.markdown(f"**Gelişme:** {fmt(tavli_sonuc.get('gelisme_suresi', 0))}")
                            
                            f2.markdown(f"**Stabilite:** {fmt(tavli_sonuc.get('stabilite', 0))}")
                            f2.markdown(f"**Yumuşama:** {fmt(tavli_sonuc.get('yumusama', 0), 0)}")

                        with tt3:
                            st.markdown(f"**Su Kaldırma (E):** {fmt(tavli_sonuc.get('su_kaldirma_e', 0))}")
                            st.markdown("---")
                            
                            ec1, ec2, ec3 = st.columns(3)
                            ec1.caption("45. Dakika")
                            ec1.markdown(f"Direnç: {fmt(tavli_sonuc.get('direnc45', 0), 0)}")
                            ec1.markdown(f"Taban: {fmt(tavli_sonuc.get('taban45', 0), 0)}")
                            ec1.markdown(f"Enerji: {fmt(tavli_sonuc.get('enerji45', 0), 0)}")
                            
                            ec2.caption("90. Dakika")
                            ec2.markdown(f"Direnç: {fmt(tavli_sonuc.get('direnc90', 0), 0)}")
                            ec2.markdown(f"Taban: {fmt(tavli_sonuc.get('taban90', 0), 0)}")
                            ec2.markdown(f"Enerji: {fmt(tavli_sonuc.get('enerji90', 0), 0)}")
                            
                            ec3.caption("135. Dakika")
                            ec3.markdown(f"Direnç: {fmt(tavli_sonuc.get('direnc135', 0), 0)}")
                            ec3.markdown(f"Taban: {fmt(tavli_sonuc.get('taban135', 0), 0)}")
                            ec3.markdown(f"Enerji: {fmt(tavli_sonuc.get('enerji135', 0), 0)}")

                # --- KAYIT BÖLÜMÜ ---
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
            else:
                st.info("ℹ️ Toplam oranı %100 yapınız.")
        else:
            st.info("👈 Soldan oranları giriniz.")



