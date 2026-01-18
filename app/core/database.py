import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --------------------------------------------------------------------------
# CACHE YÖNETİMİ - API KOTA OPTİMİZASYONU
# --------------------------------------------------------------------------
# Her worksheet için son fetch zamanını ve veriyi sakla
if 'db_cache' not in st.session_state:
    st.session_state.db_cache = {}
if 'db_cache_time' not in st.session_state:
    st.session_state.db_cache_time = {}

# Cache süresi (saniye) - worksheet'e göre farklı süreler
CACHE_DURATIONS = {
    'silolar': 30,           # Silo verileri 30 saniye cache
    'hareketler': 60,        # Hareketler 60 saniye cache
    'tavli_analiz': 60,      # Tavlı analizler 60 saniye cache
    'bugday_giris_arsivi': 60,  # Arşiv 60 saniye cache
    'bugday_spekleri': 300,  # Spesifikasyonlar 5 dakika cache (az değişir)
    'kullanicilar': 600,     # Kullanıcılar 10 dakika cache (çok az değişir)
    'default': 30            # Diğer tüm tablolar için varsayılan
}

def get_conn():
    """Google Sheets bağlantısını kurar"""
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Bağlantı Hatası: {str(e)}")
        return None

def init_db():
    """
    Main.py tarafından çağrılan başlatma fonksiyonu.
    Google Sheets sisteminde tabloların varlığını kontrol eder.
    """
    try:
        # Bağlantıyı test et
        conn = get_conn()
        if conn:
            # Örnek bir tabloyu çekerek bağlantıyı doğrula (ttl=5 ile hafif cache)
            conn.read(worksheet="kullanicilar", ttl=5)
            return True
    except:
        # Tablo yoksa veya bağlantı kurulamazsa sessizce geç veya logla
        pass
    return False

def fetch_data(worksheet_name, force_refresh=False):
    """
    Belirtilen sekmedeki tüm verileri çeker (OPTİMİZE EDİLMİŞ - CACHE'Lİ)
    
    Args:
        worksheet_name: Google Sheets sekme adı
        force_refresh: True ise cache'i atla, direkt API'den çek
    
    Returns:
        DataFrame: Sekmedeki veriler
    """
    try:
        current_time = time.time()
        
        # Cache süresini belirle
        cache_duration = CACHE_DURATIONS.get(worksheet_name, CACHE_DURATIONS['default'])
        
        # Cache kontrol et (force_refresh yoksa)
        if not force_refresh and worksheet_name in st.session_state.db_cache:
            last_fetch = st.session_state.db_cache_time.get(worksheet_name, 0)
            
            # Cache hala geçerli mi?
            if current_time - last_fetch < cache_duration:
                # Cache'den dön (API çağrısı YOK)
                return st.session_state.db_cache[worksheet_name].copy()
        
        # Cache geçersiz veya yok - API'den çek
        conn = get_conn()
        if conn:
            # ttl=5 ile streamlit-gsheets kendi cache'ini de kullanır
            df = conn.read(worksheet=worksheet_name, ttl=5)
            
            # Session cache'e kaydet
            st.session_state.db_cache[worksheet_name] = df.copy()
            st.session_state.db_cache_time[worksheet_name] = current_time
            
            return df
        else:
            # Bağlantı yoksa eski cache'i dön (varsa)
            if worksheet_name in st.session_state.db_cache:
                return st.session_state.db_cache[worksheet_name].copy()
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Veri çekme hatası ({worksheet_name}): {str(e)}")
        
        # Hata durumunda eski cache'i dön (varsa)
        if worksheet_name in st.session_state.db_cache:
            return st.session_state.db_cache[worksheet_name].copy()
        return pd.DataFrame()

def add_data(worksheet_name, data_dict):
    """Google Sheets'e yeni bir satır ekler ve cache'i temizler"""
    try:
        conn = get_conn()
        df = fetch_data(worksheet_name, force_refresh=True)  # Ekleme öncesi güncel veri
        
        # Yeni veriyi DataFrame'e dönüştür
        new_row = pd.DataFrame([data_dict])
        
        # Mevcut verinin altına ekle
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        # Sayfayı güncelle
        conn.update(worksheet=worksheet_name, data=updated_df)
        
        # CACHE'İ TEMİZLE - Bu worksheet için yeni veri var
        if worksheet_name in st.session_state.db_cache:
            del st.session_state.db_cache[worksheet_name]
        if worksheet_name in st.session_state.db_cache_time:
            del st.session_state.db_cache_time[worksheet_name]
        
        return True
    except Exception as e:
        st.error(f"Veri ekleme hatası: {str(e)}")
        return False

def clear_cache(worksheet_name=None):
    """
    Cache'i temizler
    
    Args:
        worksheet_name: Belirli bir worksheet'in cache'ini temizle. 
                       None ise tüm cache'i temizle.
    """
    if worksheet_name:
        # Sadece belirtilen worksheet'i temizle
        if worksheet_name in st.session_state.db_cache:
            del st.session_state.db_cache[worksheet_name]
        if worksheet_name in st.session_state.db_cache_time:
            del st.session_state.db_cache_time[worksheet_name]
    else:
        # Tüm cache'i temizle
        st.session_state.db_cache = {}
        st.session_state.db_cache_time = {}
