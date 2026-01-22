import streamlit as st
import pandas as pd
from datetime import datetime
import json
import time

# --- GÜNCELLENMİŞ IMPORTLAR ---
from app.core.database import fetch_data, add_data, get_conn

# PDF Kütüphanesi Kontrolü
PDF_AVAILABLE = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    PDF_AVAILABLE = True
except ImportError:
    pass

def show_katki_maliyeti_modulu():
    """Katkı ve Enzim Maliyeti Modülü - Google Sheets Uyumlu"""
    
    # Ana başlık
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 10px;">🧪 Katkı ve Enzim Maliyeti Hesaplama</h1>
        <p style="color: #666; font-size: 16px;">Katkı reçetelerinizi yönetin ve maliyetlerinizi hesaplayın</p>
    </div>
    """, unsafe_allow_html=True)
    
    # --- VERİLERİ ÇEK ---
    df_kurlar = fetch_data("katki_kurlar")
    df_enzimler = fetch_data("katki_enzimler")
    df_urunler = fetch_data("katki_urunler")
    df_recete = fetch_data("katki_recete")
    
    # Döviz kurlarını ayarla
    new_usd = 43.28
    new_eur = 50.08
    
    if not df_kurlar.empty:
        new_usd = float(df_kurlar.iloc[0]['usd_tl'])
        new_eur = float(df_kurlar.iloc[0]['eur_tl'])
    else:
        # İlk kez çalışıyorsa varsayılan ekle
        add_data("katki_kurlar", {"id": 1, "usd_tl": new_usd, "eur_tl": new_eur})

    # --- ÜST BÖLÜM: 3 KOLONLU DÜZEN ---
    st.markdown("### 📋 Kontrol Paneli")
    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    
    # 1. KOLON: DÖVİZ KURLARI
    with col1:
        with st.container(border=True, height=260):
            st.markdown("#### 💱 Döviz Kurları")
            st.markdown("Güncel döviz kurlarını TL cinsinden giriniz:")
            
            input_usd = st.number_input("**1 USD**", value=new_usd, format="%.2f", step=0.01, key="katki_usd")
            input_eur = st.number_input("**1 EUR**", value=new_eur, format="%.2f", step=0.01, key="katki_eur")
            
            if st.button("💾 Kurları Güncelle", use_container_width=True, key="katki_kur_save", type="primary"):
                try:
                    conn = get_conn()
                    # Mevcut satırı güncelle
                    if df_kurlar.empty:
                        add_data("katki_kurlar", {"id": 1, "usd_tl": input_usd, "eur_tl": input_eur})
                    else:
                        df_kurlar.at[0, 'usd_tl'] = input_usd
                        df_kurlar.at[0, 'eur_tl'] = input_eur
                        conn.update(worksheet="katki_kurlar", data=df_kurlar)
                    
                    st.success("✅ Kurlar güncellendi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Güncelleme hatası: {str(e)}")
    
    # 2. KOLON: YENİ KATKI/ENZİM
    with col2:
        with st.container(border=True, height=260):
            st.markdown("#### ⚙️ Yeni Katkı/Enzim")
            
            e_ad = st.text_input("**Katkı/Enzim Adı**", key="yeni_enzim_ad").strip().upper()
            e_birim = st.selectbox("**Para Birimi**", ["EUR", "USD", "TL"], key="yeni_enzim_birim")
            e_fiyat = st.number_input("**1 kg Fiyatı**", min_value=0.0, step=0.01, format="%.3f", key="yeni_enzim_fiyat")
            
            if st.button("💾 Katkıyı Kaydet", key="katki_ekle", use_container_width=True, type="secondary"):
                if e_ad:
                    try:
                        # İsim kontrolü
                        if not df_enzimler.empty and e_ad in df_enzimler['ad'].values:
                            st.error("Bu isimde katkı zaten var.")
                        else:
                            # ID oluştur (Max ID + 1)
                            new_id = 1
                            if not df_enzimler.empty and 'id' in df_enzimler.columns:
                                new_id = df_enzimler['id'].max() + 1
                                
                            add_data("katki_enzimler", {
                                "id": int(new_id), 
                                "ad": e_ad, 
                                "fiyat": e_fiyat, 
                                "para_birimi": e_birim
                            })
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
            
            u_ad = st.text_input("**Ürün Adı**", key="yeni_urun_ad").strip().upper()
            
            if st.button("💾 Ürünü Kaydet", key="urun_ekle", use_container_width=True, type="secondary"):
                if u_ad:
                    try:
                        if not df_urunler.empty and u_ad in df_urunler['ad'].values:
                            st.error("Bu isimde ürün zaten var.")
                        else:
                            new_id = 1
                            if not df_urunler.empty and 'id' in df_urunler.columns:
                                new_id = df_urunler['id'].max() + 1
                                
                            add_data("katki_urunler", {"id": int(new_id), "ad": u_ad})
                            st.success(f"✅ '{u_ad}' kaydedildi!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")
                else:
                    st.warning("⚠️ Ürün adı gerekli!")
    
    # --- REÇETE VE FİYAT TABLOSU (MATRIX) ---
    st.divider()
    st.markdown("### 📊 Reçete ve Fiyat Tablosu")
    
    if df_enzimler.empty:
        st.info("Henüz katkı/enzim eklenmemiş.")
    else:
        # Tablo verilerini hazırla (Matrix Oluşturma)
        # Satırlar: Enzimler, Sütunlar: Ürünler
        
        # Temel sütunlar
        table_data = df_enzimler[['id', 'ad', 'fiyat', 'para_birimi']].copy()
        table_data.columns = ['id', 'ENZİM İSMİ', 'FİYAT', 'BİRİM']
        
        # Ürün sütunlarını ekle ve gramajları doldur
        if not df_urunler.empty:
            for _, u_row in df_urunler.iterrows():
                u_id = u_row['id']
                u_name = u_row['ad']
                col_values = []
                
                for _, e_row in table_data.iterrows():
                    e_id = e_row['id']
                    gramaj = 0.0
                    # Reçete tablosundan gramajı bul
                    if not df_recete.empty:
                        match = df_recete[(df_recete['urun_id'] == u_id) & (df_recete['enzim_id'] == e_id)]
                        if not match.empty:
                            gramaj = float(match.iloc[0]['gramaj'])
                    col_values.append(gramaj)
                
                table_data[u_name] = col_values

        # Editör Konfigürasyonu
        column_config = {
            "id": None, # ID'yi gizle
            "ENZİM İSMİ": st.column_config.TextColumn("ENZİM", width="small", required=True),
            "FİYAT": st.column_config.NumberColumn("FİYAT", width="small", format="%.3f", required=True),
            "BİRİM": st.column_config.SelectboxColumn("BİRİM", width="small", options=["EUR", "USD", "TL"], required=True),
        }
        
        if not df_urunler.empty:
            for u_name in df_urunler['ad'].values:
                column_config[u_name] = st.column_config.NumberColumn(
                    u_name, width="small", format="%.3f", min_value=0.0
                )
        
        # Data Editor Gösterimi
        edited_df = st.data_editor(
            table_data,
            use_container_width=True,
            hide_index=True,
            column_config=column_config,
            num_rows="fixed",
            key="recete_editor"
        )
        
        # KAYDET BUTONU
        if st.button("🔄 DEĞİŞİKLİKLERİ KAYDET", use_container_width=True, type="primary", key="katki_kaydet"):
            try:
                conn = get_conn()
                
                # 1. Enzim Güncellemeleri (Fiyat/İsim/Birim)
                updated_enzimler = df_enzimler.copy()
                for idx, row in edited_df.iterrows():
                    e_id = row['id']
                    # İlgili satırı bul ve güncelle
                    mask = updated_enzimler['id'] == e_id
                    if mask.any():
                        updated_enzimler.loc[mask, 'ad'] = row['ENZİM İSMİ']
                        updated_enzimler.loc[mask, 'fiyat'] = row['FİYAT']
                        updated_enzimler.loc[mask, 'para_birimi'] = row['BİRİM']
                
                conn.update(worksheet="katki_enzimler", data=updated_enzimler)
                
                # 2. Reçete Güncellemeleri (Gramajlar)
                # DataFrame üzerinde işlem yapıp toplu update edeceğiz
                updated_recete = df_recete.copy()
                new_records = []
                
                if not df_urunler.empty:
                    for idx, row in edited_df.iterrows():
                        e_id = row['id']
                        for _, u_row in df_urunler.iterrows():
                            u_id = u_row['id']
                            u_name = u_row['ad']
                            gramaj = float(row[u_name])
                            
                            # Mevcut kaydı bul
                            mask = (updated_recete['urun_id'] == u_id) & (updated_recete['enzim_id'] == e_id)
                            
                            if mask.any():
                                updated_recete.loc[mask, 'gramaj'] = gramaj
                            else:
                                if gramaj > 0: # Sadece 0'dan büyükse yeni kayıt ekle
                                    new_records.append({
                                        'urun_id': int(u_id),
                                        'enzim_id': int(e_id),
                                        'gramaj': gramaj
                                    })
                
                # Yeni kayıtları ekle
                if new_records:
                    updated_recete = pd.concat([updated_recete, pd.DataFrame(new_records)], ignore_index=True)
                
                conn.update(worksheet="katki_recete", data=updated_recete)
                
                # 3. Geçmişe Kayıt (Opsiyonel ama iyi olur)
                recete_json = json.dumps(edited_df.to_dict(orient='records'), ensure_ascii=False)
                add_data("katki_recete_gecmisi", {
                    "tarih": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "urun_adi": "Toplu Güncelleme",
                    "enzim_sayisi": len(df_enzimler),
                    "recete_json": recete_json,
                    "aciklama": "Reçete tablosu güncellendi"
                })

                st.success("✅ Tüm değişiklikler başarıyla kaydedildi!")
                time.sleep(1)
                st.rerun()
                
            except Exception as ex:
                st.error(f"Kayıt hatası: {ex}")

        # --- MALİYET ANALİZ RAPORU ---
        st.divider()
        st.markdown("### 💰 Maliyet Analiz Raporu")
        
        if not df_urunler.empty:
            col_report1, col_report2 = st.columns([2, 1])
            with col_report1:
                rapor_birimi = st.radio("**Rapor Birimi:**", ["1 Çuval (50kg) Başına", "1 Ton Un Başına"], horizontal=True, key="rapor_birimi")
            
            rapor_data = []
            
            # Hesaplama
            for u_name in df_urunler['ad'].values:
                toplam_tl = 0.0
                katki_sayisi = 0
                
                for idx, row in edited_df.iterrows():
                    gramaj_cuval = float(row[u_name])
                    if gramaj_cuval > 0:
                        katki_sayisi += 1
                        fiyat = float(row["FİYAT"])
                        birim = row["BİRİM"]
                        
                        # TL'ye çevir
                        if birim == "USD": tl_kg_fiyat = fiyat * new_usd
                        elif birim == "EUR": tl_kg_fiyat = fiyat * new_eur
                        else: tl_kg_fiyat = fiyat
                        
                        # Maliyet hesabı (Gramaj 50kg çuval içindir)
                        maliyet_cuval = (gramaj_cuval / 1000) * tl_kg_fiyat
                        
                        if rapor_birimi == "1 Ton Un Başına":
                            maliyet = maliyet_cuval * 20 # 1 tonda 20 çuval var
                        else:
                            maliyet = maliyet_cuval
                            
                        toplam_tl += maliyet
                
                maliyet_usd = toplam_tl / new_usd if new_usd > 0 else 0
                maliyet_eur = toplam_tl / new_eur if new_eur > 0 else 0
                birim_aciklama = "1 ÇUVAL" if rapor_birimi == "1 Çuval (50kg) Başına" else "1 TON"
                
                rapor_data.append({
                    "Ürün": u_name, 
                    "Birim": birim_aciklama, 
                    "Katkı Sayısı": katki_sayisi,
                    "Toplam TL": toplam_tl, 
                    "Toplam USD": maliyet_usd, 
                    "Toplam EUR": maliyet_eur
                })
            
            if rapor_data:
                st.dataframe(
                    pd.DataFrame(rapor_data), 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Toplam TL": st.column_config.NumberColumn(format="%.2f ₺"),
                        "Toplam USD": st.column_config.NumberColumn(format="%.2f $"),
                        "Toplam EUR": st.column_config.NumberColumn(format="%.2f €")
                    }
                )

        # --- ÜRÜN SİLME ---
        st.divider()
        with st.expander("🗑️ Ürün Sil"):
            if not df_urunler.empty:
                silinecek = st.selectbox("Silinecek Ürün", df_urunler['ad'].tolist(), key="sil_urun_sec")
                if st.button("🗑️ Ürünü Sil", type="secondary"):
                    try:
                        conn = get_conn()
                        # Ürünü sil
                        u_id = df_urunler[df_urunler['ad'] == silinecek]['id'].values[0]
                        new_urunler = df_urunler[df_urunler['id'] != u_id]
                        conn.update(worksheet="katki_urunler", data=new_urunler)
                        
                        # Reçeteden de sil
                        new_recete = df_recete[df_recete['urun_id'] != u_id]
                        conn.update(worksheet="katki_recete", data=new_recete)
                        
                        st.success(f"{silinecek} silindi.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Silme hatası: {e}")

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
                enzim_verisi = [{'ad': r['name'], 'doz': r['doz'], 'toplam': r['total']} 
                               for r in st.session_state.enzim_rows if r['name'].strip()]
                
                data_to_save = {
                    'uretim_adi': uretim_adi,
                    'un_ton': un_ton,
                    'bugday_hiz': bugday_hiz,
                    'randiman': randiman,
                    'dozaj_akis': dk_akis_gr,
                    'enzim_verisi_json': json.dumps(enzim_verisi, ensure_ascii=False),
                    'irmik_miktari': st.session_state.get('irmik_total', 0),
                    'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'kullanici': st.session_state.get('username', 'Unknown')
                }
                
                if add_data("enzim_receteleri", data_to_save):
                    st.success("✅ Reçete kaydedildi!")
                else:
                    st.error("Kayıt başarısız.")
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
            df = fetch_data("enzim_receteleri")
            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("Kayıt yok.")
        except Exception:
            st.info("Kayıt bulunamadı.")

def show_fire_maliyet_hesaplama():
    """Fire Maliyet Hesaplama Modülü"""
    
    # Session state başlangıç değerleri
    if 'fire_calc_state' not in st.session_state:
        st.session_state.fire_calc_state = {
            "bugday_tonaji": 100.0,
            "bugday_fiyati": 10000.0,
            "fire_yuzdesi": 0.38,
            "fire_satis_fiyati": 3000.0
        }
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 10px;">🔍 Buğday Fire Maliyet Hesaplama</h1>
        <p style="color: #666; font-size: 16px;">Buğday alımındaki fire (yabancı madde) oranının maliyete etkisini hesaplayın</p>
    </div>
    """, unsafe_allow_html=True)
    
    # GİRİŞ ALANLARI
    col_input1, col_input2 = st.columns([1, 1], gap="large")
    
    with col_input1:
        st.markdown("### 📉 Buğday Bilgileri")
        with st.container(border=True):
            bugday_tonaji = st.number_input(
                "Buğday Tonajı (Ton)", 
                min_value=0.0, step=1.0, 
                value=st.session_state.fire_calc_state["bugday_tonaji"],
                help="Toplam alınan buğday miktarı"
            )
            bugday_fiyati = st.number_input(
                "Buğday Alış Fiyatı (TL/Ton)", 
                min_value=0.0, step=10.0, 
                value=st.session_state.fire_calc_state["bugday_fiyati"],
                help="Buğdayın ton başına alış fiyatı"
            )
    
    with col_input2:
        st.markdown("### 🗑️ Fire Bilgileri")
        with st.container(border=True):
            fire_yuzdesi = st.number_input(
                "Fire Yüzdesi (%)", 
                min_value=0.0, max_value=100.0, step=0.01, 
                value=st.session_state.fire_calc_state["fire_yuzdesi"],
                format="%.2f",
                help="Analiz sonucu çıkan yabancı madde oranı (Örn: 0.38)"
            )
            fire_satis_fiyati = st.number_input(
                "Fire Satış Fiyatı (TL/Ton)", 
                min_value=0.0, step=10.0, 
                value=st.session_state.fire_calc_state["fire_satis_fiyati"],
                help="Ayrılan firenin (kavuz, taş vb.) satılabileceği fiyat"
            )

    # HESAPLAMA BUTONU
    if st.button("🧮 MALİYETİ HESAPLA", type="primary", use_container_width=True):
        st.session_state.fire_calc_state = {
            "bugday_tonaji": bugday_tonaji,
            "bugday_fiyati": bugday_fiyati,
            "fire_yuzdesi": fire_yuzdesi,
            "fire_satis_fiyati": fire_satis_fiyati
        }

        # Hesaplamalar
        toplam_bugday_maliyeti = bugday_tonaji * bugday_fiyati
        fire_miktari = bugday_tonaji * (fire_yuzdesi / 100)
        net_bugday_miktari = bugday_tonaji - fire_miktari
        fire_geliri = fire_miktari * fire_satis_fiyati
        net_maliyet = toplam_bugday_maliyeti - fire_geliri
        birim_maliyet = net_maliyet / net_bugday_miktari if net_bugday_miktari > 0 else 0
        fiyat_farki = birim_maliyet - bugday_fiyati

        st.divider()
        
        # SONUÇLAR
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1:
            st.metric("📦 Net Buğday Miktarı", f"{net_bugday_miktari:,.2f} Ton", delta=f"-{fire_miktari:,.2f} Ton Fire")
        with col_res2:
            st.metric("💰 Gerçek Maliyet (Ton)", f"{birim_maliyet:,.2f} TL", delta=f"+{fiyat_farki:,.2f} TL Fark", delta_color="inverse")
        with col_res3:
            st.metric("💵 Toplam Net Maliyet", f"{net_maliyet:,.2f} TL")

        st.markdown("### 📋 Detaylı Maliyet Tablosu")
        detay_data = {
            "Parametre": [
                "Toplam Buğday Tonajı",
                "Buğday Alış Fiyatı",
                "Toplam Buğday Maliyeti",
                "Fire Miktarı (Ton)",
                "Fire Satış Fiyatı",
                "Fire Geliri",
                "Net Buğday Miktarı",
                "NET MALİYET (Toplam)"
            ],
            "Değer": [
                f"{bugday_tonaji:,.2f} Ton",
                f"{bugday_fiyati:,.2f} TL",
                f"{toplam_bugday_maliyeti:,.2f} TL",
                f"{fire_miktari:,.2f} Ton",
                f"{fire_satis_fiyati:,.2f} TL",
                f"{fire_geliri:,.2f} TL",
                f"{net_bugday_miktari:,.2f} Ton",
                f"{net_maliyet:,.2f} TL"
            ]
        }
        st.table(pd.DataFrame(detay_data))
        st.success(f"✅ Hesaplama Tamamlandı! Buğdayın tonu size **{birim_maliyet:,.2f} TL**'ye gelmektedir.")


