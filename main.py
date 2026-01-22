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
            
        role_map = {"admin": "Yönetici", "operations": "Operasyon", "viewer": "İzleyici"}
        user_role_tr = role_map.get(st.session_state.user_role, "Kullanıcı")
        
        st.caption(f"{user_role_tr} | 🟢 Çevrimiçi")
        
        if st.button("Çıkış Yap", key="sidebar_logout", icon="🚪", use_container_width=True):
            do_logout()
    
    st.divider()
    
    # --- MENÜ YAPISI ---
    
    ana_menu = st.sidebar.radio(
        "📂 Ana Menü",
        ["Dashboard", "Kalite Kontrol", "Değirmen", "Hesaplamalar", "Yönetim Paneli"],
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    
    selected_page = None
    
    if ana_menu == "Dashboard":
        selected_page = "Dashboard"
        
    elif ana_menu == "Kalite Kontrol":
        st.sidebar.markdown("### 🧪 Kalite Kontrol")
        kk_bolum = st.sidebar.radio("Bölüm Seçiniz", ["🌾 Buğday Alım & Stok", "🍞 Un Analizleri"])
        st.sidebar.markdown("---")
        
        if kk_bolum == "🌾 Buğday Alım & Stok":
            sub_page = st.sidebar.radio("İşlem Seçiniz", ["Mal Kabul", "Stok Çıkışı", "Tavlı Analiz", "Stok Hareketleri", "Giriş Arşivi", "🎯 Kalite Hedefleri"])
            selected_page = f"WHEAT_{sub_page}" 
        elif kk_bolum == "🍞 Un Analizleri":
            sub_page = st.sidebar.radio("İşlem Seçiniz", ["Un Analiz Kaydı", "Un Analiz Arşivi", "Kalite Hedefleri"])
            selected_page = f"FLOUR_{sub_page}"

    elif ana_menu == "Değirmen":
        st.sidebar.markdown("### 🏭 Değirmen")
        page_raw = st.sidebar.radio("İşlem Seçiniz", ["Üretim Kaydı", "Üretim Arşivi", "Yönetim Dashboard"])
        selected_page = f"PRODUCTION_{page_raw}"
        
    elif ana_menu == "Hesaplamalar":
        st.sidebar.markdown("### 🧮 Hesaplamalar")
        page_raw = st.sidebar.radio("İşlem Seçiniz", 
            ["Un Maliyet", "Maliyet Geçmişi", "Stratejik Analiz (BOSS)", "Fire Maliyeti", "Paçal Hesaplayıcı", "Paçal Geçmişi", "Katkı Maliyeti", "Enzim Dozajlama"])
        selected_page = f"CALC_{page_raw}"
        
    elif ana_menu == "Yönetim Paneli":
        selected_page = "ADMIN"
        
    
# --- YÖNLENDIRME (ROUTING) ---

if selected_page == "Dashboard":
    dashboard.show_dashboard()

# WHEAT
elif selected_page == "WHEAT_Mal Kabul": 
    wheat.show_mal_kabul()
elif selected_page == "WHEAT_Stok Çıkışı": 
    wheat.show_stok_cikis()
elif selected_page == "WHEAT_Tavlı Analiz": 
    wheat.show_tavli_analiz()
elif selected_page == "WHEAT_Stok Hareketleri": 
    wheat.show_stok_hareketleri()
elif selected_page == "WHEAT_Giriş Arşivi": 
    wheat.show_bugday_giris_arsivi()
elif selected_page == "WHEAT_🎯 Kalite Hedefleri": 
    wheat.show_bugday_spec_yonetimi()

# FLOUR
elif selected_page == "FLOUR_Un Analiz Kaydı": 
    flour.show_un_analiz_kaydi()
elif selected_page == "FLOUR_Un Analiz Arşivi": 
    flour.show_un_analiz_kayitlari()
elif selected_page == "FLOUR_Kalite Hedefleri": 
    flour.show_spec_yonetimi()

# PRODUCTION
elif selected_page == "PRODUCTION_Üretim Kaydı": 
    production.show_uretim_kaydi()
elif selected_page == "PRODUCTION_Üretim Arşivi": 
    production.show_uretim_arsivi()
elif selected_page == "PRODUCTION_Yönetim Dashboard": 
    production.show_yonetim_dashboard()

# CALCULATIONS
elif selected_page == "CALC_Un Maliyet": 
    flour.show_un_maliyet_hesaplama()
elif selected_page == "CALC_Maliyet Geçmişi": 
    flour.show_un_maliyet_gecmisi()
elif selected_page == "CALC_Stratejik Analiz (BOSS)":
    try:
        from app.modules import strategy
        strategy.show_strategy_module()
    except ImportError as e:
        st.error(f"⚠️ Strateji modülü yüklenemedi: {e}")
        st.info("Lütfen app/modules/strategy.py dosyasının var olduğundan emin olun.")
    except Exception as e:
        st.error(f"❌ Beklenmeyen hata: {e}")
elif selected_page == "CALC_Fire Maliyeti":
    calculations.show_fire_maliyet_hesaplama()
elif selected_page == "CALC_Paçal Hesaplayıcı": 
    mixing.show_pacal_hesaplayici()
elif selected_page == "CALC_Paçal Geçmişi": 
    mixing.show_pacal_gecmisi()
elif selected_page == "CALC_Katkı Maliyeti": 
    calculations.show_katki_maliyeti_modulu()
elif selected_page == "CALC_Enzim Dozajlama": 
    calculations.show_enzim_dozajlama()

# ADMIN
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
        # Admin olmayanlar (operations/viewer) sadece profil sekmesini görsün
        tab1, = st.tabs(["👤 Profil Ayarları"])
        with tab1: show_profile_settings()

# PROFILE
elif selected_page == "PROFILE":
    show_profile_settings()

# main.py'nin EN ALTINA (geçici test için)
if st.session_state.get('user_role') == "admin":
    with st.sidebar.expander("🧪 Test: Yeni DB Fonksiyonları"):
        if st.button("Test Update"):
            from app.core.database import update_row_by_filter
            success, msg = update_row_by_filter(
                'silolar',
                {'isim': 'CELIK SILO 1'},
                {'bugday_cinsi': 'TEST'}
            )
            st.write(f"Sonuç: {msg}")


