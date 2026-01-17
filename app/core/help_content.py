"""
Centralized Help Content for SmartMill System.
Supports multi-language (tr/en).
Structure:
HELP_CONTENT = {
    "module_key": {
        "tr": {"title": "...", "content": "..."},
        "en": {"title": "...", "content": "..."}
    }
}
"""

HELP_CONTENT = {
    "mal_kabul": {
        "tr": {
            "title": "🚛 Mal Kabul Modülü Nasıl Kullanılır?",
            "content": """
            **Bu modül, fabrikaya gelen buğdayların ilk kayıt ve analiz işlemlerini içerir.**
            
            1. **Araç Bilgileri:** Plaka, Tedarikçi ve İrsaliye (Lot No) bilgilerini eksiksiz girin.
            2. **Tartım:** Kantar entegrasyonu yoksa, manuel olarak kg cinsinden giriş yapın.
            3. **Laboratuvar Analizi:**
                *   Numune üzerinden ölçülen Protein, Gluten, Rutubet değerlerini girin.
                *   Bu değerler, buğdayın kalitesini ve hangi siloya alınacağını belirlemek için kritiktir.
            4. **Siloya Alma:** Analiz sonuçlarına göre uygun bir "Hammadde Silosu" seçin.
            
            **İpucu:** Kritik değerler (yüksek nem vb.) girildiğinde sistem sizi uyaracaktır.
            """
        },
        "en": {
            "title": "🚛 How to use Goods Receipt Module?",
            "content": """
            **This module handles the initial registration and analysis of incoming wheat.**
            
            1. **Vehicle Info:** Enter Plate, Supplier and Lot No.
            2. **Weighing:** Enter weight in kg manually if no scale integration exists.
            3. **Lab Analysis:**
                *   Enter measured Protein, Gluten, Moisture values.
                *   These determine the wheat quality and target silo.
            4. **Storage:** Select an appropriate "Raw Material Silo" based on analysis.
            """
        }
    },
    "tavli_analiz": {
        "tr": {
            "title": "🧪 Tavlı Analiz Modülü",
            "content": """
            **Tavlama (ıslatma) işleminden sonraki buğdayın durumunu takip etmek içindir.**
            
            *   Her bir silo için belirli periyotlarda alınan numuneleri buraya girin.
            *   Bu veriler, **Paçal (Karışım)** hesaplamalarında kullanılacaktır.
            *   Silo listesinden analizi yapılan siloyu seçmeyi unutmayın.
            """
        },
        "en": {
            "title": "🧪 Tempered Wheat Analysis",
            "content": """
            **Used to track wheat condition after tempering.**
            
            *   Enter periodic samples for each silo.
            *   This data feeds the **Mixing (Grist)** calculations.
            *   Ensure you select the correct silo being analyzed.
            """
        }
    }
}

def get_help_text(module_key, lang='tr'):
    """Get help dict for specific module and language"""
    data = HELP_CONTENT.get(module_key, {})
    return data.get(lang, data.get('tr', {'title': 'Yardım', 'content': 'İçerik bulunamadı.'}))
