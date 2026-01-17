import streamlit as st
import pandas as pd
import time
from datetime import datetime
import sqlite3
import json

from app.core.database import get_db_connection
from app.core.utils import turkce_karakter_duzelt
from app.core.config import INPUT_LIMITS, TERMS, get_limit
# We'll import reports when needed to avoid circular imports if any, but modules importing modules is fine if structured well.
# Reports module depends on nothing but core utils.
from app.modules.reports import create_un_maliyet_pdf_report

def save_spec(un_cinsi, parametre, min_val, max_val, hedef_val, tolerans):
    """Spesifikasyon kaydet/güncelle"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Önce var mı bak
            c.execute("SELECT id FROM un_spekleri WHERE un_cinsi=? AND parametre=?", (un_cinsi, parametre))
            exists = c.fetchone()
            
            if exists:
                c.execute("""UPDATE un_spekleri 
                           SET min_deger=?, max_deger=?, hedef_deger=?, tolerans=?, aktif=1 
                           WHERE id=?""", 
                           (min_val, max_val, hedef_val, tolerans, exists[0]))
            else:
                c.execute("""INSERT INTO un_spekleri (un_cinsi, parametre, min_deger, max_deger, hedef_deger, tolerans) 
                           VALUES (?, ?, ?, ?, ?, ?)""",
                           (un_cinsi, parametre, min_val, max_val, hedef_val, tolerans))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

def delete_spec_group(un_cinsi):
    """Bir un cinsine ait tüm spekleri sil"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM un_spekleri WHERE un_cinsi=?", (un_cinsi,))
            conn.commit()
            return True
    except Exception as e:
        return False

def get_all_specs_dataframe():
    """Tüm spekleri rapor için çek"""
    try:
        with get_db_connection() as conn:
            df = pd.read_sql("""
                SELECT un_cinsi as "Un Cinsi", 
                       parametre as "Parametre", 
                       min_deger as "Min", 
                       hedef_deger as "Hedef", 
                       max_deger as "Max" 
                FROM un_spekleri 
                ORDER BY un_cinsi, parametre
            """, conn)
            return df
    except:
        return pd.DataFrame()

