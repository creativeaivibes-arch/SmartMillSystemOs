import io
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import json

import pandas as pd
import streamlit as st
from app.core.utils import turkce_karakter_duzelt

# --- REPORTLAB IMPORT (Lazy Loading - Güvenli Yükleme) ---
PDF_AVAILABLE = False
try:
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.platypus.flowables import HRFlowable, KeepTogether
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    PDF_AVAILABLE = True
except ImportError:
    pass

# --- 1. AYAR VE STİL MERKEZİ (CONSTANTS & STYLES) ---

class ReportConstants:
    """PDF raporları için merkezi sabitler (Magic Numbers önlendi)"""
    # Renk Paleti (Kurumsal Kimlik)
    COLOR_PRIMARY = '#0B4F6C'    # Ana Mavi (Başlıklar)
    COLOR_SECONDARY = '#1E2A3A'  # Koyu Gri (Alt Başlıklar)
    COLOR_ACCENT = '#4F81BD'     # Tablo Başlık Mavi
    
    # Arkaplan Renkleri
    BG_LIGHT_BLUE = '#E6F3F7'
    BG_LIGHT_GREEN = '#D4EDDA'
    BG_LIGHT_YELLOW = '#FFF3CD'
    BG_LIGHT_ORANGE = '#FFF3E0'
    BG_LIGHT_GRAY = '#F8F9FA'
    
    # Sayfa Düzeni (A4)
    PAGE_MARGIN = 15 * mm
    PAGE_TOP_MARGIN = 12 * mm
    
    # Tablo Genişlikleri (mm)
    COL_WIDTH_STD = 45 * mm      # Standart 4'lü tablo kolonu
    COL_WIDTH_HALF = 90 * mm     # Yarım sayfa

def get_pdf_styles():
    """
    Tüm raporlar için standart ReportLab stillerini döndürür.
    Kod tekrarını önler (DRY).
    """
    if not PDF_AVAILABLE: return {}
    
    base_styles = getSampleStyleSheet()
    
    # Renk nesneleri
    c_primary = colors.HexColor(ReportConstants.COLOR_PRIMARY)
    c_secondary = colors.HexColor(ReportConstants.COLOR_SECONDARY)
    
    custom_styles = {
        'title': ParagraphStyle(
            'CustomTitle',
            parent=base_styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=c_primary,
            alignment=1, # Center
            spaceAfter=10,
            spaceBefore=0
        ),
        'subtitle': ParagraphStyle(
            'CustomSubtitle',
            parent=base_styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=10, 
            textColor=c_secondary,
            alignment=0, # Left
            spaceAfter=5,
            spaceBefore=8
        ),
        'normal': ParagraphStyle(
            'CustomNormal',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=8, # Standart yazı boyutu
            textColor=colors.black,
            alignment=0,
            leading=10
        ),
        'bold': ParagraphStyle(
            'CustomBold',
            parent=base_styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2
        ),
        'small': ParagraphStyle(
            'CustomSmall',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            textColor=colors.grey,
            alignment=0,
            leading=9
        ),
        'footer': ParagraphStyle(
            'CustomFooter',
            parent=base_styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            textColor=colors.grey,
            alignment=1 # Center
        )
    }
    return custom_styles

def turkce_karakter_duzelt_pdf(text: Optional[str]) -> str:
    """
    PDF üretimi için Türkçe karakterleri düzeltir.
    ReportLab standart fontları Türkçe karakterleri desteklemediği için ASCII'ye çevirir.
    """
    if text is None: return ""
    return turkce_karakter_duzelt(str(text))

