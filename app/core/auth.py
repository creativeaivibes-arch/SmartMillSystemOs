import streamlit as st

# --- GÜVENLİK KÜTÜPHANELERİ ---
# bcrypt kurulu mu kontrol et
BCRYPT_AVAILABLE = False
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    st.warning("⚠️ Güvenlik için 'bcrypt' kütüphanesi kurulmamış. Şifreler hash'lenemeyecek!")
    bcrypt = None

# --- ŞİFRE YÖNETİMİ FONKSİYONLARI ---
def hash_password(password):
    """Şifreyi bcrypt ile hash'le"""
    if not BCRYPT_AVAILABLE:
        st.error("❌ bcrypt kütüphanesi kurulu değil! Şifreler hash'lenemiyor.")
        return None
    
    if not password:
        st.error("❌ Şifre boş olamaz!")
        return None
    
    try:
        # Salt oluştur ve hash'le
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        st.error(f"❌ Şifre hash'leme hatası: {e}")
        return None

def check_password_hash(password, hashed_password):
    """Şifreyi bcrypt ile kontrol et (Hash doğrulama)"""
    if not BCRYPT_AVAILABLE:
        st.warning("⚠️ bcrypt kurulu değil, şifre kontrolü yapılamıyor!")
        return False
    
    if not hashed_password or not password:
        return False
    
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        st.error(f"❌ Şifre kontrol hatası: {e}")
        return False

def check_password(username, password):
    """Kullanıcıyı veritabanından doğrula"""
    # Circular import önlemek için burada import ediyoruz
    from app.core.database import get_db_connection
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM kullanicilar WHERE kullanici_adi = ?", (username,))
            user = c.fetchone()
            
            if user:
                # Kullanıcı var, şifreyi kontrol et
                # user['sifre_hash'] -> DB'deki hash
                if check_password_hash(password, user['sifre_hash']):
                    # Başarılı giriş
                    
                    # Son giriş tarihini güncelle
                    try:
                        c.execute("UPDATE kullanicilar SET son_giris_tarihi = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
                        conn.commit()
                    except:
                        pass
                    
                    # Kullanıcı bilgilerini map et
                    user_dict = dict(user)
                    user_dict['username'] = user_dict['kullanici_adi']
                    user_dict['role'] = user_dict['rol']
                    user_dict['full_name'] = user_dict.get('ad_soyad', user_dict['kullanici_adi'])
                    
                    return user_dict
            
            return None # Kullanıcı yok veya şifre yanlış
            
    except Exception as e:
        st.error(f"Giriş hatası: {e}")
        return None

def validate_password_strength(password):
    """Şifre gücünü kontrol et"""
    if len(password) < 6:
        return False, "Şifre en az 6 karakter olmalıdır"
    
    if len(password) > 100:
        return False, "Şifre çok uzun"
    
    # İsteğe bağlı: daha karmaşık kurallar ekleyebilirsiniz
    # if not any(char.isdigit() for char in password):
    #     return False, "Şifre en az bir rakam içermeli"
    
    return True, "Şifre uygun"

def do_logout():
    """Kullanıcı çıkış işlemi"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.logged_in = False
    st.rerun()

# --- ROL TANIMLARI ---
ROLES = {
    "admin": {
        "sistem": ["Kullanıcı Yönetimi", "Veritabanı Yedekleme","Yedekleme Dashboard","Sistem Logları"],  # YENİ!
        "buğday": ["Silo Durumu (Dashboard)", "Mal Kabul (Giriş)", "Stok Çıkış (Yıkama)", 
                  "Tavlı Buğday Analiz", "Paçal Hesaplayıcı", "Paçal Geçmişi (Rapor)", 
                  "Stok Hareketleri (Log)", "Buğday Giriş Arşivi"],
        "un": ["Un Analiz Kaydı", "Un Analiz Kayıtları"],
        "değirmen": ["Üretim Kaydı", "Üretim Arşivi"],
        "hesaplamalar": ["Un Maliyet Hesaplama", "Katkı Maliyet Hesaplama", 
                        "Un Geliştirici Enzim Dozajlama Hesaplama"]
    },
    "operations": {
        "buğday": ["Silo Durumu (Dashboard)", "Mal Kabul (Giriş)", "Stok Çıkış (Yıkama)", 
                  "Tavlı Buğday Analiz", "Paçal Geçmişi (Rapor)", "Stok Hareketleri (Log)"],
        "un": ["Un Analiz Kaydı", "Un Analiz Kayıtları"],
        "değirmen": ["Üretim Kaydı", "Üretim Arşivi"],
        "hesaplamalar": ["Un Maliyet Hesaplama", "Katkı Maliyet Hesaplama", 
                        "Un Geliştirici Enzim Dozajlama Hesaplama"]
    },
    "viewer": {
        "buğday": ["Silo Durumu (Dashboard)", "Paçal Geçmişi (Rapor)", 
                  "Stok Hareketleri (Log)", "Buğday Giriş Arşivi"],
        "un": ["Un Analiz Kayıtları"],
        "değirmen": ["Üretim Arşivi"],
        "hesaplamalar": ["Un Maliyet Hesaplama"]
    }
}
