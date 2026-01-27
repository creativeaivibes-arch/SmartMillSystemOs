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

# Modül İmportları
import app.modules.dashboard as dashboard
import app.modules.wheat as wheat
import app.modules.mixing as mixing
import app.modules.mill as production
import app.modules.flour as flour
import app.modules.admin as admin
import app.modules.calculations as calculations

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
    </style>
    """, unsafe_allow_html=True)

    empty1, login_col, empty2 = st.columns([1, 0.8, 1]) 
    
    with login_col:
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
        
        with st.container(border=True):
            st.markdown("<h4 style='text-align: center; color: #444;'>Giriş Yap</h4>", unsafe_allow_html=True)
            
            with st.form("login_form"):
                username = st.text_input("Kullanıcı Adı")
                password = st.text_input("Şifre", type="password")
                st.markdown("<br>", unsafe_allow_html=True)
                submit = st.form_submit_button("Sisteme Giriş", type="primary", use_container_width=True)
                
                if submit:
                    from app.core.auth import login_user
                    if login_user(username, password):
                        st.session_state.last_activity = time.time()
                        st.success(f"Hoşgeldiniz, {st.session_state.user_fullname}")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Hatalı kullanıcı adı veya şifre!")
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
            
        role_map = {
            "admin": "Yönetici", 
            "operations": "Operasyon", 
            "quality": "Kalite Kontrol",
            "management": "Üst Yönetim"  # 'viewer' yerine 'management' ekledik
        }
        user_role_tr = role_map.get(st.session_state.user_role, "Kullanıcı")
        
        st.caption(f"{user_role_tr} | 🟢 Çevrimiçi")
        
        if st.button("Çıkış Yap", key="sidebar_logout", icon="🚪", use_container_width=True):
            do_logout()
    
    st.divider()
    
    # --- MENÜ YAPISI (Senin Belirlediğin Başlıklarla) ---
    user_role = st.session_state.get('user_role', 'viewer')
    
    if user_role == "admin":
        # Admin her şeyi görür
        menu_secenekleri = ["Dashboard", "Kalite Kontrol", "Değirmen", "Finans & Strateji", "Yönetim Paneli"]
    elif user_role == "quality":
        # Kaliteci sadece Dashboard ve Kalite Kontrol görür
        menu_secenekleri = ["Dashboard", "Kalite Kontrol", "Değirmen"]
    elif user_role == "operations":
        # Operasyon sadece Dashboard ve Değirmen görür
        menu_secenekleri = ["Dashboard", "Değirmen"]
    elif user_role == "management":
        # Üst Yönetim sadece Dashboard ve Finans & Strateji görür
        menu_secenekleri = ["Dashboard","Kalite Kontrol","Finans & Strateji"]
    else:
        menu_secenekleri = ["Dashboard"]

    ana_menu = st.sidebar.radio(
        "📂 Ana Menü",
        menu_secenekleri,
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    # --- SAYFA BELİRLEME (Routing) ---
    selected_page = None
    
    if ana_menu == "Dashboard":
        selected_page = "Dashboard"

    elif ana_menu == "Kalite Kontrol":
        st.sidebar.markdown("### 🧪 Kalite Kontrol")
        kk_bolum = st.sidebar.radio(
            "Bölüm Seçiniz", 
            ["🌾 Buğday Yönetimi", "🍞 Un Yönetimi"]
        )
        if kk_bolum == "🌾 Buğday Yönetimi":
            selected_page = "KK_BUGDAY"
        elif kk_bolum == "🍞 Un Yönetimi":
            selected_page = "KK_UN"

    elif ana_menu == "Değirmen":
        selected_page = "PRODUCTION_MANAGER"
        
    elif ana_menu == "Finans & Strateji":
        selected_page = "FINANCE_DASHBOARD"
        
    elif ana_menu == "Yönetim Paneli":
        selected_page = "ADMIN"
      
    
# --- YÖNLENDIRME (ROUTING) ---

if selected_page == "Dashboard":
    dashboard.show_dashboard()

# --- A) KALİTE KONTROL: BUĞDAY YÖNETİMİ ---
elif selected_page == "KK_BUGDAY":
    st.markdown("## 🌾 Giriş & Buğday Kalite Yönetimi")
    
    # 7 Sekmeli Yapı (Sekme isimleri aynı kalıyor)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📏 Kalite Standartları",
        "🚛 Hammadde Giriş",
        "🧪 Tavlı Analiz",
        "🧮 Akıllı Paçal",
        "📜 Reçete Geçmişi",
        "📉 Stok Çıkışı",
        "📂 İzlenebilirlik"
    ])
    
    # Fonksiyon Eşleştirmeleri:
    with tab1: wheat.show_bugday_spec_yonetimi()
    with tab2: wheat.show_mal_kabul()
    with tab3: wheat.show_tavli_analiz()
    with tab4: mixing.show_pacal_hesaplayici()
    with tab5: mixing.show_pacal_gecmisi()
    with tab6: wheat.show_stok_cikis()
    
    # 🔥🔥🔥 DEĞİŞEN KISIM BURASI (TAB 7) 🔥🔥🔥
    with tab7:
        # İzlenebilirlik sekmesinin içine İKİ TANE ALT SEKME (Sub-Tab) açıyoruz
        sub_tab1, sub_tab2 = st.tabs(["🗄️ Buğday Giriş Arşivi", "📉 Stok Hareketleri (Dijital Defter)"])
        
        with sub_tab1:
            wheat.show_bugday_giris_arsivi()  # Eski detaylı arşiv
            
        with sub_tab2:
            wheat.show_stok_hareketleri()     # Yeni renkli giriş/çıkış listesi      

# --- B) KALİTE KONTROL: UN YÖNETİMİ ---
elif selected_page == "KK_UN":
    st.markdown("## 🍞 Un Kalite & Katkı Yönetimi")
    
    # Senin belirlediğin 4 Kritik Sekme
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Un Spekleri", 
        "📝 Un Analiz Gir", 
        "📚 Analiz Arşivi", 
        "🧬 Enzim Dozaj"
    ])
    
    # flour.py içindeki GERÇEK fonksiyon isimleri ile eşleştirme:
    with tab1: flour.show_spec_yonetimi()          # show_un_spekleri -> show_spec_yonetimi
    with tab2: flour.show_un_analiz_kaydi()       # show_un_analiz_giris -> show_un_analiz_kaydi
    with tab3: flour.show_un_analiz_kayitlari()    # show_analiz_arsivi -> show_un_analiz_kayitlari
    with tab4: 
        try:
            import app.modules.calculations as calc_module
            calc_module.show_enzim_dozajlama()    # flour.show_enzim_hesaplama yerine doğrudan calculations modülünden çağırdık
        except:
            st.error("Enzim modülü bulunamadı.")

# 🏭 DEĞİRMEN (PRODUCTION)
elif selected_page == "PRODUCTION_MANAGER":
    # mill.py içindeki sekmeli ana fonksiyonu çağırıyoruz
    production.show_production_yonetimi()

# 💰 FİNANS & STRATEJİ
elif selected_page == "FINANCE_DASHBOARD":
    st.markdown("## 💰 Finansal Yönetim & Strateji")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💵 Un Maliyet", 
        "📉 Maliyet Geçmişi", 
        "♟️ Stratejik Analiz",
        "🌾 Buğday Fire Maliyet",
        "🧪 Katkı Maliyet"
    ])
    
    with tab1: flour.show_un_maliyet_hesaplama()
    with tab2: flour.show_un_maliyet_gecmisi()
    with tab3:
        try:
            import app.modules.strategy as strategy
            strategy.show_strategy_module()
        except:
            st.warning("Strateji modülü bulunamadı.")
    with tab4: calculations.show_fire_maliyet_hesaplama()
    with tab5: calculations.show_katki_maliyeti_modulu()

# 🛠️ YÖNETİM PANELİ (ADMIN)
elif selected_page == "ADMIN" or selected_page == "PROFILE":
    if st.session_state.user_role == "admin":
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "👤 Profilim", 
            "👥 Kullanıcılar", 
            "🏭 Silo Yönetimi", 
            "💾 Yedekleme", 
            "📜 Sistem Logları", 
            "🛠️ Debug"
        ])
        with tab1: show_profile_settings()
        with tab2: admin.show_user_management()
        with tab3: admin.show_silo_management()
        with tab4: admin.show_backup_management()
        with tab5: admin.show_system_logs()
        with tab6: admin.show_debug_panel()
    else:
        # Diğer roller sadece profil görür
        tab1, = st.tabs(["👤 Profil Ayarları"])
        with tab1: show_profile_settings()

# 🚪 PROFİL SAYFASI
elif selected_page == "PROFILE":
    show_profile_settings()







