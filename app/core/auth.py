import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import time
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.database import fetch_data, add_data, get_conn

# Sistemin ana menüde ve yetkilendirmede kullandığı roller
ROLES = {
    "admin": "Yönetici",
    "quality": "Kalite Kontrol",
    "operations": "Operasyon",
    "management": "Üst Yönetim"
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

def send_password_email(recipient_email, recipient_name, username, new_password):
    """
    Kullanıcıya şifre bilgisini mail ile gönderir.
    
    Args:
        recipient_email: Alıcının email adresi
        recipient_name: Alıcının adı soyadı
        username: Kullanıcı adı
        new_password: Yeni şifre (düz metin)
    
    Returns:
        tuple: (başarı durumu: bool, mesaj: str)
    """
    try:
        # Secrets'ten mail ayarlarını al
        smtp_server = st.secrets["email"]["SMTP_SERVER"]
        smtp_port = int(st.secrets["email"]["SMTP_PORT"])
        sender_email = st.secrets["email"]["SENDER_EMAIL"]
        sender_password = st.secrets["email"]["SENDER_PASSWORD"]
        sender_name = st.secrets["email"]["SENDER_NAME"]
        
        # Email içeriği
        subject = "SmartMill System OS - Şifre Bilgisi"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #1e3a8a; text-align: center;">🏭 SmartMill System OS</h2>
                    <hr style="border: 1px solid #ddd;">
                    
                    <p>Merhaba <strong>{recipient_name}</strong>,</p>
                    
                    <p>Sistem yöneticisi tarafından hesabınızın şifresi sıfırlanmıştır.</p>
                    
                    <div style="background-color: #f3f4f6; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 5px 0;"><strong>Kullanıcı Adı:</strong> {username}</p>
                        <p style="margin: 5px 0;"><strong>Geçici Şifre:</strong> <span style="color: #dc2626; font-size: 18px;">{new_password}</span></p>
                    </div>
                    
                    <p><strong>⚠️ Önemli Güvenlik Uyarısı:</strong></p>
                    <ul>
                        <li>Bu şifre ile sisteme giriş yaptıktan sonra, <strong>mutlaka</strong> kendi şifrenizi değiştirin.</li>
                        <li><strong>Profil Ayarları</strong> bölümünden şifrenizi güncelleyebilirsiniz.</li>
                        <li>Bu maili güvenli bir yerde saklayın veya şifrenizi değiştirdikten sonra silin.</li>
                    </ul>
                    
                    <hr style="border: 1px solid #ddd;">
                    
                    <p style="text-align: center; color: #666; font-size: 12px;">
                        Bu mail otomatik olarak gönderilmiştir. Lütfen yanıtlamayın.<br>
                        SmartMill System OS © 2025
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Mail oluştur
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = recipient_email
        
        # HTML içeriği ekle
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Mail gönder
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True, f"Mail başarıyla gönderildi: {recipient_email}"
        
    except KeyError:
        return False, "⚠️ Mail ayarları secrets.toml dosyasında bulunamadı."
    except smtplib.SMTPAuthenticationError:
        return False, "❌ Mail gönderimi başarısız: Kimlik doğrulama hatası. Lütfen mail ayarlarını kontrol edin."
    except Exception as e:
        return False, f"❌ Mail gönderimi başarısız: {str(e)}"

def update_user_password(username, new_password, send_email=False):
    """
    Kullanıcının şifresini günceller (bcrypt ile)
    """
    try:
        conn = get_conn()
        df = fetch_data("kullanicilar")
        
        if df.empty:
            return False, "Kullanıcı tablosu bulunamadı.", None
        
        # Kullanıcıyı bul
        mask = df['kullanici_adi'] == username
        if not mask.any():
            return False, "Kullanıcı bulunamadı.", None
        
        # Kullanıcı bilgilerini al
        user_email = df.loc[mask, 'email'].iloc[0] if 'email' in df.columns else None
        user_fullname = df.loc[mask, 'ad_soyad'].iloc[0] if 'ad_soyad' in df.columns else username
        
        # Şifreyi güncelle (BCRYPT İLE)
        df.loc[mask, 'sifre_hash'] = hash_password_bcrypt(new_password)  # ← DEĞİŞTİ
        
        # Google Sheets'i güncelle
        conn.update(worksheet="kullanicilar", data=df)
        
        # Mail gönderme işlemi (değişmedi)
        if send_email and user_email and user_email.strip():
            mail_success, mail_msg = send_password_email(user_email, user_fullname, username, new_password)
            if mail_success:
                return True, "Şifre başarıyla güncellendi ve kullanıcıya mail gönderildi.", user_email
            else:
                return True, f"Şifre güncellendi ancak mail gönderilemedi: {mail_msg}", user_email
        
        return True, "Şifre başarıyla güncellendi.", user_email
        
    except Exception as e:
        return False, f"Hata oluştu: {str(e)}", None

def login_user(username, password):
    """
    Kullanıcı giriş işlemi (SHA256 ve bcrypt destekli - geriye uyumlu)
    """
    df = fetch_data("users")
    
    if df.empty:
        # Tablo boşsa varsayılan admin oluştur (bcrypt ile)
        st.warning("⚠️ Kullanıcı tablosu boş! Varsayılan yönetici oluşturuluyor...")
        admin_data = {
            'kullanici_adi': 'admin',
            'sifre_hash': hash_password_bcrypt('admin123'),  # ← BCRYPT İLE
            'rol': 'admin',
            'ad_soyad': 'Sistem Yöneticisi',
            'email': '',
            'olusturma_tarihi': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        if add_data("kullanicilar", admin_data):
            st.success("✅ Varsayılan admin oluşturuldu (Şifre: admin123). Lütfen tekrar giriş yapın.")
            time.sleep(2)
            st.rerun()
        return False

    # Kullanıcı kontrolü
    user = df[df['kullanici_adi'] == username]
    if not user.empty:
        stored_hash = user.iloc[0]['sifre_hash']
        
        # ===== GERİYE UYUMLU ŞİFRE KONTROLÜ =====
        
        # 1. Önce bcrypt ile dene
        if is_bcrypt_hash(stored_hash):
            # Bcrypt hash - modern yöntem
            if check_password_bcrypt(password, stored_hash):
                # Başarılı giriş
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_role = user.iloc[0]['rol']
                st.session_state.user_fullname = user.iloc[0]['ad_soyad']
                return True
            else:
                return False
        
        # 2. Eski SHA256 hash ise kontrol et ve otomatik geçir
        else:
            # Eski yöntemle kontrol et
            if check_password(password, stored_hash):  # ESKİ FONKSİYON
                # Şifre doğru! Otomatik bcrypt'e geçir
                if migrate_user_to_bcrypt(username, password):
                    st.info("🔒 Güvenlik: Şifreniz yeni güvenlik standardına yükseltildi.")
                
                # Başarılı giriş
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_role = user.iloc[0]['rol']
                st.session_state.user_fullname = user.iloc[0]['ad_soyad']
                return True
            else:
                return False
    
    return False

def show_profile_settings():
    """Kullanıcının kendi bilgilerini ve şifresini değiştirebileceği ekran (Hata Korumalı)"""
    st.subheader("👤 Profil ve Şifre Ayarları")
    
    # 1. Veriyi Çek
    df = fetch_data("users")
    
    # 2. Tablo Boş mu Kontrol Et
    if df.empty:
        st.warning("⚠️ 'users' tablosu boş veya okunamadı.")
        return

    # 3. Sütun İsimlerini Kontrol Et (KeyError Çözümü)
    # Eğer 'kullanici_adi' yoksa, olası İngilizce karşılıkları kontrol et
    if 'kullanici_adi' not in df.columns:
        # Yaygın alternatif isimleri düzeltmeye çalış
        col_map = {
            'username': 'kullanici_adi',
            'user_name': 'kullanici_adi',
            'email': 'email',
            'password': 'sifre_hash',
            'pass': 'sifre_hash',
            'role': 'rol'
        }
        df = df.rename(columns=col_map)
        
        # Hala yoksa hata mesajı verip dur (Çökme yerine mesaj)
        if 'kullanici_adi' not in df.columns:
            st.error("🚨 Veritabanı Hatası: 'users' tablosunda **'kullanici_adi'** sütunu bulunamadı.")
            st.write("Mevcut Sütunlar:", list(df.columns))
            st.info("Lütfen Google Sheets dosyasındaki başlıkların şu şekilde olduğundan emin olun: `kullanici_adi`, `sifre_hash`, `rol`, `ad_soyad`, `email`")
            return

    # 4. Kullanıcıyı Bul
    user_data = df[df['kullanici_adi'] == st.session_state.username]
    
    user_email = ""
    if not user_data.empty and 'email' in user_data.columns:
        user_email = user_data.iloc[0]['email']
    
    # 5. Bilgileri Göster
    with st.container(border=True):
        st.write(f"**Ad Soyad:** {st.session_state.user_fullname}")
        st.write(f"**Kullanıcı Adı:** {st.session_state.username}")
        st.write(f"**Email:** {user_email if user_email else '(Tanımlanmamış)'}")
        # Rol ismini güvenli çek
        rol_adi = ROLES.get(st.session_state.user_role, st.session_state.user_role)
        st.write(f"**Yetki Seviyesi:** {rol_adi}")

    st.divider()
    
    # 6. Şifre Değiştirme Formu
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
                success, msg, _ = update_user_password(st.session_state.username, new_pass, send_email=False)
                if success:
                    st.success("✅ Şifreniz başarıyla değiştirildi! Bir sonraki girişte yeni şifrenizi kullanın.")
                else:
                    st.error(msg)
def hash_password_bcrypt(password):
    """
    Güvenli şifre hash'leme (bcrypt ile)
    
    Args:
        password: Düz metin şifre
    
    Returns:
        str: Bcrypt hash'i
    """
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password_bcrypt(password, hashed_password):
    """
    Bcrypt hash ile şifre doğrulama
    
    Args:
        password: Düz metin şifre
        hashed_password: Bcrypt hash'i
    
    Returns:
        bool: Şifre doğru mu?
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except:
        return False


def is_bcrypt_hash(hash_string):
    """
    Bir hash'in bcrypt formatında olup olmadığını kontrol eder
    
    Bcrypt hash'leri "$2b$" ile başlar
    
    Args:
        hash_string: Kontrol edilecek hash
    
    Returns:
        bool: Bcrypt hash'i mi?
    """
    return hash_string.startswith('$2b$') or hash_string.startswith('$2a$')


def migrate_user_to_bcrypt(username, plain_password):
    """
    Kullanıcının şifresini SHA256'dan bcrypt'e geçirir
    
    Args:
        username: Kullanıcı adı
        plain_password: Doğru şifre (giriş sırasında alınır)
    
    Returns:
        bool: Geçiş başarılı mı?
    """
    try:
        conn = get_conn()
        df = fetch_data("kullanicilar")
        
        if df.empty:
            return False
        
        mask = df['kullanici_adi'] == username
        if not mask.any():
            return False
        
        # Yeni bcrypt hash oluştur
        new_hash = hash_password_bcrypt(plain_password)
        
        # Güncelle
        df.loc[mask, 'sifre_hash'] = new_hash
        conn.update(worksheet="kullanicilar", data=df)
        
        return True
    except Exception as e:
        st.error(f"Bcrypt geçiş hatası: {e}")
        return False





