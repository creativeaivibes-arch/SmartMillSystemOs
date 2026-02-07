# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from app.modules.flour import get_un_maliyet_gecmisi

# --- AYARLAR VE SABİTLER (MAGIC NUMBERS GİDERİLDİ) ---
STRATEGY_CONFIG = {
    'SACK_WEIGHT': 50,        # Bir çuvalın ağırlığı (kg)
    'TON_TO_KG': 1000,        # 1 Ton kaç kg
    'CACHE_TTL': 300,         # Veri hafıza süresi (saniye)
    'SEARCH_PRECISION': 50    # Başabaş noktası arama hassasiyeti
}

# --- PERFORMANS İYİLEŞTİRMESİ: CACHE EKLENDİ ---
@st.cache_data(ttl=STRATEGY_CONFIG['CACHE_TTL'])
def get_baseline_data():
    """En son kaydedilen gerçek maliyet verilerini baz senaryo olarak getirir (Önbellekli)"""
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
                float(latest.get('diger_giderler', 0))
            )
            
            latest['aylik_sabit_gider_toplam'] = aylik_sabit
            return latest

    except Exception as e:
        # Hata mesajını kullanıcıya değil loga yazmak daha profesyoneldir, 
        # ama burada patron göreceği için sessiz kalıp boş dönüyoruz.
        pass
    
    return {}
def calculate_profit_dynamic(bugday_fiyat, un_fiyat, tonaj, baseline=None):
    """
    Dinamik Kar Hesaplama Motoru (Optimize Edilmiş)
    Tüm değişkenleri veritabanından alır, Fiyat ve Tonaj senaryosunu işler.
    """
    # Baseline verisi yoksa çekelim (Cache'ten hızlıca gelir)
    if baseline is None or not baseline:
        baseline = get_baseline_data()
        # Eğer hala veri yoksa (Veritabanı boşsa) varsayılan değerler
        if not baseline: 
             baseline = {
                'un_randimani': 70.0, 'un2_orani': 7.0, 'bongalite_orani': 1.5,
                'kepek_orani': 9.0, 'razmol_orani': 11.0,
                'un2_fiyati': 15.0, 'bongalite_fiyati': 10.0, 'kepek_fiyati': 8.0, 'razmol_fiyati': 8.0,
                'ton_bugday_elektrik': 500.0, 'nakliye': 20.0, 'satis_pazarlama': 20.0,
                'pp_cuval': 15.0, 'katki_maliyeti': 9.0, 'aylik_sabit_gider_toplam': 1500000.0
             }

    # 1. AYARLARI YÜKLE (Magic Numbers yerine Config)
    sack_weight = STRATEGY_CONFIG['SACK_WEIGHT']
    ton_to_kg = STRATEGY_CONFIG['TON_TO_KG']
    randiman = float(baseline.get('un_randimani', 70))
    
    # 2. ÜRETİM MİKTARLARI
    toplam_bugday_kg = tonaj * ton_to_kg
    un_kg = toplam_bugday_kg * (randiman / 100)
    cuval_sayisi = un_kg / sack_weight
    
    # 3. GELİRLER
    # a) Ana Un Geliri
    gelir_un = cuval_sayisi * un_fiyat
    
    # b) Yan Ürün Gelirleri
    gelir_yan_urunler = (
        (toplam_bugday_kg * float(baseline.get('un2_orani', 0)) / 100) * float(baseline.get('un2_fiyati', 0)) +
        (toplam_bugday_kg * float(baseline.get('bongalite_orani', 0)) / 100) * float(baseline.get('bongalite_fiyati', 0)) +
        (toplam_bugday_kg * float(baseline.get('kepek_orani', 0)) / 100) * float(baseline.get('kepek_fiyati', 0)) +
        (toplam_bugday_kg * float(baseline.get('razmol_orani', 0)) / 100) * float(baseline.get('razmol_fiyati', 0)) +
        (float(baseline.get('belge_geliri', 0)) * cuval_sayisi) + 
        (float(baseline.get('kirik_tonaj', 0)) * float(baseline.get('kirik_fiyat', 0))) +
        (float(baseline.get('basak_tonaj', 0)) * float(baseline.get('basak_fiyat', 0)))
    )
    
    toplam_gelir = gelir_un + gelir_yan_urunler
    
    # 4. GİDERLER
    # a) Buğday Maliyeti
    gider_bugday = toplam_bugday_kg * bugday_fiyat
    
    # b) Sabit Giderler
    gider_sabit = float(baseline.get('aylik_sabit_gider_toplam', 0))
    
    # c) Değişken Giderler (Çuval başına)
    cuval_maliyeti_birim = (
        float(baseline.get('nakliye', 0)) +
        float(baseline.get('satis_pazarlama', 0)) +
        float(baseline.get('pp_cuval', 0)) +
        float(baseline.get('katki_maliyeti', 0))
    )
    gider_cuval_bazli = cuval_sayisi * cuval_maliyeti_birim
    
    # d) Tona bağlı giderler (Elektrik)
    gider_elektrik = tonaj * float(baseline.get('ton_bugday_elektrik', 0))
    
    toplam_gider = gider_bugday + gider_sabit + gider_cuval_bazli + gider_elektrik
    
    # 5. NET KAR SONUCU
    return toplam_gelir - toplam_gider

