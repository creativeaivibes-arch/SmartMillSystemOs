import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import time
from app.core.database import fetch_data, add_data, get_conn

# Sistemin ana menüde ve yetkilendirmede kullandığı roller
ROLES = {
    "admin": "Sistem Yöneticisi",
    "operations": "Operasyon Sorumlusu",
    "viewer": "İzleyici"
}

def hash_password(password):
    """Şifreyi güvenli hale getirir"""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_password(password, hashed_password):
    """Şifre doğrulaması yapar"""
    return hash_password(password) == hashed_password

def do_logout():
    """Kullanıcı çıkış işlemini yapar ve sayfayı yeniler"""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.user_role = None
    st.session_state.user_fullname = None
    st.rerun()

def update_user_password(username, new_password):
    """Kullanıcının şifresini günceller"""
    try:
        conn = get_conn()
        df = fetch_data("kullanicilar")
        
        if df.empty:
            return False, "Kullanıcı tablosu bulunamadı."
        
        # Kullanıcıyı bul
        mask = df['kullanici_adi'] == username
        if not mask.any():
            return False, "Kullanıcı bulunamadı."
        
        # Şifreyi güncelle
        df.loc[mask, 'sifre_hash'] = hash_password(new_password)
        
        # Google Sheets'i güncelle
        conn.update(worksheet="kullanicilar", data=df)
        return True, "Şifre başarıyla güncellendi."
    except Exception as e:
        return False, f"Hata oluştu: {str(e)}"

def login_user(username, password):
    """Kullanıcı giriş işlemi"""
    df = fetch_data("kullanicilar")
    
    if df.empty:
        # Tablo boşsa varsayılan admin oluştur
        st.warning("⚠️ Kullanıcı tablosu boş! Varsayılan yönetici oluşturuluyor...")
        admin_data = {
            'kullanici_adi': 'admin',
            'sifre_hash': hash_password('admin123'),
            'rol': 'admin',
            'ad_soyad': 'Sistem Yöneticisi',
            'olusturma_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if add_data("kullanicilar", admin_data):
            st.success("✅ Varsayılan admin oluşturuldu. Lütfen tekrar giriş yapın.")
            time.sleep(2)
            st.rerun()
        return False

    # Kullanıcı kontrolü
    user = df[df['kullanici_adi'] == username]
    if not user.empty:
        stored_hash = user.iloc[0]['sifre_hash']
        if check_password(password, stored_hash):
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.user_role = user.iloc[0]['rol']
            st.session_state.user_fullname = user.iloc[0]['ad_soyad']
            return True
            
    return False

def show_profile_settings():
    """Kullanıcının kendi bilgilerini ve şifresini değiştirebileceği ekran"""
    st.subheader("👤 Profil ve Şifre Ayarları")
    
    # Kullanıcı bilgilerini gösteren küçük bir kart
    with st.container(border=True):
        st.write(f"**Ad Soyad:** {st.session_state.user_fullname}")
        st.write(f"**Kullanıcı Adı:** {st.session_state.username}")
        st.write(f"**Yetki Seviyesi:** {ROLES.get(st.session_state.user_role, st.session_state.user_role)}")

    st.divider()
    
    with st.form("password_change_form"):
        st.write("🔑 **Şifre Değiştir**")
        new_pass = st.text_input("Yeni Şifre", type="password")
        confirm_pass = st.text_input("Yeni Şifre (Tekrar)", type="password")
        
        submit = st.form_submit_button("Şifreyi Güncelle", type="primary")
        
        if submit:
            if not new_pass:
                st.error("Lütfen yeni bir şifre girin.")
            elif new_pass != confirm_pass:
                st.error("Şifreler uyuşmuyor!")
            elif len(new_pass) < 6:
                st.warning("Şifre en az 6 karakter olmalıdır.")
            else:
                success, msg = update_user_password(st.session_state.username, new_pass)
                if success:
                    st.success("✅ Şifreniz başarıyla değiştirildi! Bir sonraki girişte yeni şifrenizi kullanın.")
                else:
                    st.error(msg)