def show_spec_yonetimi():
    """Un Kalite Spesifikasyon Yönetimi (Profesyonel Versiyon - Tam Kapsamlı)"""
    st.markdown("### 🎯 Un Kalite Spesifikasyonları (Spec)")
    
    # 1. Un Cinsi Seçimi
    try:
        with get_db_connection() as conn:
            un_cinsleri = pd.read_sql("SELECT DISTINCT un_cinsi_marka FROM un_analiz WHERE un_cinsi_marka IS NOT NULL", conn)
            spek_cinsleri = pd.read_sql("SELECT DISTINCT un_cinsi FROM un_spekleri", conn)
            # Birleştir ve sırala
            all_types = sorted(list(set(un_cinsleri['un_cinsi_marka'].tolist() + spek_cinsleri['un_cinsi'].tolist())))
    except:
        all_types = []

    # Üst Bar: Seçim
    col_sel, col_add = st.columns([2, 1])
    
    with col_sel:
        secilen_urun = st.selectbox("Düzenlenecek Un Cinsini Seçiniz", ["(Seçiniz/Yeni Ekle)"] + all_types)
    
    yeni_isim_girisi = ""
    if secilen_urun == "(Seçiniz/Yeni Ekle)":
        with col_add:
            yeni_isim_girisi = st.text_input("➕ Yeni Un Tanımla", placeholder="Örn: Tam Buğday Unu").strip()
            if yeni_isim_girisi:
                secilen_urun = yeni_isim_girisi
            else:
                secilen_urun = None

    if not secilen_urun:
        st.info("👆 Lütfen düzenlemek veya oluşturmak için bir un cinsi seçin.")
        
        # Genel Liste (Eğer hiç seçim yoksa genel listeyi gösterelim)
        st.divider()
        st.caption("📋 Sistemde Kayıtlı Tüm Spekler")
        df_all = get_all_specs_dataframe()
        if not df_all.empty:
             st.dataframe(df_all, use_container_width=True, hide_index=True)
        return

    st.divider()
    
    # Mevcut Spekleri Çek
    current_specs = {}
    try:
        with get_db_connection() as conn:
            df_specs = pd.read_sql("SELECT * FROM un_spekleri WHERE un_cinsi=?", conn, params=(secilen_urun,))
            if not df_specs.empty:
                for _, row in df_specs.iterrows():
                    current_specs[row['parametre']] = row
    except: pass

    # --- KAPSAMLI PARAMETRE LİSTESİ ---
    param_groups = {
        "Kimyasal Analizler": [
            ("protein", "Protein (%)"),
            ("rutubet", "Rutubet (%)"),
            ("kul", "Kül (%)"),
            ("gluten", "Gluten (%)"),
            ("gluten_index", "Gluten Index"),
            ("sedim", "Sedim (ml)"),
            ("gecikmeli_sedim", "Gecikmeli Sedim (ml)"),
            ("fn", "Düşme Sayısı (FN)"),
            ("ffn", "F.F.N"),
            ("nisasta_zedelenmesi", "Nişasta Zedelenmesi")
        ],
        "Farinograph & Amilograph": [
            ("su_kaldirma_f", "Su Kaldırma (Farino) (%)"),
            ("gelisme_suresi", "Gelişme Süresi (dk)"),
            ("stabilite", "Stabilite (dk)"),
            ("yumusama", "Yumuşama Derecesi (FU)"),
            ("amilograph", "Amilograph (AU)")
        ],
        "Extensograph": [
            ("enerji45", "Enerji (45 dk)"),
            ("direnc45", "Direnç (45 dk)"),
            ("taban45", "Uzama/Taban (45 dk)"),
            ("enerji90", "Enerji (90 dk)"),
            ("direnc90", "Direnç (90 dk)"),
            ("taban90", "Uzama/Taban (90 dk)"),
            ("enerji135", "Enerji (135 dk)"),
            ("direnc135", "Direnç (135 dk)"),
            ("taban135", "Uzama/Taban (135 dk)"),
            ("su_kaldirma_e", "Su Kaldırma (Extenso) (%)")
        ]
    }

    # --- DÜZENLEME FORMU ---
    st.markdown(f"### 🛠️ Düzenleme: {secilen_urun}")
    
    with st.form("spec_editor_comprehensive"):
        tabs = st.tabs(list(param_groups.keys()))
        
        # Tüm inputları saklamak için
        input_keys = [] 
        
        for idx, (group_name, params) in enumerate(param_groups.items()):
            with tabs[idx]:
                for p_key, p_label in params:
                    # Mevcut değerler
                    cur = current_specs.get(p_key, {})
                    val_min = float(cur.get('min_deger', 0.0))
                    val_tgt = float(cur.get('hedef_deger', 0.0))
                    val_max = float(cur.get('max_deger', 0.0))
                    
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    with c1:
                        st.markdown(f"**{p_label}**")
                    with c2:
                        st.number_input("Min", value=val_min, key=f"min_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    with c3:
                        st.number_input("Hedef", value=val_tgt, key=f"tgt_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    with c4:
                        st.number_input("Max", value=val_max, key=f"max_{p_key}", step=0.1, format="%.2f", label_visibility="collapsed")
                    
                    input_keys.append(p_key)
        
        st.divider()
        col_submit, col_info = st.columns([1, 2])
        with col_submit:
            submit_btn = st.form_submit_button("💾 Kaydet / Güncelle", type="primary", use_container_width=True)
        with col_info:
            st.caption("ℹ️ Sadece 0'dan büyük değer girilen parametreler kaydedilecektir. Boş (0.00) bırakılanlar yoksayılır.")

        if submit_btn:
            saved_count = 0
            for p_key in input_keys:
                s_min = st.session_state.get(f"min_{p_key}", 0.0)
                s_tgt = st.session_state.get(f"tgt_{p_key}", 0.0)
                s_max = st.session_state.get(f"max_{p_key}", 0.0)
                
                # Akıllı Kayıt: Sadece herhangi biri > 0 ise kaydet
                if s_min > 0 or s_tgt > 0 or s_max > 0:
                    if save_spec(secilen_urun, p_key, s_min, s_max, s_tgt, 0):
                        saved_count += 1
            
            if saved_count > 0:
                st.success(f"✅ Tansiyon başarılı! {saved_count} parametre güncellendi.")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("⚠️ Hiçbir değer girilmediği için değişiklik yapılmadı.")

    # --- GÖRSEL ÖZET TABLO (Seçili Un) ---
    st.divider()
    col_header, col_delete = st.columns([3, 1])
    
    with col_header:
        st.subheader(f"📋 '{secilen_urun}' Tanımlı Spekleri")
    
    with col_delete:
        # Silme Yetkisi Admin
        if st.session_state.get("user_role") == "admin":
            if st.button("🗑️ Bu Tanımı Sil", key="del_spec_main", type="secondary"):
                if delete_spec_group(secilen_urun):
                    st.success("Tanım silindi!")
                    time.sleep(1)
                    st.rerun()
    
    # Sadece seçili unun speklerini getir
    try:
        with get_db_connection() as conn:
            df_selected_specs = pd.read_sql("""
                SELECT parametre as "Parametre", 
                       min_deger as "Min", 
                       hedef_deger as "Hedef", 
                       max_deger as "Max" 
                FROM un_spekleri 
                WHERE un_cinsi = ?
                ORDER BY parametre
            """, conn, params=(secilen_urun,))
            
            if not df_selected_specs.empty:
                # Parametre adlarını güzelleştir (Opsiyonel mapping)
                st.dataframe(
                    df_selected_specs,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Min": st.column_config.NumberColumn(format="%.2f"),
                        "Hedef": st.column_config.NumberColumn(format="%.2f"),
                        "Max": st.column_config.NumberColumn(format="%.2f")
                    }
                )
            else:
                st.info("Bu ürün için henüz kaydedilmiş bir spek bulunmuyor.")
    except Exception as e:
        st.error(f"Tablo yüklenirken hata: {e}")



def save_un_analiz(lot_no, islem_tipi, **analiz_degerleri):
    """Un analizini kaydet - GÜVENLİ VERSİYON"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Önce tabloyu kontrol et, eksik sütunları ekle
            c.execute("PRAGMA table_info(un_analiz)")
            mevcut_sutunlar = [col[1] for col in c.fetchall()]
            
            # un_cinsi_marka sütununu kontrol et ve ekle
            if 'un_cinsi_marka' not in mevcut_sutunlar:
                try:
                    c.execute("ALTER TABLE un_analiz ADD COLUMN un_cinsi_marka TEXT")
                    conn.commit()
                except:
                    pass
            
            # un_markasi sütununu kontrol et ve ekle (YENİ)
            if 'un_markasi' not in mevcut_sutunlar:
                try:
                    c.execute("ALTER TABLE un_analiz ADD COLUMN un_markasi TEXT")
                    conn.commit()
                except:
                    pass
            
            # SABIT sütun listesi - un_cinsi_marka ve un_markasi eklendi
            columns = [
                'lot_no', 'islem_tipi', 'tarih',
                'un_cinsi_marka', 'un_markasi', 'uretim_silosu', 'protein', 'rutubet', 'gluten', 'gluten_index',
                'sedim', 'gecikmeli_sedim', 'fn', 'ffn', 'amilograph',
                'nisasta_zedelenmesi', 'kul', 'su_kaldirma_f', 'gelisme_suresi',
                'stabilite', 'yumusama', 'su_kaldirma_e', 'direnc45', 'direnc90',
                'direnc135', 'taban45', 'taban90', 'taban135', 'enerji45',
                'enerji90', 'enerji135', 'notlar'
            ]
            
            # Temel değerler
            values = [
                lot_no,
                islem_tipi,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            # Analiz değerleri - un_cinsi_marka ve un_markasi eklendi
            analiz_fields = [
                'un_cinsi_marka', 'un_markasi', 'uretim_silosu', 'protein', 'rutubet', 'gluten', 'gluten_index',
                'sedim', 'gecikmeli_sedim', 'fn', 'ffn', 'amilograph',
                'nisasta_zedelenmesi', 'kul', 'su_kaldirma_f', 'gelisme_suresi',
                'stabilite', 'yumusama', 'su_kaldirma_e', 'direnc45', 'direnc90',
                'direnc135', 'taban45', 'taban90', 'taban135', 'enerji45',
                'enerji90', 'enerji135', 'notlar'
            ]
            
            for field in analiz_fields:
                if field in analiz_degerleri:
                    val = analiz_degerleri[field]
                    if isinstance(val, (int, float)):
                        values.append(float(val))
                    elif isinstance(val, str):
                        if field == 'notlar':
                            values.append(str(val)[:500])
                        elif field == 'lot_no' or field == 'uretim_silosu' or field == 'un_cinsi_marka' or field == 'un_markasi':
                            values.append(str(val)[:100])  # 100 karakter sınırı
                        else:
                            values.append(str(val)[:100])
                    else:
                        values.append(None)
                else:
                    values.append(None)
            
            # GÜVENLİ SQL
            placeholders = ', '.join(['?'] * len(values))
            column_names = ', '.join(columns)
            
            query = f"INSERT INTO un_analiz ({column_names}) VALUES ({placeholders})"
            c.execute(query, values)
            conn.commit()
            
            return True, "Un analizi başarıyla kaydedildi!"
            
    except sqlite3.IntegrityError as e:
        return False, f"Bu lot numarası zaten kayıtlı: {lot_no}"
    except Exception as e:
        return False, f"Kayıt hatası: {str(e)}"    

def get_un_analiz_kayitlari():
    """Un analiz kayıtlarını getir"""
    try:
        with get_db_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM un_analiz ORDER BY tarih DESC LIMIT 100",
                conn
            )
            return df
    except:
        return pd.DataFrame()

def save_un_maliyet_hesaplama(hesaplama_verileri, kullanici):
    """Un maliyet hesaplamasını kaydet - GÜVENLİ VERSİYON"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # SQL injection koruması: column isimlerini validate et
            allowed_columns = ['un_cesidi', 'bugday_pacal_maliyeti', 'aylik_kirilan_bugday',
                              'un_randimani', 'un_satis_fiyati', 'un2_orani', 'bongalite_orani',
                              'kepek_orani', 'razmol_orani', 'belge_geliri', 'un2_fiyati',
                              'bongalite_fiyati', 'kepek_fiyati', 'razmol_fiyati',
                              'ton_bugday_elektrik', 'elektrik_gideri', 'personel_maasi',
                              'bakim_maliyeti', 'mutfak_gideri', 'finans_gideri', 'nakliye',
                              'satis_pazarlama', 'pp_cuval', 'katki_maliyeti', 'net_kar_kg',
                              'fabrika_cikis_maliyet', 'net_kar_toplam', 'toplam_gelir',
                              'toplam_gider', 'notlar', 'kullanici', 'tarih',
                              'kirik_tonaj', 'kirik_fiyat', 'basak_tonaj', 'basak_fiyat', 'diger_giderler',
                              'ay', 'yil']
            
            # Sadece allowed columns kullan
            columns_to_insert = []
            values_to_insert = []
            
            for col in allowed_columns:
                if col == 'tarih':
                    columns_to_insert.append(col)
                    values_to_insert.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                elif col == 'kullanici':
                    columns_to_insert.append(col)
                    values_to_insert.append(kullanici)
                elif col in hesaplama_verileri:
                    columns_to_insert.append(col)
                    val = hesaplama_verileri[col]
                    # Type checking
                    if isinstance(val, (int, float)):
                        values_to_insert.append(float(val))
                    elif isinstance(val, str):
                        # SQL injection koruması: tehlikeli karakterleri temizle
                        cleaned_val = val.replace("'", "''").replace(";", "")
                        values_to_insert.append(cleaned_val[:500])  # Limit length
                    else:
                        values_to_insert.append(str(val))
                else:
                    # Varsayılan değer
                    columns_to_insert.append(col)
                    values_to_insert.append(None)
            
            # GÜVENLİ SQL - parametreli sorgu
            placeholders = ', '.join(['?'] * len(values_to_insert))
            column_names = ', '.join(columns_to_insert)
            
            query = f"INSERT INTO un_maliyet_hesaplamalari ({column_names}) VALUES ({placeholders})"
            
            c.execute(query, values_to_insert)
            conn.commit()
            
            return True, "Kayıt başarılı!"
            
    except Exception as e:
        return False, f"SQL hatası: {str(e)}"

def get_un_maliyet_gecmisi():
    """Un maliyet hesaplama geçmişini getir"""
    try:
        with get_db_connection() as conn:
            # Tabloyu kontrol et
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='un_maliyet_hesaplamalari'")
            if c.fetchone() is None:
                return pd.DataFrame()
            
            # Tüm kayıtları getir
            df = pd.read_sql_query(
                "SELECT * FROM un_maliyet_hesaplamalari ORDER BY tarih DESC LIMIT 50",
                conn
            )
            return df
            
    except Exception as e:
        st.error(f"❌ Veri çekme hatası: {str(e)}")
        return pd.DataFrame()

def show_un_analiz_kaydi():
    """Un Analiz Kaydı modülü"""
    
    # Rol kontrolü: Sadece admin ve operations veri girişi yapabilir
    if st.session_state.user_role not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
        
    st.header("📝 Un Analiz Kaydı")
    
    # İki kolon
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📋 Numune Bilgileri")
        
        # Otomatik Lot No Oluştur
        auto_lot_no = f"UN-{datetime.now().strftime('%y%m%d%H%M%S')}"
        st.info(f"**Otomatik Lot No:** `{auto_lot_no}`")
        
        # Lot numarası otomatik oluşturulabilir veya manuel
        lot_no = st.text_input(
            "Lot Numarası *",
            value=auto_lot_no,
            placeholder="Örn: UN-240115001",
            help="Benzersiz lot numarası (Otomatik atanır, değiştirebilirsiniz)"
        )
        
        # Tarih
        analiz_tarihi = st.date_input("Analiz Tarihi", datetime.now())
        
        # İşlem Tipi
        islem_tipi = st.selectbox(
            "İşlem Tipi *",
            ["ÜRETİM", "SEVKİYAT", "NUMUNE", "ŞİKAYET", "İADE"]
        )

        # Un Markası (Ticari İsim) - YENİ
        un_markasi = st.text_input(
            "Un Markası (Ticari İsim)",
            placeholder="Örn: Pırlanta, Yakut, Özel Karışım...",
            help="Paket üzerine basılan ticari marka adı"
        )
        
        # Un Cinsi & Marka (Veritabanından Çek)
        try:
            with get_db_connection() as conn:
                # Hem analizlerden hem de speklerden gelenleri birleştir
                un_cinsleri = pd.read_sql("SELECT DISTINCT un_cinsi_marka FROM un_analiz WHERE un_cinsi_marka IS NOT NULL", conn)
                spek_cinsleri = pd.read_sql("SELECT DISTINCT un_cinsi FROM un_spekleri", conn)
                
                type_list = sorted(list(set(un_cinsleri['un_cinsi_marka'].tolist() + spek_cinsleri['un_cinsi'].tolist())))
        except:
            type_list = []
            
        col_type_sel, col_type_new = st.columns([2, 1])
        with col_type_sel:
            selected_type = st.selectbox("Un Cinsi Seçin *", ["(Listeden Seçin)"] + type_list + ["(Yeni Tanımla)"])
        
        if selected_type == "(Yeni Tanımla)":
            with col_type_new:
                un_cinsi_marka = st.text_input("Yeni Un Adı", placeholder="Örn: Özel Pizza Unu").strip()
        elif selected_type != "(Listeden Seçin)":
            un_cinsi_marka = selected_type
        else:
            un_cinsi_marka = ""

        # Üretim Silosu (Dinamik Liste)
        uretim_silosu = None
        if islem_tipi == "ÜRETİM":
            try:
                with get_db_connection() as conn:
                    # uretim_silolari tablosundan getir
                    c = conn.cursor()
                    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uretim_silolari'")
                    if c.fetchone():
                        c.execute("SELECT silo_adi FROM uretim_silolari WHERE aktif = 1 ORDER BY silo_adi")
                        silo_listesi = ["(Belirtilmemiş)"] + [row[0] for row in c.fetchall()]
                    else:
                        silo_listesi = [] 
            except:
                silo_listesi = []
            
            if not silo_listesi or len(silo_listesi) <= 1: 
                st.warning("⚠️ Tanımlı üretim silosu bulunamadı!")
                uretim_silosu = None
            else:
                uretim_silosu = st.selectbox(
                    "Üretim Silosu *",
                    silo_listesi,
                    help="Numunenin alındığı üretim silosu veya bant"
                )
        else:
            uretim_silosu = None
        
        if uretim_silosu == "(Belirtilmemiş)":
            uretim_silosu = None
        
        # Notlar
        notlar = st.text_area("Notlar", placeholder="Analiz notları...", height=80, max_chars=500)
    
    with col2:
        st.subheader("🧪 Un Analiz Değerleri")
        
        # 0. SPECLERİ ÇEK (Smart Validation)
        current_specs = {}
        if un_cinsi_marka:
            try:
                with get_db_connection() as conn:
                    df_specs = pd.read_sql("SELECT * FROM un_spekleri WHERE un_cinsi=?", conn, params=(un_cinsi_marka.strip(),))
                    if not df_specs.empty:
                        for _, row in df_specs.iterrows():
                            current_specs[row['parametre']] = row
            except: pass
            
        # Validasyon Takipçisi
        validation_status = {"total": 0, "passed": 0, "failed": 0}

        def validate_input(key, label, val):
            """Değeri spec ile kıyasla, görsel geri bildirim ver"""
            if key in current_specs:
                validation_status["total"] += 1
                spec = current_specs[key]
                s_min = float(spec['min_deger'])
                s_max = float(spec['max_deger'])
                s_target = float(spec['hedef_deger'])
                
                # Hedef Aralığı Bilgisi
                st.caption(f"🎯 Hedef: **{s_target:.2f}** | Aralık: **{s_min:.2f} - {s_max:.2f}**")
                
                if val < s_min or val > s_max:
                    st.error(f"❌ {label} Limit Dışı! (Min: {s_min:.2f} - Max: {s_max:.2f})")
                    validation_status["failed"] += 1
                    return False
                else:
                    # Yeşil tik (isteğe bağlı, çok kalabalık olmasın diye sadece başarılı sayısını artırıyoruz)
                    validation_status["passed"] += 1
                    return True
            return True

        # Kimyasal Analizler
        with st.expander("🧪 KİMYASAL ANALİZLER (Zorunlu)", expanded=True):
            col_k1, col_k2 = st.columns(2)
            
            with col_k1:
                # Protein
                protein = st.number_input("Protein (%)", min_value=0.0, max_value=20.0, value=11.5, step=0.1)
                validate_input("protein", "Protein", protein)
                
                # Rutubet
                rutubet = st.number_input("Rutubet (%)", min_value=0.0, max_value=20.0, value=14.5, step=0.1)
                validate_input("rutubet", "Rutubet", rutubet)
                
                # Gluten
                gluten = st.number_input("Gluten (%)", min_value=0.0, max_value=50.0, value=28.0, step=0.1)
                validate_input("gluten", "Gluten", gluten)
                                       
                # Gluten Index
                gluten_index = st.number_input("Gluten Index", min_value=0.0, max_value=100.0, value=85.0, step=1.0)
                validate_input("gluten_index", "GI", gluten_index)
            
            with col_k2:
                # Sedim
                sedim = st.number_input("Sedim (ml)", min_value=0.0, max_value=100.0, value=40.0, step=1.0)
                validate_input("sedim", "Sedim", sedim)
                
                # Gecikmeli Sedim
                gecikmeli_sedim = st.number_input("Gecikmeli Sedim (ml)", min_value=0.0, max_value=100.0, value=50.0, step=1.0)
                validate_input("gecikmeli_sedim", "G.Sedim", gecikmeli_sedim)

                
                # Mantıksal Kontrol: Gecikmeli Sedim < Sedim
                if gecikmeli_sedim > 0 and sedim > 0 and gecikmeli_sedim < sedim:
                    st.error("🚨 HATA: Gecikmeli Sedim, Normal Sedim'den düşük olamaz! (Süne riski veya ölçüm hatası)")
                
                # Düşme Sayısı
                fn = st.number_input("Düşme Sayısı (FN)", min_value=0.0, value=350.0, step=1.0)
                validate_input("fn", "Düşme Sayısı", fn)
                
                ffn = st.number_input("F.F.N", min_value=0.0, value=380.0, step=1.0)
        
        # Diğer Kimyasal Analizler
        with st.expander("🔬 DİĞER KİMYASAL ANALİZLER", expanded=False):
            col_k3, col_k4 = st.columns(2)
            
            with col_k3:
                amilograph = st.number_input("Amilograph (AU)", min_value=0.0, value=650.0, step=1.0)
                validate_input("amilograph", "Amilograph", amilograph)
                
                nisasta_zedelenmesi = st.number_input("Nişasta Zedelenmesi", min_value=0.0, value=15.0, step=0.1)
            
            with col_k4:
                kul = st.number_input("Kül (%)", min_value=0.0, value=0.720, step=0.001, format="%.3f")
                validate_input("kul", "Kül", kul)
        
        # Farinograph Analizleri
        with st.expander("📈 FARINOGRAPH ANALİZLERİ", expanded=False):
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                su_kaldirma_f = st.number_input("Su Kaldırma (%)", min_value=0.0, value=57.0, step=0.1)
                gelisme_suresi = st.number_input("Gelişme Süresi (dk)", min_value=0.0, value=1.8, step=0.1)
            
            with col_f2:
                stabilite = st.number_input("Stabilite (dk)", min_value=0.0, value=2.3, step=0.1)
                yumusama = st.number_input("Yumuşama Derecesi (FU)", min_value=0.0, value=100.0, step=1.0)
        
        # Extensograph Analizleri (İSTEĞE BAĞLI)
        with st.expander("📊 EXTENSOGRAPH ANALİZLERİ (Opsiyonel)", expanded=False):
            st.info("Bu bölümü doldurmak zorunlu değildir")
            
            # 45. dakika
            st.write("**45. Dakika:**")
            col_e45_1, col_e45_2, col_e45_3 = st.columns(3)
            with col_e45_1:
                direnc45 = st.number_input("Direnç (45)", min_value=0.0, value=610.0, step=1.0)
            with col_e45_2:
                taban45 = st.number_input("Taban (45)", min_value=0.0, value=165.0, step=1.0)
            with col_e45_3:
                enerji45 = st.number_input("Enerji (45)", min_value=0.0, value=110.0, step=1.0)
            
            # 90. dakika
            st.write("**90. Dakika:**")
            col_e90_1, col_e90_2, col_e90_3 = st.columns(3)
            with col_e90_1:
                direnc90 = st.number_input("Direnç (90)", min_value=0.0, value=900.0, step=1.0)
            with col_e90_2:
                taban90 = st.number_input("Taban (90)", min_value=0.0, value=125.0, step=1.0)
            with col_e90_3:
                enerji90 = st.number_input("Enerji (90)", min_value=0.0, value=120.0, step=1.0)
            
            # 135. dakika
            st.write("**135. Dakika:**")
            col_e135_1, col_e135_2, col_e135_3 = st.columns(3)
            with col_e135_1:
                direnc135 = st.number_input("Direnç (135)", min_value=0.0, value=980.0, step=1.0)
            with col_e135_2:
                taban135 = st.number_input("Taban (135)", min_value=0.0, value=120.0, step=1.0)
            with col_e135_3:
                enerji135 = st.number_input("Enerji (135)", min_value=0.0, value=126.0, step=1.0)
            
            su_kaldirma_e = st.number_input("Su Kaldırma (Extensograph) (%)", min_value=0.0, value=54.3, step=0.1)
    
    # --- UYGUNLUK ÖZETİ (Dashboard) ---
    if validation_status["total"] > 0:
        st.divider()
        st.markdown("### 📊 Kalite Uygunluk Özeti")
        s_col1, s_col2, s_col3 = st.columns(3)
        
        s_col1.metric("Kontrol Edilen", f"{validation_status['total']} Parametre")
        s_col2.metric("Uygun", f"{validation_status['passed']} Parametre", delta_color="normal")
        
        if validation_status["failed"] > 0:
            s_col3.metric("Limit Dışı", f"{validation_status['failed']} Parametre", delta=f"-{validation_status['failed']}", delta_color="inverse")
            st.error(f"⚠️ Toplam {validation_status['failed']} parametre kalite standartlarının dışında!")
        else:
            s_col3.metric("Limit Dışı", "0", delta_color="off")
            st.success("✅ Tüm değerler kalite standartlarına %100 uygundur.")

    # Kaydet butonu
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    
    with col_btn2:
        if st.button("✅ Un Analizini Kaydet", type="primary", use_container_width=True):
            # VALİDASYON
            if not lot_no or not islem_tipi:
                st.error("❌ Lot no ve işlem tipi zorunludur!")
                return
            
            # Un Cinsi & Marka validasyonu
            if not un_cinsi_marka.strip():
                st.error("❌ Un Cinsi & Marka zorunludur!")
                return
            
            # Üretim tipi için üretim silosu zorunlu
            if islem_tipi == "ÜRETİM" and (not uretim_silosu or uretim_silosu == "(Belirtilmemiş)"):
                st.error("❌ Üretim işlem tipinde Üretim Silosu zorunludur!")
                return
            
            if protein <= 0 or rutubet <= 0 or gluten <= 0:
                st.error("❌ Protein, rutubet ve gluten değerleri 0'dan büyük olmalıdır!")
                return
            
            try:
                # Analiz verilerini hazırla
                analiz_data = {
                    'uretim_silosu': uretim_silosu,
                    'un_cinsi_marka': un_cinsi_marka,
                    'un_markasi': un_markasi, # YENİ
                    'protein': protein,
                    'rutubet': rutubet,
                    'gluten': gluten,
                    'gluten_index': gluten_index,
                    'sedim': sedim,
                    'gecikmeli_sedim': gecikmeli_sedim,
                    'fn': fn,
                    'ffn': ffn,
                    'amilograph': amilograph,
                    'nisasta_zedelenmesi': nisasta_zedelenmesi,
                    'kul': kul,
                    'su_kaldirma_f': su_kaldirma_f,
                    'gelisme_suresi': gelisme_suresi,
                    'stabilite': stabilite,
                    'yumusama': yumusama,
                    'su_kaldirma_e': su_kaldirma_e,
                    'direnc45': direnc45,
                    'direnc90': direnc90,
                    'direnc135': direnc135,
                    'taban45': taban45,
                    'taban90': taban90,
                    'taban135': taban135,
                    'enerji45': enerji45,
                    'enerji90': enerji90,
                    'enerji135': enerji135,
                    'notlar': notlar
                }
                
                # Kaydet
                basarili, mesaj = save_un_analiz(
                    lot_no=lot_no,
                    islem_tipi=islem_tipi,
                    **analiz_data
                )
                
                if basarili:
                    st.success(f"""
                    ✅ **Un analizi başarıyla kaydedildi!**
                    
                    **Detaylar:**
                    - Lot No: **{lot_no}**
                    - İşlem Tipi: **{islem_tipi}**
                    - Un Cinsi (Spec): **{un_cinsi_marka}**
                    - Un Markası: **{un_markasi}**
                    - Analiz Tarihi: **{analiz_tarihi}**
                    """)
                    
                    # Üretim tipi ise silo bilgisi de göster
                    if islem_tipi == "ÜRETİM" and uretim_silosu:
                        st.success(f"🏭 **Üretim Silosu:** {uretim_silosu}")
                    
                    st.success(f"📊 **Analiz Değerleri:** Protein: {protein:.1f}%, Gluten: {gluten:.1f}%, Sedim: {sedim:.1f} ml")
                    
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"❌ {mesaj}")
                    
            except Exception as e:
                st.error(f"❌ Kayıt sırasında hata oluştu: {str(e)}")

