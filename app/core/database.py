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

def update_data(worksheet_name, df_updated):
    """
    Worksheet'in tamamını günceller ve cache'i temizler
    
    Args:
        worksheet_name: Google Sheets sekme adı
        df_updated: Güncellenmiş DataFrame
    
    Returns:
        bool: Başarı durumu
    """
    try:
        conn = get_conn()
        if conn:
            conn.update(worksheet=worksheet_name, data=df_updated)
            
            # Cache'i temizle
            clear_cache(worksheet_name)
            
            return True
        return False
    except Exception as e:
        st.error(f"Güncelleme hatası ({worksheet_name}): {str(e)}")
        return False


def update_row_by_filter(worksheet_name, filter_dict, update_dict):
    """
    Belirli bir satırı filtre ile bulup günceller
    
    Args:
        worksheet_name: Sekme adı
        filter_dict: Filtreleme kriteri (örn: {'lot_no': 'UN-123'})
        update_dict: Güncellenecek değerler (örn: {'protein': 12.5})
    
    Returns:
        tuple: (başarı: bool, mesaj: str)
    
    Örnek:
        update_row_by_filter('un_analizleri', 
                            {'lot_no': 'UN-123'}, 
                            {'protein': 12.5, 'gluten': 28.0})
    """
    try:
        df = fetch_data(worksheet_name, force_refresh=True)
        
        if df.empty:
            return False, f"{worksheet_name} tablosu boş!"
        
        # Filtre uygula
        mask = pd.Series([True] * len(df))
        for key, value in filter_dict.items():
            if key not in df.columns:
                return False, f"'{key}' sütunu bulunamadı!"
            mask &= (df[key] == value)
        
        # Eşleşen satır var mı?
        if not mask.any():
            return False, "Eşleşen kayıt bulunamadı!"
        
        # Güncelle
        for key, value in update_dict.items():
            if key not in df.columns:
                return False, f"'{key}' sütunu bulunamadı!"
            df.loc[mask, key] = value
        
        # Kaydet
        if update_data(worksheet_name, df):
            return True, "Güncelleme başarılı!"
        else:
            return False, "Güncelleme sırasında hata oluştu!"
        
    except Exception as e:
        return False, f"Hata: {str(e)}"


def delete_rows_by_filter(worksheet_name, filter_dict):
    """
    Belirli satırları filtre ile bulup siler
    
    Args:
        worksheet_name: Sekme adı
        filter_dict: Silinecek satırların kriteri
    
    Returns:
        tuple: (başarı: bool, mesaj: str, silinen_satir_sayisi: int)
    """
    try:
        df = fetch_data(worksheet_name, force_refresh=True)
        
        if df.empty:
            return False, "Tablo zaten boş!", 0
        
        # Filtre uygula
        mask = pd.Series([True] * len(df))
        for key, value in filter_dict.items():
            if key not in df.columns:
                return False, f"'{key}' sütunu bulunamadı!", 0
            mask &= (df[key] == value)
        
        silinen_sayi = mask.sum()
        
        if silinen_sayi == 0:
            return False, "Silinecek kayıt bulunamadı!", 0
        
        # Sil
        df_new = df[~mask]
        
        if update_data(worksheet_name, df_new):
            return True, f"{silinen_sayi} kayıt silindi!", silinen_sayi
        else:
            return False, "Silme işlemi başarısız!", 0
        
    except Exception as e:
        return False, f"Hata: {str(e)}", 0
