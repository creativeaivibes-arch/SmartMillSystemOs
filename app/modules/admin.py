# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Database importları - clear_cache EKLENDİ
from app.core.database import fetch_data, add_data, update_data, get_conn, clear_cache

# ----------------------------------------------------------------
# 1. KULLANICI YÖNETİMİ
# ----------------------------------------------------------------
def show_user_management():
    """Kullanıcı ekleme, çıkarma ve listeleme"""
    st.markdown("### 👥 Kullanıcı Yönetimi")
    
    try:
        users = fetch_data("users")
        
        # Kullanıcı Listesi Tablosu
        if not users.empty:
            # Görsel güvenlik: Şifreleri gizle
            display_users = users.copy()
            if 'password' in display_users.columns:
                display_users['password'] = "********"
            
            st.dataframe(display_users, use_container_width=True)
        else:
            st.info("Sistemde kayıtlı kullanıcı bulunamadı.")

        st.divider()

        # Yeni Kullanıcı Ekleme Formu
        with st.expander("➕ Yeni Kullanıcı Ekle", expanded=False):
            with st.form("add_user_form"):
                col1, col2 = st.columns(2)
                new_user = col1.text_input("Kullanıcı Adı (Username)")
                new_pass = col2.text_input("Şifre", type="password")
                
                new_name = st.text_input("Ad Soyad")
                new_role = st.selectbox("Yetki Rolü", ["admin", "quality", "operations", "management"])
                
                submitted = st.form_submit_button("Kullanıcıyı Kaydet")
                
                if submitted:
                    if new_user and new_pass:
                        user_data = {
                            "username": new_user,
                            "password": new_pass,
                            "role": new_role,
                            "full_name": new_name,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if add_data("users", user_data):
                            st.success(f"✅ {new_user} kullanıcısı başarıyla eklendi!")
                            clear_cache("users") # Cache temizle
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Kayıt sırasında hata oluştu.")
                    else:
                        st.error("Kullanıcı adı ve şifre boş olamaz.")

    except Exception as e:
        st.error(f"Kullanıcı verileri yüklenirken hata oluştu: {e}")
# ----------------------------------------------------------------
# 2. SILO YÖNETİMİ
# ----------------------------------------------------------------
def show_silo_management():
    """Silo Konfigürasyonu - PROFESYONEL KART + TABLO YAPISI"""

    st.markdown("""
    <style>
    .silo-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5986 100%);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 8px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
    }
    .silo-card-un {
        background: linear-gradient(135deg, #1e5f3a 0%, #2d8659 100%);
    }
    .silo-name {
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-bottom: 8px;
        opacity: 0.95;
    }
    .silo-stats {
        font-size: 22px;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .silo-sub {
        font-size: 11px;
        opacity: 0.75;
        margin-bottom: 10px;
    }
    .silo-bar-bg {
        background: rgba(255,255,255,0.2);
        border-radius: 6px;
        height: 8px;
        overflow: hidden;
        margin-bottom: 4px;
    }
    .silo-bar-fill {
        height: 8px;
        border-radius: 6px;
        transition: width 0.5s ease;
    }
    .fill-low    { background: #4ade80; }
    .fill-mid    { background: #facc15; }
    .fill-high   { background: #f87171; }
    .fill-full   { background: #ef4444; }
    .silo-pct {
        font-size: 11px;
        opacity: 0.8;
        text-align: right;
    }
    .section-title {
        font-size: 13px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 20px 0 10px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid #e2e8f0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### 🏭 Silo Konfigürasyonu ve Tanımları")

    def render_silo_editor(filtered_df, editor_key):
        edited = st.data_editor(
            filtered_df,
            num_rows="dynamic",
            use_container_width=True,
            key=editor_key,
            column_config={
                "isim":         st.column_config.TextColumn("Silo Adı", required=True),
                "kapasite":     st.column_config.NumberColumn("Kapasite (Ton)", min_value=0, required=True, format="%.0f"),
                "silo_tipi":    st.column_config.TextColumn("Tip", disabled=True),
                "mevcut_miktar":st.column_config.NumberColumn("Mevcut (Ton)", disabled=True),
                "aciklama":     st.column_config.TextColumn("Açıklama / Konum")
            }
        )
        st.caption("ℹ️ Yeni satır eklemek için tablonun en altına tıklayın.")
        return edited

    def render_silo_cards(df_silo, kart_tipi="bugday"):
        """Üstteki özet kartları çizer"""
        if df_silo.empty:
            st.info("Bu tipte henüz silo tanımlanmamış.")
            return
        cols = st.columns(len(df_silo))
        for i, (_, row) in enumerate(df_silo.iterrows()):
            kapasite = float(row.get('kapasite', 1) or 1)
            mevcut   = float(row.get('mevcut_miktar', 0) or 0)
            bos      = max(0, kapasite - mevcut)
            oran     = min(mevcut / kapasite, 1.0) if kapasite > 0 else 0
            pct      = int(oran * 100)

            if pct < 40:   fill_class = "fill-low"
            elif pct < 70: fill_class = "fill-mid"
            elif pct < 90: fill_class = "fill-high"
            else:          fill_class = "fill-full"

            kart_class = "silo-card" if kart_tipi == "bugday" else "silo-card silo-card-un"

            with cols[i]:
                st.markdown(f"""
                <div class="{kart_class}">
                    <div class="silo-name">🏗️ {row['isim']}</div>
                    <div class="silo-stats">{mevcut:.0f} <span style="font-size:13px;opacity:0.7">/ {kapasite:.0f} Ton</span></div>
                    <div class="silo-sub">Boş Alan: {bos:.0f} Ton</div>
                    <div class="silo-bar-bg">
                        <div class="silo-bar-fill {fill_class}" style="width:{pct}%"></div>
                    </div>
                    <div class="silo-pct">%{pct} dolu</div>
                </div>
                """, unsafe_allow_html=True)

    try:
        df = fetch_data("silolar", force_refresh=True)

        if df.empty:
            st.warning("Tanımlı silo bulunamadı. Aşağıdan yeni silo ekleyebilirsiniz.")
            df = pd.DataFrame(columns=['isim', 'kapasite', 'silo_tipi', 'mevcut_miktar', 'aciklama'])

        # --- DATA TİPİ DÜZELTME ---
        if 'aciklama' not in df.columns:
            df['aciklama'] = ""
        df['aciklama'] = df['aciklama'].fillna("").astype(str)

        if 'silo_tipi' not in df.columns:
            df['silo_tipi'] = "BUĞDAY"
        df['silo_tipi'] = df['silo_tipi'].fillna("BUĞDAY").astype(str)

        config_cols = ['isim', 'kapasite', 'silo_tipi', 'mevcut_miktar', 'aciklama']
        for col in config_cols:
            if col not in df.columns:
                df[col] = "" if col == 'aciklama' else 0

        df_display = df[config_cols].copy()

        # ================================================================
        # TAB YAPISI
        # ================================================================
        tab_bugday, tab_un = st.tabs(["🌾 Buğday Siloları", "🏭 Un Siloları"])

        with tab_bugday:
            df_bugday = df_display[df_display['silo_tipi'] == "BUĞDAY"].copy()

            # --- BÖLÜM 1: ÖZET KARTLAR ---
            st.markdown('<div class="section-title">📊 Anlık Doluluk Durumu</div>', unsafe_allow_html=True)
            render_silo_cards(df_bugday, kart_tipi="bugday")

            # --- BÖLÜM 2: DÜZENLEME TABLOSU ---
            st.markdown('<div class="section-title">📝 Silo Ekle / Düzenle</div>', unsafe_allow_html=True)
            edited_bugday = render_silo_editor(df_bugday, "editor_bugday")

        with tab_un:
            df_un = df_display[df_display['silo_tipi'] == "UN"].copy()

            # --- BÖLÜM 1: ÖZET KARTLAR ---
            st.markdown('<div class="section-title">📊 Anlık Doluluk Durumu</div>', unsafe_allow_html=True)
            render_silo_cards(df_un, kart_tipi="un")

            # --- BÖLÜM 2: DÜZENLEME TABLOSU ---
            st.markdown('<div class="section-title">📝 Silo Ekle / Düzenle</div>', unsafe_allow_html=True)
            edited_un = render_silo_editor(df_un, "editor_un")

        # ================================================================
        # KAYDET BUTONU
        # ================================================================
        st.divider()
        if st.button("💾 Silo Değişikliklerini Kaydet", type="primary", use_container_width=True):
            try:
                conn = get_conn()
                original_df = fetch_data("silolar", force_refresh=True)
                final_rows = []

                # --- 1. DÜZENLEME / YENİ EKLEME ---
                for edited_df, silo_tipi in [(edited_bugday, "BUĞDAY"), (edited_un, "UN")]:
                    for _, new_row in edited_df.iterrows():
                        silo_name = new_row['isim']
                        if not silo_name or str(silo_name).strip() == "":
                            continue
                        match = original_df[original_df['isim'] == silo_name] if not original_df.empty else pd.DataFrame()

                        if not match.empty:
                            existing_data = match.iloc[0].to_dict()
                            existing_data.update(new_row.to_dict())
                            final_rows.append(existing_data)
                        else:
                            new_data = new_row.to_dict()
                            new_data['silo_tipi'] = silo_tipi
                            defaults = {'protein': 0, 'gluten': 0, 'rutubet': 0, 'sedim': 0, 'maliyet': 0, 'mevcut_miktar': 0}
                            for k, v in defaults.items():
                                if k not in new_data:
                                    new_data[k] = v
                            final_rows.append(new_data)

                # --- 2. SİLME KONTROLÜ ---
                edited_isimler = set()
                for edited_df in [edited_bugday, edited_un]:
                    for isim in edited_df['isim'].tolist():
                        if isim and str(isim).strip() != "":
                            edited_isimler.add(isim)

                if not original_df.empty:
                    silinen_df = original_df[~original_df['isim'].isin(edited_isimler)]
                    if not silinen_df.empty:
                        engellenen = []
                        for _, silo in silinen_df.iterrows():
                            miktar = float(silo.get('mevcut_miktar', 0) or 0)
                            if miktar > 0:
                                engellenen.append(f"**{silo['isim']}** ({miktar} Ton stok var)")

                        if engellenen:
                            st.error(
                                "⛔ Aşağıdaki silolar **stok içerdiği için silinemez!**\n\n"
                                + "\n".join([f"- {e}" for e in engellenen])
                                + "\n\nÖnce bu siloların stoğunu sıfırlayın."
                            )
                            st.stop()

                # --- 3. KAYDET ---
                df_to_save = pd.DataFrame(final_rows)
                conn.update(worksheet="silolar", data=df_to_save)
                clear_cache("silolar")
                st.cache_data.clear()

                st.success("✅ Silo konfigürasyonu başarıyla güncellendi!")
                time.sleep(1.5)
                st.rerun()

            except Exception as e:
                st.error(f"Kayıt sırasında hata oluştu: {str(e)}")

        # ================================================================
        # SİLME BÖLÜMÜ
        # ================================================================
        st.divider()
        st.markdown('<div class="section-title">🗑️ Silo Sil</div>', unsafe_allow_html=True)

        with st.expander("⚠️ Silo silmek için buraya tıklayın", expanded=False):
            try:
                df_fresh = fetch_data("silolar", force_refresh=True)
                if not df_fresh.empty and 'isim' in df_fresh.columns:
                    silo_listesi = df_fresh['isim'].tolist()
                    secilen_silo = st.selectbox("Silinecek Siloyu Seçin", silo_listesi, key="silme_secim")

                    if secilen_silo:
                        silo_row = df_fresh[df_fresh['isim'] == secilen_silo].iloc[0]
                        miktar   = float(silo_row.get('mevcut_miktar', 0) or 0)
                        kapasite = float(silo_row.get('kapasite', 0) or 0)

                        col_info, col_btn = st.columns([3, 1])
                        with col_info:
                            if miktar > 0:
                                st.error(f"⛔ **{secilen_silo}** silosu **{miktar} Ton** stok içeriyor. Silinemez!")
                            else:
                                st.warning(f"⚠️ **{secilen_silo}** ({kapasite} Ton kapasiteli) silosu kalıcı olarak silinecek.")

                        with col_btn:
                            if miktar == 0:
                                if 'silme_onayi' not in st.session_state:
                                    st.session_state.silme_onayi = False

                                if not st.session_state.silme_onayi:
                                    if st.button("🗑️ Sil", type="secondary", use_container_width=True):
                                        st.session_state.silme_onayi = True
                                        st.rerun()
                                else:
                                    st.error("Emin misiniz?")
                                    if st.button("✅ EVET, SİL", type="primary", use_container_width=True):
                                        conn = get_conn()
                                        df_guncell = df_fresh[df_fresh['isim'] != secilen_silo]
                                        conn.update(worksheet="silolar", data=df_guncell)
                                        clear_cache("silolar")
                                        st.cache_data.clear()
                                        st.session_state.silme_onayi = False
                                        st.success(f"✅ {secilen_silo} silindi.")
                                        time.sleep(1.5)
                                        st.rerun()
                                    if st.button("❌ İptal", use_container_width=True):
                                        st.session_state.silme_onayi = False
                                        st.rerun()
                else:
                    st.info("Silinecek silo bulunamadı.")
            except Exception as e:
                st.error(f"Silme bölümü yüklenemedi: {str(e)}")

    except Exception as e:
        st.error(f"Silo verileri yüklenemedi: {e}")
# ----------------------------------------------------------------
# 3. YEDEKLEME VE GERİ YÜKLEME
# ----------------------------------------------------------------
def show_backup_restore():
    """Veritabanı yedekleme işlemleri"""
    st.markdown("### 💾 Yedekleme ve Veri Güvenliği")
    
    st.info("""
    ℹ️ **Bilgi:** Sisteminiz **Google Sheets (Bulut)** altyapısı üzerinde çalışmaktadır.
    
    **Otomatik Koruma:**
    1. ☁️ Verileriniz Google sunucularında anlık saklanır.
    2. 🕒 Hata durumunda Google E-Tablolar'da **"Dosya > Sürüm Geçmişi"** menüsünden eski tarihe dönebilirsiniz.
    """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📥 Excel Yedeği Al")
        tablolar = {
            "Kullanıcılar": "users", 
            "Buğday Siloları": "silolar", 
            "Stok Hareketleri": "hareketler", 
            "Tavlı Analizler": "tavli_analiz"
        }
        selected_table = st.selectbox("İndirilecek Tablo", list(tablolar.keys()))
        
        if st.button("📥 Yedeği İndir", type="primary"):
            try:
                df = fetch_data(tablolar[selected_table])
                csv = df.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label=f"📄 {selected_table} CSV İndir",
                    data=csv,
                    file_name=f"{tablolar[selected_table]}_backup_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"İndirme hatası: {e}")
    
    with col2:
        st.subheader("📤 Geri Yükleme (Restore)")
        st.warning("⚠️ Geri yükleme işlemi mevcut verilerin üzerine yazar. Sadece acil durumlarda kullanın.")
        uploaded_file = st.file_uploader("Yedek Dosyası Seç", type=["csv", "xlsx"])
        if uploaded_file:
            st.error("Geri yükleme özelliği sistem güvenliği için bu panelden kapatılmıştır. Lütfen manuel yükleme yapın.")

# ----------------------------------------------------------------
# 4. SİSTEM LOGLARI
# ----------------------------------------------------------------
def show_system_logs():
    """Sistemdeki hareketleri ve hataları gösterir"""
    st.markdown("### 📜 Sistem Hareket Kayıtları")
    
    try:
        logs = fetch_data("hareketler")
        
        if not logs.empty:
            if 'tarih' in logs.columns:
                logs['tarih'] = pd.to_datetime(logs['tarih'])
                logs = logs.sort_values('tarih', ascending=False)
            
            filter_text = st.text_input("Loglarda Ara (Silo, İşlem Tipi vb.)")
            if filter_text:
                mask = logs.astype(str).apply(lambda x: x.str.contains(filter_text, case=False, na=False)).any(axis=1)
                logs = logs[mask]
            
            st.dataframe(logs, use_container_width=True)
        else:
            st.info("Henüz kaydedilmiş bir hareket logu yok.")
            
    except Exception as e:
        st.error(f"Loglar okunamadı: {e}")

# ----------------------------------------------------------------
# 5. DEBUG ARAÇLARI
# ----------------------------------------------------------------
def show_debug_tools():
    """Geliştirici ve hata ayıklama araçları"""
    st.markdown("### 🛠️ Geliştirici Araçları")
    
    tab_d1, tab_d2 = st.tabs(["🧹 Önbellek & Session", "ℹ️ Sistem Bilgisi"])
    
    with tab_d1:
        st.write("Sistem yavaşladığında veya veriler güncellenmediğinde kullanın.")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("🧹 Cache (Önbellek) Temizle", type="primary"):
                st.cache_data.clear()
                clear_cache() # Tüm özel cache'leri de sil
                st.success("Tüm veri önbelleği temizlendi! Veriler yeniden çekilecek.")
                time.sleep(1)
                st.rerun()
                
        with col_c2:
             if st.button("🔄 Session State Sıfırla"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
                
        st.write("**Aktif Session State Verileri:**")
        st.json(dict(st.session_state))

    with tab_d2:
        st.write(f"**Pandas Version:** {pd.__version__}")
        st.write(f"**Streamlit Version:** {st.__version__}")
        st.write(f"**Backend:** Google Sheets API")
        st.write(f"**Aktif Kullanıcı:** {st.session_state.get('username', 'Bilinmiyor')}")
        st.write(f"**Rol:** {st.session_state.get('user_role', 'Bilinmiyor')}")