def create_silo_pdf_report(
    silo_name: str, 
    silo_data: Dict[str, Any], 
    tavli_ortalamalari: Optional[Dict[str, float]] = None, 
    kuru_ortalamalari: Optional[Dict[str, float]] = None
) -> Optional[bytes]:
    """
    Silo için profesyonel PDF raporu oluştur (TEK SAYFA OPTIMIZE)
    Yeni stil ve ayar yapısını kullanır.
    """
    
    if not PDF_AVAILABLE:
        st.error("PDF oluşturma için 'reportlab' kütüphanesi kurulu değil!")
        return None
    
    try:
        buffer = io.BytesIO()
        
        # PDF oluşturma - Constants Kullanımı
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=ReportConstants.PAGE_MARGIN,
            leftMargin=ReportConstants.PAGE_MARGIN,
            topMargin=ReportConstants.PAGE_TOP_MARGIN,
            bottomMargin=ReportConstants.PAGE_MARGIN
        )
        
        # Merkezi Stilleri Yükle
        styles = get_pdf_styles()
        
        story = []
        
        # BAŞLIK
        silo_name_fixed = turkce_karakter_duzelt_pdf(silo_name)
        story.append(Paragraph(f"SILO KALITE KONTROL RAPORU", styles['title']))
        story.append(Paragraph(f"<b>{silo_name_fixed}</b> | {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['normal']))
        story.append(Spacer(1, 4))
        
        # ========== GENEL BİLGİLER + KURU BUGDAY (YAN YANA 2 KOLON) ==========
        col_data = []
        
        # SOL KOLON: Genel Bilgiler
        bugday_cinsi = turkce_karakter_duzelt_pdf(str(silo_data.get('bugday_cinsi', '-')).strip())
        kapasite = float(silo_data.get('kapasite', 1))
        mevcut = float(silo_data.get('mevcut_miktar', 0))
        doluluk = (mevcut / kapasite * 100) if kapasite > 0 else 0
        
        genel_text = f"""<b>GENEL BILGILER</b><br/>
Bugday Cinsi: {bugday_cinsi}<br/>
Toplam Miktar: {mevcut:,.1f} Ton<br/>
Kapasite: {kapasite:,.0f} Ton<br/>
Doluluk: %{doluluk:.1f}<br/>
Maliyet: {float(silo_data.get('maliyet', 0)):,.2f} TL/KG<br/>
Tavli Stok: {float(silo_data.get('tavli_bugday_stok', 0)):,.1f} Ton"""
        
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
            Paragraph(genel_text, styles['normal']),
            Paragraph(kuru_text, styles['normal'])
        ])
        
        col_table = Table(col_data, colWidths=[ReportConstants.COL_WIDTH_HALF, ReportConstants.COL_WIDTH_HALF])
        col_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor(ReportConstants.BG_LIGHT_BLUE)),
            ('BACKGROUND', (1, 0), (1, 0), colors.HexColor(ReportConstants.BG_LIGHT_GREEN)),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        story.append(col_table)
        story.append(Spacer(1, 5))
        
        # ========== TAVLI BUGDAY ANALIZLERI ==========
        if tavli_ortalamalari and tavli_ortalamalari.get('toplam_tonaj', 0) > 0:
            
            story.append(Paragraph("TAVLI BUGDAY ANALIZ SONUCLARI", styles['subtitle']))
            
            # --- Yardımcı: Tablo Oluşturucu (DRY) ---
            def create_sub_table(title, params, bg_color):
                data = [[title, '', '', '']]
                filled = []
                for p_key, p_label, p_fmt in params:
                    if tavli_ortalamalari.get(p_key, 0) > 0:
                        filled.append((p_label, p_fmt % tavli_ortalamalari[p_key]))
                
                for i in range(0, len(filled), 2):
                    row = []
                    for j in range(2):
                        if i + j < len(filled):
                            row.extend(filled[i + j])
                        else:
                            row.extend(['', ''])
                    data.append(row)
                
                if len(data) > 1:
                    t = Table(data, colWidths=[ReportConstants.COL_WIDTH_STD] * 4)
                    t.setStyle(TableStyle([
                        ('SPAN', (0, 0), (3, 0)),
                        ('BACKGROUND', (0, 0), (3, 0), colors.HexColor(bg_color)), # Dinamik Renk
                        ('TEXTCOLOR', (0, 0), (3, 0), colors.white),
                        ('ALIGN', (0, 0), (3, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (3, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (3, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (3, 0), 3),
                        ('TOPPADDING', (0, 0), (3, 0), 3),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('FONTNAME', (0, 1), (-2, -1), 'Helvetica-Bold'),
                        ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
                        ('ALIGN', (0, 1), (-2, -1), 'LEFT'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(ReportConstants.BG_LIGHT_GRAY)]),
                    ]))
                    return t
                return None

            # 1. KİMYASAL
            kimya_params = [
                ('protein', 'Protein', '%.1f%%'), ('rutubet', 'Rutubet', '%.1f%%'),
                ('gluten', 'Gluten', '%.1f%%'), ('gluten_index', 'Gluten Index', '%.0f'),
                ('sedim', 'Sedimantasyon', '%.1f ml'), ('g_sedim', 'Gec. Sedim', '%.1f ml'),
                ('fn', 'Falling Number', '%.0f'), ('ffn', 'F.F.N', '%.0f'),
                ('kul', 'Kul', '%.2f%%'), ('amilograph', 'Amilograph', '%.0f'),
            ]
            t_kimya = create_sub_table('KIMYASAL ANALIZLER', kimya_params, ReportConstants.COLOR_PRIMARY)
            if t_kimya: story.extend([t_kimya, Spacer(1, 4)])

            # 2. FARINOGRAPH
            farino_params = [
                ('su_kaldirma_f', 'Su Kaldirma', '%.1f%%'), ('gelisme_suresi', 'Gelisme Suresi', '%.1f dk'),
                ('stabilite', 'Stabilite', '%.1f dk'), ('yumusama', 'Yumusama', '%.0f FU'),
            ]
            # Turuncu yerine secondary color veya özel bir renk kullanılabilir. Buraya hardcode renk koymak yerine
            # Constants'a eklenebilir ama şimdilik manuel renk geçelim (sadeleştirmek adına)
            t_farino = create_sub_table('FARINOGRAPH ANALIZLERI', farino_params, '#E67E22')
            if t_farino: story.extend([t_farino, Spacer(1, 4)])

            # 3. EXTENSOGRAPH
            extenso_params = [
                ('su_kaldirma_e', 'Su Kaldirma (E)', '%.1f%%'),
                ('enerji45', 'Enerji 45', '%.0f'), ('direnc45', 'Direnc 45', '%.0f'),
                ('enerji90', 'Enerji 90', '%.0f'), ('direnc90', 'Direnc 90', '%.0f'),
                ('enerji135', 'Enerji 135', '%.0f'), ('direnc135', 'Direnc 135', '%.0f'),
            ]
            t_extenso = create_sub_table('EXTENSOGRAPH ANALIZLERI', extenso_params, '#27AE60')
            if t_extenso: story.append(t_extenso)

        else:
            story.append(Paragraph("TAVLI BUGDAY ANALIZ SONUCLARI", styles['subtitle']))
            story.append(Paragraph("Bu silo icin henuz tavli bugday analiz kaydi bulunmamaktadir.", styles['normal']))
        
        # ALT BİLGİ
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Paragraph(f"Smart Mill System OS - Silo Kalite Kontrol Raporu | {datetime.now().strftime('%d/%m/%Y')}", styles['footer']))
        
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
        
    except Exception as e:
        st.error(f"PDF olusturma hatasi: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def create_pacal_pdf_report(
    tarih: str, 
    urun_adi: str, 
    oranlar: Dict[str, float], 
    analizler: Optional[Dict[str, float]]
) -> Optional[bytes]:
    """
    Paçal için profesyonel PDF raporu oluştur.
    Merkezi stil ve ayar yapısını kullanır.
    """
    
    if not PDF_AVAILABLE:
        st.error("PDF oluşturma için 'reportlab' kütüphanesi kurulu değil!")
        return None
    
    try:
        buffer = io.BytesIO()
        
        # PDF oluşturma - Constants Kullanımı
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=ReportConstants.PAGE_MARGIN,
            leftMargin=ReportConstants.PAGE_MARGIN,
            topMargin=ReportConstants.PAGE_TOP_MARGIN,
            bottomMargin=ReportConstants.PAGE_MARGIN
        )
        
        # Merkezi Stilleri Yükle
        styles = get_pdf_styles()
        
        story = []
        
        # BAŞLIK
        baslik = turkce_karakter_duzelt_pdf("PAÇAL ÜRETİM RAPORU")
        story.append(Paragraph(baslik, styles['title']))
        story.append(Spacer(1, 10))
        
        # Temel bilgiler
        urun_adi_fixed = turkce_karakter_duzelt_pdf(urun_adi)
        rapor_tarihi = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        story.append(Paragraph(f"{turkce_karakter_duzelt_pdf('Ürün Adı:')} {urun_adi_fixed}", styles['bold']))
        story.append(Paragraph(f"{turkce_karakter_duzelt_pdf('Paçal Tarihi:')} {tarih}", styles['bold']))
        story.append(Paragraph(f"{turkce_karakter_duzelt_pdf('Rapor Tarihi:')} {rapor_tarihi}", styles['bold']))
        story.append(Spacer(1, 15))
        
        # ========== 1. SILO ORANLARI ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("1. SILO KULLANIM ORANLARI"), styles['subtitle']))
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
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ReportConstants.COLOR_ACCENT)),
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
                ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor(ReportConstants.BG_LIGHT_GRAY)]),
                
                # Toplam satırı
                ('BACKGROUND', (0, -1), (1, -1), colors.HexColor(ReportConstants.BG_LIGHT_BLUE)),
                ('FONTNAME', (0, -1), (1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, -1), (1, -1), 10),
                ('TEXTCOLOR', (0, -1), (1, -1), colors.HexColor(ReportConstants.COLOR_PRIMARY)),
                ('ALIGN', (0, -1), (1, -1), 'CENTER'),
            ]))
            
            story.append(oran_table)
            story.append(Spacer(1, 15))
        
        # ========== 2. PAÇAL ANALİZ SONUÇLARI ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("2. PAÇAL ANALİZ SONUÇLARI"), styles['subtitle']))
        story.append(Spacer(1, 5))
        
        if analizler and isinstance(analizler, dict):
            # Maliyet bilgisi
            if 'maliyet' in analizler:
                maliyet_text = f"{turkce_karakter_duzelt_pdf('Paçal Maliyeti:')} {analizler['maliyet']:.2f} TL/KG"
                story.append(Paragraph(maliyet_text, styles['bold']))
                story.append(Spacer(1, 10))
            
            # ========== 2.1 KİMYASAL ANALİZLER ==========
            story.append(Paragraph(turkce_karakter_duzelt_pdf("2.1 Kimyasal Analizler"), styles['bold']))
            
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
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ReportConstants.BG_LIGHT_BLUE)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(ReportConstants.COLOR_PRIMARY)),
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
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(ReportConstants.BG_LIGHT_GRAY)]),
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
                story.append(Paragraph(turkce_karakter_duzelt_pdf("2.2 Farinograph Analizleri"), styles['bold']))
                
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
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ReportConstants.BG_LIGHT_YELLOW)),
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
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(ReportConstants.BG_LIGHT_ORANGE)]),
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
                extenso_content.append(Paragraph(extenso_baslik, styles['bold']))
                
                # Su Kaldırma (E)
                if 'su_kaldirma_e' in analizler and analizler['su_kaldirma_e'] > 0:
                    su_label = turkce_karakter_duzelt_pdf("Su Kaldırma:")
                    su_text = f"{su_label} {analizler['su_kaldirma_e']:.1f} %"
                    extenso_content.append(Paragraph(su_text, styles['normal']))
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
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ReportConstants.BG_LIGHT_BLUE)),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor(ReportConstants.COLOR_PRIMARY)),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 8),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                        
                        # Veri satırları
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(ReportConstants.BG_LIGHT_GRAY)),
                        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 8),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                        ('TOPPADDING', (0, 1), (-1, -1), 4),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor(ReportConstants.BG_LIGHT_BLUE)]),
                    ]))
                    extenso_content.append(extenso_table)
                
                # Tüm extensograph içeriğini bir arada tut
                story.append(KeepTogether(extenso_content))
            
            # Analiz istatistikleri
            if 'toplam_analiz_tonaji' in analizler and analizler['toplam_analiz_tonaji'] > 0:
                stat_text = f"{turkce_karakter_duzelt_pdf('Analiz Bilgisi:')} {analizler.get('kullanilan_silo_sayisi', 0)} {turkce_karakter_duzelt_pdf('silo')}, {analizler['toplam_analiz_tonaji']:.1f} {turkce_karakter_duzelt_pdf('ton')}"
                story.append(Spacer(1, 10))
                story.append(Paragraph(stat_text, styles['small']))
                
        else:
            # Analiz yoksa bilgi mesajı
            no_analysis_text = turkce_karakter_duzelt_pdf("Bu paçal için analiz verisi bulunmamaktadır.")
            story.append(Paragraph(no_analysis_text, styles['normal']))
        
        # ALT BİLGİ
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        
        footer_date = datetime.now().strftime('%d/%m/%Y')
        footer_text = turkce_karakter_duzelt_pdf(f"Üretim Kalite Kontrol Raporu • {footer_date}")
        
        story.append(Paragraph(footer_text, styles['footer']))
        
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

