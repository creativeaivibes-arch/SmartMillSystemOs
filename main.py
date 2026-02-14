# -*- coding: utf-8 -*-
import streamlit as st
import time

# Sayfa konfigürasyonu - EN BAŞTA OLMALI
st.set_page_config(
    page_title="SmartMill OS",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Core Imports
from app.core.utils import init_session_state
from app.core.styles import load_css
from app.core.database import init_db
from app.core.auth import check_password, do_logout, ROLES, show_profile_settings
from app.core.config import SESSION_TIMEOUT_SECONDS
from app.core.license_manager import check_license, show_license_lock_screen, LICENSE_CONFIG
from app.modules.traceability import show_traceability_dashboard

# Modül İmportları
import app.modules.dashboard as dashboard
import app.modules.wheat as wheat
import app.modules.mixing as mixing
import app.modules.mill as production
import app.modules.flour as flour
import app.modules.admin as admin
import app.modules.calculations as calculations
from app.core.languages import t, LANGUAGES # <--- YENİ EKLENEN

# --- 1. LİSANS KONTROLÜ (EN BAŞTA YAPILMALI) ---
is_valid, msg, status, days_left = check_license()

if not is_valid:
    show_license_lock_screen()  # Eğer süre bittiyse burada kod durur.

# Eğer süre bitmediyse ama az kaldıysa Sidebar'da uyarı gösterelim
if status == 'warning':
    st.sidebar.warning(f"⚠️ {msg}")

# --- APP BAŞLANGIÇ ---

# 1. Session State Başlat
init_session_state()
load_css()

# 2. Veritabanı Başlat
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# --- SESSION TIMEOUT CONTROL ---
if st.session_state.get('logged_in', False):
    current_time = time.time()
    last_activity = st.session_state.get('last_activity', current_time)
    
    if current_time - last_activity > SESSION_TIMEOUT_SECONDS:
        st.warning("⚠️ Oturumunuz zaman aşımına uğradı. Lütfen tekrar giriş yapın.")
        do_logout()
        st.stop()
    
    st.session_state.last_activity = current_time

# --- LOGIN EKRANI ---
if not st.session_state.logged_in:
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #ffffff; }
    [data-testid="stHeader"] { background-color: #ffffff; }
    .block-container { padding-top: 2rem !important; padding-bottom: 1rem !important; }
    /* Bayrak butonlarını güzelleştirme */
    div.stButton > button {
        background-color: transparent;
        border: 1px solid #eee;
        font-size: 20px;
        padding: 5px 10px;
    }
    div.stButton > button:hover {
        border-color: #4CAF50;
        background-color: #f1f8e9;
    }
    </style>
    """, unsafe_allow_html=True)

    empty1, login_col, empty2 = st.columns([1, 0.8, 1]) 
    
    with login_col:
        # --- DİL SEÇİMİ (BAYRAKLAR) ---
        # Ortalanmış bir container içinde bayraklar
        c_flag1, c_flag2, c_flag3, c_flag4 = st.columns(4)
        
        # Dil değiştirme fonksiyonu
        def set_lang(code):
            st.session_state.language_code = code
            st.rerun()

        if c_flag1.button("🇹🇷", use_container_width=True): set_lang("TR")
        if c_flag2.button("🇬🇧", use_container_width=True): set_lang("EN")
        if c_flag3.button("🇫🇷", use_container_width=True): set_lang("FR")
        if c_flag4.button("🇷🇺", use_container_width=True): set_lang("RU")
        
        st.write("") # Boşluk
        
        # --- LOGO VE BAŞLIK ---
        col_logo, col_text = st.columns([1, 2.5])
        with col_logo:
            try: 
                st.image("logo.png", use_container_width=True)
            except: 
                st.markdown("🏭")
        with col_text:
            st.markdown("""
            <div style='display: flex; flex-direction: column; justify-content: center; height: 100%;'>
                <h2 style='margin:0; padding:0; color: #000; font-weight: 800;'>SmartMill OS</h2>
                <h5 style='margin:0; padding:0; color: #666; font-weight: normal;'>Akıllı Değirmen Sistemi</h5>
            </div>
            """, unsafe_allow_html=True)
        
        st.write("") 
        
        # --- GİRİŞ FORMU ---
        with st.container(border=True):
            # Başlık Çevirisi
            header_txt = t("login_header")
            st.markdown(f"<h4 style='text-align: center; color: #444;'>{header_txt}</h4>", unsafe_allow_html=True)
            
            with st.form("login_form"):
                # Input Etiketleri Çevirisi
                username = st.text_input(t("username"))
                password = st.text_input(t("password"), type="password")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Buton Çevirisi
                btn_txt = t("login_button")
                submit = st.form_submit_button(btn_txt, type="primary", use_container_width=True)
                
                if submit:
                    from app.core.auth import login_user
                    if login_user(username, password):
                        st.session_state.last_activity = time.time()
                        # Hoşgeldiniz Mesajı Çevirisi
                        welcome_txt = t("login_welcome")
                        st.success(f"{welcome_txt}, {st.session_state.user_fullname}")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        # Hata Mesajı Çevirisi
                        err_txt = t("login_error")
                        st.error(err_txt)
    st.stop()
# --- ANA UYGULAMA ---
with st.sidebar:
    # 0. Marka
    col_brand1, col_brand2 = st.columns([1, 4])
    with col_brand1:
        try: 
            st.image("logo.png", width=50)
        except: 
            st.write("🏭")
    with col_brand2:
        st.markdown("**SmartMill System OS**")
        st.caption("Akıllı Değirmen YS")
        
    st.divider()

    # 1. Kullanıcı Paneli
    with st.container(border=False):
        col_prof1, col_prof2 = st.columns([1, 4])
        with col_prof1:
            st.markdown("## 👤")
        with col_prof2:
            st.markdown(f"**{st.session_state.username}**")
            
        # Rolü veritabanından alıp çeviriyoruz
        raw_role = st.session_state.user_role
        # languages.py içinde "role_admin", "role_quality" gibi tanımlamıştık
        role_key = f"role_{raw_role}" 
        user_role_tr = t(role_key) 
        
        st.caption(f"{user_role_tr} | 🟢 Online")
        
        # Çıkış butonu artık dilli: t("logout")
        if st.button(t("logout"), key="sidebar_logout", icon="🚪", use_container_width=True):
            do_logout()
    
    st.divider()
    
    # --- MENÜ YAPISI (DİNAMİK ÇEVİRİ) ---
    user_role = st.session_state.get('user_role', 'viewer')
    
    # 1. ÖNCE: Menü isimlerini seçilen dile göre alıp değişkenlere atıyoruz.
    # Böylece aşağıda hem listede hem de if koşullarında aynısını kullanacağız.
    opt_dashboard = t("menu_dashboard")
    opt_quality = t("menu_quality")
    opt_mill = t("menu_mill")
    opt_finance = t("menu_finance")
    opt_admin = t("menu_admin")
    
    
    # 2. Rol Bazlı Menü Listesi (Değişkenleri kullanıyoruz)
    if user_role == "admin":
        # opt_trace'i buraya ekledik
        menu_secenekleri = [opt_dashboard, opt_quality, opt_mill, opt_finance,  opt_admin]
        
    elif user_role == "quality":
        # opt_trace'i buraya ekledik
        menu_secenekleri = [opt_dashboard, opt_quality, opt_mill,]
        
    elif user_role == "operations":
        # opt_trace'i buraya ekledik
        menu_secenekleri = [opt_dashboard, opt_mill,]
        
    elif user_role == "management":
        menu_secenekleri = [opt_dashboard, opt_quality, opt_finance,]
    else:
        menu_secenekleri = [opt_dashboard]

    # 3. Menüyü Göster
    ana_menu = st.sidebar.radio(
        "📂 Menu",  # Başlık 'collapsed' olduğu için önemli değil
        menu_secenekleri,
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # --- SAYFA BELİRLEME (Routing - Çok Dilli) ---
    selected_page = None
    
    # Karşılaştırmaları yukarıdaki değişkenlerle (opt_...) yapıyoruz
    
    if ana_menu == opt_dashboard:
        selected_page = "Dashboard"

    elif ana_menu == opt_quality:
        # Alt başlığı da çeviriyoruz
        st.sidebar.markdown(f"### 🧪 {t('menu_quality')}")
        
        # Alt menüleri henüz languages.py'ye eklemedik, Türkçe kalsın şimdilik
        # İleride bunları da t('submenu_wheat') gibi yapabiliriz
        kk_bolum = st.sidebar.radio(
            "Bölüm Seçiniz", 
            ["🌾 Buğday Yönetimi", "🍞 Un Yönetimi","🔍 Geri İzlenebilirlik"]
        )
        if kk_bolum == "🌾 Buğday Yönetimi":
            selected_page = "KK_BUGDAY"
        elif kk_bolum == "🍞 Un Yönetimi":
            selected_page = "KK_UN"

    elif ana_menu == opt_mill:
        selected_page = "PRODUCTION_MANAGER"
        
    elif ana_menu == opt_finance:
        selected_page = "FINANCE_DASHBOARD"
                
    elif ana_menu == opt_admin:
        selected_page = "ADMIN"
    
# --- YÖNLENDIRME (ROUTING) ---

if selected_page == "Dashboard":
    try:
        dashboard.show_dashboard()
    except Exception as e:
        st.error("🚨 Dashboard yüklenirken bir hata oluştu.")
        st.caption(f"Hata Detayı: {str(e)}")

# --- A) KALİTE KONTROL: BUĞDAY YÖNETİMİ ---
elif selected_page == "KK_BUGDAY":
    try:
        # Başlık Dinamik Oldu
        st.markdown(f"## 🌾 {t('nav_wheat')}")
        
        # Sekme İsimleri Dinamik Oldu
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            t("tab_specs"),      # Kalite Standartları
            t("tab_intake"),     # Hammadde Giriş
            t("tab_tempered"),   # Tavlı Analiz
            t("tab_mixing"),     # Akıllı Paçal
            t("tab_stock_out"),  # Stok Çıkışı
            t("tab_trace")       # İzlenebilirlik
        ])
        
        with tab1: wheat.show_bugday_spec_yonetimi()
        with tab2: wheat.show_mal_kabul()
        with tab3: wheat.show_tavli_analiz()
        with tab4: mixing.show_pacal_hesaplayici()
        with tab5: wheat.show_stok_cikis()
        
        # İzlenebilirlik Alt Sekmeleri
        with tab6:
            sub_tab1, sub_tab2, sub_tab3, sub_tab4 = st.tabs([
                t("sub_archive_in"),    # Buğday Giriş Arşivi
                t("sub_stock_log"),     # Stok Hareketleri
                t("sub_archive_temp"),  # Tavlı Analiz Arşivi
                t("sub_mixing_log")     # Paçal Geçmişi
            ])
            
            with sub_tab1: wheat.show_bugday_giris_arsivi()
            with sub_tab2: wheat.show_stok_hareketleri()
            with sub_tab3: wheat.show_tavli_analiz_arsivi()
            with sub_tab4: mixing.show_pacal_gecmisi()

    except Exception as e:
        st.error("🚨 Buğday Yönetim Modülü yüklenirken hata oluştu.")
        st.info("Lütfen sayfayı yenileyiniz.")
        st.caption(f"Teknik Hata: {str(e)}")

# --- B) KALİTE KONTROL: UN YÖNETİMİ ---
elif selected_page == "KK_UN":
    try:
        st.markdown(f"## 🍞 {t('nav_flour')}")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            t("tab_flour_specs"),    # Un Spektleri
            t("tab_flour_entry"),    # Un Analiz Kaydı
            t("tab_flour_archive"),  # Analiz Arşivi
            t("tab_enzyme")          # Enzim Dozaj Hesaplama
        ])
        
        with tab1: flour.show_spec_yonetimi()
        with tab2: flour.show_un_analiz_kaydi()
        with tab3: flour.show_un_analiz_kayitlari()
        with tab4: calculations.show_enzim_dozajlama()

    except Exception as e:
        st.error("🚨 Un Kalite Modülü yüklenirken hata oluştu.")
        st.caption(f"Teknik Hata: {str(e)}")

# 🏭 DEĞİRMEN (PRODUCTION)
elif selected_page == "PRODUCTION_MANAGER":
    try:
        # Burası mill.py içinden başlık alıyorsa oraya da el atılabilir ama şimdilik kalsın
        production.show_production_yonetimi()
    except Exception as e:
        st.error("🚨 Üretim Yönetim Modülü yüklenirken hata oluştu.")
        st.caption(f"Teknik Hata: {str(e)}")

# 💰 FİNANS & STRATEJİ
elif selected_page == "FINANCE_DASHBOARD":
    try:
        st.markdown(f"## 💰 {t('nav_finance')}")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            t("tab_cost_calc"),  # Un Maliyet
            t("tab_cost_hist"),  # Maliyet Geçmişi
            t("tab_strategy"),   # Stratejik Analiz
            t("tab_loss"),       # Buğday Fire Maliyet
            t("tab_additives")   # Katkı Maliyet
        ])
        
        with tab1: flour.show_un_maliyet_hesaplama()
        with tab2: flour.show_un_maliyet_gecmisi()
        
        # Strateji sekmesi koruması
        with tab3:
            try:
                import app.modules.strategy as strategy
                strategy.show_strategy_module()
            except ImportError:
                st.warning("⚠️ Strateji modülü (strategy.py) bulunamadı.")
            except Exception as e_strat:
                st.error(f"❌ Strateji modülü hatası: {str(e_strat)}")
                
        with tab4: calculations.show_fire_maliyet_hesaplama()
        with tab5: calculations.show_katki_maliyeti_modulu()

    except Exception as e:
        st.error("🚨 Finans Modülü genel yükleme hatası.")
        st.caption(f"Teknik Hata: {str(e)}")
        
# 🔍 İZLENEBİLİRLİK (KARA KUTU)
elif selected_page == "TRACEABILITY":
    try:
        show_traceability_dashboard()
    except Exception as e:
        st.error("🚨 İzlenebilirlik Modülü yüklenirken hata oluştu.")
        st.caption(f"Teknik Hata: {str(e)}")

# 🛠️ YÖNETİM PANELİ (ADMIN) - Sadece Adminler Görebilir
elif selected_page == "ADMIN":
    if st.session_state.user_role == "admin":
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "👤 Profilim", 
            "👥 Kullanıcılar", 
            "🏭 Silo Yönetimi", 
            "💾 Yedekleme", 
            "📜 Sistem Logları", 
            "🛠️ Debug"
        ])
        with tab1: show_profile_settings() # Admin de kendi profilini buradan yönetir
        with tab2: admin.show_user_management()
        with tab3: admin.show_silo_management()
        with tab4: admin.show_backup_restore()
        with tab5: admin.show_system_logs()
        with tab6: admin.show_debug_tools()
    else:
        # Admin olmayan biri buraya sızmaya çalışırsa (URL zorlaması vb.)
        st.error("🚫 Bu sayfaya erişim yetkiniz bulunmamaktadır.")

# 👤 PROFİL VE AYARLAR - Tüm Kullanıcılar İçin
elif selected_page == "PROFILE":
    st.markdown("### 👤 Profil ve Kullanıcı Ayarları")
    show_profile_settings() # auth.py içindeki genel profil fonksiyonu

# --- SIDEBAR LİSANS BİLGİSİ ---
with st.sidebar:
    st.divider() # Ayırıcı çizgi
    
    # Not: Lisans ID satırını kaldırdık (Senin isteğin üzerine)
    
    # Duruma göre Görselleştirme
    if status == 'warning':
        # --- KRİTİK DÖNEM (Son 15 Gün) ---
        st.error(f"⚠️ {t('license_warning')}")
        st.markdown(f"**{t('days_left')}: {days_left}**")
        
        # Kırmızı Bar (Standart st.progress kırmızı/turuncu tonlarındadır veya theme rengini alır)
        progress_bar = min(1.0, max(0.0, days_left / 365))
        st.progress(progress_bar)
        
    else:
        # --- NORMAL DÖNEM (Yeşil Bar) ---
        st.success(f"✅ {t('license_active')}")
        
        # Özel Yeşil Progress Bar (HTML ile)
        # Standart st.progress rengi değiştirilemediği için HTML kullanıyoruz.
        percent = min(100, max(0, int((days_left / 365) * 100)))
        st.markdown(f"""
        <div style="background-color:#e6e6e6; border-radius:5px; height:10px; width:100%; margin-bottom:10px;">
            <div style="background-color:#28a745; width:{percent}%; height:10px; border-radius:5px;"></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Kalan Gün Yazısı
        c1, c2 = st.columns([2, 1])
        c1.caption(f"{t('days_left')}:")
        c2.write(f"**{days_left}**")
    
    # En Alt Footer
    st.caption(f"🏢 {LICENSE_CONFIG.get('CLIENT_NAME', 'Client')}")
    st.caption("v2.0 Enterprise")































