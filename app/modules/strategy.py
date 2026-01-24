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
            
            # ELEKTRİK: Ton başı değeri al (daha doğru)
            ton_basi_elektrik = float(latest.get('ton_bugday_elektrik', 500))  # TL/Ton
            
            # DEĞİŞKEN GİDER: Çuval başı giderleri topla
            cuval_basi_degisken = (
                float(latest.get('nakliye', 20)) +
                float(latest.get('satis_pazarlama', 20.5)) +
                float(latest.get('pp_cuval', 15)) +
                float(latest.get('katki_maliyeti', 9))
            )  # ≈ 64.5 TL/çuval
            
            # Ton başına değişken gider hesapla
            # 1 ton = 0.7 ton un = 14 çuval (50kg) 
            # 14 çuval × 64.5 TL = ~903 TL/ton
            # Elektrik ekle: 500 TL/ton
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
    """
    # Gelirler
    un_tonaj = kirilan_tonaj * (randiman / 100)
    cuval_sayisi = (un_tonaj * 1000) / 50
    un_geliri = cuval_sayisi * un_fiyat
    
    # Basit Yan Ürün Tahmini
    # Kırılan Buğday'ın geri kalanı (%30) yan üründür
    # Yan ürün ortalama fiyatı (Kepek/Razmol karışık): 9.0 TL/kg
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
    # Başlık Alanı
    st.markdown("""
    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
        <h2 style='color: #0B4F6C; margin:0;'>🔍 Stratejik Patron Analizi (DSS)</h2>
        <p style='color: #666; margin:0; font-size: 14px;'>Geçmişe değil, geleceğe odaklanın. Karar Destek Sistemi.</p>
    </div>
    """, unsafe_allow_html=True)
    
   
    python    # Baseline veriyi çek
    baseline = get_baseline_data()
    
    # ===== DEBUG: BASELINE VERİLERİNİ GÖSTER (GEÇİCİ TEST) =====
    with st.expander("🔍 DEBUG: Baseline Verileri (Test Amaçlı)", expanded=False):
        st.markdown("##### 📊 Hesaplanan Değerler:")
        
        col_d1, col_d2, col_d3 = st.columns(3)
        
        with col_d1:
            st.metric(
                "💰 Aylık Sabit Gider", 
                f"{baseline.get('aylik_sabit_gider', 0):,.0f} TL",
                help="Personel + Bakım + Mutfak + Finans + Diğer + Kira"
            )
        
        with col_d2:
            st.metric(
                "⚡ Ton Başı Değişken Gider", 
                f"{baseline.get('ton_basi_degisken_gider', 0):,.0f} TL/Ton",
                help="Elektrik + Nakliye + Pazarlama + Çuval + Katkı (çuval bazında)"
            )
        
        with col_d3:
            st.metric(
                "🌾 Buğday Paçal Maliyet", 
                f"{baseline.get('bugday_pacal_maliyeti', 0):.2f} TL/kg"
            )
        
        st.divider()
        st.markdown("##### 📋 Detaylı Breakdown:")
        
        # Sabit Gider Detayı
        st.markdown("**Sabit Gider Bileşenleri:**")
        sabit_breakdown = {
            'Personel Maaşı': baseline.get('personel_maasi', 0),
            'Bakım Maliyeti': baseline.get('bakim_maliyeti', 0),
            'Mutfak Gideri': baseline.get('mutfak_gideri', 0),
            'Finans Gideri': baseline.get('finans_gideri', 0),
            'Diğer Giderler': baseline.get('diger_giderler', 0),
            'Kira/Amortisman (Varsayım)': 500000
        }
        
        for key, val in sabit_breakdown.items():
            st.write(f"- {key}: {val:,.0f} TL")
        
        st.markdown(f"**TOPLAM SABİT:** {sum(sabit_breakdown.values()):,.0f} TL")
        
        st.divider()
        
        # Değişken Gider Detayı
        st.markdown("**Değişken Gider Bileşenleri (Ton Başı):**")
        
        cuval_basi = (
            baseline.get('nakliye', 20) +
            baseline.get('satis_pazarlama', 20.5) +
            baseline.get('pp_cuval', 15) +
            baseline.get('katki_maliyeti', 9)
        )
        
        st.write(f"- Nakliye (çuval): {baseline.get('nakliye', 0):.2f} TL")
        st.write(f"- Pazarlama (çuval): {baseline.get('satis_pazarlama', 0):.2f} TL")
        st.write(f"- PP Çuval: {baseline.get('pp_cuval', 0):.2f} TL")
        st.write(f"- Katkı: {baseline.get('katki_maliyeti', 0):.2f} TL")
        st.write(f"**Çuval Başı Toplam:** {cuval_basi:.2f} TL")
        st.write(f"**1 Ton = 14 Çuval:** {cuval_basi * 14:.2f} TL")
        st.write(f"- Elektrik (ton): {baseline.get('ton_bugday_elektrik', 0):.2f} TL")
        st.markdown(f"**TOPLAM DEĞİŞKEN:** {baseline.get('ton_basi_degisken_gider', 0):,.0f} TL/Ton")
    
    # ===== DEBUG SONU =====
    
    # --- VERİ GÜNCELLİĞİ UYARISI ---
    if baseline and 'tarih' in baseline:
    # --- VERİ GÜNCELLİĞİ UYARISI ---
    if baseline and 'tarih' in baseline:
        try:
            kayit_tarihi = pd.to_datetime(baseline['tarih'])
            readable_date = kayit_tarihi.strftime("%d %B %Y %H:%M")
            st.caption(f"ℹ️ Veriler: **{readable_date}** tarihli son maliyet kaydından alınmıştır.")
        except:
            st.info(f"ℹ️ Veriler sistemdeki son kayıttan alınmıştır.")
    else:
        st.warning("⚠️ Sistemde veri bulunamadı, varsayılan değerler kullanılıyor.")
            
    # --- YENİ NAVİGASYON (BUTONLAR) ---
    # Sekme (Tabs) yerine Radyo Butonları kullanıyoruz
    analiz_secimi = st.radio(
        "Analiz Aracı Seçiniz:",
        ["🎯 Hedef Fiyat (Goal Seek)", "🌡️ Duyarlılık Matrisi", "⚓ Kapasite ve Başabaş", "⚖️ Senaryo Karşılaştırma"],
        horizontal=True,
        label_visibility="collapsed" # Başlığı gizle
    )
    
    st.markdown("---") 
    
    # --- 1. HEDEF ODAKLI HESAPLAMA ---
    if "Hedef Fiyat" in analiz_secimi:
        with st.container(border=True): # ÇERÇEVELİ KUTU
            st.subheader("🎯 Hedeflenen Kara Ulaşmak İçin Fiyat Ne Olmalı?")
            st.info("💡 **Patron Mantığı:** Cebime girmesini istediğim parayı yazıyorum, sistem bana kaçtan satmam gerektiğini söylüyor.")
            
            col_g1, col_g2 = st.columns([1, 2])
            
            with col_g1:
                st.markdown("##### 💰 Hedef Tanımlama")
                target_profit_net = st.number_input(
                    "🎯 Hedeflenen Aylık Net Kar (TL)", 
                    value=2000000.0, step=100000.0, format="%.0f"
                )
                
                with st.expander("📝 Varsayımları Düzenle", expanded=False):
                    g_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=float(baseline.get('bugday_pacal_maliyeti', 14.6)), step=0.10)
                    g_tonaj = st.number_input("Kırılan Buğday (Ton)", value=float(baseline.get('aylik_kirilan_bugday', 3000)), step=100.0)
                    g_sabit_gider = st.number_input("Aylık Sabit Giderler (TL)", value=float(baseline.get('toplam_gider', 45000000)) * 0.10, step=100000.0)
                    current_market_price = st.number_input("Piyasa Un Fiyatı (TL/50kg)", value=float(baseline.get('un_satis_fiyati', 980)), step=5.0)

            with col_g2:
                # Hesaplamalar
                randiman = float(baseline.get('un_randimani', 70))
                un_tonaj = g_tonaj * (randiman / 100)
                cuval_sayisi = (un_tonaj * 1000) / 50
                yan_urun_geliri = (g_tonaj * 1000) * ((100 - randiman) / 100) * 9.0 
                bugday_maliyeti = g_tonaj * 1000 * g_bugday_fiyat
                if g_sabit_gider < 100000: g_sabit_gider = 3000000
                toplam_gider = bugday_maliyeti + g_sabit_gider
                
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
                
                with st.expander("🔍 Detaylı Hesaplama Özeti", expanded=False):
                    st.markdown(f"""
                    - **Üretilecek Un:** {un_tonaj:,.0f} ton ({cuval_sayisi:,.0f} çuval)
                    - **Yan Ürün Geliri:** {yan_urun_geliri:,.0f} TL
                    - **Toplam Gider:** {toplam_gider:,.0f} TL
                    """)

    # --- 2. DUYARLILIK MATRİSİ ---
    elif "Duyarlılık" in analiz_secimi:
        with st.container(border=True): # ÇERÇEVELİ KUTU
            st.subheader("🌡️ Stres Testi: Buğday Zamlanırsa Ne Olur?")
            st.info("💡 **Senaryo:** Buğday fiyatı ve Un satış fiyatı aynı anda değişirse karım ne olur?")
            
            col_s1, col_s2 = st.columns([1, 3])
            
            with col_s1:
                st.markdown("##### ⚙️ Parametreler")
                base_bugday = st.number_input("Baz Buğday (TL/kg)", value=14.50, step=0.10)
                base_un = st.number_input("Baz Un (TL/50kg)", value=950.0, step=10.0)
                
                st.divider()
                # Kritik nokta hesabı
                sim_tonaj = 3000
                sim_sabit = 3000000
                sim_un_geliri = ((sim_tonaj * 0.7 * 1000) / 50) * base_un
                sim_yan_urun = (sim_tonaj * 0.3 * 1000) * 9.0
                total_rev = sim_un_geliri + sim_yan_urun
                kritik_bugday = (total_rev - sim_sabit) / (sim_tonaj * 1000)
                
                st.error(f"**KRİTİK SINIR:** Buğday **{kritik_bugday:.2f} TL** olursa kar SIFIRLANIR.")

            with col_s2:
                bugday_prices = [base_bugday + (i * 0.25) for i in range(-2, 3)]
                un_prices = [base_un + (i * 25) for i in range(-2, 3)]
                
                records = []
                for bf in bugday_prices:
                    for uf in un_prices:
                        profit = calculate_generic_profit(bf, uf, 3000, 70, 3000000, 500) 
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

    # --- 3. KIRILMA NOKTASI ---
    elif "Kapasite" in analiz_secimi:
        with st.container(border=True): # ÇERÇEVELİ KUTU
            st.subheader("⚓ Kapasite ve Başabaş Analizi")
            st.info("💡 **Analiz:** Fabrikayı düşük kapasite çalıştırmanın 'gizli maliyeti' nedir?")
            
            col_b1, col_b2 = st.columns([1, 2])
            
            with col_b1:
                b_sabit = st.number_input("Sabit Giderler (TL)", value=3500000.0, step=100000.0)
                b_kar_marji = st.number_input("Ton Başına Brüt Kar (TL)", value=1200.0, step=50.0)
                tam_kapasite = st.number_input("Tam Kapasite (Ton/Ay)", value=4500.0, step=100.0)
                
            with col_b2:
                break_even_tonaj = b_sabit / b_kar_marji if b_kar_marji > 0 else 0
                st.metric("🎯 ZARARSIZLIK TONAJI (Başabaş)", f"{break_even_tonaj:,.0f} Ton")
                
                caps = np.linspace(500, tam_kapasite, 20)
                sacks = (caps * 0.7 * 1000) / 50
                fixed_per_sack = b_sabit / sacks
                
                df_cap = pd.DataFrame({"Kapasite (Ton)": caps, "Çuval Başı Sabit Maliyet (TL)": fixed_per_sack})
                
                c = alt.Chart(df_cap).mark_line(point=True, color='#e74c3c').encode(
                    x=alt.X('Kapasite (Ton)'),
                    y=alt.Y('Çuval Başı Sabit Maliyet (TL)'),
                    tooltip=['Kapasite (Ton)', 'Çuval Başı Sabit Maliyet (TL)']
                ).interactive()
                st.altair_chart(c, use_container_width=True)
                st.warning("⚠️ Kapasite düştükçe, çuval başına düşen sabit maliyet katlanarak artar!")

    # --- 4. SENARYO KARŞILAŞTIRMA ---
    elif "Senaryo" in analiz_secimi:
        with st.container(border=True): # ÇERÇEVELİ KUTU
            st.subheader("⚖️ Çoklu Senaryo Karşılaştırma")
            st.info("💡 **Simülasyon:** Piyasa iyiye veya kötüye giderse ne olur?")
            
            c_sc1, c_sc2, c_sc3 = st.columns(3)
            
            def scenario_card(col, title, emoji, bg_color, default_bugday, default_un):
                with col:
                    st.markdown(f"### {emoji} {title}")
                    s_bugday = st.number_input("Buğday (TL)", value=default_bugday, key=f"s_b_{title}", step=0.10)
                    s_un = st.number_input("Un (TL)", value=default_un, key=f"s_u_{title}", step=5.0)
                    
                    profit = calculate_generic_profit(s_bugday, s_un, 3000, 70, 3000000, 500)
                    
                    if profit < 0:
                        st.error(f"⚠️ ZARAR: {abs(profit):,.0f} TL")
                    else:
                        st.success(f"✅ KAR: {profit:,.0f} TL")
                    return profit

            p_pessimistic = scenario_card(c_sc1, "Kötümser", "🐻", "#ffcccc", 15.50, 920.0)
            p_realistic = scenario_card(c_sc2, "Gerçekçi", "⚖️", "#f0f0f0", 14.60, 980.0)
            p_optimistic = scenario_card(c_sc3, "İyimser", "🐂", "#ccffcc", 13.80, 1050.0)
            
            st.divider()
            diff = p_optimistic - p_pessimistic
            st.info(f"📊 İyimser ve Kötümser senaryo arasındaki fark: **{diff:,.0f} TL**")