def create_un_maliyet_pdf_report(hesaplama_verileri: Dict[str, Any]) -> Optional[bytes]:
    """
    Un Maliyet Hesaplama için profesyonel PDF raporu oluştur.
    Merkezi stil ve ayar yapısını kullanır.
    """
    
    if not PDF_AVAILABLE:
        st.error("PDF oluşturma için 'reportlab' kütüphanesi kurulu değil!")
        return None
    
    try:
        buffer = io.BytesIO()
        
        # PDF oluşturma - Constants Kullanımı
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=ReportConstants.PAGE_MARGIN,
            leftMargin=ReportConstants.PAGE_MARGIN,
            topMargin=ReportConstants.PAGE_TOP_MARGIN,
            bottomMargin=ReportConstants.PAGE_MARGIN
        )
        
        # Merkezi Stilleri Yükle
        styles = get_pdf_styles()
        
        story = []
        
        # BAŞLIK
        baslik = turkce_karakter_duzelt_pdf("AYLIK UN MALİYET RAPORU")
        story.append(Paragraph(baslik, styles['title']))
        story.append(Spacer(1, 10))
        
        # DÖNEM BİLGİSİ
        # Güvenli veri çekme (.get ile)
        ay = hesaplama_verileri.get('ay', '-')
        yil = hesaplama_verileri.get('yil', '-')
        un_cesidi = hesaplama_verileri.get('un_cesidi', '-')
        
        donem_text = turkce_karakter_duzelt_pdf(f"DÖNEM: {ay} {yil}")
        story.append(Paragraph(donem_text, styles['bold']))
        
        un_cesidi_text = turkce_karakter_duzelt_pdf(f"Un Çeşidi: {un_cesidi}")
        story.append(Paragraph(un_cesidi_text, styles['bold']))
        
        rapor_tarihi = datetime.now().strftime('%d.%m.%Y %H:%M')
        tarih_text = turkce_karakter_duzelt_pdf(f"Rapor Tarihi: {rapor_tarihi}")
        story.append(Paragraph(tarih_text, styles['normal']))
        
        story.append(Spacer(1, 15))
        
        # ========== TEMEL BİLGİLER TABLOSU ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("TEMEL BİLGİLER"), styles['subtitle']))
        story.append(Spacer(1, 5))
        
        # Temel bilgiler tablosu verisi
        temel_data = []
        temel_data.append([
            turkce_karakter_duzelt_pdf("Parametre"),
            turkce_karakter_duzelt_pdf("Değer")
        ])
        
        # Helper: Sayı formatlama
        def fmt_num(key, format_str="{:,.2f}"):
            try: return format_str.format(float(hesaplama_verileri.get(key, 0)))
            except: return "-"

        # Üretilen un miktarını hesapla (eğer veride yoksa)
        if 'un_tonaj' in hesaplama_verileri:
            un_tonaj_val = float(hesaplama_verileri['un_tonaj'])
        else:
            # Basit hesap: Kırılan * Randiman
            try:
                un_tonaj_val = float(hesaplama_verileri.get('aylik_kirilan_bugday', 0)) * (float(hesaplama_verileri.get('un_randimani', 0)) / 100)
            except:
                un_tonaj_val = 0

        # Temel parametreler
        temel_params = [
            (turkce_karakter_duzelt_pdf("Aylık Buğday Paçal Maliyeti"), f"{fmt_num('bugday_pacal_maliyeti')} TL/KG"),
            (turkce_karakter_duzelt_pdf("Aylık Kırılan Buğday"), f"{fmt_num('aylik_kirilan_bugday', '{:,.1f}')} Ton"),
            (turkce_karakter_duzelt_pdf("Un Randımanı"), f"{fmt_num('un_randimani', '{:,.1f}')} %"),
            (turkce_karakter_duzelt_pdf("Aylık Ortalama Un Satış Fiyatı (50 Kg)"), f"{fmt_num('un_satis_fiyati')} TL"),
            (turkce_karakter_duzelt_pdf("Üretilen Un Miktarı"), f"{un_tonaj_val:,.1f} Ton")
        ]
        
        for p_label, p_val in temel_params:
            temel_data.append([p_label, p_val])
        
        # Tablo Stili
        col_width_label = ReportConstants.COL_WIDTH_HALF + 20*mm
        col_width_val = 40*mm
        
        temel_table = Table(temel_data, colWidths=[col_width_label, col_width_val])
        temel_table.setStyle(TableStyle([
            # Başlık
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ReportConstants.COLOR_ACCENT)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            
            # Veri Satırları
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor(ReportConstants.BG_LIGHT_BLUE)),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor(ReportConstants.COLOR_PRIMARY)),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('ROWBACKGROUNDS', (1, 1), (1, -1), [colors.white]),
        ]))
        
        story.append(temel_table)
        story.append(Spacer(1, 15))
        
        # ========== SONUÇLAR TABLOSU ==========
        story.append(Paragraph(turkce_karakter_duzelt_pdf("HESAPLAMA SONUÇLARI"), styles['subtitle']))
        story.append(Spacer(1, 5))
        
        # Sonuçlar tablosu (Özel renkli satırlar)
        sonuc_data = []
        
        # Parametreler ve Arkaplan Renkleri
        sonuc_params = [
            ("Net Kar (50 KG)", f"{fmt_num('net_kar_50kg')} TL", ReportConstants.BG_LIGHT_BLUE),
            ("Fabrika Çıkış Maliyeti (50 Kg)", f"{fmt_num('fabrika_cikis_maliyet')} TL", ReportConstants.BG_LIGHT_YELLOW),
            ("Net Kar (Toplam)", f"{fmt_num('net_kar_toplam')} TL", ReportConstants.BG_LIGHT_GREEN)
        ]
        
        for label, val, _ in sonuc_params:
            sonuc_data.append([turkce_karakter_duzelt_pdf(label), val])
        
        sonuc_table = Table(sonuc_data, colWidths=[col_width_label, col_width_val])
        
        # Dinamik Stil Oluşturma
        table_style_cmds = [
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor(ReportConstants.COLOR_PRIMARY)),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]
        
        # Her satıra kendi rengini ver
        for i, (_, _, bg_color) in enumerate(sonuc_params):
            table_style_cmds.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor(bg_color)))
            
        sonuc_table.setStyle(TableStyle(table_style_cmds))
        
        story.append(sonuc_table)
        story.append(Spacer(1, 20))
        
        # ALT BİLGİ
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 5))
        
        footer_text = turkce_karakter_duzelt_pdf(f"Üretim Finans Raporu | {ay} {yil}")
        story.append(Paragraph(footer_text, styles['footer']))
        
        # PDF'yi oluştur
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
        
    except Exception as e:
        st.error(f"Un Maliyet PDF oluşturma hatası: {str(e)}")
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
def create_traceability_pdf_report(chain_data):
    """
    Traceability zincir verisini alır ve profesyonel PDF üretir.
    Türkçe karakter sorununu ve Veri Eşleşme sorununu çözer.
    """
    if not PDF_AVAILABLE:
        return None

    # --- 1. TÜRKÇE KARAKTER DÜZELTİCİ (PDF İÇİN ZORUNLU) ---
    def fix_txt(text):
        """ReportLab'in sevmediği Türkçe karakterleri İngilizce'ye çevirir"""
        if text is None: return "-"
        text = str(text)
        
        mapping = {
            'İ': 'I', 'Ş': 'S', 'Ğ': 'G', 'Ü': 'U', 'Ö': 'O', 'Ç': 'C',
            'ı': 'i', 'ş': 's', 'ğ': 'g', 'ü': 'u', 'ö': 'o', 'ç': 'c'
        }
        for tr, en in mapping.items():
            text = text.replace(tr, en)
        return text

       # --- YARDIMCI: AKILLI VERİ AVCISI (DÜZELTİLMİŞ) ---
    def get_val(data_dict, keys_list, suffix=""):
        """
        Excel'deki 'Enerji (45)', 'Enerji_45' veya 'enerji 45' 
        yazımlarını otomatik olarak birbirine bağlar.
        """
        if not data_dict or not isinstance(data_dict, dict):
            return "-"
        
        # 1. Sözlükteki tüm anahtarları temizle (küçük harf, boşluksuz, sembolsüz)
        # Örn: "Enerji (45)" -> "enerji45" yapar
        pool = {}
        for k, v in data_dict.items():
            clean_key = str(k).lower().replace(" ", "").replace("_", "").replace("(", "").replace(")", "").replace(".", "")
            pool[clean_key] = v
            
        # 2. Aranan kelimeyi de aynı şekilde temizleyip havuzda ara
        for key in keys_list:
            search_key = key.lower().replace(" ", "").replace("_", "").replace("(", "").replace(")", "").replace(".", "")
            if search_key in pool:
                val = pool[search_key]
                if val is None or str(val).lower() in ['nan', 'none', '', '0', '0.0']:
                    return "-"
                return f"{val} {suffix}".strip()
                
        return "-"

    # --- 3. TEMİZLİK ROBOTU ---
    def clean_data(data):
        """Pandas verisini temiz sözlüğe çevirir"""
        try:
            if hasattr(data, 'to_dict'):
                if hasattr(data, 'empty') and data.empty: return None
                if isinstance(data, pd.Series): return data.to_dict()
                if isinstance(data, pd.DataFrame): return data.iloc[0].to_dict()
            return data if isinstance(data, dict) else None
        except: return None

    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=10*mm, bottomMargin=10*mm)
        story = []
        styles = getSampleStyleSheet()
        
        # --- Başlık ---
        story.append(Paragraph("DIJITAL IZLENEBILIRLIK RAPORU", styles['Title'])) # Türkçe karakter kullanmadık
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph(f"Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0B4F6C')))
        story.append(Spacer(1, 10*mm))

        # Helper: Bölüm Başlığı
        def add_section(title):
            story.append(Paragraph(f"<b>{fix_txt(title)}</b>", styles['Heading2']))
            story.append(Spacer(1, 2*mm))

        # Helper: Tablo Yapıcı
        def make_table(rows):
            # Rows format: [("Etiket", "Değer"), ("Etiket", "Değer")]
            data = [["Parametre", "Deger"]] # Başlık
            for label, val in rows:
                data.append([fix_txt(label), fix_txt(val)])
            
            t = Table(data, colWidths=[70*mm, 90*mm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E6F3F7')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0B4F6C')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t)
            story.append(Spacer(1, 8*mm))

        # VERİLERİ HAZIRLA
        ship = clean_data(chain_data.get('SHIP'))
        lab  = clean_data(chain_data.get('LAB'))
        prd  = clean_data(chain_data.get('PRD'))
        mix  = clean_data(chain_data.get('MIX'))
        enz  = clean_data(chain_data.get('ENZ')) # Enzim eklendi

        # --- 1. SEVKİYAT BİLGİSİ ---
        add_section("1. SEVKIYAT & MUSTERI BILGISI")
        if ship:
            make_table([
                ("Musteri",       get_val(ship, ['musteri_adi', 'musteri', 'cari_adi'])),
                ("Lot No",        get_val(ship, ['lot_no'])),
                ("Arac Plaka",    get_val(ship, ['plaka'])),
                ("Sevk Tarihi",   str(get_val(ship, ['tarih']))[:19]),
                ("Urun Cinsi",    get_val(ship, ['un_cinsi_marka', 'un_markasi', 'urun_adi']))
            ])
            
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph("<b>Cikis Numune Analiz Sonuclari:</b>", styles['Normal']))
            story.append(Spacer(1, 2*mm))
            
            # Kimyasal Analizler
            make_table([
                ("Protein",           f"% {get_val(ship, ['protein'])}"),
                ("Rutubet",           f"% {get_val(ship, ['rutubet'])}"),
                ("Kul",               f"% {get_val(ship, ['kul'])}"),
                ("Sedim",             get_val(ship, ['sedim'])),
                ("Gluten",            get_val(ship, ['gluten'])),
                ("Gluten Indeks",     get_val(ship, ['gluten_index'])),
                ("FN",                get_val(ship, ['fn'])),
                ("FFN",               get_val(ship, ['ffn'])),
                ("Gecikmeli Sedim",   get_val(ship, ['gecikmeli_sedim', 'g_sedim']))
            ])
            
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("<b>Farinograph Degerleri:</b>", styles['Normal']))
            make_table([
                ("Su Kaldirma (F)",   get_val(ship, ['su_kaldirma_f'])),
                ("Gelisme Suresi",    get_val(ship, ['gelisme_suresi'])),
                ("Stabilite",         get_val(ship, ['stabilite'])),
                ("Yumusama",          get_val(ship, ['yumusama']))
            ])
            
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("<b>Extensograph Degerleri:</b>", styles['Normal']))
            make_table([
                ("Enerji 45",         get_val(ship, ['enerji45'])),
                ("Direnc 45",         get_val(ship, ['direnc45'])),
                ("Uzama 45",          get_val(ship, ['uzama45'])),
                ("Enerji 90",         get_val(ship, ['enerji90'])),
                ("Direnc 90",         get_val(ship, ['direnc90'])),
                ("Uzama 90",          get_val(ship, ['uzama90'])),
                ("Enerji 135",        get_val(ship, ['enerji135', 'enerji'])),
                ("Direnc 135",        get_val(ship, ['direnc135', 'direnc'])),
                ("Uzama 135",         get_val(ship, ['uzama135', 'uzama']))
            ])
        else:
            story.append(Paragraph("Sevkiyat verisi bulunamadi.", styles['Normal']))
            story.append(Spacer(1, 8*mm))

        # --- 2. LABORATUVAR ANALIZ ---
        add_section("2. URETIM LABORATUVAR KALITE DEGERLERI")
        if lab:
            # Kimyasal Analizler
            make_table([
                ("Protein",           f"% {get_val(lab, ['protein'])}"),
                ("Rutubet",           f"% {get_val(lab, ['rutubet'])}"),
                ("Kul",               f"% {get_val(lab, ['kul'])}"),
                ("Sedim",             get_val(lab, ['sedim'])),
                ("Gluten",            get_val(lab, ['gluten'])),
                ("Gluten Indeks",     get_val(lab, ['gluten_index'])),
                ("FN",                get_val(lab, ['fn'])),
                ("FFN",               get_val(lab, ['ffn'])),
                ("Gecikmeli Sedim",   get_val(lab, ['gecikmeli_sedim', 'g_sedim']))
            ])
            
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("<b>Farinograph Degerleri:</b>", styles['Normal']))
            make_table([
                ("Su Kaldirma (F)",   get_val(lab, ['su_kaldirma_f'])),
                ("Gelisme Suresi",    get_val(lab, ['gelisme_suresi'])),
                ("Stabilite",         get_val(lab, ['stabilite'])),
                ("Yumusama",          get_val(lab, ['yumusama']))
            ])
            
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph("<b>Extensograph Degerleri:</b>", styles['Normal']))
            make_table([
                ("Enerji 45",         get_val(lab, ['enerji45'])),
                ("Direnc 45",         get_val(lab, ['direnc45'])),
                ("Uzama 45",          get_val(lab, ['uzama45'])),
                ("Enerji 90",         get_val(lab, ['enerji90'])),
                ("Direnc 90",         get_val(lab, ['direnc90'])),
                ("Uzama 90",          get_val(lab, ['uzama90'])),
                ("Enerji 135",        get_val(lab, ['enerji135', 'enerji'])),
                ("Direnc 135",        get_val(lab, ['direnc135', 'direnc'])),
                ("Uzama 135",         get_val(lab, ['uzama135', 'uzama']))
            ])
        else:
            story.append(Paragraph("Analiz verisi bulunamadi.", styles['Normal']))
            story.append(Spacer(1, 8*mm))

        # --- 3. ÜRETİM & DEĞİRMEN ---
        add_section("3. ÜRETİM & DEĞİRMEN PARAMETRELERİ")
        if prd:
            vardiya_text = f"{get_val(prd, ['vardiya'])} ({get_val(prd, ['sorumlu'])})"
            make_table([
                ("Üretim Tarihi",     str(get_val(prd, ['tarih']))[:19]),
                ("Vardiya",           vardiya_text),
                ("Kırılan Buğday",    f"{get_val(prd, ['kirilan_bugday'])} Kg"),
                ("Tav Süresi",        f"{get_val(prd, ['tav_suresi'])} Saat"),
                ("Toplam Randıman",   f"% {float(get_val(prd, ['toplam_randiman'])):,.2f}" if get_val(prd, ['toplam_randiman']) not in ['-', '', 'nan', None] and str(get_val(prd, ['toplam_randiman'])).replace('.','').replace(',','').isdigit() else '-'),
                ("Un-1",              f"{get_val(prd, ['un_1'])} Kg"),
                ("Kepek",             f"{get_val(prd, ['kepek'])} Kg"),
                ("Kayıp Oranı",       f"% {float(get_val(prd, ['kayip'])):,.2f}" if get_val(prd, ['kayip']) not in ['-', '', 'nan', None] and str(get_val(prd, ['kayip'])).replace('.','').replace(',','').isdigit() else '-')
            ])
        else:
            story.append(Paragraph("Uretim kaydi bulunamadi.", styles['Normal']))
            story.append(Spacer(1, 8*mm))

        # --- 4. ENZİM VE KATKI (YENİ EKLENDİ) ---
        add_section("4. KULLANILAN KATKI & ENZİM REÇETESİ")
        if enz:
            try:
                enz_json = get_val(enz, ['enzim_verisi_json'])
                if enz_json and enz_json != '-':
                    enz_list = json.loads(enz_json) if isinstance(enz_json, str) else enz_json
                    enz_str = ", ".join([f"{e.get('ad')}: {e.get('doz')}gr" for e in enz_list])
                else:
                    enz_str = "-"
            except Exception as e:
                enz_str = f"Hata: {str(e)}"
            
            make_table([
                ("Reçete ID",      get_val(enz, ['enzim_id'])),
                ("Bağlı Paçal",    get_val(enz, ['uretim_kodu'])),
                ("İçerik Detayı",  enz_str)
            ])
        else:
            story.append(Paragraph("Enzim/Katki verisi bulunamadi.", styles['Normal']))
            story.append(Spacer(1, 8*mm))

        # --- 5. PAÇAL (BUĞDAY KARIŞIMI) ---
        add_section("5. BUĞDAY PAÇAL İÇERİĞİ")
        if mix:
            story.append(Paragraph(f"<b>Paçal Kodu:</b> {get_val(mix, ['batch_id'])}", styles['Normal']))
            story.append(Paragraph(f"<b>Ürün:</b> {get_val(mix, ['urun_adi'])}", styles['Normal']))
            story.append(Paragraph(f"<b>Maliyet:</b> {get_val(mix, ['maliyet'])} TL", styles['Normal']))
            story.append(Spacer(1, 3*mm))
            
            try:
                
                snapshot_json = get_val(mix, ['silo_snapshot_json'])
                if snapshot_json and snapshot_json != '-':
                    snapshot = json.loads(snapshot_json) if isinstance(snapshot_json, str) else snapshot_json
                    story.append(Paragraph("<b>Karışım Detayı:</b>", styles['Normal']))
                    for silo, data in snapshot.items():
                        if isinstance(data, dict):
                            oran = data.get('oran', 0)
                            kuru = data.get('kuru_analiz', {})
                            cins = kuru.get('cins', '-')
                            protein = kuru.get('protein', '-')
                            story.append(Paragraph(f"  • {silo}: %{oran} - {cins} (Protein: {protein}%)", styles['Normal']))
            except Exception as e:
                story.append(Paragraph(f"Karışım detayı okunamadı: {str(e)}", styles['Normal']))
        else:
            story.append(Paragraph("Pacal (Hammadde) verisi bulunamadi.", styles['Normal']))

        # PDF BİTİR
        doc.build(story)
        buffer.seek(0)
        return buffer

    except Exception as e:
        import traceback
        st.error(f"❌ PDF OLUŞTURMA HATASI: {str(e)}")
        with st.expander("🔧 Teknik Detaylar"):
            st.code(traceback.format_exc())
        return None
