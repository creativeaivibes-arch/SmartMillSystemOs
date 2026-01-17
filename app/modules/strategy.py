import streamlit as st
import pandas as pd
import numpy as np
import altair as alt # Streamlit native charting
from app.modules.flour import get_un_maliyet_gecmisi

def get_baseline_data():
    """En son kaydedilen gerçek maliyet verilerini baz senaryo olarak getirir"""
    try:
        df = get_un_maliyet_gecmisi()
        if not df.empty:
            # En son kaydı al (Tarihe göre sıralı geliyor zaten clean code'da, ama garanti olsun)
            latest = df.iloc[0].to_dict()
            return latest
    except:
        pass
    
    # Veri yoksa varsayılan değerler
    return {
        'bugday_pacal_maliyeti': 14.60,
        'aylik_kirilan_bugday': 3000.0,
        'un_randimani': 70.0,
        'un_satis_fiyati': 980.0,
        'personel_maasi': 1200000.0,
        'bakim_maliyeti': 100000.0,
        'elektrik_gideri': 1500000.0, # Tahmini
        'toplam_gider': 45000000.0, # Tahmini
        'un_cesidi': 'Standart Ekmeklik'
    }

def calculate_generic_profit(bugday_fiyat, un_fiyat, kirilan_tonaj, randiman, sabit_giderler, degisken_gider_ton_basi):
    """
    Hızlı simülasyon hesaplayıcısı.
    Karmaşık yan ürün detaylarına girmeden ana kalemler üzerinden tahmin yapar.
    """
    # Gelirler
    un_tonaj = kirilan_tonaj * (randiman / 100)
    cuval_sayisi = (un_tonaj * 1000) / 50
    un_geliri = cuval_sayisi * un_fiyat
    
    # Basit Yan Ürün Tahmini (Genelde Un gelirinin %25'i kadardır veya maliyetin bir kısmını karşılar)
    # Daha hassas olması için: Kırılan Buğday'ın geri kalanı (%30) yan üründür.
    # Yan ürün ortalama fiyatı (Kepek/Razmol karışık): 9.0 TL/kg diyelim
    yan_urun_miktari_kg = (kirilan_tonaj * 1000) * ((100 - randiman) / 100)
    yan_urun_geliri = yan_urun_miktari_kg * 9.0 
    
    toplam_gelir = un_geliri + yan_urun_geliri
    
    # Giderler
    bugday_maliyeti = kirilan_tonaj * 1000 * bugday_fiyat
    isletme_gideri = sabit_giderler + (degisken_gider_ton_basi * kirilan_tonaj)
    
    toplam_gider = bugday_maliyeti + isletme_gideri
    
    net_kar = toplam_gelir - toplam_gider
    return net_kar

