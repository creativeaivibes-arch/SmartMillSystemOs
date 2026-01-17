"""
PROFESYONEL HATA YÖNETİMİ SİSTEMİ
3 Seviyeli Loglama + Akıllı Hata ID + Otomatik Bildirim
"""

import logging
import logging.handlers
import traceback
from datetime import datetime
import os
import json
from typing import Optional, Dict, Any
import sqlite3

# Modül durumu
ERROR_HANDLING_AVAILABLE = True

# ==================== KONFİGÜRASYON ====================
class ErrorConfig:
    """Hata yönetimi konfigürasyonu"""
    
    # Log seviyeleri
    LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    # Log dosyaları
    LOG_DIR = "logs"
    ERROR_LOG = os.path.join(LOG_DIR, "errors.log")
    DEBUG_LOG = os.path.join(LOG_DIR, "debug.log")
    SYSTEM_LOG = os.path.join(LOG_DIR, "system.log")
    
    # Email bildirimi (opsiyonel)
    EMAIL_ENABLED = False
    ADMIN_EMAIL = "admin@degirmen.com.tr"
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    
    # Hata kategorileri
    ERROR_CATEGORIES = {
        'DB': 'Veritabanı',
        'AUTH': 'Kimlik Doğrulama',
        'VALIDATION': 'Doğrulama',
        'SYSTEM': 'Sistem',
        'NETWORK': 'Ağ',
        'FILE': 'Dosya İşlemleri',
        'UNKNOWN': 'Bilinmeyen'
    }

