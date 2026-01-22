import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time

from app.core.database import fetch_data, add_data

try:
    import xlsxwriter
except ImportError:
    pass

def save_uretim_kaydi(uretim_tarihi, uretim_hatti, uretim_adi, vardiya, sorumlu, **uretim_degerleri):
    """Üretim kaydını Google Sheets'e kaydet"""
    if not uretim_hatti or not vardiya:
        return False, "Üretim Hattı ve Vardiya zorunludur!"
        
    try:
        tarih_str = uretim_tarihi.strftime('%Y-%m-%d %H:%M:%S')
        
        db_data = {
            'tarih': tarih_str,
            'uretim_hatti': uretim_hatti,
            'degirmen_uretim_adi': uretim_adi,
            'vardiya': vardiya,
            'sorumlu': sorumlu,
            'kirilan_bugday': float(uretim_degerleri.get('kirilan_bugday', 0)),
            'nem_orani': float(uretim_degerleri.get('nem_orani', 0)),
            'tav_suresi': float(uretim_degerleri.get('tav_suresi', 0)),
            'un_1': float(uretim_degerleri.get('un_1', 0)),
            'un_2': float(uretim_degerleri.get('un_2', 0)),
            'razmol': float(uretim_degerleri.get('razmol', 0)),
            'kepek': float(uretim_degerleri.get('kepek', 0)),
            'bongalite': float(uretim_degerleri.get('bongalite', 0)),
            'kirik_bugday': float(uretim_degerleri.get('kirik_bugday', 0)),
            'randiman_1': float(uretim_degerleri.get('randiman_1', 0)),
            'toplam_randiman': float(uretim_degerleri.get('toplam_randiman', 0)),
            'kayip': float(uretim_degerleri.get('kayip', 0)),
            'parti_no': uretim_adi if uretim_adi else f"PRD-{datetime.now().strftime('%Y%m%d%H%M')}"
        }
        
        if add_data("uretim_kaydi", db_data):
            return True, "Üretim kaydı başarıyla eklendi!"
        else:
            return False, "Kayıt sırasında bir hata oluştu."
            
    except Exception as e:
        return False, f"Sistem hatası: {str(e)}"

def get_uretim_kayitlari():
    """Üretim kayıtlarını getir"""
    try:
        df = fetch_data("uretim_kaydi")
        
        if df.empty:
            return pd.DataFrame()
            
        if 'tarih' in df.columns:
            df['tarih'] = pd.to_datetime(df['tarih'])
            df = df.sort_values('tarih', ascending=False)
            
        return df
    except Exception as e:
        st.error(f"Kayıtlar yüklenemedi: {e}")
        return pd.DataFrame()