def show_strategy_module():
    st.header("🔍 Stratejik Patron Analizi (DSS)")
    st.caption("Karar Destek Sistemi: Geçmişe değil, geleceğe odaklanın.")
    
    # Baseline veriyi çek
    baseline = get_baseline_data()
    
    # --- A. VERİ GÜNCELLİĞİ UYARISI ---
    if baseline and 'tarih' in baseline:
        try:
            kayit_tarihi = pd.to_datetime(baseline['tarih'])
            # Tarihi daha okunaklı formatla
            readable_date = kayit_tarihi.strftime("%d %B %Y %H:%M")
            st.info(f"ℹ️ Bu analiz, **{readable_date}** tarihinde yapılan ve veritabanına kaydedilen SON maliyet hesaplamasına dayanmaktadır.")
        except:
            st.info(f"ℹ️ Bu analiz, sistemdeki son kayıtlı verilere dayanmaktadır ({baseline.get('tarih', '-')}).")
            
    # Sekmeler
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Hedef Fiyat (Goal Seek)", 
        "🌡️ Duyarlılık Matrisi", 
        "⚓ Kapasite ve Başabaş", 
        "⚖️ Senaryo Karşılaştırma"
    ])
    
    # --- 1. HEDEF ODAKLI HESAPLAMA (GELİŞMİŞ) ---
    with tab1:
        st.subheader("🎯 Hedeflenen Kara Ulaşmak İçin Fiyat Ne Olmalı?")
        
        col_g1, col_g2 = st.columns([1, 2])
        
        with col_g1:
            st.info("💡 **Senaryo:** Giderleriniz sabitken, ay sonunda cebinize girmesini istediğiniz net karı yazın.")
            
            # Vergi kaldırıldı - Direkt Net Hedef (Patron Mantığı)
            target_profit_net = st.number_input("Hedeflenen Aylık Net Kar (TL)", value=2000000.0, step=100000.0, format="%.0f")
            
            with st.expander("📝 Varsayımları Düzenle", expanded=False):
                g_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=float(baseline.get('bugday_pacal_maliyeti', 14.6)))
                g_tonaj = st.number_input("Kırılan Buğday (Ton)", value=float(baseline.get('aylik_kirilan_bugday', 3000)))
                g_sabit_gider = st.number_input("Aylık Sabit Giderler", value=float(baseline.get('toplam_gider', 45000000)) * 0.10, help="Tahmini işletme gideri") # Basit tahmin
                current_market_price = st.number_input("Mevcut Piyasa Un Fiyatı", value=float(baseline.get('un_satis_fiyati', 980)))

        with col_g2:
            # Reverse Calc
            randiman = float(baseline.get('un_randimani', 70))
            un_tonaj = g_tonaj * (randiman / 100)
            cuval_sayisi = (un_tonaj * 1000) / 50
            
            yan_urun_kg = (g_tonaj * 1000) * ((100 - randiman) / 100)
            yan_urun_geliri = yan_urun_kg * 9.0 
            
            bugday_maliyeti = g_tonaj * 1000 * g_bugday_fiyat
            
            if g_sabit_gider < 100000: g_sabit_gider = 3000000 # Fallback
            
            toplam_gider = bugday_maliyeti + g_sabit_gider
            
            # Hedef Gelir = Hedef Kar + Toplam Gider (Vergisiz)
            gerekli_toplam_gelir = target_profit_net + toplam_gider
            
            # Gerekli Un Geliri = Gerekli Toplam Gelir - Yan Ürün
            gerekli_un_geliri = gerekli_toplam_gelir - yan_urun_geliri
            
            gerekli_cuval_fiyati = gerekli_un_geliri / cuval_sayisi
            
            fark_tl = gerekli_cuval_fiyati - current_market_price
            fark_yuzde = (fark_tl / current_market_price) * 100
            
            # SONUÇ KARTLARI
            res_c1, res_c2 = st.columns(2)
            with res_c1:
                st.metric(
                    label="SATMANIZ GEREKEN MİNİMUM FİYAT", 
                    value=f"{gerekli_cuval_fiyati:,.2f} TL",
                    delta=f"{fark_tl:,.2f} TL",
                    delta_color="inverse"
                )
            with res_c2:
                st.metric(
                    label="PİYASA FARKI",
                    value=f"%{fark_yuzde:+.1f}",
                    delta="Piyasa Fiyatına Göre Konum",
                    delta_color="off" 
                )
            
            # Yorumlama
            if fark_yuzde > 10:
                st.error(f"⚠️ **KRİTİK:** Hedefinize ulaşmak için piyasanın **%{fark_yuzde:.1f}** üzerinde satmanız gerekiyor. Bu fiyata satmak zor olabilir.")
            elif fark_yuzde > 0:
                st.warning(f"⚠️ Piyasanın **%{fark_yuzde:.1f}** üzerindesiniz. Satış ekibini zorlamanız gerekebilir.")
            else:
                st.success(f"✅ Harika! Piyasa fiyatının **%{-fark_yuzde:.1f}** altında kalarak bile bu hedefi tutturabilirsiniz.")

    # --- 2. DUYARLILIK MATRİSİ (STRESS TEST) ---
    with tab2:
        st.subheader("🌡️ Stres Testi: Buğday Zamlanırsa Ne Olur?")
        
        col_s1, col_s2 = st.columns([1, 3])
        
        with col_s1:
            base_bugday = st.number_input("Baz Buğday Fiyatı", value=14.50, step=0.10)
            base_un = st.number_input("Baz Un Fiyatı", value=950.0, step=10.0)
            
            # Kritik Nokta Analizi
            sim_tonaj = 3000
            sim_sabit = 3000000
            sim_un_geliri = ((sim_tonaj * 0.7 * 1000) / 50) * base_un
            sim_yan_urun = (sim_tonaj * 0.3 * 1000) * 9.0
            total_rev = sim_un_geliri + sim_yan_urun
            
            kritik_bugday = (total_rev - sim_sabit) / (sim_tonaj * 1000)
            
            st.divider()
            st.markdown(f"**🔥 Kritik Sınır:**")
            st.markdown(f"Eğer buğday **{kritik_bugday:.2f} TL** olursa kârınız **SIFIRLANIR**!")
            
        with col_s2:
            # Matris Verisi Hazırlama (Altair için Long Format)
            bugday_prices = [base_bugday + (i * 0.25) for i in range(-2, 3)] # -0.50 ... +0.50
            un_prices = [base_un + (i * 25) for i in range(-2, 3)] # -50 ... +50
            
            records = []
            for bf in bugday_prices:
                for uf in un_prices:
                    # Basit Kar Hesabı (Fix Sabit Gider 3M)
                    profit = calculate_generic_profit(bf, uf, 3000, 70, 3000000, 500) 
                    records.append({
                        "Buğday Maliyeti": f"{bf:.2f} TL",
                        "Un Satış Fiyatı": f"{uf:.0f} TL",
                        "Net Kar (Bin TL)": int(profit / 1000),
                        "Ham Kar": profit
                    })
            
            df_long = pd.DataFrame(records)
            
            # Isı Haritası Grafiği (Kod Değişmedi)
            base = alt.Chart(df_long).encode(
                x=alt.X('Un Satış Fiyatı:O', sort=None),
                y=alt.Y('Buğday Maliyeti:O', sort=None),
                tooltip=['Buğday Maliyeti', 'Un Satış Fiyatı', 'Ham Kar']
            )
            
            heatmap = base.mark_rect().encode(
                color=alt.Color('Net Kar (Bin TL):Q', scale=alt.Scale(scheme='redyellowgreen'), legend=alt.Legend(title="Net Kar (Bin TL)"))
            )
            
            text = base.mark_text().encode(
                text='Net Kar (Bin TL):Q',
                color=alt.condition(
                    alt.datum['Net Kar (Bin TL)'] > 0,
                    alt.value('black'),
                    alt.value('white')
                )
            )
            st.altair_chart(heatmap + text, use_container_width=True)
            
            # --- B. EXCEL ÇIKTISI (Patronlar Bayılır) ---
            st.divider()
            # Önce pivot yapalım (okunabilir format)
            df_export = df_long.pivot(index="Buğday Maliyeti", columns="Un Satış Fiyatı", values="Ham Kar")
            
            # CSV string oluştur
            csv = df_export.to_csv().encode('utf-8-sig')
            
            st.download_button(
                label="📥 Bu Tabloyu Excel (CSV) Olarak İndir",
                data=csv,
                file_name=f"duyarlilik_analizi_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary"
            )

    # --- 3. KIRILMA NOKTASI & KAPASİTE ANALİZİ ---
    with tab3:
        st.subheader("⚓ Kapasite ve Başabaş Analizi")
        
        col_b1, col_b2 = st.columns([1, 2])
        
        with col_b1:
            b_sabit = st.number_input("Sabit Giderler (Aylık)", value=3500000.0, key="be_sabit")
            b_kar_marji = st.number_input("Ton Başına Ortalama Brüt Kar (TL)", value=1200.0)
            tam_kapasite = st.number_input("Tam Kapasite (Ton/Ay)", value=4500.0)
            
        with col_b2:
            tab_be1, tab_be2 = st.tabs(["📉 Başabaş Grafiği", "🏭 Kapasite Etkisi"])
            
            with tab_be1:
                break_even_tonaj = b_sabit / b_kar_marji
                st.metric("Başabaş Noktası (Zararsızlık Tonajı)", f"{break_even_tonaj:,.0f} Ton")
                
                x = np.linspace(0, tam_kapasite, 100)
                y_net = (x * b_kar_marji) - b_sabit
                
                chart_data = pd.DataFrame({"Tonaj": x, "Net Kar": y_net, "Sıfır": 0})
                st.line_chart(chart_data, x="Tonaj", y=["Net Kar", "Sıfır"], color=["#2ecc71", "#e74c3c"])
            
            with tab_be2:
                st.markdown("**Düşük Kapasitenin Çuval Başına Etkisi**")
                caps = np.linspace(500, tam_kapasite, 20)
                sacks = (caps * 0.7 * 1000) / 50
                fixed_per_sack = b_sabit / sacks
                
                df_cap = pd.DataFrame({"Kapasite (Ton)": caps, "Çuval Başına Sabit Maliyet (TL)": fixed_per_sack})
                
                c = alt.Chart(df_cap).mark_line(point=True).encode(
                    x='Kapasite (Ton)', y='Çuval Başına Sabit Maliyet (TL)', tooltip=['Kapasite (Ton)', 'Çuval Başına Sabit Maliyet (TL)']
                ).interactive()
                st.altair_chart(c, use_container_width=True)

    # --- 4. SENARYO KARŞILAŞTIRMA ---
    with tab4:
        st.subheader("⚖️ Çoklu Senaryo Karşılaştırma")
        
        c_sc1, c_sc2, c_sc3 = st.columns(3)
        
        # Senaryo Parametreleri (Defaults)
        def scenario_card(col, title, bg_color, default_bugday, default_un):
            with col:
                with st.container(border=True):
                    st.markdown(f"### {title}")
                    s_bugday = st.number_input("Buğday", value=default_bugday, key=f"s_b_{title}")
                    s_un = st.number_input("Un Fiyatı", value=default_un, key=f"s_u_{title}")
                    
                    # Hesapla
                    profit = calculate_generic_profit(s_bugday, s_un, 3000, 70, 3000000, 500)
                    profit_fmt = f"{profit:,.0f} TL"
                    
                    # --- C. DRAMATİK VURGU (Kar/Zarar/Başabaş) ---
                    if profit < 0:
                        st.markdown(f"<h2 style='color:red'>{profit_fmt}</h2>", unsafe_allow_html=True)
                        st.error(f"⚠️ ZARAR! ({profit:,.0f} TL)")
                    elif profit == 0:
                        st.markdown(f"<h2 style='color:orange'>{profit_fmt}</h2>", unsafe_allow_html=True)
                        st.warning("⚠️ BAŞA BAŞ (Ne Kar Ne Zarar)")
                    else:
                        st.markdown(f"<h2 style='color:green'>{profit_fmt}</h2>", unsafe_allow_html=True)
                        st.success("✅ KAR EDİLİYOR")
                        
                    return profit

        p_pessimistic = scenario_card(c_sc1, "🐻 Kötümser", "#ffcccc", 15.50, 920.0)
        p_realistic = scenario_card(c_sc2, "⚖️ Gerçekçi", "#f0f0f0", 14.60, 980.0)
        p_optimistic = scenario_card(c_sc3, "🐂 İyimser", "#ccffcc", 13.80, 1050.0)
        
        st.divider()
        st.markdown(f"**Fark Analizi:** İyimser senaryo, Kötümser senaryoya göre aylık **{(p_optimistic - p_pessimistic):,.0f} TL** daha karlıdır.")
