import streamlit as st
import pandas as pd
from datetime import datetime
import time

# --- DATABASE IMPORTLARI (GÜNCELLENDİ) ---
from app.core.database import fetch_data, add_data
# Excel işlemleri için gerekli kütüphaneler
try:
    import xlsxwriter
except ImportError:
    pass # Hata vermesin, aşağıda try-except ile yönetiliyor

def save_uretim_kaydi(uretim_tarihi, uretim_hatti, uretim_adi, vardiya, sorumlu, **uretim_degerleri):
    """Üretim kaydını Google Sheets'e kaydet"""
    # Validasyonlar
    if not uretim_hatti or not vardiya:
        return False, "Üretim Hattı ve Vardiya zorunludur!"
        
    try:
        # Tarih formatlama
        tarih_str = uretim_tarihi.strftime('%Y-%m-%d %H:%M:%S')
        
        # Veri Paketi Oluşturma
        db_data = {
            'tarih': tarih_str,
            'uretim_hatti': uretim_hatti,
            'degirmen_uretim_adi': uretim_adi,
            'vardiya': vardiya,
            'sorumlu': sorumlu,
            # Hammadde
            'kirilan_bugday': float(uretim_degerleri.get('kirilan_bugday', 0)),
            'nem_orani': float(uretim_degerleri.get('nem_orani', 0)), # B1 Rutubet
            'tav_suresi': float(uretim_degerleri.get('tav_suresi', 0)),
            # Çıktılar
            'un_1': float(uretim_degerleri.get('un_1', 0)),
            'un_2': float(uretim_degerleri.get('un_2', 0)),
            'razmol': float(uretim_degerleri.get('razmol', 0)),
            'kepek': float(uretim_degerleri.get('kepek', 0)),
            'bongalite': float(uretim_degerleri.get('bongalite', 0)),
            'kirik_bugday': float(uretim_degerleri.get('kirik_bugday', 0)),
            # Randımanlar
            'randiman_1': float(uretim_degerleri.get('randiman_1', 0)),
            'toplam_randiman': float(uretim_degerleri.get('toplam_randiman', 0)),
            'kayip': float(uretim_degerleri.get('kayip', 0)),
            # Parti No (Otomatik)
            'parti_no': uretim_adi if uretim_adi else f"PRD-{datetime.now().strftime('%Y%m%d%H%M')}"
        }
        
        # Google Sheets'e Kaydet
        if add_data("uretim_kaydi", db_data):
            return True, "Üretim kaydı başarıyla eklendi!"
        else:
            return False, "Kayıt sırasında bir hata oluştu."
            
    except Exception as e:
        return False, f"Sistem hatası: {str(e)}"

def get_uretim_kayitlari():
    """Üretim kayıtlarını getir"""
    try:
        # Google Sheets'ten veriyi çek
        df = fetch_data("uretim_kaydi")
        
        if df.empty:
            return pd.DataFrame()
            
        # Tarihe göre sırala (Yeniden eskiye)
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'])
            df = df.sort_values('tarih', ascending=False)
            
        return df.head(100) # Son 100 kayıt
    except Exception as e:
        st.error(f"Kayıtlar yüklenemedi: {e}")
        return pd.DataFrame()