# ==================== HATA HANDLER CLASS ====================
class ErrorHandler:
    """
    Merkezi Hata Yönetim Sistemi
    Akıllı Hata ID + 3 Seviyeli Log + Otomatik Bildirim
    """
    
    _instance = None
    _error_count = 0
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super(ErrorHandler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._setup_logging()
        self._setup_database()
        
        # Hata çözümleri veritabanı
        self._solutions_db = self._load_solutions()
    
    def _setup_logging(self):
        """3 seviyeli loglama sistemini kur"""
        
        # Log klasörünü oluştur
        os.makedirs(ErrorConfig.LOG_DIR, exist_ok=True)
        
        # 1. ROOT LOGGER (Konsol + Dosya)
        self.logger = logging.getLogger('FlourMillSystem')
        self.logger.setLevel(logging.DEBUG)
        
        # Konsol handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(module)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        
        # 2. ERROR LOGGER (Sadece hatalar)
        error_handler = logging.handlers.RotatingFileHandler(
            ErrorConfig.ERROR_LOG,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        error_handler.setLevel(logging.ERROR)
        error_format = logging.Formatter(
            '%(asctime)s | ERROR | %(module)s.%(funcName)s | %(message)s'
        )
        error_handler.setFormatter(error_format)
        
        # 3. DEBUG LOGGER (Tüm detaylar)
        debug_handler = logging.handlers.RotatingFileHandler(
            ErrorConfig.DEBUG_LOG,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_format = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s'
        )
        debug_handler.setFormatter(debug_format)
        
        # 4. SYSTEM LOGGER (Sistem olayları)
        system_handler = logging.FileHandler(ErrorConfig.SYSTEM_LOG)
        system_handler.setLevel(logging.INFO)
        system_format = logging.Formatter(
            '%(asctime)s | SYSTEM | %(message)s'
        )
        system_handler.setFormatter(system_format)
        
        # Handler'ları ekle
        self.logger.addHandler(console_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(debug_handler)
        self.logger.addHandler(system_handler)
        
        self.logger.info("✅ Hata yönetim sistemi başlatıldı")
    
    def _setup_database(self):
        """Hata logları için veritabanı tablosu oluştur"""
        try:
            conn = sqlite3.connect('bugday_stok.db')
            c = conn.cursor()
            
            c.execute('''CREATE TABLE IF NOT EXISTS hata_loglari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hata_id TEXT UNIQUE NOT NULL,
                tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                seviye TEXT NOT NULL,
                kategori TEXT NOT NULL,
                modul TEXT NOT NULL,
                fonksiyon TEXT NOT NULL,
                hata_mesaji TEXT NOT NULL,
                kullanici TEXT,
                ip_adresi TEXT,
                user_agent TEXT,
                stack_trace TEXT,
                cozum_onerisi TEXT,
                cozuldu INTEGER DEFAULT 0,
                cozulme_tarihi TIMESTAMP,
                tekrar_sayisi INTEGER DEFAULT 1,
                CONSTRAINT chk_seviye CHECK(seviye IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
                CONSTRAINT chk_kategori CHECK(kategori IN ('DB', 'AUTH', 'VALIDATION', 'SYSTEM', 'NETWORK', 'FILE', 'UNKNOWN')),
                CONSTRAINT chk_cozuldu CHECK(cozuldu IN (0, 1))
            )''')
            
            # İndeksler
            c.execute('CREATE INDEX IF NOT EXISTS idx_hata_id ON hata_loglari(hata_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_tarih ON hata_loglari(tarih)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_seviye ON hata_loglari(seviye)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_kategori ON hata_loglari(kategori)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_cozuldu ON hata_loglari(cozuldu)')
            
            conn.commit()
            conn.close()
            
            self.logger.info("✅ Hata log veritabanı tablosu oluşturuldu")
            
        except Exception as e:
            print(f"❌ Hata veritabanı kurulum hatası: {e}")
    
    def _load_solutions(self) -> Dict[str, str]:
        """Hata çözümleri veritabanı"""
        return {
            'sqlite3.OperationalError': 'Veritabanı bağlantı hatası. İnternet bağlantınızı kontrol edin.',
            'sqlite3.IntegrityError': 'Veri bütünlüğü hatası. Benzersiz alan kontrolü yapın.',
            'ValueError': 'Geçersiz değer. Lütfen girilen değerleri kontrol edin.',
            'TypeError': 'Tip uyuşmazlığı. Beklenen veri tipini kontrol edin.',
            'FileNotFoundError': 'Dosya bulunamadı. Dosya yolunu kontrol edin.',
            'PermissionError': 'Erişim izni hatası. Dosya izinlerini kontrol edin.',
            'ConnectionError': 'Ağ bağlantı hatası. İnternet bağlantınızı kontrol edin.',
            'TimeoutError': 'Zaman aşımı hatası. İşlemi tekrar deneyin.',
            'KeyError': 'Anahtar hatası. Sözlük anahtarını kontrol edin.',
            'IndexError': 'İndeks hatası. Liste/dizi boyutunu kontrol edin.',
            'ZeroDivisionError': 'Sıfıra bölme hatası. Matematiksel işlemi kontrol edin.',
            'AttributeError': 'Özellik hatası. Nesne özelliklerini kontrol edin.',
            'ImportError': 'Import hatası. Kütüphane kurulumunu kontrol edin.',
            'MemoryError': 'Bellek hatası. Sistem kaynaklarını kontrol edin.',
            'KeyboardInterrupt': 'Kullanıcı iptali. İşlem kullanıcı tarafından durduruldu.',
        }
    
    def generate_error_id(self, category: str = 'UNKNOWN') -> str:
        """Akıllı Hata ID oluştur: ERR-YYYYMMDD-SSS-CAT-MOD"""
        
        ErrorHandler._error_count += 1
        timestamp = datetime.now().strftime('%Y%m%d')
        sequence = str(ErrorHandler._error_count).zfill(3)
        
        # Kategori kısaltması
        cat_map = {
            'DB': 'DB',
            'AUTH': 'AUTH',
            'VALIDATION': 'VAL',
            'SYSTEM': 'SYS',
            'NETWORK': 'NET',
            'FILE': 'FILE',
            'UNKNOWN': 'UNK'
        }
        
        category_code = cat_map.get(category, 'UNK')
        
        return f"ERR-{timestamp}-{sequence}-{category_code}"
    
    def _categorize_error(self, error: Exception) -> str:
        """Hatayı kategoriye ayır"""
        error_name = type(error).__name__
        
        if 'sqlite' in error_name.lower():
            return 'DB'
        elif 'password' in str(error).lower() or 'auth' in str(error).lower():
            return 'AUTH'
        elif 'value' in str(error).lower() or 'type' in str(error).lower():
            return 'VALIDATION'
        elif 'file' in str(error).lower() or 'io' in str(error).lower():
            return 'FILE'
        elif 'connection' in str(error).lower() or 'network' in str(error).lower():
            return 'NETWORK'
        else:
            return 'SYSTEM'
    
    def _get_solution_suggestion(self, error: Exception, context: str) -> str:
        """Hataya özel çözüm önerisi"""
        error_name = type(error).__name__
        
        # Önceden tanımlı çözümler
        if error_name in self._solutions_db:
            return self._solutions_db[error_name]
        
        # Context'e göre özel çözümler
        if 'database' in context.lower() or 'veritabanı' in context.lower():
            return "Veritabanı bağlantısını kontrol edin. İnternet bağlantınız aktif mi?"
        
        elif 'login' in context.lower() or 'giriş' in context.lower():
            return "Kullanıcı adı ve şifrenizi kontrol edin. Hesabınız aktif mi?"
        
        elif 'save' in context.lower() or 'kaydet' in context.lower():
            return "Girdiğiniz değerleri kontrol edin. Zorunlu alanlar dolduruldu mu?"
        
        elif 'file' in context.lower() or 'dosya' in context.lower():
            return "Dosya yolunu ve izinlerini kontrol edin. Dosya mevcut mu?"
        
        return "Sistem yöneticinize başvurun ve hata ID'sini iletin."
    
    def log(
        self,
        level: str,
        message: str,
        error: Optional[Exception] = None,
        context: str = "",
        user: Optional[str] = None,
        module: str = "",
        function: str = ""
    ) -> Dict[str, Any]:
        """
        Merkezi log fonksiyonu
        Returns: {'error_id': str, 'user_message': str, 'solution': str}
        """
        
        # Hata ID oluştur
        category = self._categorize_error(error) if error else 'SYSTEM'
        error_id = self.generate_error_id(category)
        
        # Çözüm önerisi
        solution = self._get_solution_suggestion(error, context) if error else ""
        
        # Stack trace
        stack_trace = traceback.format_exc() if error else ""
        
        # Log mesajı oluştur
        log_message = f"{error_id} | {context} | {message}"
        if error:
            log_message += f" | {type(error).__name__}: {str(error)}"
        
        # Log level'a göre kaydet
        if level == 'DEBUG':
            self.logger.debug(log_message)
        elif level == 'INFO':
            self.logger.info(log_message)
        elif level == 'WARNING':
            self.logger.warning(log_message)
        elif level == 'ERROR':
            self.logger.error(log_message)
        elif level == 'CRITICAL':
            self.logger.critical(log_message)
        
        # Veritabanına kaydet (ERROR ve CRITICAL seviyeleri)
        if level in ['ERROR', 'CRITICAL'] and error:
            try:
                conn = sqlite3.connect('bugday_stok.db')
                c = conn.cursor()
                
                # IP ve User-Agent (basit versiyon)
                import socket
                try:
                    ip = socket.gethostbyname(socket.gethostname())
                except:
                    ip = "127.0.0.1"
                
                user_agent = "FlourMillSystem/2.0"
                
                # Var olan hata mı kontrol et
                c.execute('''SELECT id, tekrar_sayisi FROM hata_loglari 
                           WHERE hata_mesaji LIKE ? AND cozuldu = 0''',
                          (f"%{type(error).__name__}%",))
                
                existing = c.fetchone()
                
                if existing:
                    # Var olan hatanın tekrar sayısını artır
                    c.execute('''UPDATE hata_loglari 
                               SET tekrar_sayisi = tekrar_sayisi + 1,
                                   tarih = CURRENT_TIMESTAMP
                               WHERE id = ?''', (existing[0],))
                else:
                    # Yeni hata ekle
                    c.execute('''INSERT INTO hata_loglari 
                               (hata_id, seviye, kategori, modul, fonksiyon,
                                hata_mesaji, kullanici, ip_adresi, user_agent,
                                stack_trace, cozum_onerisi)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (error_id, level, category, module, function,
                               str(error)[:500], user, ip, user_agent,
                               stack_trace[:2000], solution))
                
                conn.commit()
                conn.close()
                
            except Exception as db_error:
                self.logger.error(f"Hata log kaydetme hatası: {db_error}")
        
        # Kullanıcı dostu mesaj
        user_message = self._create_user_message(error_id, level, context, error)
        
        return {
            'error_id': error_id,
            'user_message': user_message,
            'solution': solution,
            'category': category,
            'level': level
        }
    
    def _create_user_message(self, error_id: str, level: str, context: str, error: Exception) -> str:
        """Kullanıcı dostu hata mesajı oluştur"""
        
        if level == 'INFO':
            return f"ℹ️ {context} tamamlandı."
        
        elif level == 'WARNING':
            return f"⚠️ {context}: Dikkat gerektiren durum."
        
        elif level == 'ERROR':
            error_type = type(error).__name__ if error else "Hata"
            
            messages = {
                'DB': f"🔴 **Veritabanı Hatası** (ID: {error_id})\n\n{context} işlemi başarısız. Veritabanı bağlantısını kontrol edin.",
                'AUTH': f"🔐 **Kimlik Doğrulama Hatası** (ID: {error_id})\n\n{context} işlemi başarısız. Yetkinizi kontrol edin.",
                'VALIDATION': f"📝 **Doğrulama Hatası** (ID: {error_id})\n\n{context} işlemi başarısız. Girilen değerleri kontrol edin.",
                'FILE': f"📁 **Dosya İşlemi Hatası** (ID: {error_id})\n\n{context} işlemi başarısız. Dosya sistemini kontrol edin.",
                'NETWORK': f"🌐 **Ağ Bağlantı Hatası** (ID: {error_id})\n\n{context} işlemi başarısız. İnternet bağlantınızı kontrol edin.",
                'SYSTEM': f"⚙️ **Sistem Hatası** (ID: {error_id})\n\n{context} işlemi başarısız. Lütfen hata ID'sini kaydedin.",
                'UNKNOWN': f"❓ **Bilinmeyen Hata** (ID: {error_id})\n\n{context} işlemi başarısız. Sistem yöneticinize başvurun."
            }
            
            category = self._categorize_error(error) if error else 'UNKNOWN'
            return messages.get(category, messages['UNKNOWN'])
        
        elif level == 'CRITICAL':
            return f"🚨 **KRİTİK SİSTEM HATASI** (ID: {error_id})\n\nSistem durduruldu. Acil müdahale gerekiyor!"
        
        return f"📌 {context}"
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Hata istatistiklerini getir"""
        try:
            conn = sqlite3.connect('bugday_stok.db')
            c = conn.cursor()
            
            stats = {}
            
            # Toplam hata sayısı
            c.execute("SELECT COUNT(*) FROM hata_loglari")
            stats['total_errors'] = c.fetchone()[0]
            
            # Çözülmemiş hatalar
            c.execute("SELECT COUNT(*) FROM hata_loglari WHERE cozuldu = 0")
            stats['unresolved'] = c.fetchone()[0]
            
            # Bugünkü hatalar
            c.execute("SELECT COUNT(*) FROM hata_loglari WHERE DATE(tarih) = DATE('now')")
            stats['today_errors'] = c.fetchone()[0]
            
            # Kategori dağılımı
            c.execute('''SELECT kategori, COUNT(*) as sayi 
                       FROM hata_loglari 
                       GROUP BY kategori 
                       ORDER BY sayi DESC''')
            stats['by_category'] = dict(c.fetchall())
            
            # Sık tekrarlayan hatalar
            c.execute('''SELECT hata_mesaji, tekrar_sayisi 
                       FROM hata_loglari 
                       WHERE tekrar_sayisi > 1 
                       ORDER BY tekrar_sayisi DESC 
                       LIMIT 5''')
            stats['recurring'] = c.fetchall()
            
            conn.close()
            return stats
            
        except Exception as e:
            self.logger.error(f"İstatistik getirme hatası: {e}")
            return {}

# ==================== KOLAY KULLANIM FONKSİYONLARI ====================
# Singleton instance
_error_handler = None

def get_error_handler() -> ErrorHandler:
    """Global error handler instance"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler

def handle_error(
    error: Exception,
    context: str = "",
    user: Optional[str] = None,
    module: str = "",
    function: str = ""
) -> Dict[str, Any]:
    """
    Kolay kullanım için wrapper fonksiyon
    Returns: {'error_id': str, 'user_message': str}
    """
    handler = get_error_handler()
    
    # Hata mesajı
    error_message = f"{type(error).__name__}: {str(error)[:200]}"
    
    # Log'la ve kullanıcı mesajını al
    result = handler.log(
        level='ERROR',
        message=error_message,
        error=error,
        context=context,
        user=user,
        module=module,
        function=function
    )
    
    return result

def log_info(message: str, context: str = ""):
    """Bilgi mesajı log'la"""
    handler = get_error_handler()
    handler.log(level='INFO', message=message, context=context)

def log_warning(message: str, context: str = ""):
    """Uyarı mesajı log'la"""
    handler = get_error_handler()
    handler.log(level='WARNING', message=message, context=context)

def log_debug(message: str, context: str = ""):
    """Debug mesajı log'la"""
    handler = get_error_handler()
    handler.log(level='DEBUG', message=message, context=context)

def log_error(message: str, context: str = "", error: Optional[Exception] = None):
    """Hata mesajı log'la"""
    handler = get_error_handler()
    handler.log(level='ERROR', message=message, context=context, error=error)

# ==================== DECORATOR ====================
def error_handler(context: str = ""):
    """
    Decorator: Fonksiyonları otomatik hata yönetimi ile sarmalar
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                log_debug(f"{func.__name__} başlatıldı", context)
                result = func(*args, **kwargs)
                log_debug(f"{func.__name__} başarılı", context)
                return result
                
            except Exception as e:
                # Hata bilgileri
                module = func.__module__ if hasattr(func, '__module__') else ""
                
                # Kullanıcı bilgisi (session'dan al)
                user = None
                try:
                    import streamlit as st
                    if hasattr(st, 'session_state') and hasattr(st.session_state, 'username'):
                        user = st.session_state.username
                except:
                    pass
                
                # Hatayı işle
                result = handle_error(
                    error=e,
                    context=f"{context} - {func.__name__}",
                    user=user,
                    module=module,
                    function=func.__name__
                )
                
                # Kullanıcıya göster
                try:
                    import streamlit as st
                    st.error(result['user_message'])
                except:
                    print(result['user_message'])
                
                # Fonksiyon None dönsün
                return None
        
        return wrapper
    return decorator
