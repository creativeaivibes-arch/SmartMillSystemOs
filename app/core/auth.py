import streamlit as st
import pandas as pd
import time
import bcrypt
from datetime import datetime

# YENİ IMPORTLAR (Google Sheets)
from app.core.database import fetch_data, add_data

# --- ROL TANIMLARI ---
ROLES = {
    "admin": {
        "sistem": ["Kullanıcı Yönetimi", "Yedekleme ve Veri Güvenliği", "Sistem Logları"],
        "buğday": ["Silo Durumu (Dashboard)", "Mal Kabul (Giriş)", "Stok Çıkış (Yıkama)", 
                   "Tavlı Buğday Analiz", "Paçal Hesaplayıcı", "Paçal Geçmişi (Rapor)", 
                   "Stok Hareketleri (Log)", "Buğday Giriş Arşivi", "Buğday Spesifikasyonları"],
        "un": ["Un Analiz Kaydı", "Un Analiz Kayıtları", "Un Spesifikasyonları"],
        "değirmen": ["Üretim Kaydı", "Üretim Arşivi"],
        "hesaplamalar": ["Un Maliyet Hesaplama", "Un Maliyet Geçmişi", "Katkı Maliyet Hesaplama", 
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

# --- ŞİFRE YÖNETİMİ ---

def hash_password(password):
    """Şifreyi bcrypt ile hash'le"""
    try:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    except Exception as e:
        st.error(f"Şifreleme hatası: {e}")
        return None

def check_password_hash(password, hashed_password):
    """Şifreyi kontrol et"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def check_password(username, password):
    """
    Kullanıcıyı Google Sheets üzerinden doğrula.
    Eğer tablo boşsa varsayılan admin kullanıcısını oluşturur.
    """
    try:
        # 1. Kullanıcı tablosunu çek
        df_users = fetch_data("kullanicilar")
        
        # 2. ACİL DURUM: Eğer tablo boşsa (İlk Kurulum) Admin oluştur
        if df_users.empty:
            st.warning("⚠️ Kullanıcı tablosu boş! Varsayılan yönetici oluşturuluyor...")
            
            default_pass = "admin123"
            hashed_pw = hash_password(default_pass)
            
            admin_user = {
                "kullanici_adi": "admin",
                "sifre_hash": hashed_pw,
                "rol": "admin",
                "ad_soyad": "Sistem Yöneticisi",
                "olusturma_tarihi": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if add_data("kullanicilar", admin_user):
                st.success(f"✅ Yönetici oluşturuldu! Kullanıcı: **admin** / Şifre: **{default_pass}**")
                time.sleep(2)
                st.rerun()
            else:
                st.error("Varsayılan kullanıcı oluşturulamadı. Veritabanı bağlantısını kontrol edin.")
                return None

        # 3. Kullanıcıyı Bul (Pandas ile filtreleme)
        # Kullanıcı adını küçük harfe çevirerek arayalım (case-insensitive)
        if 'kullanici_adi' not in df_users.columns:
            st.error("Veritabanı hatası: 'kullanici_adi' sütunu bulunamadı.")
            return None

        user_row = df_users[df_users['kullanici_adi'] == username]
        
        if user_row.empty:
            return None # Kullanıcı yok
            
        # 4. Şifreyi Doğrula
        stored_hash = user_row.iloc[0]['sifre_hash']
        
        # Hash boşsa hata
        if pd.isna(stored_hash) or stored_hash == "":
            return None
            
        if check_password_hash(password, stored_hash):
            # Giriş Başarılı - Kullanıcı bilgilerini sözlük olarak dön
            user_data = user_row.iloc[0].to_dict()
            
            # Sözlük anahtarlarını standartlaştır (main.py beklentisi için)
            return {
                "username": user_data['kullanici_adi'],
                "role": user_data['rol'],
                "full_name": user_data.get('ad_soyad', user_data['kullanici_adi'])
            }
            
        return None # Şifre yanlış

    except Exception as e:
        st.error(f"Giriş işlemi hatası: {e}")
        return None

def do_logout():
    """Kullanıcı çıkış işlemi"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.logged_in = False
    st.rerun()
