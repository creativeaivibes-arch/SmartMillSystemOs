import streamlit as st
from datetime import datetime, date
from app.core.languages import t

# ==========================================
# LİSANS YAPILANDIRMASI (CONFIG)
# ==========================================
# İleride bu bilgileri veritabanından veya şifreli bir dosyadan çekebiliriz.
# Şimdilik "Hardcoded" (Gömülü) olarak buraya yazıyoruz.

LICENSE_CONFIG = {
    "CLIENT_NAME": "KONYA OVM UN FABRİKASI",  # Müşteri Adı
    "LICENSE_KEY": "SMART-2026-PRO-X8Y2",     # Lisans Anahtarı (Görünürlük için)
    "EXPIRATION_DATE": "2028-02-08",          # YYYY-AA-GG Formatında Bitiş Tarihi
    "IS_DEMO": False,                         # Demo mu Full sürüm mü?
    "MAX_USERS": 5                            # (Opsiyonel) Maksimum kullanıcı sayısı
}

# ==========================================
# LİSANS KONTROL FONKSİYONU
# ==========================================
def check_license():
    """
    Lisans durumunu kontrol eder.
    
    Dönüş Değerleri:
    - is_valid (bool): Lisans geçerli mi?
    - message (str): Kullanıcıya gösterilecek mesaj
    - status (str): Durum kodu ('ok', 'warning', 'expired', 'error')
    - days_left (int): Kalan gün sayısı
    """
    try:
        # Tarih formatını parçala (YYYY-AA-GG)
        exp_date_str = LICENSE_CONFIG.get("EXPIRATION_DATE", "2000-01-01")
        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d").date()
        today = date.today()
        
        # Kalan günü hesapla
        days_left = (exp_date - today).days
        
        # 1. DURUM: SÜRE BİTTİ (KİLİT)
        if days_left < 0:
            return False, t('license_expired'), 'expired', 0
            
        # 2. DURUM: AZ KALDI (UYARI - Son 15 gün)
        elif days_left <= 15:
            return True, f"{t('license_warning')} ({days_left} {t('days_left')})", 'warning', days_left
            
        # 3. DURUM: SORUN YOK
        else:
            return True, t('license_active'), 'ok', days_left
            
    except Exception as e:
        # Tarih formatı bozuksa veya başka hatada sistemi kilitle (Güvenlik)
        return False, f"Lisans hatası / License Error: {str(e)}", 'error', 0

# ==========================================
# KİLİT EKRANI (LOCK SCREEN)
# ==========================================
def show_license_lock_screen():
    """
    Lisans süresi dolduğunda gösterilecek "Kırmızı Ekran".
    Programın geri kalanının çalışmasını durdurur.
    """
    
    # CSS ile Arkaplanı Karart
    st.markdown("""
        <style>
            .stApp {
                background-color: #1E1E1E !important;
            }
            .lock-container {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin-top: 50px;
                padding: 40px;
                background-color: #2D2D2D;
                border: 2px solid #FF4B4B;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            }
            .lock-icon {
                font-size: 80px;
                margin-bottom: 20px;
            }
            .lock-title {
                color: #FF4B4B;
                font-size: 32px;
                font-weight: bold;
                font-family: 'Helvetica', sans-serif;
                margin-bottom: 10px;
            }
            .lock-client {
                color: #FFFFFF;
                font-size: 24px;
                margin-bottom: 20px;
            }
            .lock-info {
                color: #AAAAAA;
                font-size: 14px;
                margin-top: 20px;
                border-top: 1px solid #444;
                padding-top: 10px;
                width: 100%;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Kilit Ekranı İçeriği
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown(f"""
            <div class="lock-container">
                <div class="lock-icon">⛔</div>
                <div class="lock-title">{t('license_expired')}</div>
                <div class="lock-client">{LICENSE_CONFIG['CLIENT_NAME']}</div>
                <p style="color: #DDD;">{t('contact_support')}</p>
                <div class="lock-info">
                    License Key: {LICENSE_CONFIG['LICENSE_KEY']}<br>
                    System ID: {hash(LICENSE_CONFIG['CLIENT_NAME']) % 1000000}
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Sidebar'ı temizle (kullanıcı menüye erişemesin)
    with st.sidebar:
        st.empty()
    
    # Kodun akışını burada kes!

    st.stop()



