import streamlit as st
import pandas as pd
import time
from datetime import datetime
import io
import sqlite3
import json

from app.core.database import get_db_connection
from app.core.database import get_db_connection
from app.core.config import INPUT_LIMITS, TERMS, get_limit
from app.core.error_handling import error_handler, log_debug, log_info, log_warning, handle_error, ERROR_HANDLING_AVAILABLE
from app.modules.dashboard import get_silo_data, draw_silo
from app.core.components import render_help_button

# --- DATA MANIPULATION FUNCTIONS ---

@error_handler(context="Stok Hareketi Loglama")
def log_stok_hareketi(silo_isim, hareket_tipi, miktar, **kwargs):
    """Stok hareketini logla - HATA YÖNETİMLİ"""
    log_info(f"Stok hareketi: {silo_isim} - {hareket_tipi} - {miktar}ton", "Stok Yönetimi")
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            log_debug(f"Hareket detayları hazırlanıyor: {silo_isim}", "Stok Yönetimi")
            
            # SABIT sütun listesi (en sık kullanılanlar)
            columns = [
                'silo_isim', 'hareket_tipi', 'miktar', 'tarih',
                'protein', 'gluten', 'rutubet', 'hektolitre', 'sedim',
                'maliyet', 'lot_no', 'tedarikci', 'yore', 'notlar'
            ]
            
            # Temel değerler
            values = [
                silo_isim,
                hareket_tipi,
                abs(float(miktar)),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            # Opsiyonel değerler
            optional_fields = [
                'protein', 'gluten', 'rutubet', 'hektolitre', 'sedim',
                'maliyet', 'lot_no', 'tedarikci', 'yore', 'notlar'
            ]
            
            for field in optional_fields:
                if field in kwargs and kwargs[field] is not None:
                    val = kwargs[field]
                    if isinstance(val, (int, float)):
                        values.append(float(val))
                    else:
                        values.append(str(val)[:200])
                else:
                    values.append(None)
            
            # GÜVENLİ SQL
            placeholders = ', '.join(['?'] * len(values))
            column_names = ', '.join(columns)
            
            query = f"INSERT INTO hareketler ({column_names}) VALUES ({placeholders})"
            log_debug(f"SQL hazır: {query[:100]}...", "Stok Yönetimi")
            c.execute(query, values)
            conn.commit()
            log_info(f"Stok hareketi başarıyla loglandı: {silo_isim}", "Stok Yönetimi")
            
            return True
            
    except Exception as e:
        log_debug("Stok hareketi loglama tamamlandı (hata decorator'da)", "Stok Yönetimi")
        st.error(f"❌ Hareket kaydı hatası: {str(e)}")
        return False

def update_tavli_bugday_stok(silo_isim, eklenen_tonaj, islem_tipi="ekle"):
    """Tavlı buğday stokunu güncelle - ÇOK ÖNEMLİ"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Mevcut tavlı stoku al
            c.execute("SELECT tavli_bugday_stok FROM silolar WHERE isim = ?", (silo_isim,))
            mevcut_tavli = c.fetchone()
            
            if mevcut_tavli:
                current = float(mevcut_tavli[0]) if mevcut_tavli[0] is not None else 0
            else:
                current = 0
            
            # Yeni değeri hesapla
            if islem_tipi == "ekle":
                yeni_tavli = current + float(eklenen_tonaj)
            elif islem_tipi == "cikar":
                yeni_tavli = current - float(eklenen_tonaj)
                if yeni_tavli < 0:
                    yeni_tavli = 0
            else:
                return False
            
            # Güncelle
            c.execute("UPDATE silolar SET tavli_bugday_stok = ? WHERE isim = ?", 
                     (yeni_tavli, silo_isim))
            conn.commit()
            return True
            
    except Exception as e:
        st.error(f"Tavlı stok güncelleme hatası: {str(e)}")
        return False

def calculate_tavli_stok_from_history():
    """Geçmiş tavlı analizlerinden stokları hesapla - BİR KERE ÇALIŞTIR"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Tüm siloları al
            c.execute("SELECT isim FROM silolar")
            silos = c.fetchall()
            
            for silo_tuple in silos:
                silo_isim = silo_tuple[0]
                
                # Bu silonun tavlı analizlerini al
                c.execute('''SELECT analiz_tonaj FROM tavli_analiz 
                           WHERE silo_isim = ?''', (silo_isim,))
                analizler = c.fetchall()
                
                # Toplam tavlı tonajı hesapla
                toplam_tavli = 0
                for a in analizler:
                    if a[0] is not None:
                        try:
                            toplam_tavli += float(a[0])
                        except:
                            pass
                
                # Bu silonun stok çıkışlarını al
                c.execute('''SELECT miktar FROM hareketler 
                           WHERE silo_isim = ? AND hareket_tipi = "Çıkış"''', 
                           (silo_isim,))
                cikislar = c.fetchall()
                
                # Toplam çıkışı hesapla
                toplam_cikis = 0
                for cikis in cikislar:
                    if cikis[0] is not None:
                        try:
                            toplam_cikis += float(cikis[0])
                        except:
                            pass
                
                # Net tavlı stok
                net_tavli = toplam_tavli - toplam_cikis
                if net_tavli < 0:
                    net_tavli = 0
                
                # Güncelle
                c.execute('''UPDATE silolar SET tavli_bugday_stok = ? 
                           WHERE isim = ?''', (net_tavli, silo_isim))
                # print(f"✓ {silo_isim}: Tavlı stok = {net_tavli:.1f} Ton")
            
            conn.commit()
            return True
            
    except Exception as e:
        # print(f"❌ Tavlı stok hesaplama hatası: {str(e)}")
        return False

def recalculate_silos_from_logs():
    """Geçmiş hareketleri tarayıp Dashboard'u sıfırdan hesaplar - DÜZELTİLMİŞ"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Tüm siloları al
            c.execute("SELECT isim FROM silolar")
            silos = c.fetchall()
            
            for silo_tuple in silos:
                silo_isim = silo_tuple[0]
                
                # Bu silonun hareketlerini al
                c.execute('''SELECT hareket_tipi, miktar, protein, gluten, rutubet, 
                           hektolitre, sedim, maliyet 
                           FROM hareketler WHERE silo_isim=? 
                           ORDER BY tarih ASC, id ASC''', (silo_isim,))
                hareketler = c.fetchall()
                
                curr_miktar = 0.0
                curr_vals = {
                    'protein': 0, 'gluten': 0, 'rutubet': 0, 
                    'hektolitre': 0, 'sedim': 0, 'maliyet': 0
                }
                
                for h in hareketler:
                    h_tip = h[0]
                    h_miktar = float(h[1])
                    
                    if h_tip == 'Giriş':
                        if (curr_miktar + h_miktar) > 0:
                            # Ağırlıklı ortalama hesapla
                            for i, key in enumerate(['protein', 'gluten', 'rutubet', 
                                                    'hektolitre', 'sedim', 'maliyet']):
                                h_val = float(h[2 + i]) if h[2 + i] is not None else 0
                                curr_vals[key] = ((curr_miktar * curr_vals[key]) + 
                                                 (h_miktar * h_val)) / (curr_miktar + h_miktar)
                            curr_miktar += h_miktar
                        else:
                            curr_miktar = h_miktar
                            for i, key in enumerate(['protein', 'gluten', 'rutubet', 
                                                    'hektolitre', 'sedim', 'maliyet']):
                                curr_vals[key] = float(h[2 + i]) if h[2 + i] is not None else 0
                    
                    elif h_tip == 'Çıkış':
                        curr_miktar -= h_miktar
                        if curr_miktar < 0:
                            curr_miktar = 0
                
                # Siloyu güncelle
                c.execute('''UPDATE silolar SET 
                           mevcut_miktar=?, protein=?, gluten=?, rutubet=?, 
                           hektolitre=?, sedim=?, maliyet=? 
                           WHERE isim=?''', 
                           (curr_miktar, curr_vals['protein'], curr_vals['gluten'], 
                            curr_vals['rutubet'], curr_vals['hektolitre'], 
                            curr_vals['sedim'], curr_vals['maliyet'], silo_isim))
            
            conn.commit()
            return True
            
    except Exception as e:
        st.error(f"Silo yeniden hesaplama hatası: {str(e)}")
        return False

def add_to_bugday_giris_arsivi(lot_no, tarih, bugday_cinsi, tedarikci, yore, plaka, 
                              tonaj, fiyat, silo_isim, hektolitre, protein, rutubet, gluten, 
                              gluten_index, sedim, gecikmeli_sedim, sune, kirik_ciliz, 
                              yabanci_tane, notlar):
    """Buğday girişini arşive ekle - DÜZELTİLMİŞ"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Önce tablo var mı kontrol et, yoksa oluştur
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bugday_giris_arsivi'")
            if not c.fetchone():
                # Tabloyu oluştur (database.py'de var ama garanti olsun)
                pass # database.py handles this mostly, simplified here
            
            c.execute('''INSERT INTO bugday_giris_arsivi 
                      (lot_no, tarih, bugday_cinsi, tedarikci, yore, plaka, tonaj, 
                      fiyat, silo_isim, hektolitre, protein, rutubet, gluten, gluten_index, 
                      sedim, gecikmeli_sedim, sune, kirik_ciliz, yabanci_tane, notlar) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (lot_no, str(tarih), bugday_cinsi[:50], 
                       tedarikci[:100] if tedarikci else None, 
                       yore[:50] if yore else None, 
                       plaka[:20] if plaka else None, 
                       float(tonaj), float(fiyat), 
                       silo_isim, float(hektolitre), float(protein), float(rutubet), 
                       float(gluten), float(gluten_index), float(sedim), float(gecikmeli_sedim), 
                       float(sune), float(kirik_ciliz), float(yabanci_tane), 
                       notlar[:500] if notlar else None))
            
            conn.commit()
            return True
            
    except sqlite3.IntegrityError as e:
        if ERROR_HANDLING_AVAILABLE:
            handle_error(
                error=e,
                context=f"Buğday Arşivi Kaydı - Lot No: {lot_no}",
                user=st.session_state.username,
                module="bugday_arsivi",
                function="add_to_bugday_giris_arsivi"
            )
        st.error(f"❌ Bu lot numarası zaten kayıtlı: {lot_no}")
        return False
    except Exception as e:
        if ERROR_HANDLING_AVAILABLE:
            handle_error(
                error=e,
                context=f"Buğday Arşivi Kaydı - Genel Hata",
                user=st.session_state.username,
                module="bugday_arsivi",
                function="add_to_bugday_giris_arsivi"
            )
        st.error(f"❌ Arşiv kaydı hatası: {str(e)}")
        return False

def get_movements():
    """Stok hareketlerini detaylı getir (Arşiv ile JOIN)"""
    try:
        with get_db_connection() as conn:
            query = """
                SELECT 
                    h.id, h.tarih, h.hareket_tipi, h.silo_isim, h.miktar, 
                    h.lot_no, h.notlar,
                    -- Çakışan alanlarda Arşiv öncelikli (Giriş için), yoksa Hareket
                    COALESCE(b.tedarikci, h.tedarikci) as tedarikci,
                    COALESCE(b.yore, h.yore) as yore,
                    COALESCE(b.protein, h.protein) as protein,
                    COALESCE(b.rutubet, h.rutubet) as rutubet,
                    COALESCE(b.gluten, h.gluten) as gluten,
                    COALESCE(b.sedim, h.sedim) as sedim,
                    COALESCE(b.fiyat, h.maliyet) as alis_fiyati,
                    -- Sadece Arşiv'de olanlar
                    b.plaka, b.bugday_cinsi, b.gluten_index, b.gecikmeli_sedim, 
                    b.sune, b.kirik_ciliz, b.yabanci_tane
                FROM hareketler h
                LEFT JOIN bugday_giris_arsivi b ON h.lot_no = b.lot_no
                ORDER BY h.tarih DESC 
                LIMIT 500
            """
            df = pd.read_sql_query(query, conn)
            
            # Haşere Durumu (Notlardan Çıkarım)
            if not df.empty and 'notlar' in df.columns:
                df['hasere'] = df['notlar'].apply(lambda x: "Var" if x and "HAŞERE" in str(x).upper() else "Yok")
                
            return df
    except Exception as e:
        st.error(f"Stok hareketleri yüklenemedi: {e}")
        return pd.DataFrame()
        st.error(f"Hareketler yüklenemedi: {str(e)}")
        return pd.DataFrame()

def get_bugday_arsiv():
    """Buğday giriş arşivini getir"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Önce tablo var mı kontrol et
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bugday_giris_arsivi'")
            
            if cursor.fetchone() is None:
                # Tablo yoksa boş DataFrame dön
                return pd.DataFrame()
            
            df = pd.read_sql_query(
                """SELECT * FROM bugday_giris_arsivi 
                ORDER BY tarih DESC""", 
                conn
            )
            
            # Tarih formatını düzelt
            if 'tarih' in df.columns:
                df['tarih'] = pd.to_datetime(df['tarih'], errors='coerce')
            
            return df
            
    except Exception as e:
        if ERROR_HANDLING_AVAILABLE:
            handle_error(
                error=e,
                context="Buğday Arşivi Yükleme",
                user=st.session_state.username,
                module="bugday_arsivi",
                function="get_bugday_arsiv"
            )
        st.error(f"Arşiv yüklenemedi: {str(e)}")
        return pd.DataFrame()

def save_tavli_analiz(silo_isim, analiz_tonaj, **analiz_degerleri):
    """Tavlı buğday analizini kaydet - GÜVENLİ VERSİYON"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Önce tavli_analiz tablosu var mı kontrol et, yoksa oluştur
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tavli_analiz'")
            if not c.fetchone():
                # Tabloyu oluştur (database.py'de var)
                pass
            
            # SABIT sütun listesi
            columns = [
                'silo_isim', 'analiz_tonaj', 'tarih',
                'protein', 'rutubet', 'gluten', 'gluten_index', 'sedim', 'g_sedim',
                'fn', 'ffn', 'amilograph', 'kul', 'su_kaldirma_f', 'gelisme_suresi',
                'stabilite', 'yumusama', 'su_kaldirma_e', 'enerji45', 'direnc45',
                'taban45', 'enerji90', 'direnc90', 'taban90', 'enerji135',
                'direnc135', 'taban135', 'notlar'
            ]
            
            # Değerleri hazırla
            values = [
                silo_isim,
                float(analiz_tonaj),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            # Analiz değerleri
            analiz_fields = [
                'protein', 'rutubet', 'gluten', 'gluten_index', 'sedim', 'g_sedim',
                'fn', 'ffn', 'amilograph', 'kul', 'su_kaldirma_f', 'gelisme_suresi',
                'stabilite', 'yumusama', 'su_kaldirma_e', 'enerji45', 'direnc45',
                'taban45', 'enerji90', 'direnc90', 'taban90', 'enerji135',
                'direnc135', 'taban135', 'notlar'
            ]
            
            for field in analiz_fields:
                if field in analiz_degerleri:
                    val = analiz_degerleri[field]
                    if isinstance(val, (int, float)):
                        values.append(float(val))
                    elif isinstance(val, str) and field == 'notlar':
                        values.append(str(val)[:500])
                    else:
                        values.append(None)
                else:
                    values.append(None)
            
            # GÜVENLİ SQL - parametreli
            placeholders = ', '.join(['?'] * len(values))
            column_names = ', '.join(columns)
            
            query = f"INSERT INTO tavli_analiz ({column_names}) VALUES ({placeholders})"
            c.execute(query, values)
            conn.commit()
            
            return True, "Analiz başarıyla kaydedildi!"
            
    except Exception as e:
        if ERROR_HANDLING_AVAILABLE:
            handle_error(
                error=e,
                context=f"Tavlı Analiz Kaydı - Silo: {silo_isim}",
                user=st.session_state.username,
                module="tavli_analiz",
                function="save_tavli_analiz"
            )
        return False, f"Kayıt hatası: {str(e)}"

def get_tavli_analizler(silo_isim=None):
    """Tavlı analiz kayıtlarını getir"""
    try:
        with get_db_connection() as conn:
            # Önce tablo var mı kontrol et
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tavli_analiz'")
            
            if not cursor.fetchone():
                return pd.DataFrame()
            
            if silo_isim:
                df = pd.read_sql_query(
                    "SELECT * FROM tavli_analiz WHERE silo_isim=? ORDER BY tarih DESC LIMIT 50",
                    conn, params=(silo_isim,)
                )
            else:
                df = pd.read_sql_query(
                    "SELECT * FROM tavli_analiz ORDER BY tarih DESC LIMIT 100",
                    conn
                )
            return df
    except Exception as e:
        if ERROR_HANDLING_AVAILABLE:
            handle_error(
                error=e,
                context="Tavlı Analizleri Getirme",
                user=st.session_state.username,
                module="tavli_analiz",
                function="get_tavli_analizler"
            )
        return pd.DataFrame()

# --- QUALITY SPECIFICATION MANAGEMENT ---

def save_bugday_spec(bugday_cinsi, parametre, min_val, max_val, hedef_val):
    """Buğday spesifikasyonunu kaydet/güncelle"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Tabloyu kontrol et / oluştur
            c.execute('''CREATE TABLE IF NOT EXISTS bugday_spekleri 
                         (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                          bugday_cinsi TEXT, 
                          parametre TEXT, 
                          min_deger REAL, 
                          max_deger REAL, 
                          hedef_deger REAL, 
                          aktif INTEGER DEFAULT 1,
                          UNIQUE(bugday_cinsi, parametre))''')
            
            # Upsert logic
            c.execute("SELECT id FROM bugday_spekleri WHERE bugday_cinsi=? AND parametre=?", (bugday_cinsi, parametre))
            exists = c.fetchone()
            
            if exists:
                c.execute("""UPDATE bugday_spekleri 
                           SET min_deger=?, max_deger=?, hedef_deger=?, aktif=1 
                           WHERE id=?""", 
                           (min_val, max_val, hedef_val, exists[0]))
            else:
                c.execute("""INSERT INTO bugday_spekleri (bugday_cinsi, parametre, min_deger, max_deger, hedef_deger) 
                           VALUES (?, ?, ?, ?, ?)""",
                           (bugday_cinsi, parametre, min_val, max_val, hedef_val))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def delete_bugday_spec_group(bugday_cinsi):
    """Bir buğday cinsine ait tüm spekleri sil"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM bugday_spekleri WHERE bugday_cinsi=?", (bugday_cinsi,))
            conn.commit()
            return True
    except Exception:
        return False

def get_all_bugday_specs_dataframe():
    """Tüm buğday speklerini rapor için çek"""
    try:
        with get_db_connection() as conn:
            df = pd.read_sql("""
                SELECT bugday_cinsi as "Buğday Cinsi", 
                       parametre as "Parametre", 
                       min_deger as "Min", 
                       hedef_deger as "Hedef", 
                       max_deger as "Max" 
                FROM bugday_spekleri 
                ORDER BY bugday_cinsi, parametre
            """, conn)
            return df
    except:
        return pd.DataFrame()

def show_bugday_spec_yonetimi():
    """Buğday Kalite Spesifikasyon Yönetimi"""
    st.markdown("### 🌾 Buğday Kalite Spesifikasyonları")
    
    # 1. Cins Seçimi
    try:
        with get_db_connection() as conn:
            # Analizlerden ve speklerden gelen benzersiz isimler
            # bugday_spekleri tablosu yoksa hata verebilir, try-except kapsıyor
            try:
                spek_cinsleri = pd.read_sql("SELECT DISTINCT bugday_cinsi FROM bugday_spekleri", conn)
                all_types = sorted(spek_cinsleri['bugday_cinsi'].tolist())
            except:
                all_types = []
    except:
        all_types = []

    col_sel, col_add = st.columns([2, 1])
    
    with col_sel:
        secilen_cins = st.selectbox("Düzenlenecek Buğday Cinsini Seçiniz", ["(Seçiniz/Yeni Ekle)"] + all_types)
    
    yeni_isim_girisi = ""
    if secilen_cins == "(Seçiniz/Yeni Ekle)":
        with col_add:
            yeni_isim_girisi = st.text_input("➕ Yeni Cins Tanımla", placeholder="Örn: Genel Standart, Bezostaya").strip()
            if yeni_isim_girisi:
                secilen_cins = yeni_isim_girisi
            else:
                secilen_cins = None

    if not secilen_cins:
        st.info("👆 Lütfen düzenlemek veya oluşturmak için bir buğday cinsi seçin.")
        st.divider()
        st.caption("📋 Mevcut Tanımlar")
        df_all = get_all_bugday_specs_dataframe()
        if not df_all.empty:
            st.dataframe(df_all, use_container_width=True, hide_index=True)
        return

    st.divider()
    
    # Mevcut Spekleri Çek
    current_specs = {}
    try:
        with get_db_connection() as conn:
            df_specs = pd.read_sql("SELECT * FROM bugday_spekleri WHERE bugday_cinsi=?", conn, params=(secilen_cins,))
            if not df_specs.empty:
                for _, row in df_specs.iterrows():
                    current_specs[row['parametre']] = row
    except: pass

    # Parametre Listesi
    parametreler = [
        ("hektolitre", "Hektolitre (kg/hl)"),
        ("rutubet", "Rutubet (%)"),
        ("protein", "Protein (%)"),
        ("gluten", "Gluten (%)"),
        ("gluten_index", "Gluten Index"),
        ("sedim", "Sedim (ml)"),
        ("gecikmeli_sedim", "Gecikmeli Sedim (ml)"),
        ("sune", "Süne (%)"),
        ("kirik_ciliz", "Kırık & Cılız (%)"),
        ("yabanci_tane", "Yabancı Tane (%)")
    ]

    st.markdown(f"### 🛠️ Düzenleme: {secilen_cins}")
    
    with st.form("bugday_spec_form"):
        # Grid Layout
        cols = st.columns(2)
        input_keys = []
        
        for i, (p_key, p_label) in enumerate(parametreler):
            col = cols[i % 2]
            with col:
                st.markdown(f"**{p_label}**")
                c1, c2, c3 = st.columns(3)
                
                cur = current_specs.get(p_key, {})
                val_min = float(cur.get('min_deger', 0.0))
                val_tgt = float(cur.get('hedef_deger', 0.0))
                val_max = float(cur.get('max_deger', 0.0))
                
                with c1:
                    st.number_input("Min", value=val_min, key=f"b_min_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                with c2:
                    st.number_input("Hedef", value=val_tgt, key=f"b_tgt_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                with c3:
                    st.number_input("Max", value=val_max, key=f"b_max_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                
                input_keys.append(p_key)

        st.divider()
        col_submit, col_info = st.columns([1, 2])
        with col_submit:
            submit_btn = st.form_submit_button("💾 Kaydet / Güncelle", type="primary", use_container_width=True)
        with col_info:
            st.caption("ℹ️ Sadece 0'dan büyük değer girilen parametreler kaydedilir.")

        if submit_btn:
            saved_count = 0
            for p_key in input_keys:
                s_min = st.session_state.get(f"b_min_{p_key}", 0.0)
                s_tgt = st.session_state.get(f"b_tgt_{p_key}", 0.0)
                s_max = st.session_state.get(f"b_max_{p_key}", 0.0)
                
                if s_min > 0 or s_tgt > 0 or s_max > 0:
                    if save_bugday_spec(secilen_cins, p_key, s_min, s_max, s_tgt):
                        saved_count += 1
            
            if saved_count > 0:
                st.success(f"✅ {secilen_cins} için {saved_count} parametre güncellendi.")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("Değişiklik yapılmadı.")

    # Özet ve Silme
    st.divider()
    col_header, col_delete = st.columns([3, 1])
    with col_header:
        st.subheader(f"📋 '{secilen_cins}' Tanımlı Değerleri")
    
    with col_delete:
        if st.session_state.get("user_role") == "admin":
            if st.button("🗑️ Bu Tanımı Sil", key="del_bugday_spec", type="secondary"):
                if delete_bugday_spec_group(secilen_cins):
                    st.success("Tanım silindi!")
                    time.sleep(1)
                    st.rerun()

    df_spec_view = get_all_bugday_specs_dataframe() 
    if not df_spec_view.empty:
        # Sadece seçili olanı filtrele
        df_selected = df_spec_view[df_spec_view["Buğday Cinsi"] == secilen_cins]
        if not df_selected.empty:
            st.dataframe(df_selected, use_container_width=True, hide_index=True)
        else:
            st.info("Kayıtlı değer yok.")


# --- UI FUNCTIONS ---

@error_handler(context="Buğday Kabul Sistemi")
def show_mal_kabul():
    """Mal Kabul (Giriş) modülü"""
    # Logic extracted from original show_mal_kabul
    if ERROR_HANDLING_AVAILABLE:
        log_info("Mal Kabul modülü açıldı", "Buğday Girişi")
    
    # Rol kontrolü
    if st.session_state.user_role not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("🚜 Mal Kabul ve Stok Girişi")
    
    lot_no = f"BUGDAY-{datetime.now().strftime('%y%m%d%H%M%S')}"
    
    col1, col2 = st.columns([1, 1.5], gap="large")
    
    with col1:
        st.subheader("📋 Temel Bilgiler")
        st.info(f"**Otomatik Lot No:** `{lot_no}`")
        
        df = get_silo_data()
        if df.empty:
            st.warning("⚠️ Sistemde tanımlı silo bulunamadı!")
            st.info("👉 Lütfen **Yönetim Paneli > Silo Yönetimi** menüsünden silo tanımlayınız.")
            return
        
        secilen_silo_isim = st.selectbox("Depolanacak Silo *", df['isim'].tolist())
        
        # Kapasite Kontrolü (Strict)
        silo_row = df[df['isim'] == secilen_silo_isim].iloc[0]
        kalan_kapasite = float(silo_row.get('kapasite', 0)) - float(silo_row.get('mevcut_miktar', 0))
        if kalan_kapasite < 0: 
            kalan_kapasite = 0

        st.info(f"ℹ️ Bu siloda kalan boş yer: {kalan_kapasite:.1f} Ton")

        tarih = st.date_input("Kabul Tarihi *", datetime.now())

        # Buğday Cinsi Seçimi (Spec Destekli)
        specs_list = []
        try:
            with get_db_connection() as conn:
                # Tablo oluşsun diye spec fonksiyonunu bir kere boş çağırabiliriz veya try-catch
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bugday_spekleri'")
                if c.fetchone():
                    df_specs_list = pd.read_sql("SELECT DISTINCT bugday_cinsi FROM bugday_spekleri", conn)
                    specs_list = df_specs_list['bugday_cinsi'].tolist()
        except: pass
        
        # Standart Seçimi (Validation İçin)
        secilen_standart = st.selectbox("Standart Seçiniz", ["(Standart Yok)"] + specs_list)
        
        # Buğday Cinsi (Manuel Giriş - Bağımsız)
        bugday_cinsi = st.text_input("Buğday Cinsi *", placeholder="Örn: Bezostaya", max_chars=50)
        
        # Spec Verilerini Çek (Validasyon İçin)
        current_specs = {}
        if secilen_standart != "(Standart Yok)":
            try:
                with get_db_connection() as conn:
                    df_s = pd.read_sql("SELECT * FROM bugday_spekleri WHERE bugday_cinsi=?", conn, params=(secilen_standart,))
                    for _, row in df_s.iterrows():
                        current_specs[row['parametre']] = row
            except: pass

        tedarikci = st.text_input("Tedarikçi/Firma *", max_chars=100)
        yore = st.text_input("Yöre/Bölge *", max_chars=50)
        plaka = st.text_input("Plaka *", max_chars=20)
        notlar = st.text_area("Notlar", height=80, max_chars=200)

        # Kantar (Manuel)
        gelen_miktar = st.number_input("Gelen Miktar (Ton) *", min_value=0.0, step=0.1, format="%.1f")
        gelen_fiyat = st.number_input(f"Alış Fiyatı ({TERMS.get('fiyat', 'TL')}) *", min_value=0.0, step=0.01, format="%.2f")
    
    with col2:
        st.subheader("🧪 Laboratuvar Analiz Değerleri")
        
        # Validasyon Helper
        def validate_val(key, val, label):
            """Yardımcı validasyon fonksiyonu"""
            if key in current_specs:
                spec = current_specs[key]
                s_min = float(spec.get('min_deger', 0))
                s_max = float(spec.get('max_deger', 999))
                s_tgt = float(spec.get('hedef_deger', 0))
                
                # Hedef Bilgisi
                if s_tgt > 0:
                    st.caption(f"🎯 Hedef: {s_tgt:.1f} | Aralık: {s_min:.1f} - {s_max:.1f}")
                
                # Kontrol
                if val < s_min or (s_max > 0 and val > s_max):
                    st.error(f"❌ {label} Sınır Dışı! (Max: {s_max:.1f})")
                elif key == "sune" and val > s_max and s_max > 0:
                     st.error(f"⚠️ Yüksek Süne! Max: {s_max:.1f}")

        col_a1, col_a2, col_a3 = st.columns(3)
        
        # Helper lambda for existing defaults (still kept if no spec)
        limit = lambda k, p: get_limit(k, p)
        
        with col_a1:
            g_hl = st.number_input(TERMS["hektolitre"], 
                                 min_value=0.0, max_value=100.0, 
                                 value=limit("hektolitre", "default"), step=limit("hektolitre", "step"))
            validate_val("hektolitre", g_hl, "Hektolitre")
            
            g_rut = st.number_input(TERMS["rutubet"], 
                                  min_value=0.0, max_value=20.0, 
                                  value=limit("rutubet", "default"), step=limit("rutubet", "step"))
            validate_val("rutubet", g_rut, "Rutubet")
            
            g_prot = st.number_input(TERMS["protein"], 
                                   min_value=0.0, max_value=20.0, 
                                   value=limit("protein", "default"), step=limit("protein", "step"))
            validate_val("protein", g_prot, "Protein")
            
            g_glut = st.number_input(TERMS["gluten"], 
                                   min_value=0.0, max_value=50.0, 
                                   value=limit("gluten", "default"), step=limit("gluten", "step"))
            validate_val("gluten", g_glut, "Gluten")
        
        with col_a2:
            g_index = st.number_input(TERMS["gluten_index"], 
                                    min_value=0.0, max_value=100.0, 
                                    value=limit("gluten_index", "default"), step=limit("gluten_index", "step"))
            validate_val("gluten_index", g_index, "G.Index")
            
            g_sedim = st.number_input(TERMS["sedim"], 
                                    min_value=0.0, max_value=100.0, 
                                    value=limit("sedim", "default"), step=limit("sedim", "step"))
            validate_val("sedim", g_sedim, "Sedim")
                                    
            g_g_sedim = st.number_input(TERMS["gecikmeli_sedim"], 
                                      min_value=0.0, max_value=100.0, 
                                      value=60.0, step=0.1)
            validate_val("gecikmeli_sedim", g_g_sedim, "G.Sedim")
                                      
            sune = st.number_input(TERMS["sune"], 
                                 min_value=0.0, max_value=10.0, 
                                 value=limit("sune", "default"), step=limit("sune", "step"))
            validate_val("sune", sune, "Süne")
        
        with col_a3:
            kirik_ciliz = st.number_input("Kırık & Cılız (%)", min_value=0.0, max_value=100.0, value=2.0, step=0.1)
            validate_val("kirik_ciliz", kirik_ciliz, "Kırık/Cılız")
            
            yabanci_tane = st.number_input(TERMS["yabanci_tane"], min_value=0.0, max_value=100.0, value=2.5, step=0.1)
            validate_val("yabanci_tane", yabanci_tane, "Yabancı Tane")
            
            hasere = st.selectbox("Haşere", ["Yok", "Var"], index=0)
    
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        if st.button("💾 Kaydı Tamamla", type="primary", use_container_width=True):
            # 0. SIKI KAPASİTE KONTROLÜ
            if gelen_miktar > kalan_kapasite:
                st.error(f"❌ KAPASİTE AŞIMI! Seçtiğiniz siloda sadece {kalan_kapasite:.1f} ton boş yer var. Lütfen miktarı düzeltin veya başka bir silo seçin.")
                return

            # Validasyon
            if gelen_miktar <= 0:
                st.error("⚠️ Miktar 0'dan büyük olmalıdır!")
                return
                
            if not (bugday_cinsi and tedarikci and yore and plaka):
                 st.error("⚠️ Lütfen tüm zorunlu alanları (Cins, Tedarikçi, Yöre, Plaka) doldurunuz.")
                 return

            notlar_tam = f"Plaka: {plaka} | {notlar}" if notlar else f"Plaka: {plaka}"
            if hasere == "Var":
                notlar_tam = f"{notlar} | HAŞERE UYARISI: Var" if notlar else "HAŞERE UYARISI: Var"
            
            try:
                # 1. Stok hareketi
                if log_stok_hareketi(
                    silo_isim=secilen_silo_isim,
                    hareket_tipi="Giriş",
                    miktar=gelen_miktar,
                    protein=g_prot,
                    gluten=g_glut,
                    rutubet=g_rut,
                    hektolitre=g_hl,
                    sedim=g_sedim,
                    maliyet=gelen_fiyat,
                    lot_no=lot_no,
                    tedarikci=tedarikci,
                    yore=yore,
                    notlar=notlar_tam
                ):
                    # 2. Arşiv kaydı
                    if add_to_bugday_giris_arsivi(
                        lot_no=lot_no,
                        tarih=tarih,
                        bugday_cinsi=bugday_cinsi,
                        tedarikci=tedarikci,
                        yore=yore,
                        plaka=plaka,
                        tonaj=gelen_miktar,
                        fiyat=gelen_fiyat,
                        silo_isim=secilen_silo_isim,
                        hektolitre=g_hl,
                        protein=g_prot,
                        rutubet=g_rut,
                        gluten=g_glut,
                        gluten_index=g_index,
                        sedim=g_sedim,
                        gecikmeli_sedim=g_g_sedim,
                        sune=sune,
                        kirik_ciliz=kirik_ciliz,
                        yabanci_tane=yabanci_tane,
                        notlar=notlar_tam
                    ):
                        st.success(f"✅ Buğday kabulü başarıyla kaydedildi! Lot: {lot_no}")
                        recalculate_silos_from_logs()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Arşive kayıt yapılamadı!")
                else:
                    st.error("❌ Stok hareketi kaydedilemedi!")
            except Exception as e:
                st.error(f"❌ Hata: {str(e)}")

def show_stok_cikis():
    """Stok Çıkış (Yıkama) modülü"""
    if st.session_state.user_role not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
    
    st.header("📉 Üretime/Yıkamaya Stok Çıkışı")
    
    df = get_silo_data()
    if df.empty:
        st.error("Silo verisi yüklenemedi!")
        return
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📦 Çıkış Bilgileri")
        secilen_silo_isim = st.selectbox("Kaynak Silo *", df['isim'].tolist())
        silo_bilgisi = df[df['isim'] == secilen_silo_isim].iloc[0]
        mevcut_stok = float(silo_bilgisi['mevcut_miktar'])
        
        st.metric("Mevcut Stok", f"{mevcut_stok:.1f} Ton")
        
        cikacak_miktar = st.number_input(
            "Çıkış Miktarı (Ton) *",
            min_value=0.0,
            max_value=float(mevcut_stok) if mevcut_stok > 0 else 0.0,
            step=0.1,
            value=min(1.0, mevcut_stok) if mevcut_stok > 0 else 0.0
        )
        
        cikis_nedeni = st.selectbox("Çıkış Nedeni *", ["Üretime Gönderim", "Silo Transferi", "Satış", "Numune", "Diğer"])
        
        hedef_silo = None
        if cikis_nedeni == "Silo Transferi":
            # Hedef silo seçimi (Kaynak hariç)
            diger_silolar = [s for s in df['isim'].tolist() if s != secilen_silo_isim]
            hedef_silo = st.selectbox("➡️ Hedef Silo (Transfer)", diger_silolar)
            
        notlar = st.text_area("Notlar", height=100, max_chars=500)
    
    with col2:
        st.subheader("📊 Çıkış Önizlemesi")
        if mevcut_stok <= 0:
            st.warning("⚠️ Seçilen siloda stok bulunmamaktadır!")
            st.stop()
            
        if cikacak_miktar > 0:
            yeni_stok = mevcut_stok - cikacak_miktar
            doluluk_orani = (yeni_stok / float(silo_bilgisi['kapasite']) * 100) if float(silo_bilgisi['kapasite']) > 0 else 0
            
            with st.container(border=True):
                st.markdown("##### Çıkış Sonrası Durum (Kaynak)")
                col_info1, col_info2 = st.columns(2)
                col_info1.metric("Mevcut", f"{mevcut_stok:.1f} Ton")
                col_info2.metric("Çıkış", f"-{cikacak_miktar:.1f} Ton", delta_color="inverse")
                
                st.divider()
                col_new1, col_new2 = st.columns(2)
                col_new1.metric("Yeni Stok", f"{yeni_stok:.1f} Ton")
                col_new2.metric("Yeni Doluluk", f"%{doluluk_orani:.1f}")
                
                st.markdown(draw_silo(doluluk_orani/100, ""), unsafe_allow_html=True)
                
            if hedef_silo:
                st.success(f"➡️ **{hedef_silo}** silosuna +{cikacak_miktar:.1f} Ton eklenecek.")
        else:
            st.info("👈 Çıkış miktarı giriniz")
            
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        btn_text = "📤 Transferi Başlat" if cikis_nedeni == "Silo Transferi" else "📤 Stok Çıkışını Kaydet"
        if st.button(btn_text, type="primary", use_container_width=True):
            if cikacak_miktar <= 0:
                st.error("❌ Çıkış miktarı 0'dan büyük olmalıdır!")
                return
            
            tam_notlar = f"{cikis_nedeni}"
            if notlar.strip():
                tam_notlar += f" | {notlar}"
            
            # 1. KAYNAK SİLODAN ÇIKIŞ
            if log_stok_hareketi(secilen_silo_isim, "Çıkış", cikacak_miktar, notlar=tam_notlar):
                update_tavli_bugday_stok(secilen_silo_isim, cikacak_miktar, "cikar")
                
                # 2. HEDEF SİLOYA GİRİŞ (TRANSFER İSE)
                if cikis_nedeni == "Silo Transferi" and hedef_silo:
                    # Kaynak silonun analiz değerlerini al
                    # Circular import önlemek için fonksiyon içinde import
                    from app.modules.mixing import get_tavli_analiz_agirlikli_ortalama
                    
                    kaynak_analiz = get_tavli_analiz_agirlikli_ortalama(secilen_silo_isim)
                    
                    # Stok hareketi kaydı
                    log_stok_hareketi(
                        silo_isim=hedef_silo,
                        hareket_tipi="Giriş",
                        miktar=cikacak_miktar,
                        protein=float(silo_bilgisi.get('protein', 0)),
                        notlar=f"Transfer Girişi: {secilen_silo_isim} silosundan"
                    )
                    
                    # Tavlı Stok Güncelleme
                    update_tavli_bugday_stok(hedef_silo, cikacak_miktar, "ekle")
                
                recalculate_silos_from_logs()
                time.sleep(2)
                st.rerun()
            else:
                st.error("❌ Stok hareketi kaydedilemedi!")

def show_tavli_analiz():
    """Tavlı Buğday Analiz modülü"""
    st.header("🧪 Tavlı Buğday Analiz Kaydı")
    
    df = get_silo_data()
    if df.empty:
        st.error("Silo verisi yüklenemedi!")
        return
    
    col1, col2 = st.columns(2)
    with col1:
        secilen_silo_isim = st.selectbox("Silo Seçin *", df['isim'].tolist())
        silo_info = df[df['isim'] == secilen_silo_isim].iloc[0]
        mevcut_miktar = float(silo_info['mevcut_miktar']) if not pd.isna(silo_info['mevcut_miktar']) else 0.0
        
        tavli_stok = float(silo_info.get('tavli_bugday_stok', 0))
        kalan_kapasite = max(0.0, mevcut_miktar - tavli_stok)
        
        st.info(f"Mevcut: {mevcut_miktar:.1f} Ton | Tavlı Stok: {tavli_stok:.1f} Ton | 🟢 Eklenebilir: {kalan_kapasite:.1f} Ton")
        
        analiz_tonaj = st.number_input(
            "Analiz Tonajı (Ton) *",
            min_value=0.1,
            max_value=float(kalan_kapasite) if kalan_kapasite > 0 else 1000.0, # UI Constraint
            value=min(27.0, kalan_kapasite) if kalan_kapasite > 0 else 0.0,
            step=0.1,
            help=f"Mevcut stok ({mevcut_miktar}) - Tavlı Stok ({tavli_stok}) = {kalan_kapasite:.1f} Ton eklenebilir."
        )
        
        if analiz_tonaj > kalan_kapasite:
            st.warning(f"⚠️ Dikkat: Girilen tonaj ({analiz_tonaj}), kalan kapasiteden ({kalan_kapasite:.1f}) fazla!")
    
    with col2:
        tarih = st.date_input("Analiz Tarihi *", datetime.now())
        notlar = st.text_area("Notlar", height=60, max_chars=500)
    
    st.divider()
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🧪 Kimyasal Analizler", "📈 Farinograph", "📊 Extensograph"])
    analiz_degerleri = {}
    
    with tab1:
        c1, c2 = st.columns(2)
        with c1:
            analiz_degerleri['protein'] = st.number_input("Protein (%)", value=float(silo_info['protein']), step=0.1)
            analiz_degerleri['rutubet'] = st.number_input("Rutubet (%)", value=15.0, step=0.1)
            analiz_degerleri['gluten'] = st.number_input("Gluten (%)", value=float(silo_info['gluten']), step=0.1)
            analiz_degerleri['gluten_index'] = st.number_input("Gluten Index", value=95.0, step=1.0)
        with c2:
            analiz_degerleri['sedim'] = st.number_input("Sedim (ml)", value=50.0, step=0.1)
            analiz_degerleri['g_sedim'] = st.number_input("Gecikmeli Sedim", value=60.0, step=0.1)
            analiz_degerleri['fn'] = st.number_input("F.N.", value=250.0, step=1.0)
            analiz_degerleri['ffn'] = st.number_input("F.F.N.", value=400.0, step=1.0)
            
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            analiz_degerleri['su_kaldirma_f'] = st.number_input("Su Kaldırma (%)", value=58.0, step=0.1)
            analiz_degerleri['gelisme_suresi'] = st.number_input("Gelişme Süresi", value=3.0, step=0.1)
        with c2:
            analiz_degerleri['stabilite'] = st.number_input("Stabilite", value=8.0, step=0.1)
            analiz_degerleri['yumusama'] = st.number_input("Yumuşama", value=70.0, step=1.0)
            
    with tab3:
        analiz_degerleri['su_kaldirma_e'] = st.number_input("Su Kaldırma (E) (%)", value=58.0, step=0.1)
        st.write("45. Dakika")
        c1, c2, c3 = st.columns(3)
        analiz_degerleri['enerji45'] = c1.number_input("Enerji 45", value=115.0)
        analiz_degerleri['direnc45'] = c2.number_input("Direnç 45", value=550.0)
        analiz_degerleri['taban45'] = c3.number_input("Taban 45", value=180.0)
        
        st.write("90. Dakika")
        c1, c2, c3 = st.columns(3)
        analiz_degerleri['enerji90'] = c1.number_input("Enerji 90", value=138.0)
        analiz_degerleri['direnc90'] = c2.number_input("Direnç 90", value=650.0)
        analiz_degerleri['taban90'] = c3.number_input("Taban 90", value=170.0)
        
        st.write("135. Dakika")
        c1, c2, c3 = st.columns(3)
        analiz_degerleri['enerji135'] = c1.number_input("Enerji 135", value=145.0)
        analiz_degerleri['direnc135'] = c2.number_input("Direnç 135", value=720.0)
        analiz_degerleri['taban135'] = c3.number_input("Taban 135", value=165.0)

    st.divider()
    if st.button("💾 Tavlı Analizi Kaydet", type="primary"):
        if analiz_tonaj <= 0:
            st.error("❌ Analiz tonajı pozitif olmalı")
            return
            
        # KESİN VALİDASYON (Kayıt Anında)
        # Veritabanından tekrar güncel stok bilgisini alalım (race condition için)
        df_current = get_silo_data()
        current_silo_info = df_current[df_current['isim'] == secilen_silo_isim].iloc[0]
        current_mevcut = float(current_silo_info['mevcut_miktar'])
        current_tavli = float(current_silo_info.get('tavli_bugday_stok', 0))
        current_kalan = current_mevcut - current_tavli
        
        if analiz_tonaj > current_kalan + 0.01: # 0.01 tolerans
            st.error(f"❌ Kapasite hatası! Maksimum eklenebilir miktar: {current_kalan:.1f} Ton.")
            return
        
        success, msg = save_tavli_analiz(secilen_silo_isim, analiz_tonaj, **analiz_degerleri, notlar=notlar)
        if success:
            update_tavli_bugday_stok(secilen_silo_isim, analiz_tonaj, "ekle")
            st.success(f"✅ Analiz kaydedildi! Tavlı stok güncellendi.")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"❌ {msg}")
    
    # Geçmiş Analizler
    st.subheader("📜 Geçmiş Tavlı Analizler")
    df_gecmis = get_tavli_analizler(secilen_silo_isim)
    if not df_gecmis.empty:
        # Tarih formatı (veritabanından string geliyorsa)
        if 'tarih' in df_gecmis.columns:
            try:
                df_gecmis['tarih'] = pd.to_datetime(df_gecmis['tarih']).dt.strftime('%d.%m.%Y %H:%M')
            except: pass

        # Sütun İsimleri Haritası
        col_config = {
            "tarih": "Tarih",
            "analiz_tonaj": "Analiz (Ton)",
            "protein": "Protein",
            "rutubet": "Rutubet",
            "gluten": "Gluten",
            "gluten_index": "G. İndeks",
            "sedim": "Sedim",
            "g_sedim": "G. Sedim",
            "fn": "FN",
            "ffn": "FFN",
            "su_kaldirma_f": "Su Kld (F)",
            "gelisme_suresi": "Gelişme",
            "stabilite": "Stabilite",
            "yumusama": "Yumuşama",
            "su_kaldirma_e": "Su Kld (E)",
            "enerji45": "Enerji (45)",
            "direnc45": "Direnç (45)",
            "taban45": "Taban (45)",
            # 90 ve 135 dk verileri gerekirse eklenebilir
            "notlar": "Notlar"
        }
        
        # Sütunları filtrele ve sırala
        cols_to_show = [c for c in col_config.keys() if c in df_gecmis.columns]
        
        st.dataframe(
            df_gecmis[cols_to_show], 
            column_config={k: st.column_config.Column(v) for k, v in col_config.items()},
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Kayıt yok")

def download_styled_excel(df, filename, sheet_name="Rapor"):
    """Wrapper for shared function"""
    from app.modules.reports import download_styled_excel as shared_download
    shared_download(df, filename, sheet_name)

# --- STOK HAREKETLERİ DÜZENLEME ---

def update_stok_hareketi(hareket_id, yeni_veriler):
    """Stok hareketini ve bağlı kayıtları güncelle"""
    try:
        # ID'yi int'e çevir (Numpy type hatasını önlemek için)
        hareket_id = int(hareket_id)

        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 1. Mevcut hareketi al
            c.execute("SELECT lot_no, hareket_tipi, miktar, silo_isim FROM hareketler WHERE id=?", (hareket_id,))
            eski_kayit = c.fetchone()
            if not eski_kayit:
                return False, f"Kayıt bulunamadı! (ID: {hareket_id})"
            
            eski_lot, eski_tip, eski_miktar, silo_isim = eski_kayit
            
            # 2. Hareketler tablosunu güncelle
            # yeni_veriler dict: {'miktar': 10, 'protein': 12.5, 'sune': 1.2, ...}
            
            # Hareketler tablosunda olan kolonlar (Süne vb. yok)
            valid_cols_hareketler = [
                'miktar', 'protein', 'gluten', 'rutubet', 'hektolitre', 'sedim', 
                'maliyet', 'tedarikci', 'yore', 'notlar', 'tarih'
            ]
            
            update_fields = []
            update_values = []
            
            for key, val in yeni_veriler.items():
                if key in valid_cols_hareketler:
                    update_fields.append(f"{key}=?")
                    update_values.append(val)
            
            if update_fields:
                update_values.append(hareket_id)
                query = f"UPDATE hareketler SET {', '.join(update_fields)} WHERE id=?"
                c.execute(query, update_values)
            
            # 3. Arşiv Senkronizasyonu (Giriş ise)
            if eski_tip == "Giriş" and eski_lot:
                # Arşiv tablosunda da güncelle
                # Mapping: hareketler -> bugday_giris_arsivi
                # protein -> protein, miktar -> tonaj, maliyet -> fiyat
                
                arsiv_updates = []
                arsiv_vals = []
                
                mapping = {
                    'miktar': 'tonaj',
                    'maliyet': 'fiyat',
                    'protein': 'protein',
                    'rutubet': 'rutubet', 
                    'gluten': 'gluten',
                    'sedim': 'sedim',
                    'hektolitre': 'hektolitre',
                    'tedarikci': 'tedarikci',
                    'yore': 'yore',
                    'notlar': 'notlar'
                }
                
                for h_key, a_key in mapping.items():
                    if h_key in yeni_veriler:
                        arsiv_updates.append(f"{a_key}=?")
                        arsiv_vals.append(yeni_veriler[h_key])
                
                if arsiv_updates:
                    arsiv_vals.append(eski_lot)
                    a_query = f"UPDATE bugday_giris_arsivi SET {', '.join(arsiv_updates)} WHERE lot_no=?"
                    c.execute(a_query, arsiv_vals)

            # 4. Tavlı Stok Senkronizasyonu (Çıkış ise ve miktar değiştiyse)
            if eski_tip == "Çıkış" and 'miktar' in yeni_veriler:
                yeni_miktar = float(yeni_veriler['miktar'])
                fark = yeni_miktar - eski_miktar
                
                if abs(fark) > 0.001:
                    # Eski miktarı iade et, yeniyi düş -> aslında farkı düşmek yeterli
                    # Eğer fark pozitifse (yeni > eski): daha çok çıkış olmuş -> stok azalmalı -> update -fark
                    # Eğer fark negatifse (yeni < eski): daha az çıkış -> stok artmalı -> update -fark (fark negatif olunca + olur)
                    
                    c.execute("UPDATE silolar SET tavli_bugday_stok = tavli_bugday_stok - ? WHERE isim=?", (fark, silo_isim))

            conn.commit()
            
            # 5. Tüm siloları yeniden hesapla (Ortalamalar için)
            recalculate_silos_from_logs()
            
            return True, "Kayıt güncellendi ve stoklar yeniden hesaplandı."

    except Exception as e:
        return False, f"Güncelleme hatası: {e}"

def delete_stok_hareketi(hareket_id):
    """Stok hareketini ve bağlı kayıtları sil"""
    try:
        hareket_id = int(hareket_id)
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # 1. Kaydı bul
            c.execute("SELECT lot_no, hareket_tipi FROM hareketler WHERE id=?", (hareket_id,))
            record = c.fetchone()
            if not record:
                return False, "Kayıt bulunamadı!"
            
            lot_no, hareket_tipi = record
            
            # 2. Hareketler tablosundan sil
            c.execute("DELETE FROM hareketler WHERE id=?", (hareket_id,))
            
            # 3. Arşivden sil (Giriş ise ve Lot varsa)
            if hareket_tipi == "Giriş" and lot_no:
                c.execute("DELETE FROM bugday_giris_arsivi WHERE lot_no=?", (lot_no,))
                
            conn.commit()
            
            # 4. Yeniden hesapla (Bu işlem silinen kaydı da hesaba katarak düzeltir)
            recalculate_silos_from_logs()
            
            return True, "Kayıt başarıyla silindi ve stoklar güncellendi."
            
    except Exception as e:
        return False, f"Silme hatası: {e}"


def show_stok_hareketleri():
    """Stok Hareketleri ve Düzenleme Ekranı"""
    st.header("📋 Stok Hareket Kayıtları")
    
    # Verileri Çek
    try:
        df = get_movements()
    except:
        df = pd.DataFrame()
    
    if df.empty:
        st.info("Henüz kayıt bulunmamaktadır.")
        return

    # Admin Kontrolü
    is_admin = st.session_state.get('user_role') == 'admin'
    
    # Sütun İsimlendirme ve Seçimi
    col_map = {
        "tarih": "Tarih",
        "lot_no": "Lot No",
        "hareket_tipi": "İşlem",
        "plaka": "Plaka",
        "bugday_cinsi": "Buğday Cinsi",
        "tedarikci": "Tedarikçi",
        "yore": "Yöre / Bölge", 
        "protein": "Protein",
        "rutubet": "Rutubet",
        "gluten": "Gluten",
        "gluten_index": "Gluten Index",
        "sedim": "Sedim",
        "gecikmeli_sedim": "Gecikmeli Sedim",
        "sune": "Süne",
        "kirik_ciliz": "Kırık & Cılız",
        "yabanci_tane": "Yabancı Tane",
        "hasere": "Haşere", 
        "miktar": "Miktar (Ton)",
        "silo_isim": "Döküleceği Silo",
        "alis_fiyati": "Alış Fiyatı"
    }

    # Tarih formatı (Sadece görüntüleme için)
    df_display = df.copy()
    if 'tarih' in df_display.columns:
         try:
            df_display['tarih'] = pd.to_datetime(df_display['tarih']).dt.strftime('%d.%m.%Y %H:%M')
         except: pass

    # Rename before display
    df_display = df_display.rename(columns=col_map)
    
    # Tablo Gösterimi
    # Selection Mode (Streamlit 1.35+)
    selection = st.dataframe(
        df_display, 
        use_container_width=True,
        hide_index=True,
        on_select="rerun" if is_admin else "ignore", 
        selection_mode="single-row" if is_admin else "multi-row"
    )
    
    # Düzenleme Formu (Sadece Admin ve Seçim Varsa)
    if is_admin:
        try:
            selected_rows = selection.selection.rows
        except AttributeError:
             selected_rows = []
        
        if selected_rows: # Seçilen satırın indexi gelir
            # Seçilen satırın verilerini orjinal df'den (formatlanmamış) al
            idx = selected_rows[0]
            row = df.iloc[idx]
            
            st.divider()
            st.markdown(f"### ✏️ Kayıt Düzenle (ID: {row['id']})")
            
            with st.form("edit_movement_form"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Hareket:** {row['hareket_tipi']}")
                    st.write(f"**Silo:** {row['silo_isim']}")
                    st.write(f"**Lot:** {row['lot_no']}")
                
                with col2:
                    new_miktar = st.number_input("Miktar (Ton)", value=float(row['miktar']), step=0.1)
                    new_fiyat = st.number_input("Fiyat / Maliyet", value=float(row['alis_fiyati'] if row['alis_fiyati'] else 0.0), step=0.01)
                
                with col3:
                    new_prot = st.number_input("Protein", value=float(row['protein'] if row['protein'] else 0.0), step=0.1)
                    new_rut = st.number_input("Rutubet", value=float(row['rutubet'] if row['rutubet'] else 0.0), step=0.1)
                
                # Diğer Değerler (Expander)
                with st.expander("Diğer Değerler (Gluten, Hektolitre, Süne...)", expanded=False):
                    c_e1, c_e2, c_e3 = st.columns(3)
                    with c_e1:
                        # Hektolitre check: Hareket tablosunda yoksa giriş arşivinden gelmiş olabilir (get_movements join yapıyor)
                        h_val = float(row['hektolitre']) if 'hektolitre' in row and pd.notnull(row['hektolitre']) else 0.0
                        new_hl = st.number_input("Hektolitre", value=h_val, step=0.1)
                        
                        g_val = float(row['gluten']) if row['gluten'] and pd.notnull(row['gluten']) else 0.0
                        new_glut = st.number_input("Gluten", value=g_val, step=0.1)
                        
                    with c_e2:
                        s_val = float(row['sedim']) if row['sedim'] and pd.notnull(row['sedim']) else 0.0
                        new_sedim = st.number_input("Sedim", value=s_val, step=1.0)
                        
                        sune_val = float(row['sune']) if 'sune' in row and pd.notnull(row['sune']) else 0.0
                        new_sune = st.number_input("Süne", value=sune_val, step=0.1)
                        
                    with c_e3:
                        new_notlar = st.text_area("Notlar", value=str(row['notlar'] if row['notlar'] else ""), height=100)
                
                st.write("")
                st.write("")
                col_save, col_del = st.columns([1, 1])
                
                with col_save:
                    submit_update = st.form_submit_button("💾 Değişiklikleri Kaydet", type="primary", use_container_width=True)
                
                with col_del:
                    # Form içinde ikinci bir işlem butonu (Sil)
                    # Not: st.form_submit_button formun submit olmasını tetikler.
                    # Silme işlemi için ayrı bir onay mekanizması olduğu için bunu
                    # form dışına çıkarmak daha sağlıklı olabilir ama satır ID'si lazım.
                    # Form içinde sadece Save olsun, Silme butonunu formun altına koyalım mı?
                    # Veya form içinde submit button olarak koyup, session state ile kontrol edelim.
                    delete_btn = st.form_submit_button("🗑️ Kaydı Sil", type="secondary", use_container_width=True)
                
            if submit_update:
                update_data = {
                    'miktar': new_miktar,
                    'maliyet': new_fiyat,
                    'protein': new_prot,
                    'rutubet': new_rut,
                    'gluten': new_glut,
                    'hektolitre': new_hl,
                    'sedim': new_sedim,
                    'sune': new_sune, 
                    'notlar': new_notlar
                }
                
                success, msg = update_stok_hareketi(row['id'], update_data)
                if success:
                    st.success(msg)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)
            
            if delete_btn:
                st.session_state[f"confirm_delete_{row['id']}"] = True
                
            # Silme Onayı (Form dışında render edilebilir ama akış gereği burada)
            if st.session_state.get(f"confirm_delete_{row['id']}"):
                st.error("⚠️ BU KAYIT SİLİNECEK! Bu işlem geri alınamaz.")
                col_yes, col_no = st.columns(2)
                if col_yes.button("✅ Evet, Sil", key=f"yes_{row['id']}"):
                    success, msg = delete_stok_hareketi(row['id'])
                    if success:
                        st.success(msg)
                        # State temizle
                        del st.session_state[f"confirm_delete_{row['id']}"]
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
                
                if col_no.button("❌ İptal", key=f"no_{row['id']}"):
                    del st.session_state[f"confirm_delete_{row['id']}"]
                    st.rerun()
                update_data = {
                    'miktar': new_miktar,
                    'maliyet': new_fiyat,
                    'protein': new_prot,
                    'rutubet': new_rut,
                    'gluten': new_glut,
                    'hektolitre': new_hl,
                    'sedim': new_sedim,
                    'sune': new_sune, # update fonksiyonu bunu filtrelemeli veya kullanmalı
                    'notlar': new_notlar
                }
                
                success, msg = update_stok_hareketi(row['id'], update_data)
                if success:
                    st.success(msg)
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("👆 Düzenlemek için listeden bir satır seçiniz.")
    
    st.divider()
    # Excel indirme (görüntülenen df üzerinden)
    download_styled_excel(df_display, "stok_hareketleri.xlsx")

def show_bugday_giris_arsivi():
    """Buğday Giriş Arşivi - Filtreleme ve Raporlama"""
    st.header("🗄️ Buğday Giriş Arşivi")
    st.caption("Geçmiş buğday alım kayıtlarını filtreleyin ve analiz edin.")
    
    # Veriyi çek
    df = get_bugday_arsiv()
    if df.empty:
        st.info("📭 Henüz arşivlenmiş bir giriş kaydı bulunmuyor.")
        return
        
    # --- FİLTRELEME ALANI ---
    with st.expander("🔍 Filtreleme Seçenekleri", expanded=False):
        col_f1, col_f2, col_f3 = st.columns(3)
        
        # 1. Tarih Aralığı
        with col_f1:
            min_date = df['tarih'].min()
            max_date = df['tarih'].max()
            date_range = st.date_input(
                "Tarih Aralığı",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        
        # 2. Tedarikçi Filtresi
        with col_f2:
            suppliers = ["Tümü"] + sorted(df['tedarikci'].dropna().unique().tolist())
            selected_supplier = st.selectbox("Tedarikçi", suppliers)
            
        # 3. Buğday Cinsi Filtresi
        with col_f3:
            types = ["Tümü"] + sorted(df['bugday_cinsi'].dropna().unique().tolist())
            selected_type = st.selectbox("Buğday Cinsi", types)

    # --- FİLTRELEME MANTIĞI ---
    filtered_df = df.copy()
    
    # Tarih Filtresi
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1) # Gün sonuna kadar
        filtered_df = filtered_df[
            (filtered_df['tarih'] >= start_date) & 
            (filtered_df['tarih'] <= end_date)
        ]
    
    # Tedarikçi Filtresi
    if selected_supplier != "Tümü":
        filtered_df = filtered_df[filtered_df['tedarikci'] == selected_supplier]
        
    # Cins Filtresi
    if selected_type != "Tümü":
        filtered_df = filtered_df[filtered_df['bugday_cinsi'] == selected_type]
        
    # --- ÖZET METRİKLER (Dashboard Tarzı) ---
    if not filtered_df.empty:
        st.markdown("### 📊 Özet İstatistikler")
        m1, m2, m3, m4 = st.columns(4)
        
        total_tonaj = filtered_df['tonaj'].sum()
        avg_fiyat = filtered_df['fiyat'].mean()
        avg_protein = filtered_df['protein'].mean()
        avg_gluten = filtered_df['gluten'].mean()
        
        m1.metric("Toplam Tonaj", f"{total_tonaj:,.1f} Ton")
        m2.metric("Ortalama Fiyat", f"{avg_fiyat:.2f} ₺")
        m3.metric("Ort. Protein", f"%{avg_protein:.1f}")
        m4.metric("Ort. Gluten", f"%{avg_gluten:.1f}")
        
        st.divider()
        
        # --- TABLO ---
        # st.write(f"**Sonuçlar ({len(filtered_df)} Kayıt)**")
        # BU ALAN İSTENİLDİĞİ ÜZERE KALDIRILDI (STOK HAREKETLERİ İLE AYNI OLDUĞU İÇİN)
        # st.dataframe(...)
            
        # --- EXCEL İNDİRME (Profesyonel) ---
        
        # Sütun İsimlendirme
        excel_map = {
            "tarih": "Tarih",
            "tedarikci": "Tedarikçi",
            "lot_no": "Lot No",
            "plaka": "Plaka",
            "bugday_cinsi": "Cins",
            "silo_isim": "Silo",
            "yore": "Yöre",
            "tonaj": "Tonaj",
            "fiyat": "Fiyat",
            "protein": "Protein",
            "rutubet": "Rutubet",
            "gluten": "Gluten",
            "sune": "Süne",
            "hektolitre": "Hektolitre",
            "sedim": "Sedim",
            "notlar": "Notlar"
        }
            
        df_export = filtered_df.rename(columns=excel_map)
        
        # İstenen düzenli sıra
        export_cols = [
            "Tarih", "Lot No", "Tedarikçi", "Cins", "Silo", "Yöre", "Plaka", 
            "Tonaj", "Fiyat", "Protein", "Rutubet", "Gluten", "Sedim", "Notlar"
        ]
        valid_cols = [c for c in export_cols if c in df_export.columns]
        
        # Tarih formatlama
        if 'Tarih' in df_export.columns:
            df_export['Tarih'] = pd.to_datetime(df_export['Tarih']).dt.strftime('%d.%m.%Y')

        st.divider()
        download_styled_excel(
            df_export[valid_cols], 
            f"bugday_kabul_arsivi_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
            
    else:
        st.warning("⚠️ Seçilen filtre kriterlerine uygun kayıt bulunamadı.")
