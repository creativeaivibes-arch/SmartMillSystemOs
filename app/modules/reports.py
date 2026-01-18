import io
from datetime import datetime
import pandas as pd
import streamlit as st
from app.core.utils import turkce_karakter_duzelt

try:
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.platypus.flowables import HRFlowable, KeepTogether
    from reportlab.lib.pagesizes import A4
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

def turkce_karakter_duzelt_pdf(text):
    """PDF için Türkçe karakter düzeltme"""
    return turkce_karakter_duzelt(text)
import io
from datetime import datetime
import pandas as pd
import streamlit as st
from app.core.utils import turkce_karakter_duzelt

try:
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.platypus.flowables import HRFlowable, KeepTogether
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

def turkce_karakter_duzelt_pdf(text):
    """PDF için Türkçe karakter düzeltme"""
    return turkce_karakter_duzelt(text)

def create_silo_pdf_report(silo_name, silo_data, tavli_ortalamalari=None, kuru_ortalamalari=None):
    """
    Silo için profesyonel PDF raporu oluştur (TEK SAYFA OPTIMIZE)
    
    Args:
        silo_name: Silo adı
        silo_data: Silo genel bilgileri (dict)
        tavli_ortalamalari: Tavlı buğday analiz ortalamaları (dict)
        kuru_ortalamalari: Kuru buğday analiz ortalamaları (dict)
    """
    
    if not PDF_AVAILABLE:
        st.error("PDF oluşturma için 'reportlab' kütüphanesi kurulu değil!")
        return None
    
    try:
        # PDF dosyasını bellekten oluştur
        buffer = io.BytesIO()
        
        # PDF oluşturma - KOMPAKT MARGIN
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=12*mm,
            bottomMargin=12*mm
        )
        
        # Stiller
        styles = getSampleStyleSheet()
        
        # Başlık stili - KOMPAKT
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor('#0B4F6C'),
            alignment=1,  # ORTALANMIŞ
            spaceAfter=8,
            spaceBefore=0
        )
        
        # Alt başlık stili - KOMPAKT
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=colors.HexColor('#1E2A3A'),
            alignment=0,
            spaceAfter=4,
            spaceBefore=6
        )
        
        # Mini başlık stili
        mini_title_style = ParagraphStyle(
            'MiniTitle',
            parent=styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=colors.HexColor('#0B4F6C'),
            alignment=0,
            spaceAfter=3,
            spaceBefore=3
        )
        
        # Normal metin stili
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2
        )
        
        # Bold metin stili
        bold_style = ParagraphStyle(
            'CustomBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2
        )
        
        # İçerik oluştur
        story = []
        
        # BAŞLIK
        silo_name_fixed = turkce_karakter_duzelt_pdf(silo_name)
        story.append(Paragraph(f"SILO KALITE KONTROL RAPORU", title_style))
        story.append(Paragraph(f"<b>{silo_name_fixed}</b> | {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
        story.append(Spacer(1, 6))
        
        # ========== GENEL BİLGİLER + KURU BUGDAY (YAN YANA 2 KOLON) ==========
        col_data = []
        
        # SOL KOLON: Genel Bilgiler
        bugday_cinsi = turkce_karakter_duzelt_pdf(str(silo_data.get('bugday_cinsi', '-')).strip())
        kapasite = float(silo_data.get('kapasite', 1))
        mevcut = float(silo_data.get('mevcut_miktar', 0))
        doluluk = (mevcut / kapasite * 100) if kapasite > 0 else 0
        
        genel_text = f"""
<b>GENEL BILGILER</b><br/>
Bugday Cinsi: {bugday_cinsi}<br/>
Toplam Miktar: {mevcut:,.1f} Ton<br/>
Kapasite: {kapasite:,.0f} Ton<br/>
Doluluk: %{doluluk:.1f}<br/>
Maliyet: {float(silo_data.get('maliyet', 0)):,.2f} TL/KG<br/>
Tavli Stok: {float(silo_data.get('tavli_bugday_stok', 0)):,.1f} Ton
"""
        
        # SAĞ KOLON: Kuru Buğday
        kuru_text = "<b>KURU BUGDAY ANALIZI</b><br/>"
        if kuru_ortalamalari and len(kuru_ortalamalari) > 0:
            kuru_params = [
                ('hektolitre', 'Hektolitre', '%.1f'),
                ('protein', 'Protein', '%.1f %%'),
                ('rutubet', 'Rutubet', '%.1f %%'),
                ('gluten', 'Gluten', '%.1f %%'),
                ('gluten_index', 'Gluten Index', '%.0f'),
                ('sedim', 'Sedimantasyon', '%.1f ml'),
                ('gecikmeli_sedim', 'Gec. Sedim', '%.1f ml')
            ]
            
            for param_key, param_label, param_format in kuru_params:
                if param_key in kuru_ortalamalari and kuru_ortalamalari[param_key] > 0:
                    value = kuru_ortalamalari[param_key]
                    kuru_text += f"{param_label}: {param_format % value}<br/>"
        else:
            kuru_text += "Henuz kayit yok"
        
        col_data.append([
            Paragraph(genel_text, normal_style),
            Paragraph(kuru_text, normal_style)
        ])
        
        col_table = Table(col_data, colWidths=[90*mm, 90*mm])
        col_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E6F3F7')),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#D4EDDA')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        story.append(col_table)
        story.append(Spacer(1, 6))
        
        # ========== TAVLI BUGDAY ANALIZLERI (3 KOLON) ==========
        if tavli_ortalamalari and tavli_ortalamalari.get('toplam_tonaj', 0) > 0:
            
            story.append(Paragraph("TAVLI BUGDAY ANALIZ SONUCLARI", subtitle_style))
            
            # 3 KOLON: Kimyasal | Farinograph | Extensograph
            analiz_row = []
            
            # KOLON 1: Kimyasal
            kimya_text = "<b>Kimyasal</b><br/>"
            kimya_params = [
                ('protein', 'Protein', '%.1f%%'),
                ('rutubet', 'Rutubet', '%.1f%%'),
                ('gluten', 'Gluten', '%.1f%%'),
                ('gluten_index', 'G.Index', '%.0f'),
                ('sedim', 'Sedim', '%.1f ml'),
                ('g_sedim', 'G.Sedim', '%.1f ml'),
                ('fn', 'F.N', '%.0f'),
                ('ffn', 'F.F.N', '%.0f')
            ]
            
            for param_key, param_label, param_format in kimya_params:
                if tavli_ortalamalari.get(param_key, 0) > 0:
                    value = tavli_ortalamalari[param_key]
                    kimya_text += f"{param_label}: {param_format % value}<br/>"
            
            # KOLON 2: Farinograph
            farino_text = "<b>Farinograph</b><br/>"
            farino_params = [
                ('su_kaldirma_f', 'Su Kald.', '%.1f%%'),
                ('gelisme_suresi', 'Gelisme', '%.1f dk'),
                ('stabilite', 'Stabilite', '%.1f dk'),
                ('yumusama', 'Yumusama', '%.0f FU')
            ]
            
            for param_key, param_label, param_format in farino_params:
                if tavli_ortalamalari.get(param_key, 0) > 0:
                    value = tavli_ortalamalari[param_key]
                    farino_text += f"{param_label}: {param_format % value}<br/>"
            
            # KOLON 3: Extensograph (KOMPAKT)
            extenso_text = "<b>Extensograph</b><br/>"
            if tavli_ortalamalari.get('su_kaldirma_e', 0) > 0:
                extenso_text += f"Su Kald: {tavli_ortalamalari['su_kaldirma_e']:.1f}%<br/>"
            
            for dakika in ['45', '90', '135']:
                enerji_key = f'enerji{dakika}'
                direnc_key = f'direnc{dakika}'
                taban_key = f'taban{dakika}'
                
                if any([tavli_ortalamalari.get(enerji_key, 0) > 0,
                       tavli_ortalamalari.get(direnc_key, 0) > 0,
                       tavli_ortalamalari.get(taban_key, 0) > 0]):
                    
                    extenso_text += f"<b>{dakika}'</b> "
                    
                    if tavli_ortalamalari.get(enerji_key, 0) > 0:
                        extenso_text += f"E:{tavli_ortalamalari[enerji_key]:.0f} "
                    if tavli_ortalamalari.get(direnc_key, 0) > 0:
                        extenso_text += f"D:{tavli_ortalamalari[direnc_key]:.0f} "
                    if tavli_ortalamalari.get(taban_key, 0) > 0:
                        extenso_text += f"T:{tavli_ortalamalari[taban_key]:.0f}"
                    
                    extenso_text += "<br/>"
            
            analiz_row.append([
                Paragraph(kimya_text, normal_style),
                Paragraph(farino_text, normal_style),
                Paragraph(extenso_text, normal_style)
            ])
            
            analiz_table = Table(analiz_row, colWidths=[60*mm, 60*mm, 60*mm])
            analiz_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F8F9FA')),
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#FFF3CD')),
                ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#E6F3F7')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]))
            
            story.append(analiz_table)
        else:
            story.append(Paragraph("TAVLI BUGDAY ANALIZ SONUCLARI", subtitle_style))
            story.append(Paragraph("Bu silo icin henuz tavli bugday analiz kaydi bulunmamaktadir.", normal_style))
        
        # ALT BİLGİ
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            textColor=colors.grey,
            alignment=1
        )
        
        story.append(Paragraph(f"Smart Mill System OS - Silo Kalite Kontrol Raporu | {datetime.now().strftime('%d/%m/%Y')}", footer_style))
        
        # PDF'yi oluştur
        doc.build(story)
        
        # Buffer'dan PDF verisini al
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
        
    except Exception as e:
        st.error(f"PDF olusturma hatasi: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None


def create_pacal_pdf_report(tarih, urun_adi, oranlar, analizler):
    """
    Paçal için profesyonel PDF raporu oluştur
    """
    
    if not PDF_AVAILABLE:
        st.error("PDF oluşturma için 'reportlab' kütüphanesi kurulu değil!")
        return None
    
    try:
        # PDF dosyasını bellekten oluştur
        buffer = io.BytesIO()
        
        # PDF oluşturma - TEK SAYFA
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )
        
        # Stiller
        styles = getSampleStyleSheet()
        
        # Başlık stili
        title_style = ParagraphStyle(
            'PacalTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=colors.HexColor('#0B4F6C'),
            alignment=1,
            spaceAfter=15
        )
        
        # Alt başlık stili
        subtitle_style = ParagraphStyle(
            'PacalSubtitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#1E2A3A'),
            alignment=0,
            spaceAfter=8
        )
        
        # Bold metin stili
        bold_style = ParagraphStyle(
            'PacalBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=colors.black,
            alignment=0,
            spaceAfter=4,
        )
        
        # Normal metin stili
        normal_style = ParagraphStyle(
            'PacalNormal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            textColor=colors.black,
            alignment=0,
            spaceAfter=4,
        )
        
        # Küçük metin stili
        small_style = ParagraphStyle(
            'PacalSmall',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2,
        )
        
        # İçerik oluştur
        story = []
        
        # BAŞLIK
        baslik = turkce_karakter_duzelt_pdf("PAÇAL ÜRETİM RAPORU")
        story.append(Paragraph(baslik, title_style))
        story.append(Spacer(1, 10))
        
        # Temel bilgiler
        urun_adi_fixed = turkce_karakter_duzelt_pdf(urun_adi)
        rapor_tarihi = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        story.append(Paragraph(f"{turkce_karakter_duzelt_pdf('Ürün Adı:')} {urun_adi_fixed}", bold_style))
        story.append(Paragraph(f"{turkce_karakter_duzelt_pdf('Paçal Tarihi:')} {tarih}", bold_style))
        story.append(Paragraph(f"{turkce_karakter_duzelt_pdf('Rapor Tarihi:')} {rapor_tarihi}", bold_style))
        story.append(Spacer(1, 15))
        
        # ========== 1. SILO ORANLARI ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("1. SILO KULLANIM ORANLARI"), subtitle_style))
        story.append(Spacer(1, 5))
        
        # Silo oranları tablosu
        if oranlar:
            oran_data = []
            
            # Başlık satırı
            oran_data.append([
                turkce_karakter_duzelt_pdf("Silo"),
                turkce_karakter_duzelt_pdf("Oran (%)"),
                turkce_karakter_duzelt_pdf("Silo"),
                turkce_karakter_duzelt_pdf("Oran (%)")
            ])
            
            # Oranları listeye dönüştür ve sırala
            oran_listesi = [(silo, oran) for silo, oran in oranlar.items() if oran > 0]
            oran_listesi.sort(key=lambda x: x[1], reverse=True)
            
            # 2'li gruplar halinde düzenle
            for i in range(0, len(oran_listesi), 2):
                row = []
                for j in range(2):
                    if i + j < len(oran_listesi):
                        silo, oran = oran_listesi[i + j]
                        silo_fixed = turkce_karakter_duzelt_pdf(silo)
                        row.extend([silo_fixed, f"{oran:.1f}%"])
                    else:
                        row.extend(["", ""])
                
                oran_data.append(row)
            
            # Toplam oran
            toplam_oran = sum(oran for _, oran in oran_listesi)
            oran_data.append([
                turkce_karakter_duzelt_pdf("TOPLAM"),
                f"{toplam_oran:.1f}%",
                "",
                ""
            ])
            
            # Oranlar tablosu
            oran_table = Table(oran_data, colWidths=[100, 60, 100, 60])
            oran_table.setStyle(TableStyle([
                # Başlık satırı
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F81BD')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                
                # Veri satırları
                ('ALIGN', (0, 1), (-2, -2), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
                ('FONTNAME', (0, 1), (-2, -2), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (-1, -2), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -2), 9),
                ('BOTTOMPADDING', (0, 1), (-1, -2), 6),
                ('TOPPADDING', (0, 1), (-1, -2), 6),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.lightgrey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8F9FA')]),
                
                # Toplam satırı
                ('BACKGROUND', (0, -1), (1, -1), colors.HexColor('#E6F3F7')),
                ('FONTNAME', (0, -1), (1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (1, -1), 10),
                ('TEXTCOLOR', (0, -1), (1, -1), colors.HexColor('#0B4F6C')),
                ('ALIGN', (0, -1), (1, -1), 'CENTER'),
            ]))
            
            story.append(oran_table)
            story.append(Spacer(1, 15))
        
        # ========== 2. PAÇAL ANALİZ SONUÇLARI ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("2. PAÇAL ANALİZ SONUÇLARI"), subtitle_style))
        story.append(Spacer(1, 5))
        
        if analizler and isinstance(analizler, dict):
            # Maliyet bilgisi
            if 'maliyet' in analizler:
                maliyet_text = f"{turkce_karakter_duzelt_pdf('Paçal Maliyeti:')} {analizler['maliyet']:.2f} TL/KG"
                story.append(Paragraph(maliyet_text, bold_style))
                story.append(Spacer(1, 10))
            
            # ========== 2.1 KİMYASAL ANALİZLER ==========
            story.append(Paragraph(turkce_karakter_duzelt_pdf("2.1 Kimyasal Analizler"), bold_style))
            
            # Kimyasal analiz tablosu
            kimya_data = []
            
            # Başlık satırı
            kimya_data.append([
                turkce_karakter_duzelt_pdf("Parametre"),
                turkce_karakter_duzelt_pdf("Değer"),
                turkce_karakter_duzelt_pdf("Parametre"),
                turkce_karakter_duzelt_pdf("Değer")
            ])
            
            # Kimyasal parametreler
            kimya_params = [
                (turkce_karakter_duzelt_pdf("Protein"), 'protein', '%.1f %%'),
                (turkce_karakter_duzelt_pdf("Rutubet"), 'rutubet', '%.1f %%'),
                (turkce_karakter_duzelt_pdf("Gluten"), 'gluten', '%.1f %%'),
                (turkce_karakter_duzelt_pdf("Gluten Index"), 'gluten_index', '%.0f'),
                (turkce_karakter_duzelt_pdf("Sedimantasyon"), 'sedim', '%.1f ml'),
                (turkce_karakter_duzelt_pdf("Gecikmeli Sedim"), 'g_sedim', '%.1f ml'),
                (turkce_karakter_duzelt_pdf("F.N"), 'fn', '%.0f'),
                (turkce_karakter_duzelt_pdf("F.F.N"), 'ffn', '%.0f'),
                (turkce_karakter_duzelt_pdf("Kül"), 'kul', '%.2f %%'),
            ]
            
            # 2'li gruplar halinde düzenle
            for i in range(0, len(kimya_params), 2):
                row = []
                for j in range(2):
                    if i + j < len(kimya_params):
                        param_label, param_key, param_format = kimya_params[i + j]
                        
                        if param_key in analizler and analizler[param_key] > 0:
                            value = param_format % analizler[param_key]
                        else:
                            value = "-"
                        
                        row.extend([param_label, value])
                    else:
                        row.extend(["", ""])
                
                kimya_data.append(row)
            
            # Kimyasal tablo
            if kimya_data:
                kimya_table = Table(kimya_data, colWidths=[95, 65, 95, 65])
                kimya_table.setStyle(TableStyle([
                    # Başlık satırı
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F3F7')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0B4F6C')),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    
                    # Veri satırları
                    ('ALIGN', (0, 1), (-2, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 1), (-2, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                    ('TOPPADDING', (0, 1), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F7FF')]),
                ]))
                story.append(kimya_table)
            
            story.append(Spacer(1, 10))
            
            # ========== 2.2 FARINOGRAPH ANALİZLERİ ==========
            farino_vars = False
            farino_params = [
                ('su_kaldirma_f', '%.1f %%'),
                ('gelisme_suresi', '%.1f dk'),
                ('stabilite', '%.1f dk'),
                ('yumusama', '%.0f FU'),
            ]
            
            for param_key, _ in farino_params:
                if param_key in analizler and analizler[param_key] > 0:
                    farino_vars = True
                    break
            
            if farino_vars:
                story.append(Paragraph(turkce_karakter_duzelt_pdf("2.2 Farinograph Analizleri"), bold_style))
                
                # Farinograph tablosu
                farino_data = []
                
                # Başlık satırı
                farino_data.append([
                    turkce_karakter_duzelt_pdf("Parametre"),
                    turkce_karakter_duzelt_pdf("Değer"),
                    turkce_karakter_duzelt_pdf("Parametre"),
                    turkce_karakter_duzelt_pdf("Değer")
                ])
                
                farino_params_detay = [
                    (turkce_karakter_duzelt_pdf("Su Kaldırma"), 'su_kaldirma_f', '%.1f %%'),
                    (turkce_karakter_duzelt_pdf("Gelişme Süresi"), 'gelisme_suresi', '%.1f dk'),
                    (turkce_karakter_duzelt_pdf("Stabilite"), 'stabilite', '%.1f dk'),
                    (turkce_karakter_duzelt_pdf("Yumuşama Derecesi"), 'yumusama', '%.0f FU'),
                ]
                
                # 2'li gruplar halinde düzenle
                for i in range(0, len(farino_params_detay), 2):
                    row = []
                    for j in range(2):
                        if i + j < len(farino_params_detay):
                            param_label, param_key, param_format = farino_params_detay[i + j]
                            
                            if param_key in analizler and analizler[param_key] > 0:
                                value = param_format % analizler[param_key]
                            else:
                                value = "-"
                            
                            row.extend([param_label, value])
                        else:
                            row.extend(["", ""])
                    
                    farino_data.append(row)
                
                # Farinograph tablo
                if farino_data:
                    farino_table = Table(farino_data, colWidths=[95, 65, 95, 65])
                    farino_table.setStyle(TableStyle([
                        # Başlık satırı
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFF3CD')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#856404')),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                        
                        # Veri satırları
                        ('ALIGN', (0, 1), (-2, -1), 'LEFT'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 1), (-2, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                        ('TOPPADDING', (0, 1), (-1, -1), 4),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFF9E6')]),
                    ]))
                    story.append(farino_table)
                
                story.append(Spacer(1, 10))
            
            # ========== 2.3 EXTENSOGRAPH ANALİZLERİ ==========
            extenso_vars = False
            extenso_params = [
                'enerji45', 'direnc45', 'taban45',
                'enerji90', 'direnc90', 'taban90',
                'enerji135', 'direnc135', 'taban135',
                'su_kaldirma_e'
            ]
            
            for param_key in extenso_params:
                if param_key in analizler and analizler[param_key] > 0:
                    extenso_vars = True
                    break
            
            if extenso_vars:
                extenso_content = []
                
                extenso_baslik = turkce_karakter_duzelt_pdf("2.3 Extensograph Analizleri")
                extenso_content.append(Paragraph(extenso_baslik, bold_style))
                
                # Su Kaldırma (E)
                if 'su_kaldirma_e' in analizler and analizler['su_kaldirma_e'] > 0:
                    su_label = turkce_karakter_duzelt_pdf("Su Kaldırma:")
                    su_text = f"{su_label} {analizler['su_kaldirma_e']:.1f} %"
                    extenso_content.append(Paragraph(su_text, normal_style))
                    extenso_content.append(Spacer(1, 5))
                
                # Dakika analizleri
                dakika_data = []
                
                # Başlık satırı
                dakika_data.append([
                    turkce_karakter_duzelt_pdf("Dakika"),
                    turkce_karakter_duzelt_pdf("Enerji"),
                    turkce_karakter_duzelt_pdf("Direnç"),
                    turkce_karakter_duzelt_pdf("Taban")
                ])
                
                dakika_params = [
                    ('45', 'enerji45', 'direnc45', 'taban45'),
                    ('90', 'enerji90', 'direnc90', 'taban90'),
                    ('135', 'enerji135', 'direnc135', 'taban135'),
                ]
                
                for dakika, enerji_key, direnc_key, taban_key in dakika_params:
                    row = [f"{dakika}."]
                    
                    # Enerji
                    if enerji_key in analizler and analizler[enerji_key] > 0:
                        row.append(f"{analizler[enerji_key]:.0f}")
                    else:
                        row.append("-")
                    
                    # Direnç
                    if direnc_key in analizler and analizler[direnc_key] > 0:
                        row.append(f"{analizler[direnc_key]:.0f}")
                    else:
                        row.append("-")
                    
                    # Taban
                    if taban_key in analizler and analizler[taban_key] > 0:
                        row.append(f"{analizler[taban_key]:.0f}")
                    else:
                        row.append("-")
                    
                    dakika_data.append(row)
                
                # Extenso tablosu
                if len(dakika_data) > 1:
                    extenso_table = Table(dakika_data, colWidths=[40, 50, 50, 50])
                    extenso_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F3F7')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0B4F6C')),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                        
                        # Veri satırları
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                        ('TOPPADDING', (0, 1), (-1, -1), 4),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F7FF')]),
                    ]))
                    extenso_content.append(extenso_table)
                
                # Tüm extensograph içeriğini bir arada tut
                story.append(KeepTogether(extenso_content))
            
            # Analiz istatistikleri
            if 'toplam_analiz_tonaji' in analizler and analizler['toplam_analiz_tonaji'] > 0:
                stat_text = f"{turkce_karakter_duzelt_pdf('Analiz Bilgisi:')} {analizler.get('kullanilan_silo_sayisi', 0)} {turkce_karakter_duzelt_pdf('silo')}, {analizler['toplam_analiz_tonaji']:.1f} {turkce_karakter_duzelt_pdf('ton')}"
                story.append(Spacer(1, 10))
                story.append(Paragraph(stat_text, small_style))
                
        else:
            # Analiz yoksa bilgi mesajı
            no_analysis_text = turkce_karakter_duzelt_pdf("Bu paçal için analiz verisi bulunmamaktadır.")
            story.append(Paragraph(no_analysis_text, normal_style))
        
        # ALT BİLGİ
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        
        footer_date = datetime.now().strftime('%d/%m/%Y')
        footer_text = turkce_karakter_duzelt_pdf(f"Üretim Kalite Kontrol Raporu • {footer_date}")
        
        footer_style = ParagraphStyle(
            'PacalFooter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            textColor=colors.grey,
            alignment=1
        )
        
        story.append(Paragraph(footer_text, footer_style))
        
        # PDF'yi oluştur
        doc.build(story)
        
        # Buffer'dan PDF verisini al
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
        
    except Exception as e:
        st.error(f"Paçal PDF oluşturma hatası: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def create_un_maliyet_pdf_report(hesaplama_verileri):
    """
    Un Maliyet Hesaplama için profesyonel PDF raporu oluştur
    """
    
    if not PDF_AVAILABLE:
        st.error("PDF oluşturma için 'reportlab' kütüphanesi kurulu değil!")
        return None
    
    try:
        # PDF dosyasını bellekten oluştur
        buffer = io.BytesIO()
        
        # PDF oluşturma - TEK SAYFA
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20,
            leftMargin=20,
            topMargin=20,
            bottomMargin=20
        )
        
        # Stiller
        styles = getSampleStyleSheet()
        
        # Başlık stili
        title_style = ParagraphStyle(
            'UnMaliyetTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor('#0B4F6C'),
            alignment=1,  # ORTALI
            spaceAfter=20
        )
        
        # Alt başlık stili
        subtitle_style = ParagraphStyle(
            'UnMaliyetSubtitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=colors.HexColor('#1E2A3A'),
            alignment=0,  # SOLA HİZALI
            spaceAfter=10
        )
        
        # Bold metin stili
        bold_style = ParagraphStyle(
            'UnMaliyetBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=colors.black,
            alignment=0,
            spaceAfter=6,
        )
        
        # Normal metin stili
        normal_style = ParagraphStyle(
            'UnMaliyetNormal',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.black,
            alignment=0,
            spaceAfter=6,
        )
        
        # Footer stili
        footer_style = ParagraphStyle(
            'UnMaliyetFooter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=colors.grey,
            alignment=1,  # ORTALI
        )
        
        # İçerik oluştur
        story = []
        
        # BAŞLIK
        baslik = turkce_karakter_duzelt_pdf("AYLIK UN MALİYET RAPORU")
        story.append(Paragraph(baslik, title_style))
        story.append(Spacer(1, 10))
        
        # DÖNEM BİLGİSİ
        donem_text = turkce_karakter_duzelt_pdf(f"DÖNEM: {hesaplama_verileri['ay']} {hesaplama_verileri['yil']}")
        story.append(Paragraph(donem_text, bold_style))
        
        un_cesidi_text = turkce_karakter_duzelt_pdf(f"Un Çeşidi: {hesaplama_verileri['un_cesidi']}")
        story.append(Paragraph(un_cesidi_text, bold_style))
        
        rapor_tarihi = datetime.now().strftime('%d/%m/%Y %H:%M')
        tarih_text = turkce_karakter_duzelt_pdf(f"Rapor Tarihi: {rapor_tarihi}")
        story.append(Paragraph(tarih_text, normal_style))
        
        story.append(Spacer(1, 20))
        
        # ========== TEMEL BİLGİLER TABLOSU ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("TEMEL BİLGİLER"), subtitle_style))
        story.append(Spacer(1, 10))
        
        # Temel bilgiler tablosu
        temel_data = []
        
        # Başlık satırı
        temel_data.append([
            turkce_karakter_duzelt_pdf("Parametre"),
            turkce_karakter_duzelt_pdf("Değer")
        ])
        
        # Temel parametreler
        temel_params = [
            (turkce_karakter_duzelt_pdf("Aylık Buğday Paçal Maliyeti"), 
             f"{hesaplama_verileri['bugday_pacal_maliyeti']:,.2f} TL/KG"),
            (turkce_karakter_duzelt_pdf("Aylık Kırılan Buğday"), 
             f"{hesaplama_verileri['aylik_kirilan_bugday']:,.1f} Ton"),
            (turkce_karakter_duzelt_pdf("Un Randımanı"), 
             f"{hesaplama_verileri['un_randimani']:,.1f} %"),
            (turkce_karakter_duzelt_pdf("Aylık Ortalama Un Satış Fiyatı (50 Kg)"), 
             f"{hesaplama_verileri['un_satis_fiyati']:,.2f} TL"),
            (turkce_karakter_duzelt_pdf("Üretilen Un Miktarı"), 
             f"{hesaplama_verileri['un_tonaj']:,.1f} Ton")
        ]
        
        for param_label, param_value in temel_params:
            temel_data.append([param_label, param_value])
        
        # Temel bilgiler tablosu
        temel_table = Table(temel_data, colWidths=[200, 120])
        temel_table.setStyle(TableStyle([
            # Başlık satırı
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F81BD')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Veri satırları
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#E6F3F7')),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#0B4F6C')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ROWBACKGROUNDS', (1, 1), (1, -1), [colors.white]),
        ]))
        
        story.append(temel_table)
        story.append(Spacer(1, 20))
        
        # ========== SONUÇLAR TABLOSU ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("HESAPLAMA SONUÇLARI"), subtitle_style))
        story.append(Spacer(1, 10))
        
        # Sonuçlar tablosu
        sonuc_data = []
        
        # Başlık satırı
        sonuc_data.append([
            turkce_karakter_duzelt_pdf(""),
            turkce_karakter_duzelt_pdf("Değer")
        ])
        
        # Sonuç parametreleri (renkli ikonlu)
        sonuc_params = [
            (turkce_karakter_duzelt_pdf("💰 Net Kar (50 KG)"), 
             f"{hesaplama_verileri['net_kar_50kg']:,.2f} TL"),
            (turkce_karakter_duzelt_pdf("🏭 Fabrika Çıkış Maliyeti (50 Kg)"), 
             f"{hesaplama_verileri['fabrika_cikis_maliyet']:,.2f} TL"),
            (turkce_karakter_duzelt_pdf("💵 Net Kar (Toplam)"), 
             f"{hesaplama_verileri['net_kar_toplam']:,.2f} TL")
        ]
        
        for param_label, param_value in sonuc_params:
            sonuc_data.append([param_label, param_value])
        
        # Sonuçlar tablosu (renkli)
        sonuc_table = Table(sonuc_data, colWidths=[200, 120])
        sonuc_table.setStyle(TableStyle([
            # Başlık satırı (gizli, çünkü başlık yok)
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#F8F9FA')),
            ('FONTSIZE', (0, 0), (-1, 0), 1),
            
            # Veri satırları
            ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#E6F3F7')),  # 1. satır - mavi
            ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#FFF3CD')),  # 2. satır - sarı
            ('BACKGROUND', (0, 3), (0, 3), colors.HexColor('#D4EDDA')),  # 3. satır - yeşil
            
            ('TEXTCOLOR', (0, 1), (0, -1), colors.black),
            ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#0B4F6C')),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        story.append(sonuc_table)
        story.append(Spacer(1, 20))
        
        # ALT BİLGİ
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 10))
        
        footer_text = turkce_karakter_duzelt_pdf(f"Üretim Finans Raporu • {hesaplama_verileri['ay']} {hesaplama_verileri['yil']}")
        story.append(Paragraph(footer_text, footer_style))
        
        # PDF'yi oluştur
        doc.build(story)
        
        # Buffer'dan PDF verisini al
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
        
    except Exception as e:
        st.error(f"Un Maliyet PDF oluşturma hatası: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def download_styled_excel(df, filename, sheet_name="Rapor"):
    """Excel çıktısını profesyonel formatta hazırlar (Ortalı, Kenarlıklı, Renkli Başlık)"""
    import xlsxwriter  # Lazy import to avoid dependency issues if not used
    
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    
    # Formatlar
    header_fmt = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center',
        'fg_color': '#0B4F6C', 'font_color': 'white', 'border': 1
    })
    cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
    
    # Başlıkları uygula
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_fmt)
        worksheet.set_column(col_num, col_num, 15) # Genişlik
        
    # Hücreleri formatla (veri varsa)
    if not df.empty:
        worksheet.set_column(0, len(df.columns) - 1, 15, cell_fmt)
        
    writer.close()
    output.seek(0)
    
    st.download_button(
        label="📥 Excel Raporu İndir (Formatlı)",
        data=output,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )


