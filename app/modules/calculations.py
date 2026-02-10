import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import time

# --- DATABASE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn

# --- AYARLAR (CONFIG) - HARDCODED DEĞERLER BURAYA TAŞINDI ---
CALCULATIONS_CONFIG = {
    'DEFAULT_USD': 43.28,       # Varsayılan Dolar Kuru (DB boşsa)
    'DEFAULT_EUR': 50.08,       # Varsayılan Euro Kuru (DB boşsa)
    'MAX_ENZIM_ROWS': 10,       # Dozajlama modülündeki satır sayısı
    'DEFAULT_UN_TON': 100.0,    # Varsayılan üretim tonajı
    'DEFAULT_BUGDAY_HIZ': 12500.0, # Kg/Saat
    'DEFAULT_RANDIMAN': 70.0
}

# ==============================================================================
# BÖLÜM 3: ENZİM VE KATKI MODÜLLERİ
# ==============================================================================

def get_active_production_lots_for_enzyme():
    """Enzim reçetesi yazılacak aktif üretimleri (PRD) çeker."""
    try:
        # un_analiz tablosundaki ÜRETİM kayıtlarına bakıyoruz
        df = fetch_data("un_analiz", force_refresh=True)
        if df.empty: return []
        
        # Sadece ÜRETİM olanlar
        if 'islem_tipi' in df.columns:
            df = df[df['islem_tipi'] == "ÜRETİM"]
            
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
            df = df.sort_values('tarih', ascending=False)
            
        lot_list = []
        for _, row in df.iterrows():
            try:
                lot = str(row.get('lot_no', ''))
                if not lot or lot.lower() == 'nan': continue
                
                marka = row.get('un_markasi', '') or row.get('un_cinsi_marka', '-')
                tarih_str = row['tarih'].strftime('%d.%m %H:%M') if pd.notnull(row['tarih']) else "-"
                
                # Format: PRD-LOT | Marka | Tarih
                label = f"{lot} | {marka} | {tarih_str}"
                lot_list.append(label)
            except: continue
            
        return lot_list
    except: return []

