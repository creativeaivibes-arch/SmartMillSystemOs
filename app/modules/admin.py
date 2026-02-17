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
    """Kullanıcı Yönetimi - Profesyonel Kart Görünümü"""

    st.markdown("""
    <style>
    .user-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        transition: box-shadow 0.2s;
    }
    .user-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }

    .user-avatar {
        width: 44px; height: 44px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 18px; font-weight: 700;
        margin-bottom: 10px;
        color: white;
    }
    .avatar-admin      { background: linear-gradient(135deg, #667eea, #764ba2); }
    .avatar-quality    { background: linear-gradient(135deg, #11998e, #38ef7d); }
    .avatar-operations { background: linear-gradient(135deg, #f093fb, #f5576c); }
    .avatar-management { background: linear-gradient(135deg, #4facfe, #00f2fe); }
    .avatar-default    { background: linear-gradient(135deg, #a8a8a8, #6e6e6e); }

    .user-name {
        font-size: 15px; font-weight: 700;
        color: #1a202c; margin-bottom: 2px;
    }
    .user-fullname {
        font-size: 12px; color: #718096; margin-bottom: 8px;
    }
    .role-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .role-admin      { background: #e9d8fd; color: #553c9a; }
    .role-quality    { background: #c6f6d5; color: #276749; }
    .role-operations { background: #fed7d7; color: #9b2335; }
    .role-management { background: #bee3f8; color: #2a69ac; }
    .role-default    { background: #e2e8f0; color: #4a5568; }

    .user-meta {
        font-size: 11px; color: #a0aec0;
        margin-top: 8px; padding-top: 8px;
        border-top: 1px solid #f0f4f8;
    }
    .aktif-badge {
        display: inline-block;
        background: #c6f6d5; color: #276749;
        font-size: 10px; font-weight: 700;
        padding: 2px 8px; border-radius: 20px;
        margin-left: 6px; vertical-align: middle;
    }
    .um-header {
        display: flex; align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    .um-title {
        font-size: 22px; font-weight: 800;
        color: #1a202c;
    }
    .um-count {
        background: #edf2f7; color: #4a5568;
        font-size: 13px; font-weight: 600;
        padding: 6px 14px; border-radius: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Rol → renk/avatar eşlemesi
    ROL_CONFIG = {
        "admin":      {"badge": "role-admin",      "avatar": "avatar-admin",      "label": "Sistem Yöneticisi", "ikon": "👑"},
        "quality":    {"badge": "role-quality",    "avatar": "avatar-quality",    "label": "Kalite Kontrol",    "ikon": "🔬"},
        "operations": {"badge": "role-operations", "avatar": "avatar-operations", "label": "Operasyon",         "ikon": "⚙️"},
        "management": {"badge": "role-management", "avatar": "avatar-management", "label": "Yönetim",          "ikon": "📊"},
    }

    try:
        users = fetch_data("users")
        aktif_kullanici = st.session_state.get('username', '')

        # ================================================================
        # BAŞLIK
        # ================================================================
        toplam = len(users) if not users.empty else 0
        st.markdown(f"""
        <div class="um-header">
            <div class="um-title">👥 Kullanıcı Yönetimi</div>
            <div class="um-count">Toplam {toplam} Kullanıcı</div>
        </div>
        """, unsafe_allow_html=True)

        # ================================================================
        # KULLANICI KARTLARI
        # ================================================================
        if not users.empty:
            # Sütun isimlerini normalize et
            col_map = {
                'kullanici_adi': 'username',
                'sifre_hash': 'password',
                'rol': 'role',
                'ad_soyad': 'full_name',
            }
            for eski, yeni in col_map.items():
                if eski in users.columns and yeni not in users.columns:
                    users = users.rename(columns={eski: yeni})

            max_cols = 4
            user_list = [users.iloc[i:i+max_cols] for i in range(0, len(users), max_cols)]

            for grup in user_list:
                cols = st.columns(len(grup))
                for i, (_, row) in enumerate(grup.iterrows()):
                    username  = str(row.get('username', row.get('kullanici_adi', '?')))
                    full_name = str(row.get('full_name', row.get('ad_soyad', '')))
                    rol       = str(row.get('role', row.get('rol', 'default'))).lower()
                    email     = str(row.get('email', ''))
                    created   = str(row.get('created_at', ''))[:10]

                    cfg         = ROL_CONFIG.get(rol, {"badge": "role-default", "avatar": "avatar-default", "label": rol.capitalize(), "ikon": "👤"})
                    harf        = username[0].upper()
                    aktif_html  = '<span class="aktif-badge">● Aktif</span>' if username == aktif_kullanici else ''

                    with cols[i]:
                        email_html   = f'📧 {email}' if email and email not in ('None', 'nan', '') else ''
                        created_html = f'📅 {created}' if created and created not in ('None', 'nan', '') else ''
                        meta_html    = ' &nbsp; '.join(filter(None, [email_html, created_html]))

                        st.markdown(f"""
                        <div class="user-card">
                            <div class="user-avatar {cfg['avatar']}">{harf}</div>
                            <div class="user-name">{username}{aktif_html}</div>
                            <div class="user-fullname">{full_name or '—'}</div>
                            <span class="role-badge {cfg['badge']}">{cfg['ikon']} {cfg['label']}</span>
                            {f'<div class="user-meta">{meta_html}</div>' if meta_html else ''}
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("Sistemde kayıtlı kullanıcı bulunamadı.")

        st.divider()

        # ================================================================
        # EKLEME / SİLME — YAN YANA
        # ================================================================
        col_ekle, col_sil = st.columns(2)

        # --- YENİ KULLANICI EKLEME ---
        with col_ekle:
            with st.expander("➕ Yeni Kullanıcı Ekle", expanded=False):
                with st.form("add_user_form"):
                    new_user = st.text_input("Kullanıcı Adı")
                    new_pass = st.text_input("Şifre", type="password")
                    new_name = st.text_input("Ad Soyad")
                    new_role = st.selectbox("Yetki Rolü", ["admin", "quality", "operations", "management"],
                                            format_func=lambda x: {
                                                "admin": "👑 Sistem Yöneticisi",
                                                "quality": "🔬 Kalite Kontrol",
                                                "operations": "⚙️ Operasyon",
                                                "management": "📊 Yönetim"
                                            }[x])
                    new_email = st.text_input("E-posta (Opsiyonel)")

                    submitted = st.form_submit_button("✅ Kullanıcıyı Kaydet", type="primary", use_container_width=True)

                    if submitted:
                        if new_user and new_pass:
                            mevcut_userlar = users['username'].tolist() if not users.empty and 'username' in users.columns else []
                            if new_user in mevcut_userlar:
                                st.error(f"⛔ '{new_user}' kullanıcı adı zaten mevcut!")
                            else:
                                user_data = {
                                    "username":   new_user,
                                    "password":   new_pass,
                                    "role":       new_role,
                                    "full_name":  new_name,
                                    "email":      new_email,
                                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                if add_data("users", user_data):
                                    st.success(f"✅ {new_user} eklendi!")
                                    clear_cache("users")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Kayıt sırasında hata oluştu.")
                        else:
                            st.error("Kullanıcı adı ve şifre boş olamaz.")

        # --- KULLANICI SİLME ---
        with col_sil:
            with st.expander("🗑️ Kullanıcı Sil", expanded=False):
                try:
                    if not users.empty and 'username' in users.columns:
                        silinebilir = users[users['username'] != aktif_kullanici]['username'].tolist()

                        if not silinebilir:
                            st.info("Silinebilecek başka kullanıcı yok.")
                        else:
                            secilen = st.selectbox("Silinecek Kullanıcı", silinebilir, key="kullanici_silme_secim")

                            if secilen:
                                row       = users[users['username'] == secilen].iloc[0]
                                rol       = str(row.get('role', ''))
                                isim      = str(row.get('full_name', ''))
                                cfg       = ROL_CONFIG.get(rol, {"label": rol, "ikon": "👤"})

                                st.warning(f"⚠️ **{secilen}** ({isim}) silinecek.\nRol: {cfg['ikon']} {cfg['label']}")

                                if 'kullanici_silme_onayi' not in st.session_state:
                                    st.session_state.kullanici_silme_onayi = False

                                if not st.session_state.kullanici_silme_onayi:
                                    if st.button("🗑️ Sil", type="secondary", use_container_width=True, key="k_sil_btn"):
                                        st.session_state.kullanici_silme_onayi = True
                                        st.rerun()
                                else:
                                    st.error("Bu işlem geri alınamaz! Emin misiniz?")
                                    c1, c2 = st.columns(2)
                                    with c1:
                                        if st.button("✅ EVET, SİL", type="primary", use_container_width=True, key="k_evet_btn"):
                                            conn = get_conn()
                                            df_guncell = users[users['username'] != secilen]
                                            conn.update(worksheet="users", data=df_guncell)
                                            clear_cache("users")
                                            st.cache_data.clear()
                                            st.session_state.kullanici_silme_onayi = False
                                            st.success(f"✅ {secilen} silindi.")
                                            time.sleep(1.5)
                                            st.rerun()
                                    with c2:
                                        if st.button("❌ İptal", use_container_width=True, key="k_iptal_btn"):
                                            st.session_state.kullanici_silme_onayi = False
                                            st.rerun()
                    else:
                        st.info("Silinecek kullanıcı bulunamadı.")
                except Exception as e:
                    st.error(f"Hata: {str(e)}")

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
    .fill-low  { background: #4ade80; }
    .fill-mid  { background: #facc15; }
    .fill-high { background: #f87171; }
    .fill-full { background: #ef4444; }
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
                "isim":          st.column_config.TextColumn("Silo Adı", required=True),
                "kapasite":      st.column_config.NumberColumn("Kapasite (Ton)", min_value=0, required=True, format="%.0f"),
                "silo_tipi":     st.column_config.TextColumn("Tip", disabled=True),
                "mevcut_miktar": st.column_config.NumberColumn("Mevcut (Ton)", disabled=True),
                "aciklama":      st.column_config.TextColumn("Açıklama / Konum")
            }
        )
        st.caption("ℹ️ Yeni satır eklemek için tablonun en altına tıklayın.")
        return edited

    # DÜZELTME 1: max 4 sütun, taşma önlendi
    def render_silo_cards(df_silo, kart_tipi="bugday"):
        """Üstteki özet kartları çizer - max 4 sütun"""
        if df_silo.empty:
            st.info("Bu tipte henüz silo tanımlanmamış.")
            return

        kart_class = "silo-card" if kart_tipi == "bugday" else "silo-card silo-card-un"
        max_cols = 4

        # Siloları max 4'lük gruplara böl
        silo_gruplari = [df_silo.iloc[i:i+max_cols] for i in range(0, len(df_silo), max_cols)]

        for grup in silo_gruplari:
            cols = st.columns(len(grup))
            for i, (_, row) in enumerate(grup.iterrows()):
                kapasite = float(row.get('kapasite', 1) or 1)
                mevcut   = float(row.get('mevcut_miktar', 0) or 0)
                bos      = max(0, kapasite - mevcut)
                oran     = min(mevcut / kapasite, 1.0) if kapasite > 0 else 0
                pct      = int(oran * 100)

                if pct < 40:   fill_class = "fill-low"
                elif pct < 70: fill_class = "fill-mid"
                elif pct < 90: fill_class = "fill-high"
                else:          fill_class = "fill-full"

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
        # Ana veri — tek seferde çekiliyor, aşağıda tekrar çekilmiyor
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
            st.markdown('<div class="section-title">📊 Anlık Doluluk Durumu</div>', unsafe_allow_html=True)
            render_silo_cards(df_bugday, kart_tipi="bugday")
            st.markdown('<div class="section-title">📝 Silo Ekle / Düzenle</div>', unsafe_allow_html=True)
            edited_bugday = render_silo_editor(df_bugday, "editor_bugday")

        with tab_un:
            df_un = df_display[df_display['silo_tipi'] == "UN"].copy()
            st.markdown('<div class="section-title">📊 Anlık Doluluk Durumu</div>', unsafe_allow_html=True)
            render_silo_cards(df_un, kart_tipi="un")
            st.markdown('<div class="section-title">📝 Silo Ekle / Düzenle</div>', unsafe_allow_html=True)
            edited_un = render_silo_editor(df_un, "editor_un")

        # ================================================================
        # KAYDET BUTONU
        # ================================================================
        st.divider()
        if st.button("💾 Silo Değişikliklerini Kaydet", type="primary", use_container_width=True):
            try:
                conn = get_conn()
                # DÜZELTME 3: original_df olarak üstte çekilen df'yi kullanıyoruz
                # Gereksiz ikinci fetch_data çağrısı kaldırıldı
                original_df = df.copy()
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
        # DÜZELTME 3: df_fresh kaldırıldı, üstte çekilen df kullanılıyor
        # ================================================================
        st.divider()
        st.markdown('<div class="section-title">🗑️ Silo Sil</div>', unsafe_allow_html=True)

        with st.expander("⚠️ Silo silmek için buraya tıklayın", expanded=False):
            try:
                if not df.empty and 'isim' in df.columns:
                    silo_listesi = df['isim'].tolist()
                    secilen_silo = st.selectbox("Silinecek Siloyu Seçin", silo_listesi, key="silme_secim")

                    if secilen_silo:
                        silo_row = df[df['isim'] == secilen_silo].iloc[0]
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
                                        df_guncell = df[df['isim'] != secilen_silo]
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

    st.markdown("""
    <style>
    .yedek-kart {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        height: 100%;
    }
    .yedek-baslik {
        font-size: 16px;
        font-weight: 700;
        color: #1a202c;
        margin-bottom: 6px;
    }
    .yedek-aciklama {
        font-size: 12px;
        color: #718096;
        margin-bottom: 16px;
        line-height: 1.5;
    }
    .tablo-satir {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 12px;
        border-radius: 8px;
        margin-bottom: 6px;
        background: #f7fafc;
        border-left: 3px solid #4299e1;
        font-size: 13px;
    }
    .tablo-satir-kritik { border-left-color: #e53e3e; }
    .tablo-satir-normal { border-left-color: #48bb78; }
    .tablo-etiket {
        font-weight: 600;
        color: #2d3748;
    }
    .tablo-acik {
        font-size: 11px;
        color: #a0aec0;
    }
    .bilgi-kutu {
        background: linear-gradient(135deg, #ebf8ff, #e6fffa);
        border: 1px solid #bee3f8;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 20px;
    }
    .bilgi-satir {
        font-size: 13px;
        color: #2c5282;
        margin-bottom: 6px;
        display: flex;
        align-items: flex-start;
        gap: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### 💾 Yedekleme ve Veri Güvenliği")

    # --- BİLGİ KUTUSU ---
    st.markdown("""
    <div class="bilgi-kutu">
        <div class="bilgi-satir">☁️ <span>Verileriniz <strong>Google Sheets (Bulut)</strong> üzerinde anlık olarak saklanmaktadır.</span></div>
        <div class="bilgi-satir">🕒 <span>Hata durumunda Google E-Tablolar'da <strong>Dosya → Sürüm Geçmişi</strong> menüsünden eski tarihe dönebilirsiniz.</span></div>
        <div class="bilgi-satir">💡 <span>Aşağıdaki <strong>Tam Sistem Yedeği</strong> ile tüm kritik verilerinizi tek seferde bilgisayarınıza indirin.</span></div>
    </div>
    """, unsafe_allow_html=True)

    # Kritik tablolar tanımı
    KRITIK_TABLOLAR = [
        {"isim": "bugday_giris_arsivi", "etiket": "Buğday Giriş Arşivi",  "aciklama": "Tüm mal kabul kayıtları",        "kritik": True},
        {"isim": "hareketler",          "etiket": "Stok Hareketleri",      "aciklama": "Silo giriş/çıkış geçmişi",       "kritik": True},
        {"isim": "tavli_analiz",        "etiket": "Tavlı Analiz Verileri", "aciklama": "Laboratuvar ölçüm kayıtları",     "kritik": True},
        {"isim": "silolar",             "etiket": "Silo Tanımları",        "aciklama": "Kapasite ve stok bilgileri",      "kritik": False},
        {"isim": "users",               "etiket": "Kullanıcılar",          "aciklama": "Sistem kullanıcı listesi",        "kritik": False},
    ]

    col1, col2 = st.columns([1.2, 1])

    # ================================================================
    # BÖLÜM 1 — TAM SİSTEM YEDEĞİ
    # ================================================================
    with col1:
        st.markdown("""
        <div class="yedek-kart">
            <div class="yedek-baslik">📦 Tam Sistem Yedeği</div>
            <div class="yedek-aciklama">
                Tüm kritik tablolar tek bir Excel dosyasına, ayrı sayfalara yazılır.<br>
                Önerilen yedekleme yöntemi budur.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Yedeklenecek Tablolar:**")
        for t in KRITIK_TABLOLAR:
            renk = "tablo-satir-kritik" if t["kritik"] else "tablo-satir-normal"
            etiket_ikon = "🔴" if t["kritik"] else "🟢"
            st.markdown(f"""
            <div class="tablo-satir {renk}">
                <span class="tablo-etiket">{etiket_ikon} {t['etiket']}</span>
                <span class="tablo-acik">{t['aciklama']}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("📦 Tam Sistem Yedeği Al", type="primary", use_container_width=True):
            try:
                with st.spinner("Tüm tablolar hazırlanıyor..."):
                    import io
                    output = io.BytesIO()

                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        basarili = []
                        basarisiz = []

                        for t in KRITIK_TABLOLAR:
                            try:
                                df = fetch_data(t["isim"])
                                if not df.empty:
                                    # Sheet ismi max 31 karakter (Excel limiti)
                                    sheet_adi = t["etiket"][:31]
                                    df.to_excel(writer, sheet_name=sheet_adi, index=False)
                                    basarili.append(t["etiket"])
                                else:
                                    basarisiz.append(f"{t['etiket']} (boş)")
                            except Exception:
                                basarisiz.append(f"{t['etiket']} (hata)")

                    output.seek(0)
                    dosya_adi = f"SmartMill_Yedek_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

                    st.download_button(
                        label=f"⬇️ {dosya_adi} İndir",
                        data=output.getvalue(),
                        file_name=dosya_adi,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                    if basarili:
                        st.success(f"✅ {len(basarili)} tablo hazırlandı: {', '.join(basarili)}")
                    if basarisiz:
                        st.warning(f"⚠️ Atlanılan tablolar: {', '.join(basarisiz)}")

            except Exception as e:
                st.error(f"Yedekleme hatası: {str(e)}")

    # ================================================================
    # BÖLÜM 2 — SEÇİLİ TABLO YEDEĞİ
    # ================================================================
    with col2:
        st.markdown("""
        <div class="yedek-kart">
            <div class="yedek-baslik">📋 Seçili Tablo Yedeği</div>
            <div class="yedek-aciklama">
                Belirli bir tabloyu CSV olarak indirin.<br>
                Detaylı inceleme veya filtreleme için uygundur.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        tablo_sec = {t["etiket"]: t["isim"] for t in KRITIK_TABLOLAR}
        selected_label = st.selectbox("Tablo Seçin", list(tablo_sec.keys()), key="tekli_yedek_sec")

        if st.button("📥 Seçili Tabloyu İndir", use_container_width=True):
            try:
                df = fetch_data(tablo_sec[selected_label])
                if not df.empty:
                    csv = df.to_csv(index=False).encode('utf-8')
                    dosya_adi = f"{tablo_sec[selected_label]}_{datetime.now().strftime('%Y%m%d')}.csv"
                    st.download_button(
                        label=f"⬇️ {selected_label} CSV İndir",
                        data=csv,
                        file_name=dosya_adi,
                        mime="text/csv",
                        use_container_width=True
                    )
                    st.success(f"✅ {len(df)} satır hazırlandı.")
                else:
                    st.warning("Bu tablo henüz boş.")
            except Exception as e:
                st.error(f"İndirme hatası: {e}")

        st.divider()

        # --- GERİ YÜKLEME — KAPALI ---
        st.markdown("""
        <div style="background:#fff5f5;border:1px solid #fed7d7;border-radius:10px;padding:16px;">
            <div style="font-size:14px;font-weight:700;color:#c53030;margin-bottom:8px;">
                🔒 Geri Yükleme (Restore)
            </div>
            <div style="font-size:12px;color:#742a2a;line-height:1.6;">
                Geri yükleme özelliği veri güvenliği nedeniyle kapatılmıştır.<br><br>
                <strong>Alternatif:</strong> Google E-Tablolar'da<br>
                <strong>Dosya → Sürüm Geçmişi → Tarihe göre gözat</strong><br>
                menüsünden istediğiniz tarihe dönebilirsiniz.
            </div>
        </div>
        """, unsafe_allow_html=True)

# ----------------------------------------------------------------
# 4. SİSTEM LOGLARI
# ----------------------------------------------------------------
# ----------------------------------------------------------------
# 4. SİSTEM LOGLARI
# ----------------------------------------------------------------
def show_system_logs():
    """Audit log ve stok hareketleri"""

    st.markdown("""
    <style>
    .log-stat-kart {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    }
    .log-stat-sayi {
        font-size: 28px;
        font-weight: 800;
        color: #1a202c;
        margin-bottom: 2px;
    }
    .log-stat-etiket {
        font-size: 12px;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .islem-giris     { color: #276749; background: #c6f6d5; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    .islem-cikis     { color: #744210; background: #fefcbf; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    .islem-ekleme    { color: #2a69ac; background: #bee3f8; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    .islem-silme     { color: #9b2335; background: #fed7d7; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    .islem-guncelleme{ color: #553c9a; background: #e9d8fd; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    .islem-ziyaret   { color: #4a5568; background: #edf2f7; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### 📜 Sistem Aktivite Logları")

    tab_audit, tab_stok = st.tabs(["🔍 Kullanıcı Aktiviteleri", "📦 Stok Hareketleri"])

    # ================================================================
    # TAB 1 — KULLANICI AKTİVİTELERİ (audit_log)
    # ================================================================
    with tab_audit:
        try:
            df_log = fetch_data("audit_log", force_refresh=True)

            if df_log is None or df_log.empty:
                st.info("Henüz kayıtlı aktivite logu yok. Kullanıcılar sistemi kullandıkça burada görünecek.")
                return

            # Tarih dönüşümü
            df_log['tarih'] = pd.to_datetime(df_log['tarih'], errors='coerce')
            df_log = df_log.sort_values('tarih', ascending=False)

            bugun     = pd.Timestamp.now().normalize()
            bu_hafta  = bugun - pd.Timedelta(days=7)
            bu_ay     = bugun - pd.Timedelta(days=30)

            # --- İSTATİSTİK KARTLARI ---
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f"""
                <div class="log-stat-kart">
                    <div class="log-stat-sayi">{len(df_log[df_log['tarih'] >= bugun])}</div>
                    <div class="log-stat-etiket">Bugün</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="log-stat-kart">
                    <div class="log-stat-sayi">{len(df_log[df_log['tarih'] >= bu_hafta])}</div>
                    <div class="log-stat-etiket">Son 7 Gün</div>
                </div>""", unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="log-stat-kart">
                    <div class="log-stat-sayi">{len(df_log[df_log['tarih'] >= bu_ay])}</div>
                    <div class="log-stat-etiket">Son 30 Gün</div>
                </div>""", unsafe_allow_html=True)
            with c4:
                st.markdown(f"""
                <div class="log-stat-kart">
                    <div class="log-stat-sayi">{df_log['kullanici'].nunique()}</div>
                    <div class="log-stat-etiket">Aktif Kullanıcı</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # --- FİLTRELER ---
            f1, f2, f3 = st.columns(3)

            with f1:
                kullanici_listesi = ["Tümü"] + sorted(df_log['kullanici'].dropna().unique().tolist())
                sec_kullanici = st.selectbox("👤 Kullanıcı", kullanici_listesi, key="log_kullanici")

            with f2:
                modul_listesi = ["Tümü"] + sorted(df_log['modul'].dropna().unique().tolist())
                sec_modul = st.selectbox("📂 Modül", modul_listesi, key="log_modul")

            with f3:
                islem_listesi = ["Tümü"] + sorted(df_log['islem'].dropna().unique().tolist())
                sec_islem = st.selectbox("⚡ İşlem", islem_listesi, key="log_islem")

            # Tarih aralığı
            t1, t2 = st.columns(2)
            with t1:
                bas_tarih = st.date_input("📅 Başlangıç", value=bu_hafta.date(), key="log_bas")
            with t2:
                bit_tarih = st.date_input("📅 Bitiş", value=bugun.date(), key="log_bit")

            # --- FİLTRE UYGULA ---
            df_filtre = df_log.copy()

            if sec_kullanici != "Tümü":
                df_filtre = df_filtre[df_filtre['kullanici'] == sec_kullanici]
            if sec_modul != "Tümü":
                df_filtre = df_filtre[df_filtre['modul'] == sec_modul]
            if sec_islem != "Tümü":
                df_filtre = df_filtre[df_filtre['islem'] == sec_islem]

            df_filtre = df_filtre[
                (df_filtre['tarih'].dt.date >= bas_tarih) &
                (df_filtre['tarih'].dt.date <= bit_tarih)
            ]

            # --- SONUÇ SAYISI ---
            st.caption(f"🔎 Filtreye uyan {len(df_filtre)} kayıt gösteriliyor.")

            # --- TABLO ---
            if not df_filtre.empty:
                df_goster = df_filtre[['tarih', 'kullanici', 'rol', 'modul', 'islem', 'detay']].copy()
                df_goster['tarih'] = df_goster['tarih'].dt.strftime('%d.%m.%Y %H:%M')
                df_goster.columns = ['Tarih', 'Kullanıcı', 'Rol', 'Modül', 'İşlem', 'Detay']

                st.dataframe(
                    df_goster,
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )

                # CSV İndirme
                csv = df_filtre.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Filtrelenmiş Logu İndir (CSV)",
                    data=csv,
                    file_name=f"audit_log_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Seçilen filtrelere uyan kayıt bulunamadı.")

        except Exception as e:
            st.error(f"Audit log yüklenemedi: {str(e)}")

    # ================================================================
    # TAB 2 — STOK HAREKETLERİ (hareketler)
    # ================================================================
    with tab_stok:
        try:
            df_h = fetch_data("hareketler")

            if df_h.empty:
                st.info("Henüz stok hareketi kaydı yok.")
                return

            if 'tarih' in df_h.columns:
                df_h['tarih'] = pd.to_datetime(df_h['tarih'], errors='coerce')
                df_h = df_h.sort_values('tarih', ascending=False)

            # Arama kutusu
            arama = st.text_input("🔍 Ara (Silo, İşlem Tipi, Lot No...)", key="stok_arama")
            if arama:
                mask = df_h.astype(str).apply(
                    lambda x: x.str.contains(arama, case=False, na=False)
                ).any(axis=1)
                df_h = df_h[mask]

            st.caption(f"🔎 {len(df_h)} hareket kaydı gösteriliyor.")
            st.dataframe(df_h, use_container_width=True, hide_index=True, height=400)

        except Exception as e:
            st.error(f"Stok hareketleri yüklenemedi: {str(e)}")

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












