# -*- coding: utf-8 -*-
import streamlit as st

# 1. DESTEKLENEN DİLLER
LANGUAGES = {
    "Türkçe": "TR",
    "English": "EN",
    "Français": "FR",
    "Русский": "RU"
}

# 2. SÖZLÜK (Tüm çeviriler burada duracak)
DICTIONARY = {
    # --- GİRİŞ EKRANI (LOGIN SCREEN) ---
    "login_header": {
        "TR": "Giriş Yap",
        "EN": "Login",
        "FR": "Connexion",
        "RU": "Вход"
    },
    "username": {
        "TR": "Kullanıcı Adı",
        "EN": "Username",
        "FR": "Nom d'utilisateur",
        "RU": "Имя пользователя"
    },
    "password": {
        "TR": "Şifre",
        "EN": "Password",
        "FR": "Mot de passe",
        "RU": "Пароль"
    },
    "login_button": {
        "TR": "Sisteme Giriş",
        "EN": "Sign In",
        "FR": "Se connecter",
        "RU": "Войти"
    },
    "login_error": {
        "TR": "❌ Hatalı kullanıcı adı veya şifre!",
        "EN": "❌ Invalid username or password!",
        "FR": "❌ Nom d'utilisateur ou mot de passe incorrect !",
        "RU": "❌ Неверное имя пользователя или пароль!"
    },
    "login_welcome": {
        "TR": "Hoşgeldiniz",
        "EN": "Welcome",
        "FR": "Bienvenue",
        "RU": "Добро пожаловать"
    },

    # --- GENEL / GENERAL ---
    "welcome": {
        "TR": "Hoşgeldiniz",
        "EN": "Welcome",
        "FR": "Bienvenue",
        "RU": "Добро пожаловать"
    },
    "logout": {
        "TR": "Çıkış Yap",
        "EN": "Logout",
        "FR": "Déconnexion",
        "RU": "Выйти"
    },
    "select": {
        "TR": "Seçiniz",
        "EN": "Select",
        "FR": "Sélectionner",
        "RU": "Выбрать"
    },
    
    # --- ANA MENÜ / MAIN MENU ---
    "menu_dashboard": {
        "TR": "Dashboard",
        "EN": "Dashboard",
        "FR": "Tableau de bord",
        "RU": "Панель управления"
    },
    "menu_quality": {
        "TR": "Kalite Kontrol",
        "EN": "Quality Control",
        "FR": "Contrôle Qualité",
        "RU": "Контроль качества"
    },
    "menu_mill": {
        "TR": "Değirmen",
        "EN": "Mill Management",
        "FR": "Gestion du Moulin",
        "RU": "Управление мельницей"
    },
    "menu_finance": {
        "TR": "Finans & Strateji",
        "EN": "Finance & Strategy",
        "FR": "Finance & Stratégie",
        "RU": "Финансы и стратегия"
    },
    "menu_admin": {
        "TR": "Yönetim Paneli",
        "EN": "Admin Panel",
        "FR": "Panneau d'administration",
        "RU": "Админ панель"
    },
    
    # --- KULLANICI ROLLERİ ---
    "role_admin": {
        "TR": "Yönetici", "EN": "Admin", "FR": "Administrateur", "RU": "Администратор"
    },
    "role_quality": {
        "TR": "Kalite Kontrol", "EN": "Quality Control", "FR": "Contrôle Qualité", "RU": "Контроль качества"
    },
    "role_operations": {
        "TR": "Operasyon", "EN": "Operations", "FR": "Opérations", "RU": "Операции"
    },
    "role_management": {
        "TR": "Üst Yönetim", "EN": "Top Management", "FR": "Haute Direction", "RU": "Высшее руководство"
    },
    # --- MAL KABUL EKRANI (WHEAT INTAKE) ---
    "header_goods_receipt": {
        "TR": "Mal Kabul ve Stok Girişi",
        "EN": "Goods Receipt & Stock Entry",
        "FR": "Réception Marchandises & Entrée Stock",
        "RU": "Прием товаров и ввод запасов"
    },
    "subheader_basic_info": {
        "TR": "Temel Bilgiler",
        "EN": "Basic Information",
        "FR": "Informations de Base",
        "RU": "Основная информация"
    },
    "subheader_lab_analysis": {
        "TR": "Laboratuvar Analiz Değerleri",
        "EN": "Lab Analysis Values",
        "FR": "Valeurs d'Analyse de Laboratoire",
        "RU": "Лабораторные анализы"
    },
    "label_silo_select": {
        "TR": "Depolanacak Silo",
        "EN": "Target Silo",
        "FR": "Silo de Stockage",
        "RU": "Целевой силос"
    },
    "label_date": {
        "TR": "Kabul Tarihi",
        "EN": "Receipt Date",
        "FR": "Date de Réception",
        "RU": "Дата приема"
    },
    "label_wheat_type": {
        "TR": "Buğday Cinsi",
        "EN": "Wheat Type",
        "FR": "Type de Blé",
        "RU": "Сорт пшеницы"
    },
    "label_supplier": {
        "TR": "Tedarikçi/Firma",
        "EN": "Supplier/Company",
        "FR": "Fournisseur/Entreprise",
        "RU": "Поставщик/Компания"
    },
    "label_region": {
        "TR": "Yöre/Bölge",
        "EN": "Region",
        "FR": "Région",
        "RU": "Region"
    },
    "label_plate": {
        "TR": "Plaka",
        "EN": "Vehicle Plate",
        "FR": "Plaque d'immatriculation",
        "RU": "Номер машины"
    },
    "label_quantity": {
        "TR": "Gelen Miktar (Ton)",
        "EN": "Quantity (Ton)",
        "FR": "Quantité (Tonne)",
        "RU": "Количество (Тонн)"
    },
    "label_price": {
        "TR": "Alış Fiyatı (TL)",
        "EN": "Purchase Price (Currency)",
        "FR": "Prix d'Achat",
        "RU": "Цена покупки"
    },
    "btn_save_record": {
        "TR": "Kaydı Tamamla",
        "EN": "Complete Record",
        "FR": "Terminer l'Enregistrement",
        "RU": "Завершить запись"
    },
    # Analizler
    "ana_moisture": {"TR": "Rutubet (%)", "EN": "Moisture (%)", "FR": "Humidité (%)", "RU": "Влажность (%)"},
    "ana_protein": {"TR": "Protein (%)", "EN": "Protein (%)", "FR": "Protéine (%)", "RU": "Белок (%)"},
    "ana_gluten": {"TR": "Gluten (%)", "EN": "Gluten (%)", "FR": "Gluten (%)", "RU": "Глютен (%)"},
}

def t(key):
    """
    Seçili dile göre metni getirir.
    Örnek: t("welcome") -> "Welcome" (Eğer dil EN ise)
    """
    # Session state'den dili al, yoksa varsayılan TR
    current_lang_code = st.session_state.get('language_code', 'TR')
    
    try:
        # 1. Anahtar var mı kontrol et
        if key in DICTIONARY:
            # 2. O anahtarın içinde seçili dil var mı?
            if current_lang_code in DICTIONARY[key]:
                return DICTIONARY[key][current_lang_code]
            else:
                # Dil yoksa varsayılan olarak İngilizce veya Türkçe dön
                return DICTIONARY[key].get("EN", DICTIONARY[key].get("TR", key))
        else:
            return f"[{key}]" # Çeviri unutulmuşsa belli et (Debug için)
    except Exception:
        return key

