# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from app.modules.flour import get_un_maliyet_gecmisi

def get_baseline_data():
    """En son kaydedilen gerçek maliyet verilerini baz senaryo olarak getirir"""
    try:
        df = get_un_maliyet_gecmisi()
        if not df.empty:
            latest = df.iloc[0].to_dict()
            
            # ===== AYLIK SABİT GİDER HESAPLA (SADECE SABİT KALEMLER) =====
            aylik_sabit = (
                float(latest.get('personel_maasi', 1200000)) +      # Personel
                float(latest.get('bakim_maliyeti', 100000)) +       # Bakım
                float(latest.get('mutfak_gideri', 50000)) +         # Mutfak
                float(latest.get('finans_gideri', 0)) +             # Finans
                float(latest.get('diger_giderler', 0)) +            # Diğer
                500000  # Kira/Amortisman (sabit varsayım)
            )
            
            # ELEKTRİK: Ton başı değeri al (DEĞİŞKEN GİDER!)
            ton_basi_elektrik = float(latest.get('ton_bugday_elektrik', 500))  # TL/Ton
            
            # DEĞİŞKEN GİDER: Çuval başı giderleri topla
            cuval_basi_degisken = (
                float(latest.get('nakliye', 20)) +
                float(latest.get('satis_pazarlama', 20.5)) +
                float(latest.get('pp_cuval', 15)) +
                float(latest.get('katki_maliyeti', 9))
            )  # ≈ 64.5 TL/çuval
            
            # Ton başına değişken gider hesapla
            # 1 ton buğday → 0.7 ton un → 14 çuval (50kg) 
            # 14 çuval × 64.5 TL = ~903 TL/ton (ambalaj+nakliye+pazarlama+katkı)
            # + Elektrik: 500 TL/ton
            ton_basi_degisken = (cuval_basi_degisken * 14) + ton_basi_elektrik  # ≈ 1403 TL/ton
            
            latest['aylik_sabit_gider'] = aylik_sabit  # YENİ ALAN (≈ 1.85M TL)
            latest['ton_basi_degisken_gider'] = ton_basi_degisken  # YENİ ALAN (≈ 1403 TL/ton)
            
            return latest
    except Exception as e:
        st.warning(f"⚠️ Baseline veri çekilemedi: {e}")
    
    # Veri yoksa varsayılan değerler
    return {
        'bugday_pacal_maliyeti': 14.60,
        'aylik_kirilan_bugday': 3000.0,
        'un_randimani': 70.0,
        'un_satis_fiyati': 980.0,
        'personel_maasi': 1200000.0,
        'bakim_maliyeti': 100000.0,
        'mutfak_gideri': 50000.0,
        'finans_gideri': 0.0,
        'diger_giderler': 0.0,
        'ton_bugday_elektrik': 500.0,
        'aylik_sabit_gider': 1850000.0,  # YENİ (1.85M TL)
        'ton_basi_degisken_gider': 1403,  # YENİ (~1400 TL/ton)
        'un_cesidi': 'Standart Ekmeklik'
    }

def calculate_generic_profit(bugday_fiyat, un_fiyat, kirilan_tonaj, randiman, sabit_giderler, degisken_gider_ton_basi):
    """
    Hızlı simülasyon hesaplayıcısı.
    Karmaşık yan ürün detaylarına girmeden ana kalemler üzerinden tahmin yapar.
    
    ÖNEMLİ: Bu fonksiyon artık DEĞİŞKEN GİDERLERİ doğru hesaplıyor!
    """
    # === GELİRLER ===
    un_tonaj = kirilan_tonaj * (randiman / 100)
    cuval_sayisi = (un_tonaj * 1000) / 50
    un_geliri = cuval_sayisi * un_fiyat
    
    # Basit Yan Ürün Tahmini
    # Kırılan Buğday'ın geri kalanı (%30) yan üründür
    # Yan ürün ortalama fiyatı (Kepek/Razmol karışık): 9.0 TL/kg
    yan_urun_miktari_kg = (kirilan_tonaj * 1000) * ((100 - randiman) / 100)
    yan_urun_geliri = yan_urun_miktari_kg * 9.0 
    
    toplam_gelir = un_geliri + yan_urun_geliri
    
    # === GİDERLER ===
    bugday_maliyeti = kirilan_tonaj * 1000 * bugday_fiyat
    degisken_gider = degisken_gider_ton_basi * kirilan_tonaj  # TON BAŞI DEĞİŞKEN GİDER
    
    toplam_gider = bugday_maliyeti + sabit_giderler + degisken_gider
    
    net_kar = toplam_gelir - toplam_gider
    return net_kar