def show_uretim_kaydi():
    """Üretim Kaydı Modülü - Yenilenmiş Tasarım"""
    
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
        
    st.header("🏭 Değirmen Üretim Kaydı")
    
    # 3 KOLONLU YAPI
    col1, col2, col3 = st.columns([1, 1, 1], gap="medium")
    
    with col1:
        st.subheader("📋 Üretim Bilgileri")
        uretim_tarihi = st.date_input("Üretim Tarihi *", value=datetime.now())
        
        # Üretim Hattı
        uretim_hatti = st.text_input("Üretim Hattı *", placeholder="Hat 1, Hat 2...")
        
        uretim_adi = st.text_input("Üretim Adı", placeholder="Özel üretim ismi...")
        
        # Vardiya
        vardiya = st.text_input("Vardiya *", placeholder="08:00 - 16:00")
        
        sorumlu = st.text_input("Vardiya Sorumlusu")
        
    with col2:
        st.subheader("🌾 Hammadde Girişi")
        kirilan_bugday = st.number_input("Kırılan Buğday (Kg)", min_value=0.0, step=100.0, format="%.0f")
        b1_rutubet = st.number_input("B1 Buğday Rutubeti (%)", min_value=0.0, max_value=20.0, step=0.1)
        tav_suresi = st.number_input("Tav Süresi (Saat)", min_value=0.0, step=0.5)
        
    with col3:
        st.subheader("📦 Üretim Çıktıları (KG)")
        un_1 = st.number_input("UN (1) (KG)", min_value=0.0, step=50.0)
        un_2 = st.number_input("UN (2) (KG)", min_value=0.0, step=50.0)
        razmol = st.number_input("RAZMOL (KG)", min_value=0.0, step=50.0)
        kepek = st.number_input("KEPEK (KG)", min_value=0.0, step=50.0)
        bongalite = st.number_input("BONGALİTE (KG)", min_value=0.0, step=50.0)
        kirik = st.number_input("KIRIK (KG)", min_value=0.0, step=50.0)

    st.divider()
    
    # --- OTOMATİK HESAPLAMALAR ---
    st.subheader("📊 Randıman Hesaplamaları")
    
    # Hesaplama Mantığı
    if kirilan_bugday > 0:
        rand_un1 = (un_1 / kirilan_bugday) * 100
        rand_un2 = (un_2 / kirilan_bugday) * 100
        rand_kepek = (kepek / kirilan_bugday) * 100
        rand_razmol = (razmol / kirilan_bugday) * 100
        rand_bongalite = (bongalite / kirilan_bugday) * 100
        rand_toplam_un = rand_un1 + rand_un2
        
        toplam_cikan_kg = un_1 + un_2 + kepek + razmol + bongalite + kirik
        kayip_kg = kirilan_bugday - toplam_cikan_kg
        kayip_yuzde = (kayip_kg / kirilan_bugday) * 100
    else:
        rand_un1 = rand_un2 = rand_kepek = rand_razmol = rand_bongalite = rand_toplam_un = kayip_yuzde = 0.0
        
    # Gösterim (Metrics - 4 Kolon)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Un 1 Randıman", f"%{rand_un1:.2f}")
    m1.metric("Un 2 Randıman", f"%{rand_un2:.2f}")
    m2.metric("Kepek Randıman", f"%{rand_kepek:.2f}")
    m2.metric("Razmol Randıman", f"%{rand_razmol:.2f}")
    m3.metric("Bongalite Randoman", f"%{rand_bongalite:.2f}")
    m3.metric("Toplam Un (1+2)", f"%{rand_toplam_un:.2f}")
    m4.metric("Toplam Kayıp", f"%{kayip_yuzde:.2f}", delta_color="inverse")
    
    st.divider()
    
    # KAYDET
    if st.button("✅ ÜRETİM KAYDINI KAYDET", type="primary"):
        if not uretim_hatti or not vardiya:
            st.error("⚠️ Üretim Hattı ve Vardiya alanları zorunludur!")
            return
            
        uretim_verileri = {
            'kirilan_bugday': kirilan_bugday,
            'nem_orani': b1_rutubet,
            'tav_suresi': tav_suresi,
            'un_1': un_1,
            'un_2': un_2,
            'razmol': razmol,
            'kepek': kepek,
            'bongalite': bongalite,
            'kirik_bugday': kirik,
            'randiman_1': rand_un1,
            'toplam_randiman': rand_toplam_un,
            'kayip': kayip_yuzde
        }
        
        # uretim_silosu parametresi kaldırıldı (zaten yukarıdaki inputlarda yoktu)
        success, msg = save_uretim_kaydi(uretim_tarihi, uretim_hatti, uretim_adi, vardiya, sorumlu, **uretim_verileri)
        
        if success:
            st.success("✅ Üretim Kaydı Başarıyla Sisteme İşlendi!")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"❌ {msg}")

def show_uretim_arsivi():
    """Üretim Geçmişi / Arşivi Modülü"""
    st.header("🗄️ Üretim Arşivi")
    
    # Kayıtları getir
    df = get_uretim_kayitlari()
    
    if df.empty:
        st.info("📭 Henüz üretim kaydı bulunmamaktadır.")
        return
        
    # Filtreleme
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        vardiya_list = df['vardiya'].unique().tolist() if 'vardiya' in df.columns else []
        vardiya_filter = st.multiselect("Vardiya Filtrele", vardiya_list)
    
    filtered_df = df.copy()
    if vardiya_filter:
        filtered_df = filtered_df[filtered_df['vardiya'].isin(vardiya_filter)]
        
    # Tabloyu göster
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "tarih": st.column_config.DatetimeColumn("Tarih", format="D/M/Y H:m"),
            "parti_no": "Parti No",
            "kirilan_bugday": st.column_config.NumberColumn("Kırılan Buğday (Kg)", format="%.0f"),
            "toplam_randiman": st.column_config.NumberColumn("Toplam Randıman (%)", format="%.2f"),
            "kayip": st.column_config.NumberColumn("Kayıp (%)", format="%.2f")
        }
    )
    
    # Excel İndir
    st.divider()
    
    def create_excel_report(df):
        try:
            import io
            import xlsxwriter
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet()
            
            # Header format
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#D7E4BC',
                'border': 1
            })
            
            # Tarih formatı (Excel için)
            # String gelen tarihi datetime objesine çevirip yazmak daha iyi olabilir
            # Ancak basitlik için string bırakıyoruz.
            
            # Write headers
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Write data
            for row_num, row_data in enumerate(df.values):
                for col_num, value in enumerate(row_data):
                    # NaN kontrolü
                    if pd.isna(value):
                        value = ""
                    worksheet.write(row_num + 1, col_num, value)
                    
            workbook.close()
            output.seek(0)
            return output
        except Exception as e:
            st.error(f"Excel oluşturma hatası: {e}")
            return None

    col_exp_btn1, col_exp_btn2 = st.columns([4, 1])
    with col_exp_btn2:
        if st.button("📊 Excel Hazırla"):
            excel_data = create_excel_report(filtered_df)
            if excel_data:
                st.download_button(
                    label="📥 İndir",
                    data=excel_data,
                    file_name=f"uretim_arsivi_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
