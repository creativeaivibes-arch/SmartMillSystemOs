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
    # --- GİRİŞ EKRANI ---
    "login_header": {"TR": "Giriş Yap", "EN": "Login", "FR": "Connexion", "RU": "Вход"},
    "username": {"TR": "Kullanıcı Adı", "EN": "Username", "FR": "Nom d'utilisateur", "RU": "Имя пользователя"},
    "password": {"TR": "Şifre", "EN": "Password", "FR": "Mot de passe", "RU": "Пароль"},
    "login_button": {"TR": "Sisteme Giriş", "EN": "Sign In", "FR": "Se connecter", "RU": "Войти"},
    "login_error": {"TR": "❌ Hatalı kullanıcı adı veya şifre!", "EN": "❌ Invalid username or password!", "FR": "❌ Nom d'utilisateur ou mot de passe incorrect !", "RU": "❌ Неверное имя пользователя или пароль!"},
    "login_welcome": {"TR": "Hoşgeldiniz", "EN": "Welcome", "FR": "Bienvenue", "RU": "Добро пожаловать"},

    # --- GENEL ---
    "logout": {"TR": "Çıkış Yap", "EN": "Logout", "FR": "Déconnexion", "RU": "Выйти"},
    "select": {"TR": "Seçiniz", "EN": "Select", "FR": "Sélectionner", "RU": "Выбрать"},
    "btn_submit": {"TR": "Kaydı Tamamla", "EN": "Submit", "FR": "Soumettre", "RU": "Отправить"},

    # --- MENÜ İSİMLERİ (Hem Eski 'menu_' hem Yeni 'nav_' anahtarlarını destekler) ---
    "menu_dashboard": {"TR": "Genel Bakış", "EN": "Dashboard", "FR": "Tableau de bord", "RU": "Обзор"},
    "nav_dashboard": {"TR": "Genel Bakış", "EN": "Dashboard", "FR": "Tableau de bord", "RU": "Обзор"},
    
    "menu_quality": {"TR": "Kalite Kontrol", "EN": "Quality Control", "FR": "Contrôle Qualité", "RU": "Контроль качества"},
    "nav_wheat": {"TR": "Buğday Yönetimi", "EN": "Wheat Mgmt", "FR": "Gestion Blé", "RU": "Упр. Пшеницей"},
    "nav_flour": {"TR": "Un Yönetimi", "EN": "Flour Mgmt", "FR": "Gestion Farine", "RU": "Упр. Мукой"},
    
    "menu_mill": {"TR": "Üretim Takip", "EN": "Production", "FR": "Production", "RU": "Производство"},
    "nav_mill": {"TR": "Üretim Takip", "EN": "Production", "FR": "Production", "RU": "Производство"},
    
    "menu_finance": {"TR": "Finans & Strateji", "EN": "Finance", "FR": "Finance", "RU": "Финансы"},
    "nav_finance": {"TR": "Finans & Strateji", "EN": "Finance", "FR": "Finance", "RU": "Финансы"},
    
    "menu_admin": {"TR": "Yönetim Paneli", "EN": "Admin Panel", "FR": "Admin", "RU": "Админ"},
    "nav_admin": {"TR": "Yönetim Paneli", "EN": "Admin Panel", "FR": "Admin", "RU": "Админ"},
    
    "nav_profile": {"TR": "Profil & Ayarlar", "EN": "Profile", "FR": "Profil", "RU": "Профиль"},

    # --- KULLANICI ROLLERİ ---
    "role_admin": {"TR": "Yönetici", "EN": "Admin", "FR": "Administrateur", "RU": "Администратор"},
    "role_quality": {"TR": "Kalite Kontrol", "EN": "Quality Control", "FR": "Contrôle Qualité", "RU": "Контроль качества"},
    "role_operations": {"TR": "Operasyon", "EN": "Operations", "FR": "Opérations", "RU": "Операции"},
    "role_management": {"TR": "Üst Yönetim", "EN": "Top Management", "FR": "Haute Direction", "RU": "Высшее руководство"},

    # --- BUĞDAY (WHEAT) SEKMELERİ ---
    "tab_specs": {"TR": "📏 Kalite Standartları", "EN": "📏 Standards", "FR": "📏 Normes", "RU": "📏 Стандарты"},
    "tab_intake": {"TR": "🚛 Hammadde Giriş", "EN": "🚛 Intake", "FR": "🚛 Réception", "RU": "🚛 Приемка"},
    "tab_tempered": {"TR": "🧪 Tavlı Analiz", "EN": "🧪 Tempered Analysis", "FR": "🧪 Analyse Mouillée", "RU": "🧪 Увлажненный анализ"},
    "tab_mixing": {"TR": "🧮 Akıllı Paçal", "EN": "🧮 Smart Blending", "FR": "🧮 Mélange Intelligent", "RU": "🧮 Умное смешивание"},
    "tab_stock_out": {"TR": "📉 Stok Çıkışı", "EN": "📉 Stock Out", "FR": "📉 Sortie Stock", "RU": "📉 Выход запаса"},
    "tab_trace": {"TR": "📂 İzlenebilirlik", "EN": "📂 Traceability", "FR": "📂 Traçabilité", "RU": "📂 Прослеживаемость"},
        # İzlenebilirlik Alt Sekmeleri
        "sub_archive_in": {"TR": "🗄️ Buğday Giriş Arşivi", "EN": "🗄️ Intake Archive", "FR": "🗄️ Archive Réception", "RU": "🗄️ Архив приемки"},
        "sub_stock_log": {"TR": "📉 Stok Hareketleri", "EN": "📉 Stock Logs", "FR": "📉 Mouvements Stock", "RU": "📉 Логи запаса"},
        "sub_archive_temp": {"TR": "🧪 Tavlı Analiz Arşivi", "EN": "🧪 Analysis Archive", "FR": "🧪 Archive Analyse", "RU": "🧪 Архив анализов"},
        "sub_mixing_log": {"TR": "📜 Paçal Geçmişi", "EN": "📜 Blending History", "FR": "📜 Historique Mélange", "RU": "📜 История смешивания"},

    # --- UN (FLOUR) SEKMELERİ ---
    "tab_flour_specs": {"TR": "🎯 Un Spektleri", "EN": "🎯 Flour Specs", "FR": "🎯 Spécifications", "RU": "🎯 Спецификации"},
    "tab_flour_entry": {"TR": "📝 Un Analiz Kaydı", "EN": "📝 Analysis Entry", "FR": "📝 Saisie Analyse", "RU": "📝 Ввод анализа"},
    "tab_flour_archive": {"TR": "📚 Analiz Arşivi", "EN": "📚 Analysis Archive", "FR": "📚 Archive Analyse", "RU": "📚 Архив анализов"},
    "tab_enzyme": {"TR": "🧬 Enzim Dozaj Hesaplama", "EN": "🧬 Enzyme Dosage", "FR": "🧬 Dosage Enzyme", "RU": "🧬 Дозировка ферментов"},

    # --- FİNANS SEKMELERİ ---
    "tab_cost_calc": {"TR": "💵 Un Maliyet", "EN": "💵 Flour Cost", "FR": "💵 Coût Farine", "RU": "💵 Стоимость муки"},
    "tab_cost_hist": {"TR": "📉 Maliyet Geçmişi", "EN": "📉 Cost History", "FR": "📉 Historique Coûts", "RU": "📉 История затрат"},
    "tab_strategy": {"TR": "♟️ Stratejik Analiz", "EN": "♟️ Strategic Analysis", "FR": "♟️ Analyse Stratégique", "RU": "♟️ Стратегический анализ"},
    "tab_loss": {"TR": "🌾 Buğday Fire Maliyet", "EN": "🌾 Wheat Loss", "FR": "🌾 Perte Blé", "RU": "🌾 Потери пшеницы"},
    "tab_additives": {"TR": "🧪 Katkı Maliyet", "EN": "🧪 Additive Cost", "FR": "🧪 Coût Additifs", "RU": "🧪 Стоимость добавок"},

    # --- ADMIN SEKMELERİ ---
    "tab_my_profile": {"TR": "👤 Profilim", "EN": "👤 My Profile", "FR": "👤 Mon Profil", "RU": "👤 Мой профиль"},
    "tab_users": {"TR": "👥 Kullanıcılar", "EN": "👥 Users", "FR": "👥 Utilisateurs", "RU": "👥 Пользователи"},
    "tab_silo_mgmt": {"TR": "🏭 Silo Yönetimi", "EN": "🏭 Silo Mgmt", "FR": "🏭 Gestion Silos", "RU": "🏭 Упр. силосами"},
    "tab_backup": {"TR": "💾 Yedekleme", "EN": "💾 Backup", "FR": "💾 Sauvegarde", "RU": "💾 Резервное копирование"},
    "tab_logs": {"TR": "📜 Sistem Logları", "EN": "📜 System Logs", "FR": "📜 Logs Système", "RU": "📜 Системные логи"},
    "tab_debug": {"TR": "🛠️ Debug", "EN": "🛠️ Debug", "FR": "🛠️ Débogage", "RU": "🛠️ Отладка"},

    # --- DASHBOARD (YENİ EKLENENLER) ---
    "dash_header": {"TR": "Fabrika Kontrol Merkezi", "EN": "Factory Control Center", "FR": "Centre de Contrôle de l'Usine", "RU": "Центр управления заводом"},
    "btn_refresh": {"TR": "Yenile", "EN": "Refresh", "FR": "Actualiser", "RU": "Обновить"},
    "dash_alert_title": {"TR": "Akıllı Uyarı Sistemi", "EN": "Smart Alert System", "FR": "Système d'Alerte Intelligent", "RU": "Интеллектуальная система оповещения"},
    "btn_download_pdf": {"TR": "PDF Rapor İndir", "EN": "Download PDF Report", "FR": "Télécharger le Rapport PDF", "RU": "Скачать отчет в PDF"},
    "dash_finance_title": {"TR": "Finans", "EN": "Finance", "FR": "Finance", "RU": "Финансы"},
    "dash_stock_value": {"TR": "Stok Değeri", "EN": "Stock Value", "FR": "Valeur du Stock", "RU": "Стоимость запасов"},
    "dash_avg_cost": {"TR": "Ort. Maliyet", "EN": "Avg. Cost", "FR": "Coût Moyen", "RU": "Ср. Себестоимость"},
    "dash_unit_cost": {"TR": "Birim Maliyet", "EN": "Unit Cost", "FR": "Coût Unitaire", "RU": "Себестоимость единицы"},
    "lbl_currency": {"TR": "TL/Kg", "EN": "TRY/kg", "FR": "TRY/kg", "RU": "TRY/кг"},
    "dash_stock_life": {"TR": "Stok Ömrü", "EN": "Stock Life", "FR": "Durée de Stockage", "RU": "Срок хранения запасов"},
    "dash_daily_milling": {"TR": "Günlük Kırma (Ton)", "EN": "Daily Milling (Tons)", "FR": "Mouture Quotidienne (Tonnes)", "RU": "Суточный размол (Тонн)"},
    "dash_remaining_time": {"TR": "Kalan Süre", "EN": "Remaining Time", "FR": "Temps Restant", "RU": "Оставшееся время"},
    "dash_last_24h": {"TR": "Son 24 Saat", "EN": "Last 24 Hours", "FR": "Dernières 24 Heures", "RU": "Последние 24 часа"},
    "dash_input": {"TR": "Giriş", "EN": "Intake", "FR": "Réception", "RU": "Прием"},
    "dash_output": {"TR": "Çıkış", "EN": "Output", "FR": "Expédition", "RU": "Отпуск"},
    "dash_stock_move_7d": {"TR": "Son 7 Günlük Stok Hareketi", "EN": "Last 7 Days Stock Movement", "FR": "Mouvement des Stocks (7 jours)", "RU": "Движение запасов (последние 7 дней)"},
    "dash_live_status": {"TR": "Anlık Silo Durumu", "EN": "Live Silo Status", "FR": "État des Silos en Temps Réel", "RU": "Текущее состояние силосов"},
    "lbl_steel_silo": {"TR": "Çelik Silo", "EN": "Steel Silo", "FR": "Silo en Acier", "RU": "Стальной силос"},
    "lbl_variety": {"TR": "Cins", "EN": "Variety", "FR": "Variété", "RU": "Сорт"},
    "btn_edit_variety": {"TR": "Cins Düzenle", "EN": "Edit Variety", "FR": "Modifier la Variété", "RU": "Редактировать сорт"},
    "lbl_tempered_stock": {"TR": "Tavlı Buğday Stok", "EN": "Tempered Wheat Stock", "FR": "Stock de Blé Conditionné", "RU": "Запас отволоженного зерна"},
    "msg_stock_low": {"TR": "Stok azalıyor", "EN": "Stock Decreasing", "FR": "Stock Faible", "RU": "Запас уменьшается"},

    # --- MAL KABUL & ANALİZ PARAMETRELERİ ---
    "header_goods_receipt": {"TR": "Ham Madde Giriş", "EN": "Raw Material Intake", "FR": "Réception Matières", "RU": "Прием сырья"},
    "subheader_basic_info": {"TR": "Temel Bilgiler", "EN": "General Information", "FR": "Informations Générales", "RU": "Общая информация"},
    "label_lot": {"TR": "Lot No", "EN": "Batch No", "FR": "N° de Lot", "RU": "Номер партии"},
    "label_silo": {"TR": "Depolanacak Silo", "EN": "Target Bin", "FR": "Silo de Destination", "RU": "Силос назначения"},
    "label_balance": {"TR": "Kalan Kapasite", "EN": "Balance", "FR": "Stock Actuel", "RU": "Остаток"},
    "label_date": {"TR": "Kabul Tarihi", "EN": "Date", "FR": "Date", "RU": "Дата"},
    "label_standard": {"TR": "Standart", "EN": "Standard", "FR": "Standard", "RU": "Стандарт"},
    "label_variety": {"TR": "Buğday Cinsi", "EN": "Variety", "FR": "Variété", "RU": "Сорт"},
    "label_supplier": {"TR": "Tedarikçi/Firma", "EN": "Supplier", "FR": "Fournisseur", "RU": "Поставщик"},
    "label_origin": {"TR": "Yöre/Bölge", "EN": "Region", "FR": "Provenance", "RU": "Регион"},
    "label_plate": {"TR": "Plaka", "EN": "Plate No", "FR": "Immatriculation", "RU": "Номер ТС"},
    "label_notes": {"TR": "Notlar", "EN": "Notes", "FR": "Remarques", "RU": "Примечания"},
    "label_weight": {"TR": "Gelen Miktar (Ton)", "EN": "Net Weight", "FR": "Poids Net", "RU": "Вес нетто"},
    "label_price": {"TR": "Alış Fiyatı (TL)", "EN": "Price", "FR": "Prix", "RU": "Цена"},
    "subheader_quality": {"TR": "Laboratuvar Analiz Değerleri", "EN": "Quality Parameters", "FR": "Paramètres Qualité", "RU": "Лабораторные показатели"},
    "ana_test_weight": {"TR": "Hektolitre", "EN": "Test Weight", "FR": "Poids Spécifique", "RU": "Натура"},
    "ana_moisture": {"TR": "Rutubet (%)", "EN": "Moisture", "FR": "Humidité", "RU": "Влажность"},
    "ana_protein": {"TR": "Protein (%)", "EN": "Protein", "FR": "Protéine", "RU": "Белок"},
    "ana_gluten": {"TR": "Gluten (%)", "EN": "Wet Gluten", "FR": "Gluten Humide", "RU": "Клейковина"},
    "ana_gluten_index": {"TR": "Gluten Index", "EN": "Gluten Index", "FR": "Index de Gluten", "RU": "ИДК"},
    "ana_sedim": {"TR": "Sedim (ml)", "EN": "Sedimentation", "FR": "Zélény", "RU": "Седиментация"},
    "ana_falling_number": {"TR": "Düşme Sayısı (FN)", "EN": "Falling Number", "FR": "Temps de Chute", "RU": "Число падения"}
}

def t(key):
    """
    Seçili dile göre metni getirir.
    """
    current_lang_code = st.session_state.get('language_code', 'TR')
    
    try:
        if key in DICTIONARY:
            if current_lang_code in DICTIONARY[key]:
                return DICTIONARY[key][current_lang_code]
            else:
                return DICTIONARY[key].get("EN", DICTIONARY[key].get("TR", key))
        else:
            return f"[{key}]"
    except Exception:
        return key

