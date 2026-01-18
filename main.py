import streamlit as st
from app.core.utils import init_session_state
from app.core.auth import login_user, do_logout, show_profile_settings, ROLES
from app.modules import dashboard, wheat, flour, production, lab, reports

# 1. Sayfa Ayarları ve Oturum Başlatma
st.set_page_config(
    page_title="SmartMill System OS",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_session_state()

# 2. Giriş Kontrolü
if not st.session_state.get('logged_in', False):
    st.markdown("<h1 style='text-align: center;'>🏭 SmartMill System OS</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Lütfen devam etmek için giriş yapın.</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Kullanıcı Adı")
            password = st.text_input("Şifre", type="password")
            submit = st.form_submit_button("Giriş Yap", type="primary", use_container_width=True)
            
            if submit:
                if login_user(username, password):
                    st.success("Giriş başarılı! Yönlendiriliyorsunuz...")
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")
    st.stop()

# 3. Kenar Çubuğu (Sidebar) Menüsü
with st.sidebar:
    st.title("🏗️ SmartMill")
    st.write(f"Hoş geldin, **{st.session_state.user_fullname}**")
    st.caption(f"Yetki: {ROLES.get(st.session_state.user_role, st.session_state.user_role)}")
    st.divider()
    
    # Menü Seçenekleri
    menu_options = [
        "📊 Dashboard",
        "🌾 Buğday Kabul & Stok",
        "🧪 Laboratuvar (Un Analizleri)",
        "🏭 Üretim & Valsler",
        "🧮 Hesaplamalar & Maliyet",
        "👤 Profil Ayarları",  # Yeni Eklenen
        "🚪 Çıkış Yap"
    ]
    
    choice = st.radio("Ana Menü", menu_options)

# 4. Sayfa Yönlendirmeleri
if choice == "📊 Dashboard":
    dashboard.show_dashboard()

elif choice == "🌾 Buğday Kabul & Stok":
    tab1, tab2 = st.tabs(["Kamyon Giriş Kaydı", "Silo Durumları"])
    with tab1:
        wheat.show_wheat_entry()
    with tab2:
        wheat.show_silo_status()

elif choice == "🧪 Laboratuvar (Un Analizleri)":
    tab1, tab2, tab3 = st.tabs(["Un Analiz Kaydı", "Analiz Arşivi", "Spesifikasyon (Spec) Yönetimi"])
    with tab1:
        flour.show_un_analiz_kaydi()
    with tab2:
        flour.show_un_analiz_kayitlari()
    with tab3:
        flour.show_spec_yonetimi()

elif choice == "🏭 Üretim & Valsler":
    production.show_production_main()

elif choice == "🧮 Hesaplamalar & Maliyet":
    tab1, tab2 = st.tabs(["Un Maliyet Hesaplama", "Maliyet Geçmişi"])
    with tab1:
        flour.show_un_maliyet_hesaplama()
    with tab2:
        flour.show_un_maliyet_gecmisi()

elif choice == "👤 Profil Ayarları":
    show_profile_settings()

elif choice == "🚪 Çıkış Yap":
    if st.button("Çıkışı Onayla"):
        do_logout()