def hesapla_kritik_bugday_fiyati(un_fiyat, kirilan_tonaj, randiman, sabit_giderler, degisken_gider_ton_basi):
    """
    🎯 KRİTİK BUĞDAY FİYATI HESAPLAYICI (DÜZELTME!)
    
    Net Kar = 0 olduğu noktada buğday fiyatını bulur.
    
    Formül:
    Gelir = Gider
    (Un Geliri + Yan Ürün Geliri) = (Buğday Maliyeti + Sabit Gider + Değişken Gider)
    
    Bilinmeyen: Buğday Fiyatı
    """
    un_tonaj = kirilan_tonaj * (randiman / 100)
    cuval_sayisi = (un_tonaj * 1000) / 50
    un_geliri = cuval_sayisi * un_fiyat
    
    # Yan ürün geliri (sabit - buğday fiyatından bağımsız)
    yan_urun_kg = (kirilan_tonaj * 1000) * ((100 - randiman) / 100)
    yan_urun_geliri = yan_urun_kg * 9.0
    
    toplam_gelir = un_geliri + yan_urun_geliri
    
    # Sabit ve değişken giderler
    isletme_gideri = sabit_giderler + (degisken_gider_ton_basi * kirilan_tonaj)
    
    # Kritik buğday fiyatı:
    # Buğday Maliyeti = Toplam Gelir - İşletme Gideri
    # Buğday Fiyatı (TL/kg) = Buğday Maliyeti / (Kırılan Tonaj × 1000)
    
    kritik_bugday_maliyeti = toplam_gelir - isletme_gideri
    kritik_bugday_fiyati = kritik_bugday_maliyeti / (kirilan_tonaj * 1000)
    
    return kritik_bugday_fiyati

