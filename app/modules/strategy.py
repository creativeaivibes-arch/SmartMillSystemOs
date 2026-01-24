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
                float(latest.get('personel_maasi', 1200000)) +
                float(latest.get('bakim_maliyeti', 100000)) +
                float(latest.get('mutfak_gideri', 50000)) +
                float(latest.get('finans_gideri', 0)) +
                float(latest.get('diger_giderler', 0)) +
                500000  # Kira/Amortisman (sabit varsayım)
            )
            
            # ELEKTRİK: Ton başı değeri al (DEĞİŞKEN GİDER!)
            ton_basi_elektrik = float(latest.get('ton_bugday_elektrik', 500))
            
            # DEĞİŞKEN GİDER: Çuval başı giderleri topla
            cuval_basi_degisken = (
                float(latest.get('nakliye', 20)) +
                float(latest.get('satis_pazarlama', 20.5)) +
                float(latest.get('pp_cuval', 15)) +
                float(latest.get('katki_maliyeti', 9))
            )
            
            # Ton başına değişken gider hesapla
            ton_basi_degisken = (cuval_basi_degisken * 14) + ton_basi_elektrik
            
            latest['aylik_sabit_gider'] = aylik_sabit
            latest['ton_basi_degisken_gider'] = ton_basi_degisken
            
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
        'aylik_sabit_gider': 1850000.0,
        'ton_basi_degisken_gider': 1403,
        'un_cesidi': 'Standart Ekmeklik',
        'un2_orani': 7.0,
        'un2_fiyati': 17.0,
        'bongalite_orani': 1.5,
        'bongalite_fiyati': 11.6,
        'kepek_orani': 9.0,
        'kepek_fiyati': 8.9,
        'razmol_orani': 11.0,
        'razmol_fiyati': 9.1,
        'belge_geliri': 0.0,
        'kirik_tonaj': 0.0,
        'kirik_fiyat': 0.0,
        'basak_tonaj': 0.0,
        'basak_fiyat': 0.0
    }

