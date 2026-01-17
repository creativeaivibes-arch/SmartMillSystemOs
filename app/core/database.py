import sqlite3
from contextlib import contextmanager
from .auth import hash_password

# --- VERİTABANI BAĞLANTI YÖNETİCİSİ ---
@contextmanager
def get_db_connection():
    """Veritabanı bağlantısını context manager ile yönet - GÜVENLİ VERSİYON"""
    conn = sqlite3.connect('bugday_stok.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # Foreign key desteği
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """Veritabanını başlat - TÜM MODÜLLER DAHİL GÜNCEL VERSİYON"""
    with get_db_connection() as conn:
        c = conn.cursor()

        # --- KULLANICILAR TABLOSU ---
        c.execute('''CREATE TABLE IF NOT EXISTS kullanicilar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullanici_adi TEXT UNIQUE NOT NULL,
            sifre_hash TEXT NOT NULL,
            rol TEXT NOT NULL CHECK(rol IN ('admin', 'operations', 'viewer')),
            ad_soyad TEXT,
            eposta TEXT,
            telefon TEXT,
            departman TEXT,
            aktif INTEGER DEFAULT 1,
            olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            son_giris_tarihi TIMESTAMP,
            son_sifre_degistirme TIMESTAMP,
            giris_denemesi INTEGER DEFAULT 0,
            kilitli INTEGER DEFAULT 0,
            CONSTRAINT chk_rol CHECK(rol IN ('admin', 'operations', 'viewer')),
            CONSTRAINT chk_aktif CHECK(aktif IN (0, 1)),
            CONSTRAINT chk_kilitli CHECK(kilitli IN (0, 1))
        )''')

        c.execute('CREATE INDEX IF NOT EXISTS idx_kullanici_adi ON kullanicilar(kullanici_adi)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_rol ON kullanicilar(rol)')

        # --- Varsayılan Kullanıcıları Ekle ---
        # Admin
        c.execute("SELECT COUNT(*) FROM kullanicilar WHERE kullanici_adi = 'admin'")
        if c.fetchone()[0] == 0:
            admin_hash = hash_password("149597")
            if admin_hash:
                c.execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad_soyad, eposta) VALUES (?, ?, ?, ?, ?)",
                          ('admin', admin_hash, 'admin', 'Sistem Yöneticisi', 'admin@degirmen.com.tr'))

        # Kantar
        c.execute("SELECT COUNT(*) FROM kullanicilar WHERE kullanici_adi = 'kantar'")
        if c.fetchone()[0] == 0:
            kantar_hash = hash_password("123456")
            if kantar_hash:
                c.execute("INSERT INTO kullanicilar (kullanici_adi, sifre_hash, rol, ad_soyad, departman) VALUES (?, ?, ?, ?, ?)",
                          ('kantar', kantar_hash, 'operations', 'Kantar Operatörü', 'Kantar'))

        # --- KATKI MALİYET MODÜLÜ TABLOLARI ---
        c.execute('''CREATE TABLE IF NOT EXISTS katki_enzimler 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT UNIQUE, fiyat REAL, para_birimi TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS katki_urunler 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT UNIQUE)''')
        c.execute('''CREATE TABLE IF NOT EXISTS katki_recete 
                   (urun_id INTEGER, enzim_id INTEGER, gramaj REAL, PRIMARY KEY (urun_id, enzim_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS katki_kurlar 
                   (id INTEGER PRIMARY KEY, usd_tl REAL, eur_tl REAL)''')
        
        c.execute("SELECT count(*) FROM katki_kurlar")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO katki_kurlar (id, usd_tl, eur_tl) VALUES (1, 32.0, 35.0)")

        # --- BUGDAY GIRIS ARSIVI TABLOSU ---
        c.execute('''CREATE TABLE IF NOT EXISTS bugday_giris_arsivi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_no TEXT UNIQUE NOT NULL,
            tarih DATE NOT NULL,
            bugday_cinsi TEXT NOT NULL,
            tedarikci TEXT,
            yore TEXT,
            plaka TEXT,
            tonaj REAL NOT NULL,
            fiyat REAL NOT NULL,
            silo_isim TEXT NOT NULL,
            hektolitre REAL,
            protein REAL,
            rutubet REAL,
            gluten REAL,
            gluten_index REAL,
            sedim REAL,
            gecikmeli_sedim REAL,
            sune REAL,
            kirik_ciliz REAL,
            yabanci_tane REAL,
            notlar TEXT,
            kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('CREATE INDEX IF NOT EXISTS idx_bugday_lot_no ON bugday_giris_arsivi(lot_no)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_bugday_tarih ON bugday_giris_arsivi(tarih)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_bugday_silo ON bugday_giris_arsivi(silo_isim)')
        
        # Schema Migration: bugday_giris_arsivi eksik sütunları
        c.execute("PRAGMA table_info(bugday_giris_arsivi)")
        arsiv_sutunlar = [col[1] for col in c.fetchall()]
        
        eksik_sutunlar = [
            ("rutubet", "REAL"),
            ("gecikmeli_sedim", "REAL"),
            ("gluten_index", "REAL")
        ]
        
        for sutun, tip in eksik_sutunlar:
            if sutun not in arsiv_sutunlar:
                try:
                    c.execute(f"ALTER TABLE bugday_giris_arsivi ADD COLUMN {sutun} {tip}")
                except: pass

        # --- SİLOLAR TABLOSU ---
        c.execute('''CREATE TABLE IF NOT EXISTS silolar (
            id INTEGER PRIMARY KEY, 
            isim TEXT UNIQUE, 
            kapasite REAL, 
            mevcut_miktar REAL, 
            protein REAL, 
            gluten REAL, 
            rutubet REAL, 
            hektolitre REAL, 
            sedim REAL, 
            enerji REAL, 
            "index" REAL DEFAULT 0, 
            g_sedim REAL DEFAULT 0, 
            amilo REAL DEFAULT 0, 
            direnc135 REAL DEFAULT 0, 
            taban135 REAL DEFAULT 0, 
            bugday_cinsi TEXT DEFAULT '', 
            maliyet REAL DEFAULT 0,
            parti_no TEXT DEFAULT '',
            tedarikci TEXT DEFAULT '',
            alim_tarihi DATE DEFAULT NULL,
            tavli_bugday_stok REAL DEFAULT 0
        )''')

        # Sütun Kontrolü ve ALTER TABLE işlemleri
        c.execute("PRAGMA table_info(silolar)")
        mevcut_sutunlar = [col[1] for col in c.fetchall()]
        
        yeni_sutunlar = [
            ("fn", "REAL DEFAULT 0"), ("ffn", "REAL DEFAULT 0"), ("kul", "REAL DEFAULT 0"),
            ("su_kaldirma_f", "REAL DEFAULT 0"), ("gelisme_suresi", "REAL DEFAULT 0"),
            ("stabilite", "REAL DEFAULT 0"), ("yumusama", "REAL DEFAULT 0"),
            ("su_kaldirma_e", "REAL DEFAULT 0"), ("enerji45", "REAL DEFAULT 0"),
            ("direnc45", "REAL DEFAULT 0"), ("taban45", "REAL DEFAULT 0"),
            ("enerji90", "REAL DEFAULT 0"), ("direnc90", "REAL DEFAULT 0"),
            ("taban90", "REAL DEFAULT 0"), ("enerji135", "REAL DEFAULT 0")
        ]

        for sutun_adi, sutun_tipi in yeni_sutunlar:
            if sutun_adi not in mevcut_sutunlar:
                try:
                    c.execute(f"ALTER TABLE silolar ADD COLUMN {sutun_adi} {sutun_tipi}")
                except: pass

        # --- TAVLI ANALIZ TABLOSU ---
        c.execute('''CREATE TABLE IF NOT EXISTS tavli_analiz (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            silo_isim TEXT NOT NULL,
            analiz_tonaj REAL NOT NULL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            protein REAL,
            rutubet REAL,
            gluten REAL,
            gluten_index REAL,
            sedim REAL,
            g_sedim REAL,
            fn REAL,
            ffn REAL,
            amilograph REAL,
            kul REAL,
            su_kaldirma_f REAL,
            gelisme_suresi REAL,
            stabilite REAL,
            yumusama REAL,
            su_kaldirma_e REAL,
            enerji45 REAL,
            direnc45 REAL,
            taban45 REAL,
            enerji90 REAL,
            direnc90 REAL,
            taban90 REAL,
            enerji135 REAL,
            direnc135 REAL,
            taban135 REAL,
            notlar TEXT
        )''')

        # --- DİĞER TÜM TABLOLAR ---
        c.execute('''CREATE TABLE IF NOT EXISTS hareketler (
            id INTEGER PRIMARY KEY, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            silo_isim TEXT, hareket_tipi TEXT, miktar REAL, protein REAL, gluten REAL, 
            rutubet REAL, hektolitre REAL, sedim REAL, enerji REAL, "index" REAL, 
            g_sedim REAL, amilo REAL, direnc135 REAL, taban135 REAL, maliyet REAL,
            lot_no TEXT DEFAULT '', tedarikci TEXT DEFAULT '', yore TEXT DEFAULT '', notlar TEXT DEFAULT ''
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS pacal_kayitlari (
            id INTEGER PRIMARY KEY, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            urun_adi TEXT, silo_oranlari_json TEXT, sonuc_analizleri_json TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS un_analiz (
            id INTEGER PRIMARY KEY, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            lot_no TEXT UNIQUE, islem_tipi TEXT, 
            un_cinsi_marka TEXT,  -- YENİ EKLENDİ
            uretim_silosu TEXT, protein REAL, 
            rutubet REAL, gluten REAL, gluten_index REAL, sedim REAL, gecikmeli_sedim REAL, 
            fn REAL, ffn REAL, amilograph REAL, nisasta_zedelenmesi REAL, kul REAL, 
            su_kaldirma_f REAL, gelisme_suresi REAL, stabilite REAL, yumusama REAL, 
            su_kaldirma_e REAL, direnc45 REAL, direnc90 REAL, direnc135 REAL, 
            taban45 REAL, taban90 REAL, taban135 REAL, enerji45 REAL, enerji90 REAL, 
            enerji135 REAL, notlar TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS uretim_kaydi (
            id INTEGER PRIMARY KEY, 
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            parti_no TEXT,
            vardiya TEXT,
            sorumlu TEXT,
            bugday_giris REAL DEFAULT 0,
            kirilan_bugday REAL DEFAULT 0,
            nem_orani REAL DEFAULT 0,
            tav_suresi REAL DEFAULT 0,
            un_uretim_toplam REAL DEFAULT 0,
            luks_un REAL DEFAULT 0,
            ekmeklik_un REAL DEFAULT 0,
            bongalite REAL DEFAULT 0,
            razmol REAL DEFAULT 0,
            kepek REAL DEFAULT 0,
            elektrik_tuketimi REAL DEFAULT 0,
            durus_suresi REAL DEFAULT 0,
            notlar TEXT,
            
            -- Eski/Diğer alanlar (Geri uyumluluk için)
            uretim_hatti TEXT, degirmen_uretim_adi TEXT,
            un_1 REAL DEFAULT 0, un_2 REAL DEFAULT 0,
            kirik_bugday REAL DEFAULT 0, toplam REAL DEFAULT 0, 
            randiman_1 REAL DEFAULT 0, toplam_randiman REAL DEFAULT 0, 
            kayip REAL DEFAULT 0, kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        # Schema Migration: uretim_kaydi
        new_prod_cols = {
            'parti_no': 'TEXT', 'vardiya': 'TEXT', 'sorumlu': 'TEXT',
            'bugday_giris': 'REAL', 'nem_orani': 'REAL', 'tav_suresi': 'REAL',
            'un_uretim_toplam': 'REAL', 'luks_un': 'REAL', 'ekmeklik_un': 'REAL',
            'elektrik_tuketimi': 'REAL', 'durus_suresi': 'REAL',
            'uretim_silo_adi': 'TEXT'
        }
        for col, dtype in new_prod_cols.items():
            try:
                c.execute(f"ALTER TABLE uretim_kaydi ADD COLUMN {col} {dtype}")
            except: pass

        c.execute('''CREATE TABLE IF NOT EXISTS un_maliyet_hesaplamalari (
            id INTEGER PRIMARY KEY, 
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            un_cesidi TEXT, 
            bugday_pacal_maliyeti REAL, 
            aylik_kirilan_bugday REAL,
            un_randimani REAL,
            un_satis_fiyati REAL,
            un2_orani REAL,
            bongalite_orani REAL,
            kepek_orani REAL,
            razmol_orani REAL,
            belge_geliri REAL,
            un2_fiyati REAL,
            bongalite_fiyati REAL,
            kepek_fiyati REAL,
            razmol_fiyati REAL,
            ton_bugday_elektrik REAL,
            elektrik_gideri REAL,
            personel_maasi REAL,
            bakim_maliyeti REAL,
            mutfak_gideri REAL,
            finans_gideri REAL,
            nakliye REAL,
            satis_pazarlama REAL,
            pp_cuval REAL,
            katki_maliyeti REAL,
            net_kar_kg REAL,
            fabrika_cikis_maliyet REAL,
            net_kar_toplam REAL,
            toplam_gelir REAL,
            toplam_gider REAL,
            notlar TEXT,
            kullanici TEXT,
            
            -- YENİ EKLENEN SÜTUNLAR (v2)
            kirik_tonaj REAL,
            kirik_fiyat REAL,
            basak_tonaj REAL,
            basak_fiyat REAL,
            diger_giderler REAL,
            ay TEXT,
            yil INTEGER
        )''')
        
        # --- UN SPESİFİKASYONLARI (Kütüphane) ---
        c.execute('''CREATE TABLE IF NOT EXISTS un_spekleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            un_cinsi TEXT NOT NULL,
            parametre TEXT NOT NULL,
            min_deger REAL DEFAULT 0,
            max_deger REAL DEFAULT 0,
            hedef_deger REAL DEFAULT 0,
            tolerans REAL DEFAULT 0,
            aktif INTEGER DEFAULT 1,
            CONSTRAINT uniq_spec UNIQUE (un_cinsi, parametre)
        )''')
        
        # Schema Migration: Eksik sütunları ekle (Mevcut veritabanı için)
        new_cols = {
            'kirik_tonaj': 'REAL', 'kirik_fiyat': 'REAL',
            'basak_tonaj': 'REAL', 'basak_fiyat': 'REAL',
            'diger_giderler': 'REAL', 'aylik_kirilan_bugday': 'REAL',
            'un_randimani': 'REAL', 'fabrika_cikis_maliyet': 'REAL',
            'toplam_gelir': 'REAL', 'toplam_gider': 'REAL',
            'ay': 'TEXT', 'yil': 'INTEGER',
            
            # Missing columns fix
            'un_satis_fiyati': 'REAL', 'un2_orani': 'REAL', 'bongalite_orani': 'REAL',
            'kepek_orani': 'REAL', 'razmol_orani': 'REAL', 'belge_geliri': 'REAL',
            'un2_fiyati': 'REAL', 'bongalite_fiyati': 'REAL', 'kepek_fiyati': 'REAL',
            'razmol_fiyati': 'REAL', 'ton_bugday_elektrik': 'REAL', 'elektrik_gideri': 'REAL',
            'personel_maasi': 'REAL', 'bakim_maliyeti': 'REAL', 'mutfak_gideri': 'REAL',
            'finans_gideri': 'REAL', 'nakliye': 'REAL', 'satis_pazarlama': 'REAL',
            'pp_cuval': 'REAL', 'katki_maliyeti': 'REAL', 'net_kar_toplam': 'REAL',
            'notlar': 'TEXT'
        }
        for col, dtype in new_cols.items():
            try:
                c.execute(f"ALTER TABLE un_maliyet_hesaplamalari ADD COLUMN {col} {dtype}")
            except: pass

        c.execute('''CREATE TABLE IF NOT EXISTS enzim_receteleri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uretim_adi TEXT,
            un_ton REAL,
            bugday_hiz REAL,
            randiman REAL,
            dozaj_akis REAL,
            enzim_verisi_json TEXT,
            irmik_miktari REAL,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            kullanici TEXT
        )''')

        # --- ÜRETİM SİLOLARI (Flour Silos) ---
        c.execute('''CREATE TABLE IF NOT EXISTS uretim_silolari (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            silo_adi TEXT UNIQUE, 
            aciklama TEXT, 
            aktif INTEGER DEFAULT 1
        )''')

        # --- Varsayılan Siloları Ekle (KALDIRILDI - Manuel Yönetim İçin) ---
        # c.execute('SELECT count(*) FROM silolar')
        # if c.fetchone()[0] == 0:
        #     # Kullanıcı manuel ekleyecek
        #     pass

        # Tüm işlemlerden sonra tek commit
        conn.commit()