def show_strategy_module():
    # Başlık Alanı
    st.markdown("""
    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
        <h2 style='color: #0B4F6C; margin:0;'>📊 Stratejik Patron Analizi (DSS)</h2>
        <p style='color: #666; margin:0; font-size: 14px;'>Geçmişe değil, geleceğe odaklanın. Karar Destek Sistemi.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Baseline veriyi çek
    baseline = get_baseline_data()
    
    # --- YENİ NAVİGASYON (BUTONLAR) ---
    analiz_secimi = st.radio(
        "Analiz Aracı Seçiniz:",
        ["🎯 Hedef Fiyat (Goal Seek)", "🌡️ Duyarlılık Matrisi", "⚓ Kapasite ve Başabaş", "⚖️ Senaryo Karşılaştırma"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.markdown("---") 
    
    # --- 1. HEDEF ODAKLI HESAPLAMA ---
    if "Hedef Fiyat" in analiz_secimi:
        with st.container(border=True):
            st.subheader("🎯 Hedeflenen Kara Ulaşmak İçin Fiyat Ne Olmalı?")
            st.info("💡 **Patron Mantığı:** Cebime girmesini istediğim parayı yazıyorum, sistem bana kaçtan satmam gerektiğini söylüyor.")
            
            col_g1, col_g2 = st.columns([1, 2])
            
            with col_g1:
                st.markdown("##### 💰 Hedef Tanımlama")
                target_profit_net = st.number_input(
                    "🎯 Hedeflenen Aylık Net Kar (TL)", 
                    value=2000000.0, step=100000.0, format="%.0f"
                )
                
                with st.expander("🔧 Varsayımları Düzenle", expanded=False):
                    g_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=float(baseline.get('bugday_pacal_maliyeti', 14.6)), step=0.10)
                    g_tonaj = st.number_input("Kırılan Buğday (Ton)", value=float(baseline.get('aylik_kirilan_bugday', 3000)), step=100.0)
                    g_sabit_gider = st.number_input("Aylık Sabit Giderler (TL)", value=float(baseline.get('aylik_sabit_gider', 1850000)), step=100000.0)
                    g_degisken_gider = st.number_input("Ton Başı Değişken Gider (TL)", value=float(baseline.get('ton_basi_degisken_gider', 1403)), step=50.0)
                    current_market_price = st.number_input("Piyasa Un Fiyatı (TL/50kg)", value=float(baseline.get('un_satis_fiyati', 980)), step=5.0)
            
            with col_g2:
                # Hesaplamalar
                randiman = float(baseline.get('un_randimani', 70))
                un_tonaj = g_tonaj * (randiman / 100)
                cuval_sayisi = (un_tonaj * 1000) / 50
                
                # Yan ürün geliri
                yan_urun_geliri = (g_tonaj * 1000) * ((100 - randiman) / 100) * 9.0 
                
                # Giderler
                bugday_maliyeti = g_tonaj * 1000 * g_bugday_fiyat
                degisken_gider_toplam = g_degisken_gider * g_tonaj
                toplam_gider = bugday_maliyeti + g_sabit_gider + degisken_gider_toplam
                
                # Gerekli gelir
                gerekli_toplam_gelir = target_profit_net + toplam_gider
                gerekli_un_geliri = gerekli_toplam_gelir - yan_urun_geliri
                gerekli_cuval_fiyati = gerekli_un_geliri / cuval_sayisi if cuval_sayisi > 0 else 0
                
                fark_tl = gerekli_cuval_fiyati - current_market_price
                fark_yuzde = (fark_tl / current_market_price) * 100 if current_market_price > 0 else 0
                
                # SONUÇ KARTLARI
                res_c1, res_c2 = st.columns(2)
                with res_c1:
                    st.metric("🎯 SATMANIZ GEREKEN FİYAT", f"{gerekli_cuval_fiyati:,.2f} TL", delta=f"Piyasa farkı: {fark_tl:,.2f} TL")
                with res_c2:
                    st.metric("📊 PİYASA KONUMU", f"%{fark_yuzde:+.1f}", delta="Piyasa Fiyatına Göre", delta_color="off")
                
                if fark_yuzde > 10:
                    st.error(f"⚠️ **KRİTİK:** Hedef için piyasanın **%{fark_yuzde:.1f}** üzerinde satmanız lazım.")
                elif fark_yuzde > 0:
                    st.warning(f"⚠️ **DİKKAT:** Piyasanın **%{fark_yuzde:.1f}** üzerindesiniz.")
                else:
                    st.success(f"✅ **HARİKA:** Piyasanın **%{abs(fark_yuzde):.1f}** altında kalarak bile bu karı yapabilirsiniz.")
                
                with st.expander("📋 Detaylı Hesaplama Özeti", expanded=False):
                    st.markdown(f"""
                    **GELİRLER:**
                    - Üretilecek Un: {un_tonaj:,.0f} ton ({cuval_sayisi:,.0f} çuval)
                    - Un Geliri: {gerekli_un_geliri:,.0f} TL
                    - Yan Ürün Geliri: {yan_urun_geliri:,.0f} TL
                    - **Toplam Gelir:** {gerekli_toplam_gelir:,.0f} TL
                    
                    **GİDERLER:**
                    - Buğday Maliyeti: {bugday_maliyeti:,.0f} TL
                    - Sabit Giderler: {g_sabit_gider:,.0f} TL
                    - Değişken Giderler: {degisken_gider_toplam:,.0f} TL
                    - **Toplam Gider:** {toplam_gider:,.0f} TL
                    
                    **NET KAR:** {target_profit_net:,.0f} TL
                    """)

    # --- 2. DUYARLILIK MATRİSİ ---
    elif "Duyarlılık" in analiz_secimi:
        with st.container(border=True):
            st.subheader("🌡️ Stres Testi: Buğday Zamlanırsa Ne Olur?")
            st.info("💡 **Senaryo:** Buğday fiyatı ve Un satış fiyatı aynı anda değişirse karım ne olur?")
            
            col_s1, col_s2 = st.columns([1, 3])
            
            with col_s1:
                st.markdown("##### ⚙️ Parametreler")
                
                # ✅ DÜZELTİLDİ: Baseline'dan çek!
                base_bugday = st.number_input(
                    "Baz Buğday (TL/kg)", 
                    value=float(baseline.get('bugday_pacal_maliyeti', 14.60)), 
                    step=0.10, 
                    key="sens_bugday"
                )
                base_un = st.number_input(
                    "Baz Un (TL/50kg)", 
                    value=float(baseline.get('un_satis_fiyati', 980.0)), 
                    step=10.0, 
                    key="sens_un"
                )
                sens_tonaj = st.number_input(
                    "Kırılan Tonaj", 
                    value=float(baseline.get('aylik_kirilan_bugday', 3000.0)), 
                    step=100.0, 
                    key="sens_tonaj"
                )
                sens_sabit = st.number_input(
                    "Sabit Gider", 
                    value=float(baseline.get('aylik_sabit_gider', 1850000)), 
                    step=100000.0, 
                    key="sens_sabit"
                )
                sens_degisken = st.number_input(
                    "Ton Başı Değişken", 
                    value=float(baseline.get('ton_basi_degisken_gider', 1403)), 
                    step=50.0, 
                    key="sens_degisken"
                )
                
                st.divider()
                
                # ✅ DÜZELTME: Kritik sınır hesabı
                kritik_bugday = hesapla_kritik_bugday_fiyati(
                    un_fiyat=base_un,
                    kirilan_tonaj=sens_tonaj,
                    randiman=float(baseline.get('un_randimani', 70)),
                    sabit_giderler=sens_sabit,
                    degisken_gider_ton_basi=sens_degisken
                )
                
                if kritik_bugday > 0:
                    st.error(f"⚠️ **KRİTİK SINIR:** Buğday **{kritik_bugday:.2f} TL/kg** olursa kar SIFIRLANIR.")
                    
                    # Kritik noktaya ne kadar yakınız?
                    kritik_mesafe = kritik_bugday - base_bugday
                    if kritik_mesafe < 1.0:
                        st.warning(f"🚨 **ACİL:** Kritik noktaya sadece **{kritik_mesafe:.2f} TL** kaldı!")
                    else:
                        st.info(f"📊 Kritik noktaya **{kritik_mesafe:.2f} TL** mesafe var.")
                else:
                    st.success("✅ Mevcut fiyatlarla zarar edilmiyor.")

            with col_s2:
                # Matris aralıkları (baz değerlerin etrafında ±2 adım)
                bugday_prices = [base_bugday + (i * 0.50) for i in range(-2, 3)]  # ±1 TL aralık
                un_prices = [base_un + (i * 50) for i in range(-2, 3)]  # ±100 TL aralık
                
                records = []
                for bf in bugday_prices:
                    for uf in un_prices:
                        profit = calculate_generic_profit(
                            bf, uf, sens_tonaj, 
                            float(baseline.get('un_randimani', 70)), 
                            sens_sabit, sens_degisken
                        ) 
                        records.append({
                            "Buğday": f"{bf:.2f}",
                            "Un Fiyatı": f"{uf:.0f}",
                            "Net Kar (Bin TL)": int(profit / 1000)
                        })
                
                df_long = pd.DataFrame(records)
                
                base_chart = alt.Chart(df_long).encode(
                    x=alt.X('Un Fiyatı:O', title='Un Satış Fiyatı (TL/50kg)'),
                    y=alt.Y('Buğday:O', title='Buğday Maliyeti (TL/kg)'),
                    tooltip=['Buğday', 'Un Fiyatı', 'Net Kar (Bin TL)']
                )
                heatmap = base_chart.mark_rect().encode(
                    color=alt.Color('Net Kar (Bin TL):Q', scale=alt.Scale(scheme='redyellowgreen'))
                )
                text = base_chart.mark_text().encode(
                    text='Net Kar (Bin TL):Q',
                    color=alt.condition(alt.datum['Net Kar (Bin TL)'] > 0, alt.value('black'), alt.value('white'))
                )
                st.altair_chart(heatmap + text, use_container_width=True)
                
                st.caption("📊 **Renk Kodu:** Yeşil = Kar, Sarı = Düşük Kar, Kırmızı = Zarar")

    # --- 3. KIRILMA NOKTASI ---
    elif "Kapasite" in analiz_secimi:
        with st.container(border=True):
            st.subheader("⚓ Kapasite ve Başabaş Analizi")
            st.info("💡 **Analiz:** Fabrikayı düşük kapasite çalıştırmanın 'gizli maliyeti' nedir?")
            
            col_b1, col_b2 = st.columns([1, 2])
            
            with col_b1:
                b_sabit = st.number_input("Sabit Giderler (TL)", value=float(baseline.get('aylik_sabit_gider', 1850000)), step=100000.0, key="kap_sabit")
                b_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=14.60, step=0.10, key="kap_bugday")
                b_un_fiyat = st.number_input("Un Satış (TL/50kg)", value=980.0, step=10.0, key="kap_un")
                b_degisken = st.number_input("Ton Başı Değişken (TL)", value=float(baseline.get('ton_basi_degisken_gider', 1403)), step=50.0, key="kap_degisken")
                tam_kapasite = st.number_input("Tam Kapasite (Ton/Ay)", value=4500.0, step=100.0, key="kap_tam")
                
            with col_b2:
                # Ton başı brüt kar marjı
                un_tonaj_per_ton = 0.7  # %70 randıman
                cuval_per_ton = (un_tonaj_per_ton * 1000) / 50  # 14 çuval
                un_geliri_per_ton = cuval_per_ton * b_un_fiyat
                
                yan_urun_per_ton = (1000 * 0.3) * 9.0  # 300 kg × 9 TL = 2700 TL
                
                toplam_gelir_per_ton = un_geliri_per_ton + yan_urun_per_ton
                
                bugday_maliyet_per_ton = 1000 * b_bugday_fiyat
                degisken_maliyet_per_ton = b_degisken
                
                brut_kar_per_ton = toplam_gelir_per_ton - bugday_maliyet_per_ton - degisken_maliyet_per_ton
                
                # Başabaş tonajı
                break_even_tonaj = b_sabit / brut_kar_per_ton if brut_kar_per_ton > 0 else 0
                
                kpi_c1, kpi_c2 = st.columns(2)
                with kpi_c1:
                    st.metric("🎯 ZARARSIZLIK TONAJI", f"{break_even_tonaj:,.0f} Ton")
                with kpi_c2:
                    kapasite_yuzdesi = (break_even_tonaj / tam_kapasite) * 100 if tam_kapasite > 0 else 0
                    st.metric("📊 Minimum Kapasite Kullanımı", f"%{kapasite_yuzdesi:.1f}")
                
                # Kapasite grafiği
                caps = np.linspace(break_even_tonaj if break_even_tonaj > 0 else 500, tam_kapasite, 20)
                profits = []
                for cap in caps:
                    profit = calculate_generic_profit(b_bugday_fiyat, b_un_fiyat, cap, 70, b_sabit, b_degisken)
                    profits.append(profit / 1000)  # Bin TL
                
                df_cap = pd.DataFrame({"Kapasite (Ton)": caps, "Net Kar (Bin TL)": profits})
                
                c = alt.Chart(df_cap).mark_line(point=True, color='#2ecc71', strokeWidth=3).encode(
                    x=alt.X('Kapasite (Ton)'),
                    y=alt.Y('Net Kar (Bin TL)'),
                    tooltip=['Kapasite (Ton)', 'Net Kar (Bin TL)']
                ).interactive()
                
                # Başabaş çizgisi
                break_line = alt.Chart(pd.DataFrame({'y': [0]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y:Q')
                
                st.altair_chart(c + break_line, use_container_width=True)
                st.warning(f"⚠️ **{break_even_tonaj:,.0f} ton**'un altında çalışmak ZARAR getirir!")
    # --- 4. SENARYO KARŞILAŞTIRMA ---
    elif "Senaryo" in analiz_secimi:
        with st.container(border=True):
            st.subheader("⚖️ Çoklu Senaryo Karşılaştırma")
            st.info("💡 **Simülasyon:** Piyasa iyiye veya kötüye giderse ne olur?")
            
            # Ortak parametreler
            sc_tonaj = st.number_input("Kırılan Tonaj (Ton)", value=3000.0, step=100.0, key="sc_tonaj")
            sc_sabit = st.number_input("Sabit Giderler (TL)", value=float(baseline.get('aylik_sabit_gider', 1850000)), step=100000.0, key="sc_sabit")
            sc_degisken = st.number_input("Ton Başı Değişken (TL)", value=float(baseline.get('ton_basi_degisken_gider', 1403)), step=50.0, key="sc_degisken")
            
            st.divider()
            
            c_sc1, c_sc2, c_sc3 = st.columns(3)
            
            def scenario_card(col, title, emoji, default_bugday, default_un):
                with col:
                    st.markdown(f"### {emoji} {title}")
                    s_bugday = st.number_input("Buğday (TL/kg)", value=default_bugday, key=f"s_b_{title}", step=0.10)
                    s_un = st.number_input("Un (TL/50kg)", value=default_un, key=f"s_u_{title}", step=5.0)
                    
                    profit = calculate_generic_profit(s_bugday, s_un, sc_tonaj, 70, sc_sabit, sc_degisken)
                    
                    if profit < 0:
                        st.error(f"⚠️ ZARAR: {abs(profit):,.0f} TL")
                    else:
                        st.success(f"✅ KAR: {profit:,.0f} TL")
                    return profit

            p_pessimistic = scenario_card(c_sc1, "Kötümser", "🐻", 15.50, 920.0)
            p_realistic = scenario_card(c_sc2, "Gerçekçi", "⚖️", 14.60, 980.0)
            p_optimistic = scenario_card(c_sc3, "İyimser", "🐂", 13.80, 1050.0)
            
            st.divider()
            diff = p_optimistic - p_pessimistic
            avg = (p_pessimistic + p_realistic + p_optimistic) / 3
            
            result_c1, result_c2 = st.columns(2)
            with result_c1:
                st.metric("📊 Senaryo Farkı", f"{diff:,.0f} TL", delta="İyimser - Kötümser")
            with result_c2:
                st.metric("📈 Ortalama Kar", f"{avg:,.0f} TL")
            
            # Risk analizi
            if p_pessimistic < 0:
                st.error("🚨 **YÜKSEK RİSK:** Kötümser senaryoda zarar var! Acil önlem gerekli.")
            elif p_realistic > p_optimistic * 0.8:
                st.success("✅ **DÜŞÜK RİSK:** Tüm senaryolarda karlısınız.")
            else:
                st.warning("⚠️ **ORTA RİSK:** Piyasa kötüye giderse kar marjı düşüyor.")
                

