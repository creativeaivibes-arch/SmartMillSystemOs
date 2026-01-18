import streamlit as st

def init_session_state():
    """Session state'i başlat"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.session_state.username = None
        st.session_state.active_module = None
        st.session_state.selected_menu = "Silo Durumu (Dashboard)"
        st.session_state.show_debug = False
    
    # PDF state
    if 'pdf_bytes' not in st.session_state:
        st.session_state.pdf_bytes = None
    if 'pdf_dosya_adi' not in st.session_state:
        st.session_state.pdf_dosya_adi = None
    
    # ✅ DATABASE CACHE STATE (YENİ!)
    if 'db_cache' not in st.session_state:
        st.session_state.db_cache = {}
    if 'db_cache_time' not in st.session_state:
        st.session_state.db_cache_time = {}

def turkce_karakter_duzelt(text):
    """Türkçe karakterleri düzelt"""
    if not isinstance(text, str):
        return text
    cevirme_tablosu = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    for turkce, ingilizce in cevirme_tablosu.items():
        text = text.replace(turkce, ingilizce)
    return text