def show_uretim_kaydi():
    """Üretim Kaydı Modülü"""
    
    if st.session_state.get('user_role') not in ["admin", "operations"]:
        st.warning("⛔ Bu modüle erişim izniniz yok!")
        return
        
    st.header("🏭 Değirmen Üretim Kaydı")
    
    col1, col2, col3 = st.columns([1, 1, 1], gap="medium")
    
    with col1:
        st.subheader("📋 Üretim Bilgileri")
        uretim_tarihi = st.date_input("Üretim Tarihi *", value=datetime.now())
        uretim_hatti = st.text_input("Üretim Hattı *", placeholder="Yeni Degirmen, Eski Degirmen...")
        uretim_adi = st.text_input("Üretim Adı", placeholder="Ekmeklik, Pidelik...")
        vardiya = st.text_input("Vardiya *", placeholder="08:00 - 18:00")
        sorumlu = st.text_input("Vardiya Sorumlusu")
        
    with col2:
        st.subheader("🌾 Hammadde Girişi")
        kirilan_bugday = st.number_input("Kırılan Buğday (Kg)", min_value=49058.0, step=100.0, format="%.0f")
        b1_rutubet = st.number_input("B1 Buğday Rutubeti (%)", min_value=18,0 max_value=20.0, step=0.1)
        tav_suresi = st.number_input("Tav Süresi (Saat)", min_value=48.0, step=0.5)
        
    with col3:
        st.subheader("📦 Üretim Çıktıları (KG)")
        un_1 = st.number_input("UN (1) (KG)", min_value=0.0, step=50.0)
        un_2 = st.number_input("UN (2) (KG)", min_value=0.0, step=50.0)
        razmol = st.number_input("RAZMOL (KG)", min_value=0.0, step=50.0)
        kepek = st.number_input("KEPEK (KG)", min_value=0.0, step=50.0)
        bongalite = st.number_input("BONGALİTE (KG)", min_value=0.0, step=50.0)
        kirik = st.number_input("KIRIK (KG)", min_value=0.0, step=50.0)
    st.divider()
    
    st.subheader("📊 Randıman Hesaplamaları")
    
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
        
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Un 1 Randıman", f"%{rand_un1:.2f}")
    m1.metric("Un 2 Randıman", f"%{rand_un2:.2f}")
    m2.metric("Kepek Randıman", f"%{rand_kepek:.2f}")
    m2.metric("Razmol Randıman", f"%{rand_razmol:.2f}")
    m3.metric("Bongalite Randoman", f"%{rand_bongalite:.2f}")
    m3.metric("Toplam Un (1+2)", f"%{rand_toplam_un:.2f}")
    m4.metric("Toplam Kayıp", f"%{kayip_yuzde:.2f}", delta_color="inverse")
    
    st.divider()
    
    if st.button("✅ ÜRETİM KAYDINI KAYDET", type="primary"):
        # ===== VALİDASYON =====
        from app.core.config import validate_numeric_input
        
        # Zorunlu alan kontrolü
        if not uretim_hatti or not vardiya:
            st.error("⚠️ Üretim Hattı ve Vardiya alanları zorunludur!")
            return
        
        # Üretim değerleri için validasyon
        uretim_degerleri_kontrol = {
            'Kırılan Buğday': kirilan_bugday,
            'Un 1': un_1,
            'Un 2': un_2,
            'Razmol': razmol,
            'Kepek': kepek,
            'Bongalite': bongalite,
            'Kırık': kirik,
            'Tav Süresi': tav_suresi
        }
        
        validasyon_hatalari = []
        
        for alan_adi, deger in uretim_degerleri_kontrol.items():
            valid, msg, _ = validate_numeric_input(
                deger, 
                alan_adi.lower().replace(' ', '_'),
                allow_zero=True,  # Sıfır kabul edilebilir (üretilmemiş olabilir)
                allow_negative=False  # Negatif kabul edilmez
            )
            if not valid:
                validasyon_hatalari.append(f"{alan_adi}: {msg}")
        
        # Rutubet özel validasyonu (0-20 arası)
        if b1_rutubet < 0 or b1_rutubet > 20:
            validasyon_hatalari.append("B1 Buğday Rutubeti: %0-%20 arasında olmalıdır!")
        
        # Mantıksal kontrol: Çıkan toplam ürün, girilen buğdaydan fazla olamaz
        if kirilan_bugday > 0:
            toplam_cikan = un_1 + un_2 + razmol + kepek + bongalite + kirik
            if toplam_cikan > kirilan_bugday * 1.05:  # %5 tolerans
                validasyon_hatalari.append(
                    f"Toplam çıktı ({toplam_cikan:.0f} kg), "
                    f"giren buğdaydan ({kirilan_bugday:.0f} kg) fazla olamaz!"
                )
        
        # Hata varsa göster ve çık
        if validasyon_hatalari:
            st.error("🚫 Lütfen aşağıdaki hataları düzeltin:")
            for hata in validasyon_hatalari:
                st.write(f"- {hata}")
            return
        
        # ===== VALİDASYON BAŞARILI - KAYIT YAP =====
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
        
        success, msg = save_uretim_kaydi(uretim_tarihi, uretim_hatti, uretim_adi, vardiya, sorumlu, **uretim_verileri)
        
        if success:
            st.success("✅ Üretim Kaydı Başarıyla Sisteme İşlendi!")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error(f"❌ {msg}")

