import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import json
import time

# --- DATABASE IMPORTLARI ---
from app.core.database import fetch_data, add_data, get_conn

# Plotly ve PDF Kontrolü
try:
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError:
    px = None
    go = None

PDF_AVAILABLE = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    PDF_AVAILABLE = True
except ImportError:
    pass

# ==============================================================================
# BÖLÜM 3: ENZİM VE KATKI MODÜLLERİ (DÜZELTİLMİŞ)
# ==============================================================================

def show_katki_maliyeti_modulu():
    """Katkı ve Enzim Maliyeti Modülü - HATA DÜZELTİLDİ"""
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h1 style="color: #0B4F6C; margin-bottom: 10px;">🧪 Katkı ve Enzim Maliyeti Hesaplama</h1>
    </div>
    """, unsafe_allow_html=True)
    
    df_kurlar = fetch_data("katki_kurlar")
    df_enzimler = fetch_data("katki_enzimler")
    df_urunler = fetch_data("katki_urunler")
    df_recete = fetch_data("katki_recete")
    
    new_usd = 43.28
    new_eur = 50.08
    
    if not df_kurlar.empty:
        new_usd = float(df_kurlar.iloc[0]['usd_tl'])
        new_eur = float(df_kurlar.iloc[0]['eur_tl'])
    else:
        add_data("katki_kurlar", {"id": 1, "usd_tl": new_usd, "eur_tl": new_eur})

    st.markdown("### 📋 Kontrol Paneli")
    col1, col2, col3 = st.columns([1, 1, 1], gap="large")
    
    with col1:
        with st.container(border=True, height=260):
            st.markdown("#### 💱 Döviz Kurları")
            input_usd = st.number_input("**1 USD**", value=new_usd, format="%.2f", step=0.01, key="katki_usd")
            input_eur = st.number_input("**1 EUR**", value=new_eur, format="%.2f", step=0.01, key="katki_eur")
            
            if st.button("💾 Kurları Güncelle", use_container_width=True, key="katki_kur_save", type="primary"):
                try:
                    conn = get_conn()
                    if df_kurlar.empty:
                        add_data("katki_kurlar", {"id": 1, "usd_tl": input_usd, "eur_tl": input_eur})
                    else:
                        df_kurlar.at[0, 'usd_tl'] = input_usd
                        df_kurlar.at[0, 'eur_tl'] = input_eur
                        conn.update(worksheet="katki_kurlar", data=df_kurlar)
                    st.success("✅ Kurlar güncellendi!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Güncelleme hatası: {str(e)}")
    
    with col2:
        with st.container(border=True, height=260):
            st.markdown("#### ⚙️ Yeni Katkı/Enzim")
            e_ad = st.text_input("**Katkı/Enzim Adı**", key="yeni_enzim_ad").strip().upper()
            e_birim = st.selectbox("**Para Birimi**", ["EUR", "USD", "TL"], key="yeni_enzim_birim")
            e_fiyat = st.number_input("**1 kg Fiyatı**", min_value=0.0, step=0.01, format="%.3f", key="yeni_enzim_fiyat")
            
            if st.button("💾 Katkıyı Kaydet", key="katki_ekle", use_container_width=True, type="secondary"):
                if e_ad:
                    try:
                        new_id = 1
                        if not df_enzimler.empty and 'id' in df_enzimler.columns:
                            new_id = df_enzimler['id'].max() + 1
                        add_data("katki_enzimler", {"id": int(new_id), "ad": e_ad, "fiyat": e_fiyat, "para_birimi": e_birim})
                        st.success(f"✅ '{e_ad}' kaydedildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")
    
    with col3:
        with st.container(border=True, height=260):
            st.markdown("#### 🥖 Yeni Ürün")
            u_ad = st.text_input("**Ürün Adı**", key="yeni_urun_ad").strip().upper()
            
            if st.button("💾 Ürünü Kaydet", key="urun_ekle", use_container_width=True, type="secondary"):
                if u_ad:
                    try:
                        new_id = 1
                        if not df_urunler.empty and 'id' in df_urunler.columns:
                            new_id = df_urunler['id'].max() + 1
                        add_data("katki_urunler", {"id": int(new_id), "ad": u_ad})
                        st.success(f"✅ '{u_ad}' kaydedildi!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Hata: {str(e)}")

    st.divider()
    st.markdown("### 📊 Reçete ve Fiyat Tablosu")
    
    if not df_enzimler.empty:
        table_data = df_enzimler[['id', 'ad', 'fiyat', 'para_birimi']].copy()
        table_data.columns = ['id', 'ENZİM İSMİ', 'FİYAT', 'BİRİM']
        
        if not df_urunler.empty:
            for _, u_row in df_urunler.iterrows():
                u_id = u_row['id']
                u_name = u_row['ad']
                col_values = []
                for _, e_row in table_data.iterrows():
                    e_id = e_row['id']
                    gramaj = 0.0
                    if not df_recete.empty:
                        match = df_recete[(df_recete['urun_id'] == u_id) & (df_recete['enzim_id'] == e_id)]
                        if not match.empty:
                            gramaj = float(match.iloc[0]['gramaj'])
                    col_values.append(gramaj)
                table_data[u_name] = col_values

        column_config = {
            "id": None,
            "ENZİM İSMİ": st.column_config.TextColumn("ENZİM", width="small", required=True),
            "FİYAT": st.column_config.NumberColumn("FİYAT", width="small", format="%.3f", required=True),
            "BİRİM": st.column_config.SelectboxColumn("BİRİM", width="small", options=["EUR", "USD", "TL"], required=True),
        }
        
        if not df_urunler.empty:
            for u_name in df_urunler['ad'].values:
                column_config[u_name] = st.column_config.NumberColumn(u_name, width="small", format="%.3f", min_value=0.0)
        
        edited_df = st.data_editor(table_data, use_container_width=True, hide_index=True, column_config=column_config, num_rows="fixed", key="recete_editor")
        
        if st.button("🔄 DEĞİŞİKLİKLERİ KAYDET", use_container_width=True, type="primary", key="katki_kaydet"):
            try:
                conn = get_conn()
                
                # ===== 1. ENZİMLERİ GÜNCELLE =====
                updated_enzimler = df_enzimler.copy()
                for idx, row in edited_df.iterrows():
                    e_id = row['id']
                    mask = updated_enzimler['id'] == e_id
                    if mask.any():
                        updated_enzimler.loc[mask, 'ad'] = row['ENZİM İSMİ']
                        updated_enzimler.loc[mask, 'fiyat'] = row['FİYAT']
                        updated_enzimler.loc[mask, 'para_birimi'] = row['BİRİM']
                conn.update(worksheet="katki_enzimler", data=updated_enzimler)
                
                # ===== 2. REÇETE TABLOSUNU GÜNCELLE (HATA DÜZELTİLDİ) =====
                
                # Eğer katki_recete tablosu boşsa veya kolonları yoksa, baştan oluştur
                if df_recete.empty or 'urun_id' not in df_recete.columns:
                    st.warning("⚠️ katki_recete tablosu boş veya hatalı. Yeni kayıtlar oluşturuluyor...")
                    updated_recete = pd.DataFrame(columns=['urun_id', 'enzim_id', 'gramaj'])
                else:
                    updated_recete = df_recete.copy()
                
                new_records = []
                
                if not df_urunler.empty:
                    for idx, row in edited_df.iterrows():
                        e_id = int(row['id'])
                        for _, u_row in df_urunler.iterrows():
                            u_id = int(u_row['id'])
                            u_name = u_row['ad']
                            gramaj = float(row[u_name])
                            
                            # Mevcut kayıt var mı kontrol et
                            if not updated_recete.empty:
                                mask = (updated_recete['urun_id'] == u_id) & (updated_recete['enzim_id'] == e_id)
                                if mask.any():
                                    # Var olan kaydı güncelle
                                    updated_recete.loc[mask, 'gramaj'] = gramaj
                                else:
                                    # Yeni kayıt ekle (sadece gramaj > 0 ise)
                                    if gramaj > 0:
                                        new_records.append({
                                            'urun_id': u_id, 
                                            'enzim_id': e_id, 
                                            'gramaj': gramaj
                                        })
                            else:
                                # Tablo boş, direkt ekle
                                if gramaj > 0:
                                    new_records.append({
                                        'urun_id': u_id, 
                                        'enzim_id': e_id, 
                                        'gramaj': gramaj
                                    })
                
                # Yeni kayıtları tabloya ekle
                if new_records:
                    new_df = pd.DataFrame(new_records)
                    updated_recete = pd.concat([updated_recete, new_df], ignore_index=True)
                
                # Sıfır gramajlı kayıtları temizle (opsiyonel)
                if not updated_recete.empty:
                    updated_recete = updated_recete[updated_recete['gramaj'] > 0]
                
                # Google Sheets'e yaz
                conn.update(worksheet="katki_recete", data=updated_recete)
                
                st.success("✅ Değişiklikler kaydedildi!")
                time.sleep(1)
                st.rerun()
                
            except KeyError as ke:
                st.error(f"❌ Kolon hatası: '{ke}' - Lütfen Google Sheets'teki 'katki_recete' tablosuna 'urun_id', 'enzim_id', 'gramaj' kolonlarını ekleyin!")
            except Exception as ex:
                st.error(f"❌ Kayıt hatası: {ex}")
                st.write("**Hata Detayı:**")
                st.code(str(ex))
