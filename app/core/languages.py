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
        "TR": "Giriş Yap", "EN": "Login", "FR": "Connexion", "RU": "Вход"
    },
    "username": {
        "TR": "Kullanıcı Adı", "EN": "Username", "FR": "Nom d'utilisateur", "RU": "Имя пользователя"
    },
    "password": {
        "TR": "Şifre", "EN": "Password", "FR": "Mot de passe", "RU": "Пароль"
    },
    "login_button": {
        "TR": "Sisteme Giriş", "EN": "Sign In", "FR": "Se connecter", "RU": "Войти"
    },
    "login_error": {
        "TR": "❌ Hatalı kullanıcı adı veya şifre!",
        "EN": "❌ Invalid username or password!",
        "FR": "❌ Nom d'utilisateur ou mot de passe incorrect !",
        "RU": "❌ Неверное имя пользователя или пароль!"
    },
    "login_welcome": {
        "TR": "Hoşgeldiniz", "EN": "Welcome", "FR": "Bienvenue", "RU": "Добро пожаловать"
    },

    # --- GENEL / GENERAL ---
    "welcome": {
        "TR": "Hoşgeldiniz", "EN": "Welcome", "FR": "Bienvenue", "RU": "Добро пожаловать"
    },
    "logout": {
        "TR": "Çıkış Yap", "EN": "Logout", "FR": "Déconnexion", "RU": "Выйти"
    },
    "select": {
        "TR": "Seçiniz", "EN": "Select", "FR": "Sélectionner", "RU": "Выбрать"
    },
    
    # --- ANA MENÜ / MAIN MENU ---
    "menu_dashboard": {
        "TR": "Dashboard", "EN": "Dashboard", "FR": "Tableau de bord", "RU": "Панель управления"
    },
    "menu_quality": {
        "TR": "Kalite Kontrol", "EN": "Quality Control", "FR": "Contrôle Qualité", "RU": "Контроль качества"
    },
    "menu_mill": {
        "TR": "Değirmen", "EN": "Mill Management", "FR": "Gestion du Moulin", "RU": "Управление мельницей"
    },
    "menu_finance": {
        "TR": "Finans & Strateji", "EN": "Finance & Strategy", "FR": "Finance & Stratégie", "RU": "Финансы и стратегия"
    },
    "menu_admin": {
        "TR": "Yönetim Paneli", "EN": "Admin Panel", "FR": "Panneau d'administration", "RU": "Админ панель"
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

    # --- MAL KABUL / WHEAT INTAKE (YENİ EKLENENLER) ---
    "header_goods_receipt": {
        "TR": "Ham Madde Giriş",
        "EN": "Raw Material Intake",
        "FR": "Réception Matières Premières",
        "RU": "Прием сырья"
    },
    "subheader_basic_info": {
        "TR": "Temel Bilgiler",
        "EN": "General Information",
        "FR": "Informations Générales",
        "RU": "Общая информация"
    },
    "label_lot": {
        "TR": "Lot No",
        "EN": "Batch No / Lot ID",
        "FR": "N° de Lot",
        "RU": "Номер партии"
    },
    "label_silo": {
        "TR": "Depolanacak Silo",
        "EN": "Target Bin / Dest. Silo",
        "FR": "Silo de Destination",
        "RU": "Силос назначения"
    },
    "label_balance": {
        "TR": "Kalan Kapasite",
        "EN": "Current Stock / Balance",
        "FR": "Stock Actuel",
        "RU": "Текущий остаток"
    },
    "label_date": {
        "TR": "Kabul Tarihi",
        "EN": "Intake Date",
        "FR": "Date de Réception",
        "RU": "Дата приемки"
    },
    "label_standard": {
        "TR": "Standart",
        "EN": "Standard",
        "FR": "Standard",
        "RU": "Стандарт / ГОСТ"
    },
    "label_variety": {
        "TR": "Buğday Cinsi",
        "EN": "Wheat Variety",
        "FR": "Variété de Blé",
        "RU": "Сорт пшеницы"
    },
    "label_supplier": {
        "TR": "Tedarikçi/Firma",
        "EN": "Supplier",
        "FR": "Fournisseur",
        "RU": "Поставщик"
    },
    "label_origin": {
        "TR": "Yöre/Bölge",
        "EN": "Origin / Region",
        "FR": "Provenance",
        "RU": "Происхождение"
    },
    "label_plate": {
        "TR": "Plaka",
        "EN": "Truck Plate / Vehicle ID",
        "FR": "Immatriculation",
        "RU": "Номер ТС"
    },
    "label_notes": {
        "TR": "Notlar",
        "EN": "Remarks / Notes",
        "FR": "Remarques",
        "RU": "Примечания"
    },
    "label_weight": {
        "TR": "Gelen Miktar (Ton)",
        "EN": "Net Weight / Intake Qty",
        "FR": "Poids Net",
        "RU": "Вес нетто / Приход"
    },
    "label_price": {
        "TR": "Alış Fiyatı (TL)",
        "EN": "Purchase Price",
        "FR": "Prix d'Achat",
        "RU": "Закупочная цена"
    },
    "subheader_quality": {
        "TR": "Laboratuvar Analiz Değerleri",
        "EN": "Quality Parameters",
        "FR": "Paramètres de Qualité",
        "RU": "Лабораторные показатели"
    },
    "btn_submit": {
        "TR": "Kaydı Tamamla",
        "EN": "Submit Entry / Save",
        "FR": "Enregistrer",
        "RU": "Сохранить запись"
    },
    
    # --- ANALİZ PARAMETRELERİ ---
    "ana_test_weight": {"TR": "Hektolitre", "EN": "Test Weight", "FR": "Poids Spécifique (PS)", "RU": "Натура (Natura)"},
    "ana_moisture": {"TR": "Rutubet (%)", "EN": "Moisture", "FR": "Humidité", "RU": "Влажность"},
    "ana_protein": {"TR": "Protein (%)", "EN": "Protein", "FR": "Protéine", "RU": "Белок"},
    "ana_gluten": {"TR": "Gluten (%)", "EN": "Wet Gluten", "FR": "Gluten Humide", "RU": "Клейковина"},
    "ana_gluten_index": {"TR": "Gluten Index", "EN": "Gluten Index", "FR": "Index de Gluten", "RU": "Индекс клейковины (ИДК)"},
    "ana_sedim": {"TR": "Sedim (ml)", "EN": "Sedimentation (Zeleny)", "FR": "Indice de Zélény", "RU": "Седиментация"},
    "ana_falling_number": {"TR": "Düşme Sayısı (FN)", "EN": "Falling Number", "FR": "Temps de Chute", "RU": "Число падения"},
    
} # <--- İŞTE BU PARANTEZ ÇOK ÖNEMLİ, UNUTULURSA SYNTAX HATASI VERİR

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
            return f"[{key}]" # Çeviri unutulmuşsa belli et
    except Exception:
        return key