def show_katki_maliyeti_modulu():
    """Katkı ve Enzim Maliyeti Modülü - Config Entegreli Final Versiyon"""
    
    # --- 1. VERİTABANI BAŞLATMA VE KONTROL ---
    df_kurlar = fetch_data("katki_kurlar")
    df_enzimler = fetch_data("katki_enzimler")
    df_urunler = fetch_data("katki_urunler")
    df_recete = fetch_data("katki_recete")
    df_arsiv = fetch_data("katki_maliyet_arsivi")

    # A) Tablo Başlatıcılar
    if df_recete.empty or 'urun_id' not in df_recete.columns:
        df_recete = pd.DataFrame(columns=['urun_id', 'enzim_id', 'gramaj'])

    if df_arsiv.empty or 'maliyet_tl' not in df_arsiv.columns:
        cols = ['id', 'tarih', 'urun_adi', 'maliyet_tl', 'maliyet_usd', 'maliyet_eur', 'usd_kuru', 'eur_kuru', 'detay_json']
        df_arsiv = pd.DataFrame(columns=cols)

    # B) Kurları Al (Config'den varsayılan, DB varsa oradan güncel)
    usd_val = CALCULATIONS_CONFIG['DEFAULT_USD']
    eur_val = CALCULATIONS_CONFIG['DEFAULT_EUR']
    
    if not df_kurlar.empty:
        try:
            if 'usd_tl' in df_kurlar.columns: usd_val = float(df_kurlar.iloc[0]['usd_tl'])
            if 'eur_tl' in df_kurlar.columns: eur_val = float(df_kurlar.iloc[0]['eur_tl'])
        except: pass
    else:
        add_data("katki_kurlar", {"id": 1, "usd_tl": usd_val, "eur_tl": eur_val})

    # --- 2. ARAYÜZ ---
    tab_hesap, tab_arsiv = st.tabs(["🧮 Maliyet Hesaplayıcı & Reçete", "📜 Geçmiş Maliyet Kayıtları"])

    # ==========================================================================
    # SEKME 1: HESAPLAMA VE DÜZENLEME
    # ==========================================================================
    with tab_hesap:
        st.markdown("""
        <div style="background-color:#e0f2fe; padding:15px; border-radius:10px; margin-bottom:20px; border-left:5px solid #0284c7;">
            <h3 style="color:#0369a1; margin:0;">🧪 Katkı & Enzim Maliyet Analizi</h3>
            <p style="margin:0; color:#0c4a6e;">Anlık kur ile 50kg çuval başı maliyet simülasyonu</p>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1, 1], gap="small")
        
        with col1:
            with st.container(border=True):
                st.markdown("##### 💱 Döviz Kurları")
                c_kur1, c_kur2 = st.columns(2)
                
                # Etiketleri görünür yaptık ve bayrak ekledik
                input_usd = c_kur1.number_input("🇺🇸 USD ($)", value=usd_val, format="%.2f")
                input_eur = c_kur2.number_input("🇪🇺 EUR (€)", value=eur_val, format="%.2f")
                
                if st.button("Güncelle", use_container_width=True, key="btn_kur_update"):
                    with st.spinner("Kur güncelleniyor..."):
                        conn = get_conn()
                        new_kur_df = pd.DataFrame([{"id": 1, "usd_tl": input_usd, "eur_tl": input_eur}])
                        conn.update(worksheet="katki_kurlar", data=new_kur_df)
                        st.success("Kurlar güncellendi")
                        time.sleep(0.5)
                        st.rerun()
        
        with col2:
            with st.container(border=True):
                st.markdown("##### 🧪 Yeni Katkı")
                with st.popover("Ekleme Paneli", use_container_width=True):
                    e_ad = st.text_input("Katkı Adı", key="new_enzim_name").strip().upper()
                    e_birim = st.selectbox("Para Birimi", ["EUR", "USD", "TL"], key="new_enzim_currency")
                    e_fiyat = st.number_input("Kg Fiyatı", min_value=0.0, format="%.3f", key="new_enzim_price")
                    
                    if st.button("Kaydet", key="btn_add_enzim"):
                        if e_ad:
                            if not df_enzimler.empty and e_ad in df_enzimler['ad'].values:
                                st.error(f"'{e_ad}' zaten kayıtlı!")
                            else:
                                new_id = 1 if df_enzimler.empty else df_enzimler['id'].max() + 1
                                add_data("katki_enzimler", {"id": int(new_id), "ad": e_ad, "fiyat": e_fiyat, "para_birimi": e_birim})
                                st.success(f"{e_ad} eklendi")
                                st.rerun()

        with col3:
            with st.container(border=True):
                st.markdown("##### 🥖 Yeni Ürün")
                with st.popover("Ürün Ekle", use_container_width=True):
                    u_ad = st.text_input("Ürün Adı", key="new_prod_name").strip().upper()
                    if st.button("Kaydet", key="btn_add_product"):
                        if u_ad:
                            if not df_urunler.empty and u_ad in df_urunler['ad'].values:
                                st.error(f"'{u_ad}' zaten kayıtlı!")
                            else:
                                new_id = 1 if df_urunler.empty else df_urunler['id'].max() + 1
                                add_data("katki_urunler", {"id": int(new_id), "ad": u_ad})
                                st.success(f"{u_ad} eklendi")
                                st.rerun()

        st.markdown("### 📝 Reçete Gramaj Girişi (gr / 50kg Çuval)")
        
        # Duplicate temizliği (Güvenlik)
        if not df_enzimler.empty: df_enzimler = df_enzimler.drop_duplicates(subset=['ad'], keep='last')
        if not df_urunler.empty: df_urunler = df_urunler.drop_duplicates(subset=['ad'], keep='last')
        
        if not df_enzimler.empty and not df_urunler.empty:
            table_data = df_enzimler[['id', 'ad', 'fiyat', 'para_birimi']].copy()
            table_data.columns = ['id', 'HAMMADDE', 'FİYAT', 'KUR']
            
            # Reçete matrisini oluştur
            for _, u_row in df_urunler.iterrows():
                u_id = u_row['id']
                col_values = []
                for _, e_row in table_data.iterrows():
                    e_id = e_row['id']
                    gramaj = 0.0
                    if not df_recete.empty:
                        match = df_recete[(df_recete['urun_id'] == u_id) & (df_recete['enzim_id'] == e_id)]
                        if not match.empty:
                            gramaj = float(match.iloc[-1]['gramaj'])
                    col_values.append(gramaj)
                table_data[u_row['ad']] = col_values

            column_config = {
                "id": None,
                "HAMMADDE": st.column_config.TextColumn("HAMMADDE", disabled=True, width="medium"),
                "FİYAT": st.column_config.NumberColumn("BİRİM FİYAT", format="%.2f", width="small"),
                "KUR": st.column_config.SelectboxColumn("KUR", options=["EUR", "USD", "TL"], width="small"),
            }
            for u_ad in df_urunler['ad']:
                column_config[u_ad] = st.column_config.NumberColumn(f"{u_ad} (gr)", format="%.1f")

            edited_df = st.data_editor(
                table_data,
                use_container_width=True,
                hide_index=True,
                column_config=column_config,
                num_rows="fixed",
                key="recete_editor_main"
            )

            col_save, col_delete, _ = st.columns([1.5, 1.5, 3])
            
            if col_save.button("💾 Değişiklikleri Kaydet", type="primary", use_container_width=True):
                conn = get_conn()
                updated_enzimler = df_enzimler.copy()
                # 1. Enzim Fiyatlarını Güncelle
                for idx, row in edited_df.iterrows():
                    mask = updated_enzimler['id'] == row['id']
                    if mask.any():
                        updated_enzimler.loc[mask, 'fiyat'] = row['FİYAT']
                        updated_enzimler.loc[mask, 'para_birimi'] = row['KUR']
                conn.update(worksheet="katki_enzimler", data=updated_enzimler)
                
                # 2. Reçete Gramajlarını Güncelle
                new_records = []
                for _, u_row in df_urunler.iterrows():
                    u_id = u_row['id']
                    u_ad = u_row['ad']
                    for _, row in edited_df.iterrows():
                        e_id = row['id']
                        gramaj = float(row.get(u_ad, 0))
                        if gramaj > 0:
                            new_records.append({'urun_id': int(u_id), 'enzim_id': int(e_id), 'gramaj': gramaj})
                
                if new_records:
                    conn.update(worksheet="katki_recete", data=pd.DataFrame(new_records))
                else:
                    # Boş reçete kaydet (temizle)
                    conn.update(worksheet="katki_recete", data=pd.DataFrame(columns=['urun_id', 'enzim_id', 'gramaj']))
                
                st.success("✅ Veriler güncellendi!")
                time.sleep(1)
                st.rerun()

            with col_delete:
                with st.popover("🗑️ Tanım Sil", use_container_width=True):
                    type_to_del = st.radio("Silinecek:", ["Ürün", "Katkı/Enzim"])
                    if type_to_del == "Ürün":
                        to_del = st.selectbox("Ürün Seç:", df_urunler['ad'].unique())
                        if st.button("🔥 Sil"):
                            conn = get_conn()
                            # Ürünü sil
                            df_u_new = df_urunler[df_urunler['ad'] != to_del]
                            conn.update(worksheet="katki_urunler", data=df_u_new)
                            # Ürüne ait reçeteyi sil
                            target_id = df_urunler[df_urunler['ad'] == to_del]['id'].iloc[0]
                            df_r_new = df_recete[df_recete['urun_id'] != target_id]
                            conn.update(worksheet="katki_recete", data=df_r_new)
                            st.rerun()
                    else:
                        to_del = st.selectbox("Katkı Seç:", df_enzimler['ad'].unique())
                        if st.button("🔥 Sil"):
                            conn = get_conn()
                            # Enzimi sil
                            df_e_new = df_enzimler[df_enzimler['ad'] != to_del]
                            conn.update(worksheet="katki_enzimler", data=df_e_new)
                            # Enzime ait reçeteyi sil
                            target_id = df_enzimler[df_enzimler['ad'] == to_del]['id'].iloc[0]
                            df_r_new = df_recete[df_recete['enzim_id'] != target_id]
                            conn.update(worksheet="katki_recete", data=df_r_new)
                            st.rerun()

            st.divider()
            st.subheader("💰 Birim Çuval Maliyet Analizi (50 Kg)")
            
            # --- MALİYET HESAPLAMA MOTORU ---
            maliyet_listesi = []
            for _, u_row in df_urunler.iterrows():
                u_ad = u_row['ad']
                toplam_tl = 0.0
                detaylar = []
                if u_ad in edited_df.columns:
                    for _, row in edited_df.iterrows():
                        gramaj = float(row[u_ad])
                        if gramaj > 0:
                            birim_fiyat = float(row['FİYAT'])
                            kur = row['KUR']
                            # Kur çevrimi
                            if kur == "USD": carpan = input_usd
                            elif kur == "EUR": carpan = input_eur
                            else: carpan = 1.0
                            
                            tutar_tl = (gramaj / 1000) * birim_fiyat * carpan
                            toplam_tl += tutar_tl
                            detaylar.append({
                                "hammadde": row['HAMMADDE'],
                                "gramaj": gramaj,
                                "birim_fiyat": birim_fiyat,
                                "kur": kur,
                                "tutar_tl": tutar_tl
                            })
                    maliyet_listesi.append({
                        "Ürün Adı": u_ad,
                        "Maliyet (TL)": toplam_tl,
                        "Maliyet (USD)": toplam_tl / input_usd if input_usd > 0 else 0,
                        "Maliyet (EUR)": toplam_tl / input_eur if input_eur > 0 else 0,
                        "detaylar": detaylar
                    })
            
            df_sonuc = pd.DataFrame(maliyet_listesi)
            if not df_sonuc.empty:
                st.dataframe(
                    df_sonuc[['Ürün Adı', 'Maliyet (TL)', 'Maliyet (USD)', 'Maliyet (EUR)']],
                    use_container_width=True,
                    column_config={
                        "Maliyet (TL)": st.column_config.NumberColumn(format="%.2f ₺"),
                        "Maliyet (USD)": st.column_config.NumberColumn(format="%.2f $"),
                        "Maliyet (EUR)": st.column_config.NumberColumn(format="%.2f €"),
                    }
                )
                
                col_archive, _ = st.columns([1, 2])
                if col_archive.button("✅ Bu Maliyet Tablosunu Arşivle", type="primary", use_container_width=True):
                    try:
                        conn = get_conn()
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        unique_id_base = int(datetime.now().timestamp())
                        current_archive = df_arsiv.copy()
                        new_rows = []
                        for idx, item in enumerate(maliyet_listesi):
                            if item["Maliyet (TL)"] > 0:
                                new_rows.append({
                                    "id": unique_id_base + idx,
                                    "tarih": timestamp,
                                    "urun_adi": item["Ürün Adı"],
                                    "maliyet_tl": float(item["Maliyet (TL)"]),
                                    "maliyet_usd": float(item["Maliyet (USD)"]),
                                    "maliyet_eur": float(item["Maliyet (EUR)"]),
                                    "usd_kuru": float(input_usd),
                                    "eur_kuru": float(input_eur),
                                    "detay_json": json.dumps(item["detaylar"], ensure_ascii=False)
                                })
                        if new_rows:
                            new_df = pd.DataFrame(new_rows)
                            final_archive = pd.concat([current_archive, new_df], ignore_index=True)
                            conn.update(worksheet="katki_maliyet_arsivi", data=final_archive)
                            st.success("✅ Başarıyla Arşivlendi!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Maliyeti 0 olan ürünler arşivlenmez.")
                    except Exception as e:
                        st.error(f"Arşivleme hatası: {e}")
            else:
                st.info("Hesaplanacak ürün yok.")
        else:
            st.warning("Lütfen önce katkı ve ürün tanımlayın.")

    # ==========================================================================
    # SEKME 2: ARŞİV VE GEÇMİŞ
    # ==========================================================================
    with tab_arsiv:
        st.markdown("### 📜 Geçmiş Maliyet Kayıtları")
        
        df_arsiv_guncel = fetch_data("katki_maliyet_arsivi")
        
        if not df_arsiv_guncel.empty and 'tarih' in df_arsiv_guncel.columns:
            df_arsiv_guncel['tarih'] = pd.to_datetime(df_arsiv_guncel['tarih'], errors='coerce')
            df_show = df_arsiv_guncel.dropna(subset=['tarih']).sort_values('tarih', ascending=False)
            
            if not df_show.empty:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    tarihler = df_show['tarih'].dt.date.unique()
                    secilen_tarih = st.selectbox("Tarih Filtresi", ["Tümü"] + sorted(list(tarihler), reverse=True))
                with col_f2:
                    urunler = df_show['urun_adi'].unique()
                    secilen_urun = st.selectbox("Ürün Filtresi", ["Tümü"] + sorted(list(urunler)))
                
                if secilen_tarih != "Tümü":
                    df_show = df_show[df_show['tarih'].dt.date == secilen_tarih]
                if secilen_urun != "Tümü":
                    df_show = df_show[df_show['urun_adi'] == secilen_urun]
                
                st.dataframe(
                    df_show[['tarih', 'urun_adi', 'maliyet_tl', 'maliyet_usd', 'maliyet_eur']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "tarih": st.column_config.DatetimeColumn("Tarih", format="DD.MM.YYYY HH:mm"),
                        "maliyet_tl": st.column_config.NumberColumn("TL", format="%.2f ₺"),
                        "maliyet_usd": st.column_config.NumberColumn("USD", format="%.2f $"),
                        "maliyet_eur": st.column_config.NumberColumn("EUR", format="%.2f €"),
                    }
                )
                
                st.divider()
                
                col_detay, col_sil = st.columns([3, 1])
                
                with col_detay:
                    st.markdown("#### 🔍 Detay İncele")
                    def format_func_guvenli(x):
                        try:
                            ts = x.get('tarih')
                            if pd.isnull(ts): return f"{x['urun_adi']} - (Tarih Yok)"
                            return f"{x['urun_adi']} - {ts.strftime('%d.%m.%Y %H:%M')} (ID: {x['id']})"
                        except: return f"Kayıt {x.get('id', '?')}"

                    secilen_kayit = st.selectbox("Kayıt Seç:", df_show.to_dict('records'), format_func=format_func_guvenli)
                    
                    if secilen_kayit:
                        try:
                            detay_veri = json.loads(secilen_kayit['detay_json'])
                            df_detay = pd.DataFrame(detay_veri)
                            st.info(f"Kurlar: 1$={secilen_kayit.get('usd_kuru')} | 1€={secilen_kayit.get('eur_kuru')}")
                            st.dataframe(df_detay, use_container_width=True)
                        except: st.error("Veri detayı okunamadı.")
                
                with col_sil:
                    st.markdown("#### 🗑️ Sil")
                    st.write("")
                    if secilen_kayit:
                        if st.button("Seçili Kaydı Sil", type="primary"):
                            try:
                                conn = get_conn()
                                target_id = secilen_kayit['id']
                                df_new_archive = df_arsiv_guncel[df_arsiv_guncel['id'] != target_id]
                                conn.update(worksheet="katki_maliyet_arsivi", data=df_new_archive)
                                st.success("Silindi!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e: st.error(f"Hata: {e}")
            else: st.info("Gösterilecek geçerli kayıt bulunamadı.")
        else: st.info("Henüz arşiv kaydı yok.")
            
def show_enzim_dozajlama():
    """Un Geliştirici Enzim Dozajlama - PRD LINKING VE ENZ-ID EKLENDİ"""
    
    # Session State Başlatma
    if 'enzim_last_data' not in st.session_state:
        st.session_state.enzim_last_data = {
            'un_ton': CALCULATIONS_CONFIG['DEFAULT_UN_TON'],
            'bugday_hiz': CALCULATIONS_CONFIG['DEFAULT_BUGDAY_HIZ'],
            'randiman': CALCULATIONS_CONFIG['DEFAULT_RANDIMAN'],
            'dk_akis_gr': 30.0,
            'enzim_rows': [{'name': '', 'doz': '', 'total': 0} for _ in range(CALCULATIONS_CONFIG['MAX_ENZIM_ROWS'])]
        }
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 5px;">🧬 Akıllı Enzim & Reçete Yönetimi</h1>
        <p style="color: #666; margin:0;">Üretim partisine özel dozajlama ve izlenebilirlik kaydı</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_left, col_right = st.columns([1, 1.5], gap="large")
    
    # --- 1. ÜRETİM VE KİMLİK SEÇİMİ ---
    with col_left:
        st.markdown("### 🔗 1. Üretim Bağlantısı")
        with st.container(border=True):
            # YENİ: Otomatik Enzim ID
            enzim_id = f"ENZ-{datetime.now().strftime('%y%m%d%H%M')}"
            st.info(f"🆔 **Reçete Kimliği:** `{enzim_id}`")
            
            # YENİ: Üretim Seçimi (PRD Linki)
            # Dosyanın tepesindeki yardımcı fonksiyonu kullanıyoruz
            uretim_listesi = get_active_production_lots_for_enzyme()
            secilen_uretim = st.selectbox(
                "Hangi Üretime Uygulanacak? (PRD) *",
                ["(Genel / Stoktan)"] + uretim_listesi
            )
            
            uretim_kodu = "GENEL"
            uretim_adi_display = "Stoktan"
            
            if secilen_uretim != "(Genel / Stoktan)":
                try: 
                    # Format: PRD-LOT | Marka | Tarih
                    parts = secilen_uretim.split(' | ')
                    uretim_kodu = parts[0].strip()
                    if len(parts) > 1: uretim_adi_display = parts[1]
                except: pass
                st.caption(f"🔗 Bağlı Lot: **{uretim_kodu}**")

            st.divider()
            
            last_data = st.session_state.enzim_last_data
            
            col1, col2 = st.columns(2)
            with col1:
                un_ton = st.number_input("Hedef Un (Ton)", min_value=0.1, value=float(last_data['un_ton']), step=0.1)
            with col2:
                bugday_hiz = st.number_input("Buğday Hızı (kg/s)", min_value=100.0, value=float(last_data['bugday_hiz']), step=100.0)
            
            col3, col4 = st.columns(2)
            with col3:
                randiman = st.number_input("Randıman (%)", min_value=1.0, max_value=100.0, value=float(last_data['randiman']), step=0.1)
            with col4:
                dk_akis_gr = st.number_input("Dozaj Akışı (gr/dk)", min_value=1.0, value=float(last_data['dk_akis_gr']), step=1.0)

            # Hesaplamalar
            try:
                cuval_sayisi = (un_ton * 1000) / 50
                uretim_ton_saat = bugday_hiz * (randiman / 100) / 1000
                toplam_dakika = (un_ton / uretim_ton_saat * 60) if uretim_ton_saat > 0 else 0
                toplam_gereken_karisim = toplam_dakika * dk_akis_gr
            except:
                cuval_sayisi = 0
                toplam_gereken_karisim = 0
                toplam_dakika = 0
            
            saat = int(toplam_dakika // 60)
            dakika = int(toplam_dakika % 60)
            st.info(f"📦 Çuval: **{cuval_sayisi:,.0f}** | ⏳ Süre: **{saat}s {dakika}dk**")

    # --- 2. ENZİM LİSTESİ ---
    with col_right:
        st.markdown("### 🧪 2. Reçete İçeriği (gr/çuval)")
        
        if 'enzim_rows' not in st.session_state:
            st.session_state.enzim_rows = st.session_state.enzim_last_data['enzim_rows']
            
        toplam_enzim_agirligi = 0
        
        # Başlıklar
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.caption("Katkı Adı")
        c2.caption("Doz (gr/50kg)")
        c3.caption("Toplam (gr)")

        for i in range(CALCULATIONS_CONFIG['MAX_ENZIM_ROWS']):
            cols = st.columns([2, 1, 1])
            with cols[0]:
                st.session_state.enzim_rows[i]['name'] = st.text_input(f"E{i}", value=st.session_state.enzim_rows[i]['name'], key=f"en_{i}", label_visibility="collapsed", placeholder="Katkı Adı")
            with cols[1]:
                doz_val = st.text_input(f"D{i}", value=st.session_state.enzim_rows[i]['doz'], key=f"ed_{i}", label_visibility="collapsed", placeholder="0")
                st.session_state.enzim_rows[i]['doz'] = doz_val
            with cols[2]:
                try:
                    d_float = float(doz_val.replace(',', '.')) if doz_val.strip() else 0.0
                    satir_toplam = cuval_sayisi * d_float
                    st.session_state.enzim_rows[i]['total'] = satir_toplam
                    toplam_enzim_agirligi += satir_toplam
                    if satir_toplam > 0: st.markdown(f"**:green[{satir_toplam:,.0f}]**")
                except: st.write("-")

        irmik_miktari = max(0, toplam_gereken_karisim - toplam_enzim_agirligi)
        
        c_res1, c_res2 = st.columns(2)
        with c_res1: st.metric("🧪 Aktif Madde", f"{toplam_enzim_agirligi:,.0f} gr")
        with c_res2: st.metric("🧱 İrmik Dolgu", f"{irmik_miktari:,.0f} gr")

    st.divider()
    col_save, _ = st.columns([1, 2])
    
    with col_save:
        if st.button("✅ REÇETEYİ KAYDET (ENZ-ID)", type="primary", use_container_width=True):
            try:
                # Dolu satırları filtrele
                enzim_verisi = [{'ad': r['name'], 'doz': r['doz'], 'toplam': r['total']} 
                               for r in st.session_state.enzim_rows if r['name'].strip()]
                
                if not enzim_verisi:
                    st.error("⚠️ En az bir katkı maddesi giriniz.")
                else:
                    data_to_save = {
                        'enzim_id': enzim_id,       # YENİ: ID
                        'uretim_kodu': uretim_kodu, # YENİ: PRD Linki (PRD-...)
                        'uretim_adi': uretim_adi_display, # Eski uyumluluk için isim
                        'un_ton': un_ton,
                        'bugday_hiz': bugday_hiz,
                        'randiman': randiman,
                        'dozaj_akis': dk_akis_gr,
                        'enzim_verisi_json': json.dumps(enzim_verisi, ensure_ascii=False),
                        'irmik_miktari': irmik_miktari,
                        'tarih': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'kullanici': st.session_state.get('username', 'Sistem')
                    }
                    
                    if add_data("enzim_receteleri", data_to_save):
                        st.success(f"✅ Reçete Kaydedildi! Kimlik: {enzim_id}")
                        st.balloons()
                        # Son verileri hatırla
                        st.session_state.enzim_last_data.update({
                            'un_ton': un_ton, 'bugday_hiz': bugday_hiz,
                            'randiman': randiman, 'dk_akis_gr': dk_akis_gr,
                            'enzim_rows': st.session_state.enzim_rows.copy()
                        })
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("Kayıt hatası.")
            except Exception as e:
                st.error(f"Hata: {e}")
def show_fire_maliyet_hesaplama():
    """Fire Maliyet Hesaplama Modülü - NET ZARAR GÖSTERGELİ & TR FORMATLI"""
    
    # --- YARDIMCI: TÜRKÇE PARA FORMATI ---
    def tr_fmt(deger):
        """12345.67 -> 12.345,67 formatına çevirir"""
        try:
            # Önce standart format (12,345.67)
            s = "{:,.2f}".format(float(deger))
            # Sonra karakterleri değiştir (12.345,67)
            return s.replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "0,00"

    if 'fire_calc_state' not in st.session_state:
        st.session_state.fire_calc_state = {
            "bugday_tonaji": 27.0,
            "bugday_fiyati": 14500.0,
            "fire_yuzdesi": 5.00,
            "fire_satis_fiyati": 13500.0
        }
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 10px;">🔥 Buğday Fire ve Zarar Analizi</h1>
    </div>
    """, unsafe_allow_html=True)
    
    col_input1, col_input2 = st.columns([1, 1], gap="large")
    
    with col_input1:
        st.markdown("### 📉 Buğday Bilgileri")
        with st.container(border=True):
            bugday_tonaji = st.number_input("Buğday Tonajı (Ton)", min_value=0.0, step=1.0, value=float(st.session_state.fire_calc_state["bugday_tonaji"]))
            bugday_fiyati = st.number_input("Buğday Alış Fiyatı (TL/Ton)", min_value=0.0, step=10.0, value=float(st.session_state.fire_calc_state["bugday_fiyati"]))
    
    with col_input2:
        st.markdown("### 🗑️ Fire Bilgileri")
        with st.container(border=True):
            fire_yuzdesi = st.number_input("Fire Yüzdesi (%)", min_value=0.0, max_value=100.0, step=0.01, value=float(st.session_state.fire_calc_state["fire_yuzdesi"]), format="%.2f")
            fire_satis_fiyati = st.number_input("Fire/Kepek Satış Fiyatı (TL/Ton)", min_value=0.0, step=10.0, value=float(st.session_state.fire_calc_state["fire_satis_fiyati"]), help="Bu fireyi kaça satıyorsunuz?")

    if st.button("🧮 ZARAR ANALİZİNİ HESAPLA", type="primary", use_container_width=True):
        st.session_state.fire_calc_state = {
            "bugday_tonaji": bugday_tonaji,
            "bugday_fiyati": bugday_fiyati,
            "fire_yuzdesi": fire_yuzdesi,
            "fire_satis_fiyati": fire_satis_fiyati
        }

        # 1. Temel Hesaplamalar
        toplam_odememiz_gereken = bugday_tonaji * bugday_fiyati
        fire_miktari = bugday_tonaji * (fire_yuzdesi / 100)
        net_bugday_miktari = bugday_tonaji - fire_miktari
        
        # 2. Fire Geliri ve Net Maliyet
        fire_geliri = fire_miktari * fire_satis_fiyati
        net_cebimizden_cikan = toplam_odememiz_gereken - fire_geliri
        
        # 3. Birim Maliyet (Gerçekleşen)
        birim_maliyet = net_cebimizden_cikan / net_bugday_miktari if net_bugday_miktari > 0 else 0
        fiyat_farki = birim_maliyet - bugday_fiyati
        
        # 4. NET ZARAR HESABI (Buğday Fiyatına alıp Fire Fiyatına sattığımız aradaki fark)
        fireye_odenen_para = fire_miktari * bugday_fiyati
        net_zarar_tutari = fireye_odenen_para - fire_geliri

        st.divider()
        st.markdown("### 📊 Sonuçlar")
        
        # İlk Satır: Miktar ve Birim Maliyet (TÜRKÇE FORMATLI)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                "📦 Net Buğday", 
                f"{tr_fmt(net_bugday_miktari)} Ton", 
                delta=f"-{tr_fmt(fire_miktari)} Ton Fire", 
                delta_color="inverse"
            )
        with c2:
            st.metric(
                "💰 Gerçek Ton Maliyeti", 
                f"{tr_fmt(birim_maliyet)} TL", 
                delta=f"+{tr_fmt(fiyat_farki)} TL Fark", 
                delta_color="inverse"
            )
        with c3:
            st.metric(
                "💵 Toplam Net Maliyet", 
                f"{tr_fmt(net_cebimizden_cikan)} TL"
            )
            
        st.divider()
        
        # İkinci Satır: NET ZARAR VURGUSU (TÜRKÇE FORMATLI)
        st.markdown(f"""
        <div style='background-color: #fee2e2; padding: 20px; border-radius: 10px; border: 1px solid #ef4444; text-align: center;'>
            <h3 style='color: #991b1b; margin:0;'>🚨 TOPLAM FİRE ZARARI</h3>
            <h1 style='color: #dc2626; margin: 10px 0;'>-{tr_fmt(net_zarar_tutari)} TL</h1>
            <p style='color: #7f1d1d; margin:0;'>Bu fire olmasaydı (veya %0 olsaydı) cebinizde kalacak olan tutar.</p>
        </div>
        """, unsafe_allow_html=True)



