def show_un_analiz_kayitlari():
    """Un Analiz Kayıtları modülü"""
    
    st.header("📚 Un Analiz Kayıtları")
    
    # Kayıtları yükle
    df_un = get_un_analiz_kayitlari()
    
    if df_un.empty:
        st.info("📭 Henüz un analiz kaydı bulunmamaktadır.")
        return
    
    # Tarih formatını düzelt (Sadece Gün/Ay/Yıl)
    df_un['tarih'] = pd.to_datetime(df_un['tarih']).dt.strftime('%d/%m/%Y')
    
    # YENİ: Üretim Siloları Yönetimi Butonu (sadece admin ve operations)
    if st.session_state.user_role in ["admin", "operations"]:
        with st.expander("⚙️ Üretim Siloları Yönetimi", expanded=False):
            try:
                with get_db_connection() as conn:
                    c = conn.cursor()
                    # Tablo yoksa oluştur
                    c.execute('''CREATE TABLE IF NOT EXISTS uretim_silolari 
                                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                                 silo_adi TEXT UNIQUE, 
                                 aciklama TEXT, 
                                 aktif INTEGER DEFAULT 1)''')
                    
                    c.execute("SELECT id, silo_adi, aciklama, aktif FROM uretim_silolari ORDER BY silo_adi")
                    silolar = c.fetchall()
                    
                    if silolar:
                        st.write("### Mevcut Üretim Siloları")
                        silo_df = pd.DataFrame(silolar, columns=['ID', 'Silo Adı', 'Açıklama', 'Aktif'])
                        silo_df['Aktif'] = silo_df['Aktif'].apply(lambda x: '✅' if x == 1 else '❌')
                        
                        st.dataframe(
                            silo_df,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Yeni silo ekleme
                        col_silo1, col_silo2 = st.columns([2, 1])
                        with col_silo1:
                            yeni_silo = st.text_input(
                                "Yeni Üretim Silosu Adı",
                                placeholder="Örn: İhracat Paketleme, Özel Üretim Hattı",
                                key="yeni_silo_kayit"
                            )
                        with col_silo2:
                            st.write("")  # Boşluk
                            if st.button("➕ Silo Ekle", key="silo_ekle_kayit"):
                                if yeni_silo.strip():
                                    try:
                                        c.execute("INSERT INTO uretim_silolari (silo_adi) VALUES (?)", 
                                                 (yeni_silo.strip(),))
                                        conn.commit()
                                        st.success(f"✅ '{yeni_silo}' eklendi!")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Silo eklenemedi: {str(e)}")
                                else:
                                    st.warning("⚠️ Silo adı gerekli!")
                    else:
                        st.info("Henüz üretim silosu tanımlanmamış.")
                        
            except Exception as e:
                st.error(f"Üretim siloları yüklenemedi: {str(e)}")
    
    # Filtreleme
    st.subheader("🔍 Filtreleme")
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        # Tüm işlem tiplerini göster
        islem_tipi_listesi = ["Tümü", "ÜRETİM", "SEVKİYAT", "NUMUNE", "ŞİKAYET", "İADE"]
        islem_tipi_filtre = st.selectbox(
            "İşlem Tipi",
            islem_tipi_listesi
        )
    
    with col_f2:
        # Tarih aralığı
        gun_sayisi = st.slider("Son Kaç Gün?", 1, 365, 30)
        tarih_limit = datetime.now() - pd.Timedelta(days=gun_sayisi)
    
    with col_f3:
        # Üretim silosu filtresi
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute("SELECT DISTINCT uretim_silosu FROM un_analiz WHERE uretim_silosu IS NOT NULL AND uretim_silosu != ''")
                silo_listesi = ["Tümü"] + [row[0] for row in c.fetchall()]
                
                silo_filtre = st.selectbox(
                    "Üretim Silosu",
                    silo_listesi
                )
        except:
            silo_filtre = "Tümü"
    
    # Filtrele
    filtered = df_un.copy()
    filtered['tarih_datetime'] = pd.to_datetime(filtered['tarih'], format='%d/%m/%Y')
    
    # Tarih filtresi
    filtered = filtered[filtered['tarih_datetime'] >= tarih_limit]
    
    # İşlem tipi filtresi
    if islem_tipi_filtre != "Tümü":
        filtered = filtered[filtered['islem_tipi'] == islem_tipi_filtre]
    
    # Üretim silosu filtresi
    if silo_filtre != "Tümü":
        filtered = filtered[filtered['uretim_silosu'] == silo_filtre]
    
    st.divider()
    
    # Detaylı tablo
    st.subheader(f"📋 Kayıtlar ({len(filtered)} adet)")
    
    # Görüntülenecek sütunlar
    display_cols = [
        'tarih', 'lot_no', 'islem_tipi', 'un_cinsi_marka', 'un_markasi',
        'protein', 'rutubet', 'gluten', 'gluten_index', 'sedim', 
        'gecikmeli_sedim', 'fn', 'ffn', 'amilograph', 'nisasta_zedelenmesi', 
        'kul', 'su_kaldirma_f', 'gelisme_suresi', 'stabilite', 'yumusama',
        'direnc45', 'taban45', 'enerji45', 'direnc90', 'taban90', 'enerji90',
        'direnc135', 'taban135', 'enerji135', 'uretim_silosu', 'notlar'
    ]
    
    # Sadece mevcut sütunları al
    available_cols = [col for col in display_cols if col in filtered.columns]
    display_df = filtered[available_cols].copy()
    
    # Sütun isimlerini Türkçeleştir
    column_mapping = {
        'tarih': 'Tarih',
        'lot_no': 'Lot Numarası',
        'islem_tipi': 'İşlem Tipi',
        'un_cinsi_marka': 'Un Cinsi (Spec)',
        'un_markasi': 'Un Markası (Ticari)',
        'protein': 'Protein %',
        'rutubet': 'Rutubet %',
        'gluten': 'Gluten %',
        'gluten_index': 'Gluten Index',
        'sedim': 'Sedimantasyon ml',
        'gecikmeli_sedim': 'Gecikmeli Sedim ml',
        'fn': 'F.N',
        'ffn': 'F.F.N',
        'amilograph': 'Amilograph',
        'nisasta_zedelenmesi': 'Nişasta Zedelenmesi',
        'kul': 'Kül %',
        'su_kaldirma_f': 'Su Kaldırma F %',
        'gelisme_suresi': 'Gelişme Süresi dk',
        'stabilite': 'Stabilite dk',
        'yumusama': 'Yumuşama FU',
        'direnc45': 'Direnç 45',
        'taban45': 'Taban 45',
        'enerji45': 'Enerji 45',
        'direnc90': 'Direnç 90',
        'taban90': 'Taban 90',
        'enerji90': 'Enerji 90',
        'direnc135': 'Direnç 135',
        'taban135': 'Taban 135',
        'enerji135': 'Enerji 135',
        'uretim_silosu': 'Üretim Silosu',
        'notlar': 'Notlar'
    }
    
    # Sütun isimlerini güncelle
    display_df = display_df.rename(columns=column_mapping)
    
    # Sayfalama
    page_size = 30
    total_pages = max(1, len(display_df) // page_size + (1 if len(display_df) % page_size > 0 else 0))
    
    if total_pages > 1:
        page_num = st.number_input("Sayfa", min_value=1, max_value=total_pages, value=1, step=1)
        start_idx = (page_num - 1) * page_size
        end_idx = min(page_num * page_size, len(display_df))
        
        st.caption(f"Gösterilen: {start_idx + 1}-{end_idx} / {len(display_df)} kayıt")
        page_df = display_df.iloc[start_idx:end_idx]
    else:
        page_df = display_df
    
    # Tabloyu göster
    st.dataframe(
        page_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Excel İndirme Butonu
    st.divider()
    if not filtered.empty:
        from app.modules.reports import download_styled_excel
        
        filename = f"un_analiz_kayitlari_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        download_styled_excel(display_df, filename, "Un Analiz Raporu")

def show_un_maliyet_hesaplama():
    """Un Maliyet Hesaplama modülü"""
    
    st.header("🧮 Un Maliyet Hesaplama")
    
    # Session State'i başlat
    if 'un_maliyet_hesaplama_verileri' not in st.session_state: 
        st.session_state.un_maliyet_hesaplama_verileri = None
    if 'hesaplama_yapildi' not in st.session_state:
        st.session_state.hesaplama_yapildi = False
    
    # Para birimi
    currency = st.selectbox("Para Birimi", ["TL"], index=0)
    
    # AY/YIL FİLTRELEME
    col_filter1, col_filter2 = st.columns(2)    
    with col_filter1:
        ay_listesi = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", 
                     "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
        secilen_ay = st.selectbox("Hesaplama Ayı", ay_listesi, index=datetime.now().month - 1)
    
    with col_filter2:
        yil_listesi = list(range(2026, 2037)) # 2026-2036
        secilen_yil = st.selectbox("Hesaplama Yılı", yil_listesi, index=0)
    
    # HESAPLAMA KISMI
    st.subheader(f"Un Maliyeti Hesapla - {secilen_ay} {secilen_yil}")
    
    # Üç kolonlu layout (User Request)
    col1, col2, col3 = st.columns(3, gap="medium")
    
    # 1. KOLON: TEMEL BİLGİLER
    with col1:
        st.markdown("#### 📋 TEMEL BİLGİLER")
        
        un_cesidi = st.text_input(
            "Un Çeşidi *",
            value="Ekmeklik",
            placeholder="Örn: Ekmeklik, Pizza, Özel Karışım"
        )
        
        bugday_pacal_maliyeti = st.number_input(
            "Buğday Paçal Maliyeti (TL/KG) *",
            min_value=0.0,
            value=14.60,
            step=0.01,
            format="%.2f"
        )
        
        aylik_kirilan_bugday = st.number_input(
            "Aylık Kırılan Buğday (Ton) *",
            min_value=0.0,
            value=3000.0,
            step=0.1,
            format="%.1f"
        )
        
        un_randimani = st.number_input(
            "Un Randımanı (%) *",
            min_value=0.0,
            max_value=100.0,
            value=70.0,
            step=0.1,
            format="%.1f"
        )
        
        un_satis_fiyati = st.number_input(
            "Un Satış Fiyatı (50 KG) *",
            min_value=0.0,
            value=980.00,
            step=0.01,
            format="%.2f"
        )
        
        belge_geliri = st.number_input(
            "Belge Geliri (50 KG)",
            min_value=0.0,
            value=0.00,
            step=0.01,
            format="%.2f"
        )

    # 2. KOLON: YAN ÜRÜNLER & EK GELİRLER
    with col2:
        st.markdown("#### 📊 YAN ÜRÜN ORANLARI (%)")
        
        col_y1, col_y2 = st.columns(2)
        with col_y1:
            un2_orani = st.number_input("2. Un Oranı", min_value=0.0, value=7.0, step=0.1, format="%.1f")
            bongalite_orani = st.number_input("Bongalite", min_value=0.0, value=1.5, step=0.1, format="%.1f")
        with col_y2:
            kepek_orani = st.number_input("Kepek Oranı", min_value=0.0, value=9.0, step=0.1, format="%.1f")
            razmol_orani = st.number_input("Razmol Oranı", min_value=0.0, value=11.0, step=0.1, format="%.1f")
            
        st.markdown("#### 💰 YAN ÜRÜN FİYATLARI")
        
        col_fiyat1, col_fiyat2 = st.columns(2)
        with col_fiyat1:
            un2_fiyati = st.number_input("2. Un Fiyat", min_value=0.0, value=17.00, step=0.01, format="%.2f")
            bongalite_fiyati = st.number_input("Bongalite Fiyat", min_value=0.0, value=11.60, step=0.01, format="%.2f")
        with col_fiyat2:
            kepek_fiyati = st.number_input("Kepek Fiyat", min_value=0.0, value=8.90, step=0.01, format="%.2f")
            razmol_fiyati = st.number_input("Razmol Fiyat", min_value=0.0, value=9.10, step=0.01, format="%.2f")
            
        st.markdown("#### 🌾 EK GELİRLER")
        col_ek1, col_ek2 = st.columns(2)
        with col_ek1:
            kirik_tonaj = st.number_input("Satılan Kırık (Kg)", min_value=0.0, step=10.0)
            basak_tonaj = st.number_input("Satılan Başak (Kg)", min_value=0.0, step=10.0)
        with col_ek2:
            kirik_fiyat = st.number_input("Kırık Fiyat (TL)", min_value=0.0, step=0.01)
            basak_fiyat = st.number_input("Başak Fiyat (TL)", min_value=0.0, step=0.01)

    # 3. KOLON: GİDERLER
    with col3:
        st.markdown("#### 🏢 AYLIK SABİT GİDERLER")
        
        personel_maasi = st.number_input("Personel Maaşı", min_value=0.0, value=1200000.00, step=1000.0, format="%.2f")
        bakim_maliyeti = st.number_input("Bakım Maliyeti", min_value=0.0, value=100000.00, step=1000.0, format="%.2f")
        mutfak_gideri = st.number_input("Mutfak (Kantin)", min_value=0.0, value=50000.00, step=1000.0, format="%.2f")
        finans_gideri = st.number_input("Finans (Banka)", min_value=0.0, value=0.00, step=1000.0, format="%.2f")
        diger_giderler = st.number_input("Diğer Giderler", min_value=0.0, value=0.00, step=1000.0, format="%.2f")
        
        st.markdown("#### ⚡ ELEKTRİK")
        ton_bugday_elektrik = st.number_input("1 Ton Buğday Elektrik (TL)", min_value=0.0, value=500.00, step=0.01)
        elektrik_gideri_aylik = ton_bugday_elektrik * aylik_kirilan_bugday
        st.caption(f"Aylık Elektrik: {elektrik_gideri_aylik:,.0f} {currency}")
        
        st.markdown("#### 🛒 ÇUVAL BAŞI GİDERLER")
        col_cg1, col_cg2 = st.columns(2)
        with col_cg1:
            nakliye = st.number_input("Nakliye", min_value=0.0, value=20.00, step=0.5)
            satis_pazarlama = st.number_input("Pazarlama", min_value=0.0, value=20.50, step=0.5)
        with col_cg2:
            pp_cuval = st.number_input("PP Çuval", min_value=0.0, value=15.00, step=0.5)
            katki_maliyeti = st.number_input("Enzim/Katkı", min_value=0.0, value=9.00, step=0.5)

    
    # HESAPLA butonu
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("🧮 HESAPLAMAYI YAP", type="primary", use_container_width=True, key="hesapla_btn"):
            # Validasyon
            if not un_cesidi.strip():
                st.error("❌ Un çeşidi zorunludur!")
                return
            
            # HESAPLAMALAR
            try:
                # 1. Un tonajı
                un_tonaj = aylik_kirilan_bugday * (un_randimani / 100)
                
                # 2. Çuval sayısı
                cuval_sayisi = (un_tonaj * 1000) / 50
                
                # 3. GELİRLER
                un_geliri = cuval_sayisi * un_satis_fiyati
                un2_geliri = (aylik_kirilan_bugday * (un2_orani / 100) * 1000) * un2_fiyati
                bongalite_geliri = (aylik_kirilan_bugday * (bongalite_orani / 100) * 1000) * bongalite_fiyati
                kepek_geliri = (aylik_kirilan_bugday * (kepek_orani / 100) * 1000) * kepek_fiyati
                razmol_geliri = (aylik_kirilan_bugday * (razmol_orani / 100) * 1000) * razmol_fiyati
                belge_geliri_toplam = belge_geliri * cuval_sayisi
                
                # EK GELİRLER
                kirik_geliri = kirik_tonaj * kirik_fiyat
                basak_geliri = basak_tonaj * basak_fiyat
                
                toplam_gelir = un_geliri + un2_geliri + bongalite_geliri + kepek_geliri + razmol_geliri + belge_geliri_toplam + kirik_geliri + basak_geliri
                
                # 4. GİDERLER
                bugday_maliyeti_toplam = bugday_pacal_maliyeti * aylik_kirilan_bugday * 1000
                
                nakliye_toplam = nakliye * cuval_sayisi
                satis_pazarlama_toplam = satis_pazarlama * cuval_sayisi
                pp_cuval_toplam = pp_cuval * cuval_sayisi
                katki_toplam = katki_maliyeti * cuval_sayisi
                
                firma_giderleri_toplam = (
                    elektrik_gideri_aylik + personel_maasi + bakim_maliyeti + 
                    mutfak_gideri + finans_gideri + diger_giderler + nakliye_toplam + 
                    satis_pazarlama_toplam + pp_cuval_toplam + katki_toplam
                )
                
                toplam_gider = bugday_maliyeti_toplam + firma_giderleri_toplam
                
                # 5. NET KAR
                net_kar_toplam = toplam_gelir - toplam_gider
                net_kar_50kg = net_kar_toplam / cuval_sayisi if cuval_sayisi > 0 else 0
                fabrika_cikis_maliyet = un_satis_fiyati - net_kar_50kg
                
                # Sonuçları Session State'te sakla
                st.session_state.hesaplama_yapildi = True
                
                # Verileri hazırla
                hesaplama_verileri = {
                    'ay': secilen_ay,
                    'yil': secilen_yil,
                    'un_cesidi': un_cesidi,
                    'bugday_pacal_maliyeti': bugday_pacal_maliyeti,
                    'aylik_kirilan_bugday': aylik_kirilan_bugday,
                    'un_randimani': un_randimani,
                    'un_satis_fiyati': un_satis_fiyati,
                    'un2_orani': un2_orani,
                    'bongalite_orani': bongalite_orani,
                    'kepek_orani': kepek_orani,
                    'razmol_orani': razmol_orani,
                    'belge_geliri': belge_geliri,
                    'un2_fiyati': un2_fiyati,
                    'bongalite_fiyati': bongalite_fiyati,
                    'kepek_fiyati': kepek_fiyati,
                    'razmol_fiyati': razmol_fiyati,
                    'ton_bugday_elektrik': ton_bugday_elektrik,
                    'elektrik_gideri': elektrik_gideri_aylik,
                    'personel_maasi': personel_maasi,
                    'bakim_maliyeti': bakim_maliyeti,
                    'mutfak_gideri': mutfak_gideri,
                    'finans_gideri': finans_gideri,
                    'diger_giderler': diger_giderler,
                    'nakliye': nakliye,
                    'kirik_tonaj': kirik_tonaj, 'kirik_fiyat': kirik_fiyat,
                    'basak_tonaj': basak_tonaj, 'basak_fiyat': basak_fiyat,
                    'nakliye': nakliye,
                    'satis_pazarlama': satis_pazarlama,
                    'pp_cuval': pp_cuval,
                    'katki_maliyeti': katki_maliyeti,
                    'net_kar_kg': net_kar_50kg / 50, # kg başına kar
                    'net_kar_50kg': net_kar_50kg,
                    'fabrika_cikis_maliyet': fabrika_cikis_maliyet,
                    'net_kar_toplam': net_kar_toplam,
                    'un_tonaj': un_tonaj,
                    'toplam_gelir': toplam_gelir,
                    'toplam_gider': toplam_gider
                }
                
                st.session_state.un_maliyet_hesaplama_verileri = hesaplama_verileri
                
                # Veritabanına kaydet
                kullanici = st.session_state.get('username', 'Bilinmeyen')
                saved, msg = save_un_maliyet_hesaplama(hesaplama_verileri, kullanici)
                
                if saved:
                    st.success(f"✅ Hesaplama kaydedildi ve tamamlandı! - {secilen_ay} {secilen_yil}")
                else:
                    st.warning(f"⚠️ Hesaplama yapıldı ANCAK kayıt edilemedi! \n\nHata Detayı: {msg}")
                     # Kayıt edilmediği için rerun yapma, kullanıcının hatayı görmesini sağla
                    
                time.sleep(1)
                st.rerun()  # Sayfayı yeniden yükle
                
            except Exception as e:
                st.error(f"❌ Hesaplama hatası: {str(e)}")
    
    # Hesaplama yapıldıysa sonuçları göster
    if st.session_state.hesaplama_yapildi and st.session_state.un_maliyet_hesaplama_verileri:
        veriler = st.session_state.un_maliyet_hesaplama_verileri
        
        st.divider()
        st.subheader("📊 HESAPLAMA SONUÇLARI")
        
        # 3 METRİK ORTAYA HİZALANMIŞ ŞEKİLDE
        col_r1, col_r2, col_r3 = st.columns(3)
        
        with col_r1:
            st.metric("💰 Net Kar (50 KG Çuval)", 
                     f"{veriler['net_kar_50kg']:,.2f} {currency}")
        
        with col_r2:
            st.metric("🏭 Fabrika Çıkış Maliyeti", 
                     f"{veriler['fabrika_cikis_maliyet']:,.2f} {currency}")
        
        with col_r3:
            st.metric("💵 Net Kar (Toplam)", 
                     f"{veriler['net_kar_toplam']:,.2f} {currency}")
        
        # PDF OLUŞTURMA BUTONU
        st.divider()
        col_pdf1, col_pdf2, col_pdf3 = st.columns([1, 2, 1])
        with col_pdf2:
            # PDF butonuna tıklanıp tıklanmadığını kontrol et
            if st.button("📄 PDF RAPOR OLUŞTUR", type="secondary", use_container_width=True, key="pdf_btn"):
                with st.spinner("PDF raporu oluşturuluyor..."):
                    pdf_bytes = create_un_maliyet_pdf_report(veriler)
                    
                    if pdf_bytes:
                        # PDF'yi indirme butonu - bu sefer gösterilecek
                        st.session_state.pdf_bytes = pdf_bytes
                        st.session_state.pdf_dosya_adi = f"UN_MALIYET_{veriler['ay']}_{veriler['yil']}_{veriler['un_cesidi'].replace(' ', '_')}.pdf"
                        st.rerun()
                    else:
                        st.error("PDF oluşturulamadı!")
        
        # PDF indirme butonu (session state'ten geldiyse göster)
        if st.session_state.get('pdf_bytes') is not None and st.session_state.get('pdf_dosya_adi'):
            st.divider()
            col_indir1, col_indir2, col_indir3 = st.columns([1, 2, 1])
            with col_indir2:
                st.download_button(
                    label="📥 PDF'yi İndir",
                    data=st.session_state.pdf_bytes,
                    file_name=st.session_state.pdf_dosya_adi,
                    mime="application/pdf",
                    use_container_width=True,
                    key="indir_btn"
                )
                
                # Temizle butonu
                if st.button("🗑️ PDF'i Temizle", type="secondary", use_container_width=True, key="temizle_btn"):
                    if 'pdf_bytes' in st.session_state:
                        del st.session_state.pdf_bytes
                    if 'pdf_dosya_adi' in st.session_state:
                        del st.session_state.pdf_dosya_adi
                    st.rerun()



def show_un_maliyet_gecmisi():
    """Un Maliyet Geçmişi Modülü (Gelişmiş)"""
    st.header("📉 Un Maliyet Geçmişi")
    
    df = get_un_maliyet_gecmisi()
    
    if df.empty:
        st.info("Henüz maliyet kaydı bulunmamaktadır.")
        return
        
    # Eksik kolonları hesapla (Geriye dönük uyumluluk)
    if 'net_kar_50kg' not in df.columns and 'net_kar_kg' in df.columns:
        df['net_kar_50kg'] = df['net_kar_kg'] * 50
        
    # --- FİLTRELER ---
    with st.expander("🔍 Filtreleme Seçenekleri", expanded=False):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # Benzersiz Yılları Al
            if 'yil' in df.columns:
                years = sorted(df['yil'].dropna().unique().astype(int), reverse=True)
                selected_year = st.selectbox("Yıl Seçin", ["Tümü"] + [str(y) for y in years])
            else:
                selected_year = "Tümü"
                
        with col_f2:
             # Benzersiz Ayları Al
            if 'ay' in df.columns:
                months = df['ay'].dropna().unique().tolist()
                # Sort order for months could be implemented if needed
                selected_month = st.selectbox("Ay Seçin", ["Tümü"] + months)
            else:
                selected_month = "Tümü"
                
    # Filtreleme Mantığı
    filtered_df = df.copy()
    if selected_year != "Tümü":
        filtered_df = filtered_df[filtered_df['yil'] == int(selected_year)]
    if selected_month != "Tümü":
        filtered_df = filtered_df[filtered_df['ay'] == selected_month]
        
    # --- TABLO ---
    st.markdown(f"**Gösterilen Kayıt Sayısı:** {len(filtered_df)}")
    
    # İstenen Sütunlar (User Request: Sadece Tarih, Dönem, Un Çeşidi)
    # Detaylar zaten tıklayınca açılıyor.
    cols_to_show = ["tarih", "ay", "yil", "un_cesidi"]
    valid_cols = [c for c in cols_to_show if c in filtered_df.columns]
    
    display_df = filtered_df[valid_cols].copy()
    
    event = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "tarih": st.column_config.DatetimeColumn("İşlem Tarihi", format="D/M/Y H:m"),
            "ay": "Dönem Ay",
            "yil": st.column_config.NumberColumn("Dönem Yıl", format="%d"),
            "un_cesidi": "Un Çeşidi"
        },
        selection_mode="single-row",
        on_select="rerun"
    )
    
    # --- DETAY GÖRÜNÜMÜ & SİLME ---
    if len(event.selection['rows']) > 0:
        selected_index = event.selection['rows'][0]
        selected_row = filtered_df.iloc[selected_index]
        
        st.divider()
        # TL Format Helper (150,000.00 -> 150.000,00)
        def tr_fmt(val):
            try:
                if pd.isna(val): return "0,00"
                return f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except:
                return str(val)

        col_d1, col_d2 = st.columns([3, 1])
        
        with col_d1:
            # 1. Başlık Kartı
            st.markdown(f"### 🗓️ {selected_row['ay']} {selected_row['yil']} - {selected_row['un_cesidi']}")
            
            m4, m5, m6 = st.columns(3)
            m4.metric("Fabrika Çıkış (50kg)", f"{tr_fmt(selected_row.get('fabrika_cikis_maliyet', 0))} TL")
            m5.metric("Un Satış Fiyatı", f"{tr_fmt(selected_row.get('un_satis_fiyati', 0))} TL")
            m6.metric("Net Kar (50kg Çuval)", f"{tr_fmt(selected_row.get('net_kar_50kg', 0))} TL")
            
            st.caption(f"Kayıt Tarihi: {selected_row['tarih']} | Kaydeden: {selected_row['kullanici']}")
            
            st.divider()
            
            # 3. İki Kolonlu Detay
            dc1, dc2 = st.columns(2)
            
            with dc1:
                with st.container(border=True):
                    st.markdown("**📉 Gider Kalemleri (Aylık)**")
                    st.write(f"- ⚡ Elektrik: **{tr_fmt(selected_row['elektrik_gideri'])} TL**")
                    st.write(f"- 👥 Personel: **{tr_fmt(selected_row['personel_maasi'])} TL**")
                    st.write(f"- 🛠️ Bakım: **{tr_fmt(selected_row['bakim_maliyeti'])} TL**")
                    st.write(f"- 🚛 Nakliye (Çuval): **{selected_row['nakliye']} TL**")
                    st.write(f"- 🛍️ Çuval Maliyeti: **{selected_row['pp_cuval']} TL**")

            with dc2:
                with st.container(border=True):
                    st.markdown("**📈 Gelir & Üretim**")
                    st.write(f"- 🌾 Kırılan Buğday: **{tr_fmt(selected_row['aylik_kirilan_bugday'])} Ton**")
                    st.write(f"- 🏭 Un Randımanı: **%{selected_row['un_randimani']}**")
                    st.write(f"- 💰 Un Satış Fiyatı: **{tr_fmt(selected_row['un_satis_fiyati'])} TL**")
                    if selected_row.get('belge_geliri'):
                         st.write(f"- 📄 Belge Geliri: **{tr_fmt(selected_row['belge_geliri'])} TL**")
            
        with col_d2:
            st.warning("⚠️ Bu İşlemler Geri Alınamaz")
            if st.button("🗑️ Kaydı Sil", type="primary", use_container_width=True):
                try:
                    with get_db_connection() as conn:
                        c = conn.cursor()
                        c.execute("DELETE FROM un_maliyet_hesaplamalari WHERE id = ?", (int(selected_row['id']),))
                        conn.commit()
                    st.success("Kayıt silindi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Silme hatası: {e}")