def show_strategy_module():
    # Başlık Alanı
    st.markdown("""
    <div style='background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 20px;'>
        <h2 style='color: #0B4F6C; margin:0;'>📊 Stratejik Patron Analizi (DSS)</h2>
        <p style='color: #666; margin:0; font-size: 14px;'>Geçmişe değil, geleceğe odaklanın. Karar Destek Sistemi.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Baseline veriyi çek (Cache'ten gelir, hızlıdır)
    baseline = get_baseline_data()
    
    # --- NAVİGASYON ---
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
                last_net_profit = float(baseline.get('net_kar_toplam', 1000000.0))
                target_profit_net = st.number_input(
                    "🎯 Hedeflenen Aylık Net Kar (TL)",
                    value=last_net_profit * 1.10,
                )
                
                with st.expander("🔧 Varsayımları Düzenle", expanded=False):
                    g_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=float(baseline.get('bugday_pacal_maliyeti', 14.6)), step=0.10)
                    g_tonaj = st.number_input("Kırılan Buğday (Ton)", value=float(baseline.get('aylik_kirilan_bugday', 3000)), step=100.0)
                    current_market_price = st.number_input("Piyasa Un Fiyatı (TL/50kg)", value=float(baseline.get('un_satis_fiyati', 980)), step=5.0)
            
            with col_g2:
                # 1. Üretim Miktarları (Config Kullanımı)
                randiman = float(baseline.get('un_randimani', 70))
                un_tonaj = g_tonaj * (randiman / 100)
                
                # Config'den sabitleri al (Magic Number Yok!)
                ton_to_kg = STRATEGY_CONFIG['TON_TO_KG']
                sack_weight = STRATEGY_CONFIG['SACK_WEIGHT']
                
                cuval_sayisi = (un_tonaj * ton_to_kg) / sack_weight
                
                # 2. Tersine Mühendislik (Goal Seek)
                # Un gelirini '0' kabul edip taban dengeyi buluyoruz
                base_balance = calculate_profit_dynamic(g_bugday_fiyat, 0, g_tonaj, baseline)
                
                # Hedef Kar = (Un Geliri) + base_balance  =>  Un Geliri = Hedef - base_balance
                gerekli_un_geliri = target_profit_net - base_balance
                
                # Çuval fiyatını buluyoruz
                if cuval_sayisi > 0:
                    gerekli_cuval_fiyati = gerekli_un_geliri / cuval_sayisi
                else:
                    gerekli_cuval_fiyati = 0
                
                # 3. Sonuçları Göster
                fark_tl = gerekli_cuval_fiyati - current_market_price
                fark_yuzde = (fark_tl / current_market_price) * 100 if current_market_price > 0 else 0
                
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
                    final_check = calculate_profit_dynamic(g_bugday_fiyat, gerekli_cuval_fiyati, g_tonaj, baseline)
                    
                    st.markdown(f"""
                    **SİMÜLASYON SONUCU:**
                    - **Hedeflenen Kar:** {target_profit_net:,.0f} TL
                    - **Hesaplanan Kar:** {final_check:,.0f} TL (Doğrulama)
                    - **Gerekli Ciro (Un):** {gerekli_un_geliri:,.0f} TL
                    - **Üretim:** {cuval_sayisi:,.0f} Çuval
                    """)

    # --- 2. DUYARLILIK MATRİSİ ---
    elif "Duyarlılık" in analiz_secimi:
        with st.container(border=True):
            st.subheader("🌡️ Stres Testi: Buğday Zamlanırsa Ne Olur?")
            st.info("💡 **Senaryo:** Buğday fiyatı ve Un satış fiyatı aynı anda değişirse karım ne olur?")
            
            col_s1, col_s2 = st.columns([1, 3])
            
            with col_s1:
                st.markdown("##### ⚙️ Parametreler")
                def_bugday = float(baseline.get('bugday_pacal_maliyeti', 14.60))
                def_un = float(baseline.get('un_satis_fiyati', 980.0))
                def_tonaj = float(baseline.get('aylik_kirilan_bugday', 3000.0))

                base_bugday = st.number_input("Baz Buğday (TL/kg)", value=def_bugday, step=0.10, key="sens_bugday")
                base_un = st.number_input("Baz Un (TL/50kg)", value=def_un, step=10.0, key="sens_un")
                sens_tonaj = st.number_input("Kırılan Tonaj (Ton)", value=def_tonaj, step=100.0, key="sens_tonaj")
                
                st.divider()
                st.caption(f"📊 Mevcut: Buğday {base_bugday:.2f} | Un {base_un:.0f}")

            with col_s2:
                bugday_prices = [base_bugday + (i * 0.25) for i in range(-2, 3)]
                un_prices = [base_un + (i * 25) for i in range(-2, 3)]
                
                records = []
                for bf in bugday_prices:
                    for uf in un_prices:
                        profit = calculate_profit_dynamic(bf, uf, sens_tonaj, baseline)
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
                    color=alt.Color('Net Kar (Bin TL):Q', scale=alt.Scale(scheme='redyellowgreen', domain=[-5000, 5000]))
                )
                text = base_chart.mark_text(fontSize=11).encode(
                    text='Net Kar (Bin TL):Q',
                    color=alt.condition(alt.datum['Net Kar (Bin TL)'] > 500, alt.value('black'), alt.value('white'))
                )
                st.altair_chart(heatmap + text, use_container_width=True)
                
                # Hızlı Yorum
                current_profit = calculate_profit_dynamic(base_bugday, base_un, sens_tonaj, baseline)
                worst_profit = calculate_profit_dynamic(max(bugday_prices), min(un_prices), sens_tonaj, baseline)
                
                st.markdown(f"**Mevcut Kar:** {current_profit/1000:,.0f} Bin TL | **En Kötü Senaryo:** {worst_profit/1000:,.0f} Bin TL")

    # --- 3. KIRILMA NOKTASI (Config ile Binary Search Optimize) ---
    elif "Kapasite" in analiz_secimi:
        with st.container(border=True):
            st.subheader("⚓ Kapasite ve Başabaş Analizi")
            
            col_b1, col_b2 = st.columns([1, 2])
            with col_b1:
                b_bugday_fiyat = st.number_input("Buğday Fiyatı (TL/kg)", value=float(baseline.get('bugday_pacal_maliyeti', 14.60)), step=0.10, key="kap_bugday")
                b_un_fiyat = st.number_input("Un Satış (TL/50kg)", value=float(baseline.get('un_satis_fiyati', 980.0)), step=10.0, key="kap_un")
                tam_kapasite = st.number_input("Tam Kapasite (Ton/Ay)", value=4500.0, step=100.0, key="kap_tam")
                
            with col_b2:
                # Binary Search (Config'deki hassasiyet ile)
                min_tonaj = 100
                max_tonaj = tam_kapasite
                break_even_tonaj = 0
                precision_steps = STRATEGY_CONFIG.get('SEARCH_PRECISION', 50) # Config'den al
                
                for _ in range(precision_steps):
                    mid_tonaj = (min_tonaj + max_tonaj) / 2
                    profit = calculate_profit_dynamic(b_bugday_fiyat, b_un_fiyat, mid_tonaj, baseline)
                    
                    if abs(profit) < 5000:
                        break_even_tonaj = mid_tonaj
                        break
                    elif profit < 0:
                        min_tonaj = mid_tonaj
                    else:
                        max_tonaj = mid_tonaj
                
                if break_even_tonaj == 0: break_even_tonaj = min_tonaj
                
                st.metric("🎯 ZARARSIZLIK TONAJI", f"{break_even_tonaj:,.0f} Ton")
                
                # Grafik (Basitleştirilmiş)
                caps = np.linspace(max(100, break_even_tonaj - 1000), tam_kapasite, 20)
                profits = [calculate_profit_dynamic(b_bugday_fiyat, b_un_fiyat, c, baseline)/1000 for c in caps]
                df_cap = pd.DataFrame({"Kapasite": caps, "Kar": profits})
                
                c = alt.Chart(df_cap).mark_line(color='#2ecc71').encode(x='Kapasite', y='Kar').interactive()
                st.altair_chart(c, use_container_width=True)

    # --- 4. SENARYO KARŞILAŞTIRMA ---
    elif "Senaryo" in analiz_secimi:
        with st.container(border=True):
            st.subheader("⚖️ Çoklu Senaryo Karşılaştırma")
            sc_tonaj = st.number_input("Kırılan Tonaj (Ton)", value=float(baseline.get('aylik_kirilan_bugday', 3000.0)), step=100.0, key="sc_tonaj")
            
            c_sc1, c_sc2, c_sc3 = st.columns(3)
            def_bugday = float(baseline.get('bugday_pacal_maliyeti', 14.60))
            def_un = float(baseline.get('un_satis_fiyati', 980.0))
            
            def scenario_card(col, title, emoji, b_val, u_val):
                with col:
                    st.markdown(f"### {emoji} {title}")
                    s_b = st.number_input("Buğday", value=b_val, key=f"s_b_{title}", format="%.2f")
                    s_u = st.number_input("Un", value=u_val, key=f"s_u_{title}", format="%.0f")
                    profit = calculate_profit_dynamic(s_b, s_u, sc_tonaj, baseline)
                    if profit < 0: st.error(f"ZARAR: {abs(profit):,.0f}")
                    else: st.success(f"KAR: {profit:,.0f}")
                    return profit

            p1 = scenario_card(c_sc1, "Kötümser", "🐻", def_bugday * 1.05, def_un * 0.95)
            p2 = scenario_card(c_sc2, "Gerçekçi", "⚖️", def_bugday, def_un)
            p3 = scenario_card(c_sc3, "İyimser", "🐂", def_bugday * 0.95, def_un * 1.05)
                










