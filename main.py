import streamlit as st
from app.core.utils import init_session_state
from app.core.auth import login_user, do_logout, show_profile_settings, ROLES

# Senin klasör yapındaki gerçek dosya isimlerine göre importlar (production yerine mill kullanıldı)
import app.modules.dashboard as dashboard
import app.modules.wheat as wheat
import app.modules.flour as flour
import app.modules.mill as mill # production.py yerine mill.py çağırıldı

# 1. Sayfa Ayarları
st.set_page_config(page_title="SmartMill System OS", page_icon="🏭", layout="wide")
init_session_state()

# 2. Giriş Kontrolü
if not st.session_state.get('logged_in', False):
    st.markdown("<h1 style='text-align: center;'>🏭 SmartMill System OS</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            u = st.text_input("Kullanıcı Adı")
            p = st.text_input("Şifre", type="password")
            if st.form_submit_button("Giriş Yap", type="primary", use_container_width=True):
                if login_user(u, p): st.rerun()
                else: st.error("Hatalı giriş!")
    st.stop()

# 3. Menü
with st.sidebar:
    st.title("🏗️ SmartMill")
    st.write(f"Kullanıcı: **{st.session_state.user_fullname}**")
    choice = st.radio("Menü", [
        "📊 Dashboard", 
        "🌾 Buğday & Stok", 
        "🧪 Laboratuvar", 
        "🏭 Üretim & Valsler", 
        "🧮 Maliyet", 
        "👤 Profil Ayarları", 
        "🚪 Çıkış"
    ])

# 4. Yönlendirmeler
if choice == "📊 Dashboard":
    dashboard.show_dashboard()
elif choice == "🌾 Buğday & Stok":
    tab1, tab2 = st.tabs(["Kamyon Giriş", "Silo Durumları"])
    with tab1: wheat.show_wheat_entry()
    with tab2: wheat.show_silo_status()
elif choice == "🧪 Laboratuvar":
    tab1, tab2, tab3 = st.tabs(["Un Analiz Kaydı", "Analiz Arşivi", "Spec Yönetimi"])
    with tab1: flour.show_un_analiz_kaydi()
    with tab2: flour.show_un_analiz_kayitlari()
    with tab3: flour.show_spec_yonetimi()
elif choice == "🏭 Üretim & Valsler":
    # mill.py içindeki ana fonksiyonu çağırıyoruz
    mill.show_production_main() 
elif choice == "🧮 Maliyet":
    tab1, tab2 = st.tabs(["Un Maliyet Hesaplama", "Maliyet Geçmişi"])
    with tab1: flour.show_un_maliyet_hesaplama()
    with tab2: flour.show_un_maliyet_gecmisi()
elif choice == "👤 Profil Ayarları":
    show_profile_settings()
elif choice == "🚪 Çıkış":
    if st.button("Çıkışı Onayla"):
        do_logout()
