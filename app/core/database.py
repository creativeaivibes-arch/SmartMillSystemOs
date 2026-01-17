import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- AYARLAR ---
TTL_SECONDS = 0 

def get_conn():
    """
    Google Sheets bağlantısını kurar.
    ÖZEL DÜZELTME: Private Key format hatasını otomatik giderir.
    """
    try:
        # 1. Secrets içindeki ham veriyi al (Hata vermemesi için try içinde)
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            secrets = st.secrets["connections"]["gsheets"]
            
            # 2. Private Key var mı bak
            if "private_key" in secrets:
                pk = secrets["private_key"]
                # Eğer \n karakterleri "yazı" olarak geldiyse, onları gerçek satır başı yap
                if "\\n" in pk:
                    pk = pk.replace("\\n", "\n")
                
                # 3. Düzeltilmiş şifre ile bağlanmayı zorla
                return st.connection("gsheets", type=GSheetsConnection, private_key=pk)
    except Exception:
        # Bir sorun olursa varsayılan yöntemi dene
        pass
        
    return st.connection("gsheets", type=GSheetsConnection)

def fetch_data(sheet_name):
    """Veri okuma"""
    conn = get_conn()
    try:
        df = conn.read(worksheet=sheet_name, ttl=TTL_SECONDS)
        if df is None: return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()

def add_data(sheet_name, data_dict):
    """Veri ekleme"""
    conn = get_conn()
    try:
        existing_data = fetch_data(sheet_name)
        new_row = pd.DataFrame([data_dict])
        
        if existing_data.empty:
            updated_data = new_row
        else:
            updated_data = pd.concat([existing_data, new_row], ignore_index=True)
            
        conn.update(worksheet=sheet_name, data=updated_data)
        return True
    except Exception as e:
        st.error(f"Kayıt eklenirken hata: {e}")
        return False