def calculate_profit_from_baseline(bugday_fiyat_override=None, un_fiyat_override=None, tonaj_override=None, baseline=None):
    """
    Baseline'dan gelen GERÇEK KAYITLI VERİYİ kullanarak kar hesapla.
    Sadece belirtilen parametreleri değiştir, geri kalanı kayıttan al.
    
    Args:
        bugday_fiyat_override: Simülasyon için buğday fiyatı (None ise baseline'dan alır)
        un_fiyat_override: Simülasyon için un fiyatı (None ise baseline'dan alır)
        tonaj_override: Simülasyon için tonaj (None ise baseline'dan alır)
        baseline: get_baseline_data() ile çekilen kayıt
    
    Returns:
        net_kar: Net kar (TL)
    """
    if baseline is None:
        baseline = get_baseline_data()
    
    # Simülasyon parametreleri (override varsa kullan, yoksa baseline'dan al)
    bugday_fiyat = bugday_fiyat_override if bugday_fiyat_override is not None else float(baseline.get('bugday_pacal_maliyeti', 14.6))
    un_fiyat = un_fiyat_override if un_fiyat_override is not None else float(baseline.get('un_satis_fiyati', 980))
    kirilan_tonaj = tonaj_override if tonaj_override is not None else float(baseline.get('aylik_kirilan_bugday', 3000))
    
    # GERİ KALAN HER ŞEY BASELINE'DAN GELİYOR!
    randiman = float(baseline.get('un_randimani', 70))
    
    # === GELİRLER ===
    # 1. Ana Un Geliri
    un_tonaj = kirilan_tonaj * (randiman / 100)
    cuval_sayisi = (un_tonaj * 1000) / 50
    un_geliri = cuval_sayisi * un_fiyat
    
    # 2. Yan Ürün Gelirleri (BASELINE'DAN!)
    toplam_bugday_kg = kirilan_tonaj * 1000
    
    un2_geliri = (toplam_bugday_kg * float(baseline.get('un2_orani', 7)) / 100) * float(baseline.get('un2_fiyati', 17))
    bon_geliri = (toplam_bugday_kg * float(baseline.get('bongalite_orani', 1.5)) / 100) * float(baseline.get('bongalite_fiyati', 11.6))
    kep_geliri = (toplam_bugday_kg * float(baseline.get('kepek_orani', 9)) / 100) * float(baseline.get('kepek_fiyati', 8.9))
    raz_geliri = (toplam_bugday_kg * float(baseline.get('razmol_orani', 11)) / 100) * float(baseline.get('razmol_fiyati', 9.1))
    belge_geliri = float(baseline.get('belge_geliri', 0)) * cuval_sayisi
    kirik_geliri = float(baseline.get('kirik_tonaj', 0)) * float(baseline.get('kirik_fiyat', 0))
    basak_geliri = float(baseline.get('basak_tonaj', 0)) * float(baseline.get('basak_fiyat', 0))
    
    toplam_gelir = un_geliri + un2_geliri + bon_geliri + kep_geliri + raz_geliri + belge_geliri + kirik_geliri + basak_geliri
    
    # === GİDERLER ===
    bugday_maliyeti = kirilan_tonaj * 1000 * bugday_fiyat
    
    # Sabit giderler (BASELINE'DAN!)
    sabit_gider = float(baseline.get('aylik_sabit_gider', 1850000))
    
    # Değişken giderler (BASELINE'DAN!)
    degisken_gider = float(baseline.get('ton_basi_degisken_gider', 1403)) * kirilan_tonaj
    
    toplam_gider = bugday_maliyeti + sabit_gider + degisken_gider
    
    # === NET KAR ===
    return toplam_gelir - toplam_gider

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
                    current_market_price = st.number_input("Piyasa Un Fiyatı (TL/50kg)", value=float(baseline.get('un_satis_fiyati', 980)), step=5.0)
            
            with col_g2:
                # Hesaplamalar
                randiman = float(baseline.get('un_randimani', 70))
                un_tonaj = g_tonaj * (randiman / 100)
                cuval_sayisi = (un_tonaj * 1000) / 50
                
                # Yan ürün ve diğer gelirler (BASELINE'DAN)
                toplam_bugday_kg = g_tonaj * 1000
                yan_urun_geliri = (
                    (toplam_bugday_kg * float(baseline.get('un2_orani', 7)) / 100) * float(baseline.get('un2_fiyati', 17)) +
                    (toplam_bugday_kg * float(baseline.get('bongalite_orani', 1.5)) / 100) * float(baseline.get('bongalite_fiyati', 11.6)) +
                    (toplam_bugday_kg * float(baseline.get('kepek_orani', 9)) / 100) * float(baseline.get('kepek_fiyati', 8.9)) +
                    (toplam_bugday_kg * float(baseline.get('razmol_orani', 11)) / 100) * float(baseline.get('razmol_fiyati', 9.1)) +
                    float(baseline.get('belge_geliri', 0)) * cuval_sayisi +
                    float(baseline.get('kirik_tonaj', 0)) * float(baseline.get('kirik_fiyat', 0)) +
                    float(baseline.get('basak_tonaj', 0)) * float(baseline.get('basak_fiyat', 0))
                )
                
                # Giderler
                bugday_maliyeti = g_tonaj * 1000 * g_bugday_fiyat
                sabit_gider = float(baseline.get('aylik_sabit_gider', 1850000))
                degisken_gider_toplam = float(baseline.get('ton_basi_degisken_gider', 1403)) * g_tonaj
                toplam_gider = bugday_maliyeti + sabit_gider + degisken_gider_toplam
                
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
                    - Sabit Giderler: {sabit_gider:,.0f} TL
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
                
                # ✅ Baseline'dan çek!
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
                    "Kırılan Tonaj (Ton)", 
                    value=float(baseline.get('aylik_kirilan_bugday', 3000.0)), 
                    step=100.0, 
                    key="sens_tonaj"
                )
                
                st.divider()
                
                # ✅ TEMİZ VE AÇIK BİLGİLENDİRME
                st.info(f"""
                📊 **Mevcut Koşullar:**
                - Buğday: **{base_bugday:.2f} TL/kg**
                - Un Satış: **{base_un:.0f} TL/50kg**
                - Kırılan: **{sens_tonaj:,.0f} ton/ay**
                """)
                
                st.caption("👇 Aşağıdaki tabloda farklı fiyat senaryolarının kar/zarar etkisini görebilirsiniz.")

            with col_s2:
                # Matris aralıkları (baz değerlerin etrafında ±2 adım)
                bugday_prices = [base_bugday + (i * 0.50) for i in range(-2, 3)]  # ±1 TL aralık
                un_prices = [base_un + (i * 50) for i in range(-2, 3)]  # ±100 TL aralık
                
                records = []
                for bf in bugday_prices:
                    for uf in un_prices:
                        profit = calculate_profit_from_baseline(
                            bugday_fiyat_override=bf,
                            un_fiyat_override=uf,
                            tonaj_override=sens_tonaj,
                            baseline=baseline
                        )
                        records.append({
                            "Buğday": f"{bf:.2f}",
                            "Un Fiyatı": f"{uf:.0f}",
                            "Net Kar (Bin TL)": int(profit / 1000)
                        })
                
                df_long = pd.DataFrame(records)
                
                base_chart = alt.Chart(df_long).encode(
                    x=alt.X('Un Fiyatı:O', title='Un Satış Fiyatı (TL/50kg)', axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Buğday:O', title='Buğday Maliyeti (TL/kg)'),
                    tooltip=[
                        alt.Tooltip('Buğday:N', title='Buğday Fiyatı'),
                        alt.Tooltip('Un Fiyatı:N', title='Un Fiyatı'),
                        alt.Tooltip('Net Kar (Bin TL):Q', title='Net Kar (Bin TL)', format=',')
                    ]
                )
                heatmap = base_chart.mark_rect().encode(
                    color=alt.Color(
                        'Net Kar (Bin TL):Q', 
                        scale=alt.Scale(scheme='redyellowgreen', domain=[-6000, 6000]),
                        legend=alt.Legend(title="Net Kar (Bin TL)")
                    )
                )
                text = base_chart.mark_text(fontSize=11, fontWeight='bold').encode(
                    text=alt.Text('Net Kar (Bin TL):Q', format=','),
                    color=alt.condition(
                        alt.datum['Net Kar (Bin TL)'] > 500, 
                        alt.value('black'), 
                        alt.value('white')
                    )
                )
                st.altair_chart(heatmap + text, use_container_width=True)
                
                # Yorum Paneli
                st.markdown("---")
                st.markdown("##### 🔍 Hızlı Yorum")
                
                # Mevcut durum karı
                current_profit = calculate_profit_from_baseline(
                    bugday_fiyat_override=base_bugday,
                    un_fiyat_override=base_un,
                    tonaj_override=sens_tonaj,
                    baseline=baseline
                )
                
                col_y1, col_y2 = st.columns(2)
                with col_y1:
                    st.metric("💼 Mevcut Kar", f"{current_profit/1000:,.0f} Bin TL")
                
                with col_y2:
                    # En kötü senaryo
                    worst_profit = calculate_profit_from_baseline(
                        bugday_fiyat_override=max(bugday_prices),
                        un_fiyat_override=min(un_prices),
                        tonaj_override=sens_tonaj,
                        baseline=baseline
                    )
                    st.metric(
                        "⚠️ En Kötü Senaryo", 
                        f"{worst_profit/1000:,.0f} Bin TL",
                        delta=f"{(worst_profit - current_profit)/1000:,.0f} Bin TL",
                        delta_color="inverse"
                    )
                
                # Risk değerlendirmesi
                if worst_profit < 0:
                    st.error("🚨 **YÜKSEK RİSK:** Buğday zamlanıp un düşerse zarar riski var!")
                elif worst_profit > current_profit * 0.5:
                    st.success("✅ **DÜŞÜK RİSK:** En kötü senaryoda bile makul kar var.")
                else:
                    st.warning("⚠️ **ORTA RİSK:** Kötü senaryoda kar önemli ölçüde azalıyor.")
                
                st.caption("📊 **Renk Kodu:** Koyu Yeşil = Yüksek Kar | Açık Yeşil = Orta Kar | Sarı = Düşük Kar | Kırmızı = Zarar")

    # --- 3. KIRILMA NOKTASI ---
    elif "Kapasite" in analiz_secimi:
        with st.container(border=True):
            st.subheader("⚓ Kapasite ve Başabaş Analizi")
            st.info("💡 **Analiz:** Fabrikayı düşük kapasite çalıştırmanın 'gizli maliyeti' nedir?")
            
            col_b1, col_b2 = st.columns([1, 2])
            
            with col_b1:
                b_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=float(baseline.get('bugday_pacal_maliyeti', 14.60)), step=0.10, key="kap_bugday")
                b_un_fiyat = st.number_input("Un Satış (TL/50kg)", value=float(baseline.get('un_satis_fiyati', 980.0)), step=10.0, key="kap_un")
                tam_kapasite = st.number_input("Tam Kapasite (Ton/Ay)", value=4500.0, step=100.0, key="kap_tam")
                
            with col_b2:
                # Başabaş tonajı bulmak için binary search
                min_tonaj = 100
                max_tonaj = tam_kapasite
                break_even_tonaj = 0
                
                for _ in range(50):  # 50 iterasyon yeterli
                    mid_tonaj = (min_tonaj + max_tonaj) / 2
                    profit = calculate_profit_from_baseline(
                        bugday_fiyat_override=b_bugday_fiyat,
                        un_fiyat_override=b_un_fiyat,
                        tonaj_override=mid_tonaj,
                        baseline=baseline
                    )
                    
                    if abs(profit) < 10000:  # 10K TL tolerans
                        break_even_tonaj = mid_tonaj
                        break
                    elif profit < 0:
                        min_tonaj = mid_tonaj
                    else:
                        max_tonaj = mid_tonaj
                
                if break_even_tonaj == 0:
                    break_even_tonaj = min_tonaj
                
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
                    profit = calculate_profit_from_baseline(
                        bugday_fiyat_override=b_bugday_fiyat,
                        un_fiyat_override=b_un_fiyat,
                        tonaj_override=cap,
                        baseline=baseline
                    )
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
                