def show_yonetim_dashboard():
    """Yönetim Dashboard'u - Patron Görünümü"""
    st.header("📊 Yönetim Dashboard'u")
    st.caption("Üretim performansı, trendler ve karşılaştırmalar")
    
    df = get_uretim_kayitlari()
    
    if df.empty:
        st.info("📭 Henüz üretim kaydı bulunmamaktadır.")
        return
    
    col_period1, col_period2 = st.columns([1, 3])
    
    with col_period1:
        period = st.selectbox(
            "Dönem Seçin",
            ["Son 7 Gün", "Son 30 Gün", "Son 3 Ay", "Son 6 Ay", "Son 1 Yıl", "Tümü"],
            index=1
        )
    
    today = datetime.now().date()
    if period == "Son 7 Gün":
        start_date = today - timedelta(days=7)
    elif period == "Son 30 Gün":
        start_date = today - timedelta(days=30)
    elif period == "Son 3 Ay":
        start_date = today - timedelta(days=90)
    elif period == "Son 6 Ay":
        start_date = today - timedelta(days=180)
    elif period == "Son 1 Yıl":
        start_date = today - timedelta(days=365)
    else:
        start_date = None
    
    if start_date:
        df_filtered = df[df['tarih'].dt.date >= start_date].copy()
    else:
        df_filtered = df.copy()
    
    st.divider()
    
    st.subheader("📈 Performans Özeti")
    
    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    
    with col_m1:
        toplam_bugday = df_filtered['kirilan_bugday'].sum()
        st.metric("Toplam Buğday", f"{toplam_bugday/1000:,.1f} Ton")
    
    with col_m2:
        toplam_un = (df_filtered['un_1'].sum() + df_filtered['un_2'].sum())
        st.metric("Toplam Un", f"{toplam_un/1000:,.1f} Ton")
    
    with col_m3:
        ort_randiman = df_filtered['toplam_randiman'].mean()
        st.metric("Ort. Randıman", f"%{ort_randiman:.2f}")
    
    with col_m4:
        ort_kayip = df_filtered['kayip'].mean()
        st.metric("Ort. Kayıp", f"%{ort_kayip:.2f}", delta_color="inverse")
    
    with col_m5:
        uretim_sayisi = len(df_filtered)
        st.metric("Üretim Sayısı", f"{uretim_sayisi}")
    
    st.divider()
    
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        
        st.subheader("📉 Randıman Trend Analizi")
        
        df_trend = df_filtered.copy()
        df_trend['tarih_str'] = df_trend['tarih'].dt.strftime('%d.%m.%Y')
        
        fig_trend = go.Figure()
        
        fig_trend.add_trace(go.Scatter(
            x=df_trend['tarih_str'],
            y=df_trend['toplam_randiman'],
            mode='lines+markers',
            name='Toplam Randıman',
            line=dict(color='#1e3a8a', width=3),
            marker=dict(size=8)
        ))
        
        fig_trend.add_trace(go.Scatter(
            x=df_trend['tarih_str'],
            y=df_trend['kayip'],
            mode='lines+markers',
            name='Kayıp',
            line=dict(color='#dc2626', width=2, dash='dash'),
            marker=dict(size=6)
        ))
        
        hedef_randiman = 78.0
        fig_trend.add_hline(y=hedef_randiman, line_dash="dot", line_color="green", 
                           annotation_text=f"Hedef: %{hedef_randiman}")
        
        fig_trend.update_layout(
            title="Günlük Randıman ve Kayıp Trendi",
            xaxis_title="Tarih",
            yaxis_title="Yüzde (%)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig_trend, use_container_width=True)
        
        st.divider()
        
        st.subheader("👥 Vardiya Performans Karşılaştırması")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            vardiya_stats = df_filtered.groupby('vardiya').agg({
                'kirilan_bugday': 'sum',
                'toplam_randiman': 'mean',
                'kayip': 'mean'
            }).reset_index()
            
            vardiya_stats['kirilan_bugday'] = vardiya_stats['kirilan_bugday'] / 1000
            
            fig_vardiya = px.bar(
                vardiya_stats,
                x='vardiya',
                y='kirilan_bugday',
                title='Vardiyalara Göre Toplam Üretim (Ton)',
                labels={'kirilan_bugday': 'Toplam (Ton)', 'vardiya': 'Vardiya'},
                color='kirilan_bugday',
                color_continuous_scale='Blues'
            )
            
            fig_vardiya.update_layout(height=350, showlegend=False)
            st.plotly_chart(fig_vardiya, use_container_width=True)
        
        with col_g2:
            fig_vardiya_rand = go.Figure()
            
            fig_vardiya_rand.add_trace(go.Bar(
                x=vardiya_stats['vardiya'],
                y=vardiya_stats['toplam_randiman'],
                name='Ortalama Randıman',
                marker_color='#1e3a8a'
            ))
            
            fig_vardiya_rand.update_layout(
                title='Vardiyalara Göre Ortalama Randıman',
                xaxis_title='Vardiya',
                yaxis_title='Randıman (%)',
                height=350
            )
            
            st.plotly_chart(fig_vardiya_rand, use_container_width=True)
        
        st.divider()
        
        st.subheader("🏭 Üretim Hattı Performansı")
        
        hat_stats = df_filtered.groupby('uretim_hatti').agg({
            'kirilan_bugday': 'sum',
            'toplam_randiman': 'mean',
            'kayip': 'mean'
        }).reset_index()
        
        hat_stats['kirilan_bugday'] = hat_stats['kirilan_bugday'] / 1000
        
        fig_hat = px.bar(
            hat_stats,
            x='uretim_hatti',
            y=['toplam_randiman', 'kayip'],
            title='Üretim Hatlarına Göre Randıman ve Kayıp Karşılaştırması',
            labels={'value': 'Yüzde (%)', 'uretim_hatti': 'Üretim Hattı', 'variable': 'Metrik'},
            barmode='group',
            color_discrete_map={'toplam_randiman': '#1e3a8a', 'kayip': '#dc2626'}
        )
        
        fig_hat.update_layout(height=400)
        st.plotly_chart(fig_hat, use_container_width=True)
        
        st.divider()
        
        st.subheader("📅 Dönemsel Karşılaştırma")
        
        df_comp = df_filtered.copy()
        df_comp['hafta'] = df_comp['tarih'].dt.isocalendar().week
        df_comp['ay'] = df_comp['tarih'].dt.month
        
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            comp_type = st.radio("Karşılaştırma Türü", ["Haftalık", "Aylık"], horizontal=True)
        
        if comp_type == "Haftalık":
            group_col = 'hafta'
            title_suffix = "Hafta"
        else:
            group_col = 'ay'
            title_suffix = "Ay"
        
        period_stats = df_comp.groupby(group_col).agg({
            'kirilan_bugday': 'sum',
            'toplam_randiman': 'mean'
        }).reset_index()
        
        period_stats['kirilan_bugday'] = period_stats['kirilan_bugday'] / 1000
        
        fig_period = go.Figure()
        
        fig_period.add_trace(go.Bar(
            x=period_stats[group_col],
            y=period_stats['kirilan_bugday'],
            name='Toplam Üretim (Ton)',
            marker_color='#60a5fa',
            yaxis='y'
        ))
        
        fig_period.add_trace(go.Scatter(
            x=period_stats[group_col],
            y=period_stats['toplam_randiman'],
            name='Ortalama Randıman (%)',
            marker_color='#dc2626',
            yaxis='y2',
            mode='lines+markers',
            line=dict(width=3)
        ))
        
        fig_period.update_layout(
            title=f'{title_suffix} Bazında Üretim ve Randıman',
            xaxis_title=title_suffix,
            yaxis=dict(title='Toplam Üretim (Ton)', side='left'),
            yaxis2=dict(title='Randıman (%)', overlaying='y', side='right'),
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_period, use_container_width=True)
        
    except ImportError:
        st.warning("📊 Grafik gösterimi için Plotly kütüphanesi gereklidir.")
    
    st.divider()
    
    st.subheader("🏆 Performans Sıralaması")
    
    col_top1, col_top2 = st.columns(2)
    
    with col_top1:
        st.markdown("**🟢 En Yüksek Randıman (Top 5)**")
        top_randiman = df_filtered.nlargest(5, 'toplam_randiman')[['tarih', 'uretim_hatti', 'toplam_randiman', 'vardiya']]
        top_randiman['tarih'] = top_randiman['tarih'].dt.strftime('%d.%m.%Y')
        top_randiman.columns = ['Tarih', 'Hat', 'Randıman (%)', 'Vardiya']
        st.dataframe(top_randiman, use_container_width=True, hide_index=True)
    
    with col_top2:
        st.markdown("**🔴 En Düşük Randıman (Bottom 5)**")
        bottom_randiman = df_filtered.nsmallest(5, 'toplam_randiman')[['tarih', 'uretim_hatti', 'toplam_randiman', 'vardiya']]
        bottom_randiman['tarih'] = bottom_randiman['tarih'].dt.strftime('%d.%m.%Y')
        bottom_randiman.columns = ['Tarih', 'Hat', 'Randıman (%)', 'Vardiya']
        st.dataframe(bottom_randiman, use_container_width=True, hide_index=True)

def show_uretim_arsivi():
    """Üretim Arşivi - Geliştirilmiş Versiyon"""
    st.header("🗄️ Üretim Arşivi ve Raporlama")
    
    df = get_uretim_kayitlari()
    
    if df.empty:
        st.info("📭 Henüz üretim kaydı bulunmamaktadır.")
        return
    
    st.subheader("📊 Genel Özet")
    
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    
    with col_s1:
        toplam_bugday = df['kirilan_bugday'].sum()
        st.metric("Toplam Buğday", f"{toplam_bugday:,.0f} Kg")
    
    with col_s2:
        toplam_un = df['un_1'].sum() + df['un_2'].sum()
        st.metric("Toplam Un Üretimi", f"{toplam_un:,.0f} Kg")
    
    with col_s3:
        ortalama_randiman = df['toplam_randiman'].mean()
        st.metric("Ortalama Randıman", f"%{ortalama_randiman:.2f}")
    
    with col_s4:
        ortalama_kayip = df['kayip'].mean()
        st.metric("Ortalama Kayıp", f"%{ortalama_kayip:.2f}", delta_color="inverse")
    
    st.divider()
    
    st.subheader("🔍 Filtreleme")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    
    with col_f1:
        today = datetime.now().date()
        date_options = {
            "Bugün": (today, today),
            "Son 7 Gün": (today - timedelta(days=7), today),
            "Son 30 Gün": (today - timedelta(days=30), today),
            "Son 3 Ay": (today - timedelta(days=90), today),
            "Son 6 Ay": (today - timedelta(days=180), today),
            "Son 1 Yıl": (today - timedelta(days=365), today),
            "Tüm Kayıtlar": (None, None)
        }
        
        date_filter = st.selectbox("Tarih Aralığı", list(date_options.keys()), index=6)
        start_date, end_date = date_options[date_filter]
    
    with col_f2:
        if 'uretim_hatti' in df.columns:
            hat_list = ["Tümü"] + sorted(df['uretim_hatti'].unique().tolist())
            hat_filter = st.selectbox("Üretim Hattı", hat_list)
        else:
            hat_filter = "Tümü"
    
    with col_f3:
        if 'vardiya' in df.columns:
            vardiya_list = ["Tümü"] + sorted(df['vardiya'].unique().tolist())
            vardiya_filter = st.selectbox("Vardiya", vardiya_list)
        else:
            vardiya_filter = "Tümü"
    
    filtered_df = df.copy()
    
    if start_date and end_date:
        filtered_df = filtered_df[(filtered_df['tarih'].dt.date >= start_date) & (filtered_df['tarih'].dt.date <= end_date)]
    
    if hat_filter != "Tümü":
        filtered_df = filtered_df[filtered_df['uretim_hatti'] == hat_filter]
    
    if vardiya_filter != "Tümü":
        filtered_df = filtered_df[filtered_df['vardiya'] == vardiya_filter]
    
    st.info(f"📋 Toplam {len(filtered_df)} kayıt gösteriliyor.")
    
    st.divider()
    
    column_mapping = {
        'tarih': 'Tarih',
        'uretim_hatti': 'Üretim Hattı',
        'degirmen_uretim_adi': 'Üretim Adı',
        'vardiya': 'Vardiya',
        'sorumlu': 'Sorumlu',
        'kirilan_bugday': 'Kırılan Buğday (Kg)',
        'nem_orani': 'Nem Oranı (%)',
        'tav_suresi': 'Tav Süresi (Saat)',
        'un_1': 'Un 1 (Kg)',
        'un_2': 'Un 2 (Kg)',
        'razmol': 'Razmol (Kg)',
        'kepek': 'Kepek (Kg)',
        'bongalite': 'Bongalite (Kg)',
        'kirik_bugday': 'Kırık Buğday (Kg)',
        'randiman_1': 'Un 1 Randıman (%)',
        'toplam_randiman': 'Toplam Randıman (%)',
        'kayip': 'Kayıp (%)',
        'parti_no': 'Parti No'
    }
    
    display_df = filtered_df.rename(columns=column_mapping)
    
    if 'Tarih' in display_df.columns:
        display_df['Tarih'] = display_df['Tarih'].dt.strftime('%d.%m.%Y %H:%M')
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()
    
    def create_excel_report(df):
        try:
            import io
            import xlsxwriter
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet("Üretim Raporu")
            
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': True,
                'valign': 'top',
                'fg_color': '#1e3a8a',
                'font_color': 'white',
                'border': 1,
                'align': 'center'
            })
            
            number_format = workbook.add_format({'num_format': '#,##0.00'})
            date_format = workbook.add_format({'num_format': 'dd.mm.yyyy hh:mm'})
            
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)
            
            for row_num, row_data in enumerate(df.values):
                for col_num, value in enumerate(row_data):
                    if pd.isna(value):
                        value = ""
                    
                    if col_num == 0 and isinstance(value, str):
                        worksheet.write(row_num + 1, col_num, value)
                    elif isinstance(value, (int, float)):
                        worksheet.write(row_num + 1, col_num, value, number_format)
                    else:
                        worksheet.write(row_num + 1, col_num, value)
            
            workbook.close()
            output.seek(0)
            return output
        except Exception as e:
            st.error(f"Excel oluşturma hatası: {e}")
            return None
    
    col_btn1, col_btn2 = st.columns([4, 1])
    
    with col_btn2:
        if st.button("📊 Excel Raporu Hazırla", use_container_width=True):
            excel_data = create_excel_report(display_df)
            if excel_data:
                st.download_button(
                    label="📥 Excel İndir",
                    data=excel_data,
                    file_name=f"uretim_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )



