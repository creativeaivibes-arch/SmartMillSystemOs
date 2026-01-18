import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

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
            # Örnek bir tabloyu çekerek bağlantıyı doğrula
            conn.read(worksheet="kullanicilar", ttl=0)
            return True
    except:
        # Tablo yoksa veya bağlantı kurulamazsa sessizce geç veya logla
        pass
    return False

def fetch_data(worksheet_name):
    """Belirtilen sekmedeki tüm verileri çeker"""
    try:
        conn = get_conn()
        if conn:
            # ttl=0 verinin her seferinde güncel gelmesini sağlar
            return conn.read(worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.error(f"Veri çekme hatası ({worksheet_name}): {str(e)}")
    return pd.DataFrame()

def add_data(worksheet_name, data_dict):
    """Google Sheets'e yeni bir satır ekler"""
    try:
        conn = get_conn()
        df = fetch_data(worksheet_name)
        
        # Yeni veriyi DataFrame'e dönüştür
        new_row = pd.DataFrame([data_dict])
        
        # Mevcut verinin altına ekle
        updated_df = pd.concat([df, new_row], ignore_index=True)
        
        # Sayfayı güncelle
        conn.update(worksheet=worksheet_name, data=updated_df)
        return True
    except Exception as e:
        st.error(f"Veri ekleme hatası: {str(e)}")
        return False
