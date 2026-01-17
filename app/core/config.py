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
