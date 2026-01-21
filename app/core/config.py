# SmartMill System Configuration

# --- SYSTEM SETTINGS ---
SESSION_TIMEOUT_SECONDS = 1800  # 30 Minutes
PAGINATION_LIMIT = 50

# --- TERMINOLOGY STANDARDIZATION ---
TERMS = {
    "rutubet": "Rutubet (%)",
    "protein": "Protein (%)",
    "gluten": "Gluten (%)",
    "gluten_index": "Gluten İndeksi",
    "sedim": "Sedimantasyon (ml)",
    "gecikmeli_sedim": "Gecikmeli Sedim (ml)",
    "hektolitre": "Hektolitre (kg/hl)",
    "fn": "Düşme Sayısı (FN)",
    "ffn": "Fungal Düşme Sayısı (FFN)",
    "kul": "Kül (%)",
    "sune": "Süne (%)",
    "yabanci_tane": "Yabancı Tane (%)"
}

# --- INPUT LIMITS (Validation) ---
# Format: 'field_key': {'min': float, 'max': float, 'default': float, 'step': float}
INPUT_LIMITS = {
    # Wheat Analysis
    "protein": {"min": 0.0, "max": 25.0, "default": 13.0, "step": 0.1},
    "gluten": {"min": 0.0, "max": 50.0, "default": 28.0, "step": 0.1},
    "rutubet": {"min": 0.0, "max": 20.0, "default": 12.0, "step": 0.1},
    "hektolitre": {"min": 0.0, "max": 100.0, "default": 78.0, "step": 0.1},
    "sedim": {"min": 0.0, "max": 100.0, "default": 35.0, "step": 1.0},
    "gluten_index": {"min": 0.0, "max": 100.0, "default": 90.0, "step": 1.0},
    "sune": {"min": 0.0, "max": 100.0, "default": 0.5, "step": 0.1},
    "kul": {"min": 0.0, "max": 5.0, "default": 0.6, "step": 0.01},
    
    # Process Parameters
    "tonaj": {"min": 0.1, "max": 1000.0, "default": 25.0, "step": 0.1},
    "fiyat": {"min": 0.0, "max": 1000.0, "default": 10.0, "step": 0.1},
    
    # Rheology
    "enerji": {"min": 0.0, "max": 500.0, "default": 130.0, "step": 1.0},
    "direnc": {"min": 0.0, "max": 1000.0, "default": 400.0, "step": 5.0},
    "uzama": {"min": 0.0, "max": 300.0, "default": 140.0, "step": 1.0},
    "stabilite": {"min": 0.0, "max": 30.0, "default": 8.0, "step": 0.1}
}

def get_limit(key, param):
    """Safely get a limit parameter"""
    return INPUT_LIMITS.get(key, {}).get(param, 0.0)

def validate_numeric_input(value, field_key, allow_zero=True, allow_negative=False):
    """
    Numerik input validasyonu
    
    Args:
        value: Kontrol edilecek değer
        field_key: INPUT_LIMITS dict'indeki key (örn: 'protein', 'tonaj')
        allow_zero: Sıfır kabul edilsin mi?
        allow_negative: Negatif değer kabul edilsin mi?
    
    Returns:
        tuple: (geçerli_mi: bool, hata_mesaji: str, düzeltilmiş_değer: float)
    
    Örnek:
        valid, msg, corrected = validate_numeric_input(150, 'protein')
        if not valid:
            st.error(msg)
    """
    try:
        value = float(value)
    except:
        return False, f"❌ Geçersiz sayı formatı!", 0.0
    
    # Negatif kontrol
    if not allow_negative and value < 0:
        return False, f"❌ Negatif değer girilemez!", 0.0
    
    # Sıfır kontrol
    if not allow_zero and value == 0:
        return False, f"❌ Değer sıfır olamaz!", 0.0
    
    # Limit kontrolü
    if field_key in INPUT_LIMITS:
        limits = INPUT_LIMITS[field_key]
        min_val = limits.get('min', 0.0)
        max_val = limits.get('max', float('inf'))
        
        if value < min_val:
            return False, f"❌ Minimum değer: {min_val}", min_val
        
        if value > max_val:
            return False, f"❌ Maksimum değer: {max_val}", max_val
    
    return True, "", value


def validate_capacity(current_stock, capacity, adding_amount):
    """
    Kapasite kontrolü
    
    Args:
        current_stock: Mevcut stok (ton)
        capacity: Toplam kapasite (ton)
        adding_amount: Eklenecek miktar (ton)
    
    Returns:
        tuple: (geçerli_mi: bool, hata_mesaji: str, kalan_kapasite: float)
    """
    try:
        current_stock = float(current_stock)
        capacity = float(capacity)
        adding_amount = float(adding_amount)
    except:
        return False, "❌ Geçersiz sayı formatı!", 0.0
    
    kalan = capacity - current_stock
    
    if adding_amount > kalan:
        return False, f"❌ Kapasite aşımı! Sadece {kalan:.1f} ton yer var.", kalan
    
    return True, "", kalan


def validate_stock_withdrawal(current_stock, withdrawal_amount):
    """
    Stok çıkış kontrolü
    
    Args:
        current_stock: Mevcut stok (ton)
        withdrawal_amount: Çıkış miktarı (ton)
    
    Returns:
        tuple: (geçerli_mi: bool, hata_mesaji: str)
    """
    try:
        current_stock = float(current_stock)
        withdrawal_amount = float(withdrawal_amount)
    except:
        return False, "❌ Geçersiz sayı formatı!"
    
    if withdrawal_amount > current_stock:
        return False, f"❌ Yetersiz stok! Mevcut: {current_stock:.1f} ton"
    
    if withdrawal_amount <= 0:
        return False, "❌ Çıkış miktarı sıfırdan büyük olmalı!"
    
    return True, ""

