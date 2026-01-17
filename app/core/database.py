import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- AYARLAR ---
# Verilerin ne kadar sürede bir güncelleneceği (Saniye)
# 0 yaparsan her seferinde taze veri çeker ama biraz yavaşlayabilir.
TTL_SECONDS = 0 

def get_conn():
    """Google Sheets bağlantısını kurar."""
    return st.connection("gsheets", type=GSheetsConnection)

def fetch_data(sheet_name):
    """
    Belirtilen Excel sayfasındaki (Worksheet) tüm verileri okur.
    Örnek: fetch_data("un_analiz")
    """
    conn = get_conn()
    try:
        # Veriyi çek ve DataFrame formatına çevir
        df = conn.read(worksheet=sheet_name, ttl=TTL_SECONDS)
        
        # Eğer boş gelirse veya sütunlar eksikse boş DataFrame dön
        if df is None:
             return pd.DataFrame()
        return df
    except Exception as e:
        # Eğer sayfa henüz yoksa hata vermemesi için boş dönüyoruz
        return pd.DataFrame()

def add_data(sheet_name, data_dict):
    """
    Excel sayfasına yeni bir satır ekler.
    Kullanımı: add_data("un_analiz", {'Tarih': '2026-01-17', 'Randıman': 76, ...})
    """
    conn = get_conn()
    try:
        # 1. Mevcut verileri çek
        existing_data = fetch_data(sheet_name)
        
        # 2. Yeni veriyi tablo formatına (DataFrame) çevir
        new_row = pd.DataFrame([data_dict])
        
        # 3. Eski veri ile yeni veriyi birleştir
        if existing_data.empty:
            updated_data = new_row
        else:
            # Sütun isimlerinin uyuşmasını garantiye alalım (boşlukları temizle vs.)
            updated_data = pd.concat([existing_data, new_row], ignore_index=True)
            
        # 4. Google Sheets'i güncelle
        conn.update(worksheet=sheet_name, data=updated_data)
        return True
    except Exception as e:
        st.error(f"Kayıt eklenirken bir hata oluştu: {e}")
        return False

# --- ÖZEL FONKSİYONLAR (Main.py ile uyum için) ---

def add_wheat_entry(data):
    """Buğday Giriş Arşivine veri ekler."""
    return add_data("bugday_giris_arsivi", data)

def get_all_wheat():
    """Tüm buğday arşivini getirir."""
    return fetch_data("bugday_giris_arsivi")

def add_flour_analysis(data):
    """Un Analiz sayfasına veri ekler."""
    return add_data("un_analiz", data)

def get_all_flour():
    """Tüm un analizlerini getirir."""
    return fetch_data("un_analiz")

def add_movement(data):
    """Hareketler (Stok/İşlem) sayfasına veri ekler."""
    return add_data("hareketler", data)

def get_movements():
    """Tüm hareket kayıtlarını getirir."""
    return fetch_data("hareketler")

def add_cost_entry(data):
    """Maliyet hesaplamaları sayfasına veri ekler."""
    return add_data("un_maliyet_hesaplamalari", data)

def get_costs():
    """Tüm maliyet kayıtlarını getirir."""
    return fetch_data("un_maliyet_hesaplamalari")

def add_spec(data):
    """Buğday spekleri (Referans değerler) sayfasına veri ekler."""
    return add_data("bugday_spekleri", data)

def get_specs():
    """Tüm spekleri getirir."""
    return fetch_data("bugday_spekleri")
