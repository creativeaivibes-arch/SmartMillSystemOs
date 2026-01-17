import streamlit as st
import pandas as pd
from datetime import datetime
import json
import io
import time
import sqlite3
from app.core.database import get_db_connection

# PDF Kütüphanesi Kontrolü
PDF_AVAILABLE = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus.flowables import HRFlowable
    PDF_AVAILABLE = True
except ImportError:
    pass

def show_katki_maliyeti_modulu():
    """Katkı ve Enzim Maliyeti Modülü"""
    
    # Ana başlık
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 10px;">🧪 Katkı ve Enzim Maliyeti Hesaplama</h1>
        <p style="color: #666; font-size: 16px;">Katkı reçetelerinizi yönetin ve maliyetlerinizi hesaplayın</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Döviz kurlarını getir
    new_usd = 43.28
    new_eur = 50.08
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            curr_kurlar = cursor.execute("SELECT usd_tl, eur_tl FROM katki_kurlar WHERE id=1").fetchone()
            if curr_kurlar:
                new_usd = float(curr_kurlar[0]) 
                new_eur = float(curr_kurlar[1])
            else:
                cursor.execute("CREATE TABLE IF NOT EXISTS katki_kurlar (id INTEGER PRIMARY KEY, usd_tl REAL, eur_tl REAL)")
                # Default values if table created or empty
                new_usd = 43.28
                new_eur = 50.08
                cursor.execute("INSERT OR IGNORE INTO katki_kurlar (id, usd_tl, eur_tl) VALUES (1, ?, ?)", (new_usd, new_eur))
                conn.commit()
    except Exception as e:
        # Fallback values
        pass
    
    # --- TABLOLARI KONTROL ET VE GÜNCELLE ---
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # katki_recete_gecmisi tablosunu kontrol et
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='katki_recete_gecmisi'")
            if not cursor.fetchone():
                # Tablo yoksa oluştur
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS katki_recete_gecmisi (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        urun_adi TEXT,
                        enzim_sayisi INTEGER,
                        recete_json TEXT,
                        aciklama TEXT DEFAULT 'Reçete güncellendi'
                    )
                ''')
                conn.commit()
            
            # Diğer tabloları da kontrol et
            cursor.execute('''CREATE TABLE IF NOT EXISTS katki_enzimler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT UNIQUE,
                fiyat REAL,
                para_birimi TEXT
            )''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS katki_urunler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT UNIQUE
            )''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS katki_recete (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                urun_id INTEGER,
                enzim_id INTEGER,
                gramaj REAL,
                UNIQUE(urun_id, enzim_id)
            )''')
            conn.commit()

    except Exception as e:
        st.error(f"Tablo kontrol hatası: {e}")
    
    # --- ÜST BÖLÜM: 3 KOLONLU DÜZEN ---
    st.markdown("### 📋 Kontrol Paneli")
    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    
    # 1. KOLON: DÖVİZ KURLARI
    with col1:
        with st.container(border=True, height=260):
            st.markdown("#### 💱 Döviz Kurları")
            st.markdown("Güncel döviz kurlarını TL cinsinden giriniz:")
            
            input_usd = st.number_input("**1 USD**", 
                                      value=float(new_usd), 
                                      format="%.2f", 
                                      step=0.01, 
                                      key="katki_usd",
                                      help="Amerikan Doları TL karşılığı")
            
            input_eur = st.number_input("**1 EUR**", 
                                      value=float(new_eur), 
                                      format="%.2f", 
                                      step=0.01, 
                                      key="katki_eur",
                                      help="Euro TL karşılığı")
            
            if st.button("💾 Kurları Güncelle", 
                        use_container_width=True, 
                        key="katki_kur_save",
                        type="primary"):
                try:
                    with get_db_connection() as conn:
                        conn.execute("UPDATE katki_kurlar SET usd_tl=?, eur_tl=? WHERE id=1", (input_usd, input_eur))
                        conn.commit()
                    st.success("✅ Kurlar güncellendi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Güncelleme hatası: {str(e)}")
    
    # 2. KOLON: YENİ KATKI/ENZİM
    with col2:
        with st.container(border=True, height=260):
            st.markdown("#### ⚙️ Yeni Katkı/Enzim")
            
            e_ad = st.text_input("**Katkı/Enzim Adı**", 
                                key="yeni_enzim_ad",
                                placeholder="Örn: Askorbik Asit, Amilaz",
                                help="Katkı veya enzim adını giriniz").strip().upper()
            
            e_birim = st.selectbox("**Para Birimi**", 
                                  ["EUR", "USD", "TL"], 
                                  key="yeni_enzim_birim",
                                  help="Katkının satın alındığı para birimi")
            
            e_fiyat = st.number_input("**1 kg Fiyatı**", 
                                     min_value=0.0, 
                                     step=0.01, 
                                     format="%.3f", 
                                     key="yeni_enzim_fiyat",
                                     help="1 kilogram fiyatı (seçilen para biriminde)")
            
            if st.button("💾 Katkıyı Kaydet", 
                        key="katki_ekle", 
                        use_container_width=True,
                        type="secondary"):
                if e_ad:
                    try:
                        with get_db_connection() as conn:
                            conn.execute("INSERT INTO katki_enzimler (ad, fiyat, para_birimi) VALUES (?, ?, ?)",
                                         (e_ad, e_fiyat, e_birim))
                            conn.commit()
                        st.success(f"✅ '{e_ad}' kaydedildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")
                else:
                    st.warning("⚠️ Katkı/enzim adı gerekli!")
    
    # 3. KOLON: YENİ ÜRÜN
    with col3:
        with st.container(border=True, height=260):
            st.markdown("#### 🥖 Yeni Ürün")
            
            u_ad = st.text_input("**Ürün Adı**", 
                                key="yeni_urun_ad",
                                placeholder="Örn: Ekstra Ekmeklik, Süper Pizza",
                                help="Katkı reçetesinin uygulanacağı ürün adı").strip().upper()
            
            if st.button("💾 Ürünü Kaydet", 
                        key="urun_ekle", 
                        use_container_width=True,
                        type="secondary"):
                if u_ad:
                    try:
                        with get_db_connection() as conn:
                            conn.execute("INSERT INTO katki_urunler (ad) VALUES (?)", (u_ad,))
                            conn.commit()
                        st.success(f"✅ '{u_ad}' kaydedildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")
                else:
                    st.warning("⚠️ Ürün adı gerekli!")
    
    # --- REÇETE VE FİYAT TABLOSU ---
    st.divider()
    st.markdown("### 📊 Reçete ve Fiyat Tablosu")
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM katki_enzimler ORDER BY ad")
            enzimler_raw = cursor.fetchall()
            
            cursor.execute("SELECT * FROM katki_urunler ORDER BY ad")
            urunler_raw = cursor.fetchall()
            
            if not enzimler_raw or not urunler_raw:
                st.info("Henüz katkı/enzim veya ürün eklenmemiş.")
                # We continue to avoid crashing, but there's nothing to show
                
            # DataFramelere çevir
            enzimler_df = pd.DataFrame(enzimler_raw, columns=['id', 'ad', 'fiyat', 'para_birimi'])
            urunler_df = pd.DataFrame(urunler_raw, columns=['id', 'ad'])
            
            # Tablo verileri
            column_names = ["ENZİM İSMİ", "FİYAT", "BİRİM"] + list(urunler_df['ad'].values) if not urunler_df.empty else ["ENZİM İSMİ", "FİYAT", "BİRİM"]
            
            table_data = []
            if not enzimler_df.empty:
                for _, e_row in enzimler_df.iterrows():
                    row = [e_row['ad'], e_row['fiyat'], e_row['para_birimi']]
                    
                    # Her ürün için gramaj değerini al
                    if not urunler_df.empty:
                        for _, u_row in urunler_df.iterrows():
                            res = cursor.execute("SELECT gramaj FROM katki_recete WHERE urun_id=? AND enzim_id=?", 
                                               (u_row['id'], e_row['id'])).fetchone()
                            row.append(float(res[0]) if res else 0.0)
                    
                    table_data.append(row)
            
            # Sütun konfigürasyonu
            column_config = {
                "ENZİM İSMİ": st.column_config.TextColumn("ENZİM", width="small", required=True),
                "FİYAT": st.column_config.NumberColumn("FİYAT", width="small", format="%.3f", required=True),
                "BİRİM": st.column_config.SelectboxColumn("BİRİM", width="small", options=["EUR", "USD", "TL"], required=True),
            }
            
            if not urunler_df.empty:
                for u_name in urunler_df['ad'].values:
                    display_name = u_name[:15] + "..." if len(u_name) > 15 else u_name
                    column_config[u_name] = st.column_config.NumberColumn(
                        display_name,
                        width="small",
                        format="%.3f",
                        min_value=0.0
                    )
            
            # Tabloyu göster
            edited_df = st.data_editor(
                pd.DataFrame(table_data, columns=column_names) if table_data else pd.DataFrame(columns=column_names),
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
                num_rows="fixed",
                key="recete_editor"
            )
            
            # KAYDET BUTONU
            if st.button("🔄 DEĞİŞİKLİKLERİ KAYDET", use_container_width=True, type="primary", key="katki_kaydet"):
                # REÇETE GEÇMİŞİNİ VE ANA TABLOLARI KAYDET
                try:
                    # JSON hazırla
                    recete_verisi = {}
                    if not urunler_df.empty:
                        for idx, row in edited_df.iterrows():
                            enzim_adi = row["ENZİM İSMİ"]
                            recete_verisi[enzim_adi] = {}
                            for u_name in urunler_df['ad'].values:
                                recete_verisi[enzim_adi][u_name] = float(row[u_name])
                    
                    recete_json = json.dumps(recete_verisi, ensure_ascii=False)
                    
                    # Geçmişe kaydet
                    if not urunler_df.empty:
                        for u_name in urunler_df['ad'].values:
                            conn.execute('''
                                INSERT INTO katki_recete_gecmisi (urun_adi, enzim_sayisi, recete_json, aciklama)
                                VALUES (?, ?, ?, ?)
                            ''', (u_name, len(enzimler_df), recete_json, f"Reçete güncellendi - {u_name}"))
                    
                    # Güncellemeler
                    for idx, row in edited_df.iterrows():
                        if idx < len(table_data): # Ensure we are updating existing rows
                            eski_ad = table_data[idx][0]
                            conn.execute("UPDATE katki_enzimler SET ad=?, fiyat=?, para_birimi=? WHERE ad=?", 
                                         (row["ENZİM İSMİ"].upper(), float(row["FİYAT"]), row["BİRİM"], eski_ad))
                            
                            if not urunler_df.empty:
                                e_id_res = conn.execute("SELECT id FROM katki_enzimler WHERE ad=?", (row["ENZİM İSMİ"].upper(),)).fetchone()
                                if e_id_res:
                                    e_id = e_id_res[0]
                                    for u_col in urunler_df['ad'].values:
                                        u_id_res = urunler_df[urunler_df['ad'] == u_col]['id'].values
                                        if len(u_id_res) > 0:
                                            u_id = u_id_res[0]
                                            conn.execute("INSERT OR REPLACE INTO katki_recete (urun_id, enzim_id, gramaj) VALUES (?,?,?)",
                                                         (int(u_id), int(e_id), float(row[u_col])))
                    
                    conn.commit()
                    st.success("✅ Tüm değişiklikler kaydedildi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as ex:
                    st.error(f"Kayıt hatası: {ex}")

            # --- MALİYET ANALİZ RAPORU ---
            st.divider()
            st.markdown("### 💰 Maliyet Analiz Raporu")
            
            if not urunler_df.empty and not enzimler_df.empty:
                col_report1, col_report2 = st.columns([2, 1])
                with col_report1:
                    rapor_birimi = st.radio("**Rapor Birimi:**", ["1 Çuval (50kg) Başına", "1 Ton Un Başına"], horizontal=True, key="rapor_birimi")
                
                rapor_data = []
                for u_name in urunler_df['ad'].values:
                    toplam_tl = 0.0
                    for idx, row in edited_df.iterrows():
                        gramaj_cuval = float(row[u_name])
                        if gramaj_cuval > 0:
                            fiyat = float(row["FİYAT"])
                            birim = row["BİRİM"]
                            if birim == "USD": tl_kg_fiyat = fiyat * new_usd
                            elif birim == "EUR": tl_kg_fiyat = fiyat * new_eur
                            else: tl_kg_fiyat = fiyat
                            
                            maliyet_cuval = (gramaj_cuval / 1000) * tl_kg_fiyat
                            maliyet = maliyet_cuval * 20 if rapor_birimi == "1 Ton Un Başına" else maliyet_cuval
                            toplam_tl += maliyet
                    
                    maliyet_usd = toplam_tl / new_usd if new_usd > 0 else 0
                    maliyet_eur = toplam_tl / new_eur if new_eur > 0 else 0
                    katki_sayisi = sum(1 for idx, row in edited_df.iterrows() if float(row[u_name]) > 0)
                    birim_aciklama = "1 ÇUVAL" if rapor_birimi == "1 Çuval (50kg) Başına" else "1 TON"
                    
                    rapor_data.append({
                        "Ürün": u_name, "Birim": birim_aciklama, "Katkı Sayısı": katki_sayisi,
                        "Toplam TL": toplam_tl, "Toplam USD": maliyet_usd, "Toplam EUR": maliyet_eur
                    })
                
                if rapor_data:
                    st.dataframe(pd.DataFrame(rapor_data), use_container_width=True, hide_index=True)
            
            # --- ÜRÜN SİLME ---
            st.divider()
            st.markdown("### 🗑️ Ürün Silme")
            if not urunler_df.empty:
                silinecek = st.selectbox("Silinecek Ürün", urunler_df['ad'].tolist(), key="sil_urun_sec")
                if st.button("🗑️ Ürünü Sil", type="secondary"):
                    try:
                        u_id = urunler_df[urunler_df['ad'] == silinecek]['id'].values[0]
                        conn.execute("DELETE FROM katki_recete WHERE urun_id = ?", (int(u_id),))
                        conn.execute("DELETE FROM katki_urunler WHERE id = ?", (int(u_id),))
                        conn.commit()
                        st.success(f"{silinecek} silindi.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Silme hatası: {e}")

    except Exception as e:
        st.error(f"Veri yükleme hatası: {e}")

def show_enzim_dozajlama():
    """Un Geliştirici Enzim Dozajlama Hesaplama Modülü"""
    
    if 'enzim_last_data' not in st.session_state:
        st.session_state.enzim_last_data = {
            'uretim_adi': 'Ekmeklik',
            'un_ton': 100.0,
            'bugday_hiz': 12500.0,
            'randiman': 70.0,
            'dk_akis_gr': 30.0,
            'enzim_rows': [{'name': '', 'doz': '', 'total': 0} for _ in range(10)]
        }
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 5px;">🧬 Un Geliştirici Enzim Dozajlama Hesaplama</h1>
    </div>
    """, unsafe_allow_html=True)
    
    col_left, col_right = st.columns([1, 1.5], gap="large")
    
    with col_left:
        st.markdown("### ⚙️ 1. Üretim Parametreleri")
        with st.container(border=True):
            last_data = st.session_state.enzim_last_data
            uretim_adi = st.text_input("**Üretim Adı**", value=last_data['uretim_adi'], key="enzim_uretim_adi")
            
            col1, col2 = st.columns(2)
            with col1:
                un_ton = st.number_input("**Hedef Un (Ton)**", min_value=0.1, value=float(last_data['un_ton']), step=0.1, key="enzim_un_ton")
            with col2:
                bugday_hiz = st.number_input("**Buğday Hızı (kg/saat)**", min_value=100.0, value=float(last_data['bugday_hiz']), step=100.0, key="enzim_bugday_hiz")
            
            col3, col4 = st.columns(2)
            with col3:
                randiman = st.number_input("**Randıman (%)**", min_value=1.0, max_value=100.0, value=float(last_data['randiman']), step=0.1, key="enzim_randiman")
            with col4:
                dk_akis_gr = st.number_input("**Dozaj Akışı (gr/dk)**", min_value=1.0, value=float(last_data['dk_akis_gr']), step=1.0, key="enzim_dk_akis_gr")

    with col_right:
        st.markdown("### 🧪 2. Enzim/Katkı Listesi")
        
        if 'enzim_rows' not in st.session_state:
            st.session_state.enzim_rows = st.session_state.enzim_last_data['enzim_rows']
            
        for i in range(10):
            cols = st.columns([2, 1, 1])
            with cols[0]:
                st.session_state.enzim_rows[i]['name'] = st.text_input(f"Enzim {i+1}", value=st.session_state.enzim_rows[i]['name'], key=f"enzim_name_{i}", label_visibility="collapsed", placeholder=f"Enzim {i+1}")
            with cols[1]:
                st.session_state.enzim_rows[i]['doz'] = st.text_input(f"Doz {i+1}", value=st.session_state.enzim_rows[i]['doz'], key=f"enzim_doz_{i}", label_visibility="collapsed", placeholder="gr/çuval")
            with cols[2]:
                total = st.session_state.enzim_rows[i]['total']
                st.write(f"{total:,.0f} gr" if total > 0 else "0 gr")

        st.divider()
        irmik = st.session_state.get('irmik_total', 0)
        st.metric("🧱 İrmik Dolgu Miktarı", f"{irmik:,.0f} gr")

    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("🧮 HESAPLA", use_container_width=True, type="primary"):
            try:
                dakika = (un_ton * 1000) / (bugday_hiz * (randiman / 100)) * 60
                cuval_sayisi = (un_ton * 1000) / 50
                toplam_akis = dakika * dk_akis_gr
                toplam_enzim = 0
                
                for i, row in enumerate(st.session_state.enzim_rows):
                    if row.get('name', '').strip() and row.get('doz', '').strip():
                        try:
                            doz_degeri = float(row['doz'].replace(',', '.'))
                            ihtiyac = cuval_sayisi * doz_degeri
                            st.session_state.enzim_rows[i]['total'] = ihtiyac
                            toplam_enzim += ihtiyac
                        except:
                            st.session_state.enzim_rows[i]['total'] = 0
                    else:
                        st.session_state.enzim_rows[i]['total'] = 0
                
                st.session_state.irmik_total = max(0, toplam_akis - toplam_enzim)
                st.session_state.enzim_last_data.update({
                    'uretim_adi': uretim_adi, 'un_ton': un_ton, 'bugday_hiz': bugday_hiz,
                    'randiman': randiman, 'dk_akis_gr': dk_akis_gr,
                    'enzim_rows': st.session_state.enzim_rows.copy()
                })
                st.success("✅ Hesaplama tamamlandı!")
                st.rerun()
            except Exception as e:
                st.error(f"Hesaplama hatası: {e}")

    with col_btn2:
        if st.button("💾 REÇETEYİ KAYDET", use_container_width=True):
            try:
                with get_db_connection() as conn:
                    # Create table if not exists
                    conn.execute('''CREATE TABLE IF NOT EXISTS enzim_receteleri (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        uretim_adi TEXT,
                        un_ton REAL,
                        bugday_hiz REAL,
                        randiman REAL,
                        dozaj_akis REAL,
                        enzim_verisi_json TEXT,
                        irmik_miktari REAL,
                        tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        kullanici TEXT
                    )''')
                    
                    enzim_verisi = [{'ad': r['name'], 'doz': r['doz'], 'toplam': r['total']} 
                                   for r in st.session_state.enzim_rows if r['name'].strip()]
                    
                    conn.execute('''INSERT INTO enzim_receteleri 
                        (uretim_adi, un_ton, bugday_hiz, randiman, dozaj_akis, enzim_verisi_json, irmik_miktari, kullanici)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (uretim_adi, un_ton, bugday_hiz, randiman, dk_akis_gr, 
                         json.dumps(enzim_verisi, ensure_ascii=False), st.session_state.get('irmik_total', 0), 
                         st.session_state.get('username', 'Unknown')))
                    conn.commit()
                st.success("✅ Reçete kaydedildi!")
            except Exception as e:
                st.error(f"Kayıt hatası: {e}")
                
    with col_btn3:
        if st.button("🗑️ TEMİZLE", use_container_width=True, type="secondary"):
            st.session_state.enzim_rows = [{'name': '', 'doz': '', 'total': 0} for _ in range(10)]
            if 'irmik_total' in st.session_state: del st.session_state.irmik_total
            st.rerun()

    # Geçmiş Gösterimi
    st.divider()
    if st.checkbox("📋 Geçmiş Reçeteleri Göster"):
        try:
            with get_db_connection() as conn:
                df = pd.read_sql_query("SELECT id, uretim_adi, un_ton, tarih FROM enzim_receteleri ORDER BY tarih DESC LIMIT 20", conn)
                st.dataframe(df, use_container_width=True)
        except Exception:
            st.info("Kayıt bulunamadı.")
