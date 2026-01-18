import streamlit as st
from app.core.utils import init_session_state
from app.core.auth import login_user, do_logout, show_profile_settings, ROLES

# Modülleri klasör bazlı değil, dosya bazlı direkt çağırıyoruz (Daha güvenli yöntem)
import app.modules.dashboard as dashboard
import app.modules.wheat as wheat
import app.modules.flour as flour
import app.modules.production as production

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
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Kullanıcı Adı")
            password = st.text_input("Şifre", type="password")
            submit = st.form_submit_button("Giriş Yap", type="primary", use_container_width=True)
            
            if submit:
                if login_user(username, password):
                    st.success("Giriş başarılı!")
                    st.rerun()
                else:
                    st.error("Hatalı kullanıcı adı veya şifre!")
    st.stop()

# 3. Kenar Çubuğu Menüsü
with st.sidebar:
    st.title("🏗️ SmartMill")
    st.write(f"Hoş geldin, **{st.session_state.user_fullname}**")
    st.divider()
    
    choice = st.radio("Ana Menü", [
        "📊 Dashboard",
        "🌾 Buğday Kabul & Stok",
        "🧪 Laboratuvar (Un Analizleri)",
        "🏭 Üretim & Valsler",
        "🧮 Hesaplamalar & Maliyet",
        "👤 Profil Ayarları",
        "🚪 Çıkış Yap"
    ])

# 4. Sayfa Yönlendirmeleri
if choice == "📊 Dashboard":
    dashboard.show_dashboard()

elif choice == "🌾 Buğday Kabul & Stok":
    tab1, tab2 = st.tabs(["Kamyon Giriş", "Silo Durumları"])
    with tab1: wheat.show_wheat_entry()
    with tab2: wheat.show_silo_status()

elif choice == "🧪 Laboratuvar (Un Analizleri)":
    tab1, tab2, tab3 = st.tabs(["Un Analiz Kaydı", "Analiz Arşivi", "Spec Yönetimi"])
    with tab1: flour.show_un_analiz_kaydi()
    with tab2: flour.show_un_analiz_kayitlari()
    with tab3: flour.show_spec_yonetimi()

elif choice == "🏭 Üretim & Valsler":
    production.show_production_main()

elif choice == "🧮 Hesaplamalar & Maliyet":
    tab1, tab2 = st.tabs(["Un Maliyet Hesaplama", "Maliyet Geçmişi"])
    with tab1: flour.show_un_maliyet_hesaplama()
    with tab2: flour.show_un_maliyet_gecmisi()

elif choice == "👤 Profil Ayarları":
    show_profile_settings()

elif choice == "🚪 Çıkış Yap":
    if st.button("Çıkışı Onayla"):
        do_logout()
