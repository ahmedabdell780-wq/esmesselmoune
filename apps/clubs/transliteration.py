# -*- coding: utf-8 -*-
"""
Transliteration helper for Algerian Arabic names, cities, and football passports.
"""
import re
from datetime import date

# Known town/city transliterations in Wilaya Tipaza / Algeria
CITIES_DICT = {
    'قوراية': 'GOURAYA',
    'سيدي غيلاس': 'SIDI GHILES',
    'حجوط': 'HADJOUT',
    'زرالدة': 'ZERALDA',
    'القليعة': 'KOLEA',
    'قليعة': 'KOLEA',
    'الشفة': 'CHIFFA',
    'شفة': 'CHIFFA',
    'البليدة': 'BLIDA',
    'بليدة': 'BLIDA',
    'القبة': 'KOUBA',
    'قبة': 'KOUBA',
    'تيزي وزو': 'TIZI OUZOU',
    'مسلمون': 'MESSELMOUN',
    'عين بسام': 'AIN BESSAM',
    'تيبازة': 'TIPAZA',
    'تيبازه': 'TIPAZA',
    'شرشال': 'CHERCHELL',
    'الجزائر': 'ALGER',
    'الداموس': 'DAMOUS',
    'بوسماعيل': 'BOU ISMAIL',
    'فوكة': 'FOUKA',
    'الارهاط': 'LARHAT',
    'سيدي راشد': 'SIDI RACHED',
    'بورقيقة': 'BOURKIKA',
    'مراد': 'MENACEUR',
    'مناصر': 'MENACEUR',
    'الناظور': 'NADOR',
    'أحمر العين': 'AHMER EL AIN',
    'بوهارون': 'BOUHAROUN',
    'خميستي': 'KHEMISTI',
    'حطاطبة': 'HATTATBA',
}

# Known Algerian family & given names
NAMES_DICT = {
    # Family names
    'غانم': 'GHANEM',
    'بلجيلالي': 'BELDJILALI',
    'بلعيدي': 'BELAIDI',
    'بن سعيداني': 'BENSAIDANI',
    'بوحدي': 'BOUHADI',
    'بوحادي': 'BOUHADI',
    'جدوّر': 'DJEDDOR',
    'جدور': 'DJEDDOR',
    'حدوش': 'HADDOUCHE',
    'داهل': 'DAHEL',
    'رياض': 'RIAD',
    'شرفاوي': 'CHARFAOUI',
    'صبان': 'SABBANE',
    'عبداللاوي': 'ABDELLAOUI',
    'عبد اللاوي': 'ABDELLAOUI',
    'عشودة': 'ACHOUDA',
    'عماري': 'AMMARI',
    'عمروش': 'AMROUCHE',
    'لعرب': 'LAREB',
    'مختاري': 'MOKHTARI',
    'مسيلتي': 'MESSELTI',
    'موساوي': 'MOUSSAOUI',
    'نذير': 'NADHIR',
    'بسكري': 'BESKRI',
    'بلجوهرة': 'BELDJOUHRA',
    'بلجوهر': 'BELDJOUHRA',
    'بهيلي': 'BAHILI',
    'بهلي': 'BAHILI',
    'بوزيان': 'BOUZIANE',
    'حموني': 'HAMMOUNI',
    'داود': 'DAOUD',
    'عطاف': 'ATTAF',
    'عوايجية': 'AOUAIDJIA',
    'لنتري': 'LANTRI',
    'لعنتري': 'LANTRI',
    'العنطري': 'LANTRI',
    'مامو': 'MAMOU',
    'دهيلي': 'DEHILI',
    'بن حدوش': 'BEN HADDOUCHE',
    'حساين': 'HASSAINE',
    'زيبوش': 'ZIBOUCHE',
    'سداوي': 'SADAOUI',
    'سليماني': 'SLIMANI',
    'شامي': 'CHAMI',
    'مسكي': 'MESKI',
    'عبيدات': 'OBEIDAT',
    'عمورة': 'AMOURA',
    'يحياوي': 'YAHIAOUI',
    'يمناين': 'YEMNAINE',
    'بوشعور': 'BOUCHEOUR',
    'دعدي': 'DAADI',
    'ابدوزان': 'IBDOUZENE',
    'إبدوزن': 'IBDOUZENE',
    'احموين': 'AHMOUINE',
    'إحموين': 'AHMOUINE',
    'سعدون': 'SAADOUN',
    'حلولي': 'HELLOULI',
    'حلوي': 'HELLOULI',
    'مصطفاوي': 'MOSTEFAOUI',
    'بوستة': 'BOUSETTA',
    'حرتي': 'HARTI',
    'بوعبد الله': 'BOUABDALLAH',
    'خليفي': 'KHELIFI',
    'بلقاسمي': 'BELKACEMI',
    'بلقاسم': 'BELKACEMI',
    'لبيض': 'LABIAD',
    'حلاحل': 'HLAHEL',
    'حلحال': 'HLAHEL',
    'حطالي': 'HATTALI',
    'ولد أعرب': 'OULD LAREB',
    'شرقي': 'CHERGUI',
    'شرفي': 'CHERFI',
    'لعلاوي': 'LAALAOUI',
    'عزيني': 'AZZINI',
    'بزيو': 'BEZIOU',
    'بوكري': 'BOUKRI',
    'عزبي': 'AZBI',

    # Given names
    'عبد الجليل': 'ABDELDJALIL',
    'باسل': 'BASSEL',
    'عبد الباسط': 'ABDELBASSET',
    'عبد المالك': 'ABDELMALEK',
    'عبد العالي': 'ABDELALI',
    'عبد الرزاق': 'ABDELRAZAK',
    'محمد شريف': 'MOHAMED CHERIF',
    'محمد': 'MOHAMED',
    'إياد': 'IYAD',
    'اياد': 'IYAD',
    'أحمد': 'AHMED',
    'احمد': 'AHMED',
    'محمد أمين': 'MOHAMED AMINE',
    'محمد امين': 'MOHAMED AMINE',
    'يحيى': 'YAHIA',
    'يحي': 'YAHIA',
    'عبد الرؤوف': 'ABDELRAOUF',
    'عبد النور': 'ABDELNOUR',
    'لخضر يوسف': 'LAKHDAR YOUCEF',
    'هارون': 'HAROUN',
    'رفيق': 'RAFIK',
    'عبد الصمد': 'ABDESSAMAD',
    'عامر': 'AMER',
    'أيمن': 'AYMEN',
    'ايمن': 'AYMEN',
    'سيف الدين': 'SEIF EDDINE',
    'نجم الدين': 'NEDJM EDDINE',
    'عبد الوهاب': 'ABDELOUAHAB',
    'إدريس': 'IDRIS',
    'ادريس': 'IDRIS',
    'محمد سعيد': 'MOHAMED SAID',
    'محمد ياسين': 'MOHAMED YACINE',
    'عبد الرحمن': 'ABDELRAHMAN',
    'عبد الرحمان': 'ABDELRAHMAN',
    'ياسر': 'YASSER',
    'كريم': 'KARIM',
    'عبد الكريم': 'ABDELKARIM',
    'شيب': 'CHAYEB',
    'شيث': 'CHAYEB',
    'عبد الرحيم': 'ABDELRAHIM',
    'غيث': 'GHAITH',
    'محمد عامر': 'MOHAMED AMER',
    'هيثم': 'HAITHEM',
    'سيد أحمد': 'SID AHMED',
    'المهدي': 'EL MAHDI',
    'مهدي': 'MAHDI',
    'محمد زكرياء': 'MOHAMED ZAKARIA',
    'زكرياء': 'ZAKARIA',
    'اسماعيل': 'ISMAIL',
    'إسماعيل': 'ISMAIL',
    'جلول شمس الدين': 'DJELLOUL CHAMS EDDINE',
    'عبد الحفيظ': 'ABDELHAFIDH',
    'هشام': 'HICHAM',
    'وائل': 'OUAIL',
    'أنيس': 'ANIS',
    'انيس': 'ANIS',
    'أحمد صهيب': 'AHMED SOUHAIB',
    'ياسين': 'YACINE',
    'فارس': 'FARES',
    'لؤي عبد المنعم': 'LOUAI ABDELMOUNAIM',
    'وسيم': 'WASSIM',
    'محمد ضياء الدين': 'MOHAMED DHIA EDDINE',
    'عبد الحق': 'ABDELHAK',
    'بدر الدين': 'BADR EDDINE',
    'محمد أكرم': 'MOHAMED AKRAM',
    'أنس': 'ANAS',
    'انس': 'ANAS',
    'قيس عبد المعين': 'QAIS ABDELMOIN',
    'محمد عماد الدين': 'MOHAMED IMAD EDDINE',
    'عبد الله': 'ABDELLAH',
    'يوسف تاج الدين': 'YOUCEF TADJ EDDINE',
    'آدم': 'ADEM',
    'ادم': 'ADEM',
    'محمد سامط': 'MOHAMED SAMET',
    'محمد سامي': 'MOHAMED SAMI',
    'محمد جواد': 'MOHAMED DJAWAD',
    'جواد': 'DJAWAD',
    'صابر': 'SABER',
    'محمد آدم': 'MOHAMED ADEM',
    'يحي عبد الباسط': 'YAHIA ABDELBASSET',
    'ضياء الدين': 'DHIA EDDINE',
    'فايز': 'FAYEZ',
    'أمين محمد': 'AMINE MOHAMED',
    'يونس': 'YOUNES',
    'أشرف': 'ACHRAF',
    'اشرف': 'ACHRAF',
    'إسحاق': 'ISHAQ',
    'اسحاق': 'ISHAQ',
    'صلاح الدين': 'SALAH EDDINE',
    'محفوظ': 'MAHFOUD',
    'محمد رسم': 'MOHAMED RACIM',
    'محمد رسيم': 'MOHAMED RACIM',
    'أيوب': 'AYOUB',
    'ايوب': 'AYOUB',
    'يعقوب': 'YACOUB',
    'محمد إدريس': 'MOHAMED IDRIS',
    'أمير': 'AMIR',
    'امير': 'AMIR',
    'عبد الرزاق إياد': 'ABDELRAZAK IYAD',
    'خير الدين': 'KHEIR EDDINE',
    'إياد عبد القادر': 'IYAD ABDELKADER',
    'إسحاق علال الدين': 'ISHAQ ALLAL EDDINE',
    'سراج الدين': 'SIRADJ EDDINE',
}

# Phonetic character table for fallback
ARABIC_CHAR_MAP = {
    'ا': 'A', 'أ': 'A', 'إ': 'I', 'آ': 'A', 'ء': '', 'ئ': 'I', 'ؤ': 'OU',
    'ب': 'B', 'ت': 'T', 'ث': 'TH', 'ج': 'DJ', 'ح': 'H', 'خ': 'KH',
    'د': 'D', 'ذ': 'DH', 'ر': 'R', 'ز': 'Z', 'س': 'S', 'ش': 'CH',
    'ص': 'S', 'ض': 'D', 'ط': 'T', 'ظ': 'DH', 'ع': 'A', 'غ': 'GH',
    'ف': 'F', 'ق': 'K', 'ك': 'K', 'ل': 'L', 'م': 'M', 'ن': 'N',
    'ه': 'H', 'ة': 'A', 'و': 'OU', 'ي': 'I', 'ى': 'A',
    ' ': ' ', '-': '-'
}

def transliterate_text(arabic_text):
    """Transliterate Arabic name/text to standard Algerian French spelling."""
    if not arabic_text:
        return ""
    text = arabic_text.strip()
    
    # Check exact match
    if text in NAMES_DICT:
        return NAMES_DICT[text]
    if text in CITIES_DICT:
        return CITIES_DICT[text]

    # Handle composite names with spaces
    words = text.split()
    translated_words = []
    i = 0
    while i < len(words):
        # Try two words together (e.g. بن سعيداني, عبد الجليل, سيف الدين)
        if i + 1 < len(words):
            pair = f"{words[i]} {words[i+1]}"
            if pair in NAMES_DICT:
                translated_words.append(NAMES_DICT[pair])
                i += 2
                continue
            if pair in CITIES_DICT:
                translated_words.append(CITIES_DICT[pair])
                i += 2
                continue
        # Try three words
        if i + 2 < len(words):
            triplet = f"{words[i]} {words[i+1]} {words[i+2]}"
            if triplet in NAMES_DICT:
                translated_words.append(NAMES_DICT[triplet])
                i += 3
                continue

        w = words[i]
        if w in NAMES_DICT:
            translated_words.append(NAMES_DICT[w])
        elif w in CITIES_DICT:
            translated_words.append(CITIES_DICT[w])
        else:
            # Fallback phonetic transliteration
            res = ""
            for char in w:
                res += ARABIC_CHAR_MAP.get(char, char.upper())
            translated_words.append(res)
        i += 1

    return " ".join(translated_words).upper()


def get_player_passport_defaults(player):
    """
    Generate complete pre-filled default data for a player passport.
    Returns a dict with all passport fields and 12 pre-filled rows.
    """
    # Names: prioritize explicitly entered French names if available
    last_fr = (getattr(player, 'last_name_fr', '') or '').strip()
    if not last_fr:
        last_fr = transliterate_text(player.last_name)
    first_fr = (getattr(player, 'first_name_fr', '') or '').strip()
    if not first_fr:
        first_fr = transliterate_text(player.first_name)
    full_name_fr = f"{last_fr} {first_fr}".strip()
    
    # Place of birth
    raw_pob = (getattr(player, 'place_of_birth', '') or '').strip()
    if raw_pob:
        if re.search(r'[a-zA-Z]', raw_pob):
            place_fr = raw_pob.upper()
        else:
            place_fr = transliterate_text(raw_pob)
    else:
        place_fr = "GOURAYA"
    
    # Date of birth
    dob = player.date_of_birth or date(2011, 1, 1)
    
    # License number
    license_num = ""
    if hasattr(player, 'card_number') and player.card_number:
        # Check if user set a specific license or use clean format
        license_num = ""
    
    # Determine active seasons based on category
    cat_name = player.category.name.upper() if player.category else "U17"
    if "U15" in cat_name:
        # U15: الموسم الحالي فقط (2026/2027)
        active_seasons = {"2026/2027"}
    elif "U17" in cat_name:
        # U17: الموسم الماضي والموسم الحالي فقط (2025/2026 و 2026/2027)
        active_seasons = {"2025/2026", "2026/2027"}
    elif "U20" in cat_name:
        # U20: الموسمين الماضيين والموسم الحالي (2024/2025 و 2025/2026 و 2026/2027)
        active_seasons = {"2024/2025", "2025/2026", "2026/2027"}
    else:
        active_seasons = {"2026/2027"}
    
    # Generate the 12 rows (from 12 ans to 23 ans)
    rows_data = []
    birth_year = dob.year
    for age in range(12, 24):
        s1 = birth_year + age
        s2 = s1 + 1
        season_str = f"{s1}/{s2}"
        
        if season_str in active_seasons:
            rows_data.append({
                'age': f"{age} ans",
                'season': season_str,
                'status': "Amateur",
                'loan_permanent': "Permanent",
                'period': "01/07 - 30/06",
                'club': "ES Messelmoun",
                'league': "Ligue Wilaya de Football - Tipaza",
            })
        else:
            rows_data.append({
                'age': f"{age} ans",
                'season': "",
                'status': "",
                'loan_permanent': "",
                'period': "",
                'club': "",
                'league': "",
            })

    return {
        'full_name_fr': full_name_fr,
        'license_number': license_num,
        'date_of_birth': dob,
        'place_of_birth_fr': place_fr,
        'nationality': "Algérienne",
        'club_name': "ES Messelmoun",
        'ligue_name': "Ligue Wilaya de Football - Tipaza",
        'declaration_text': "Je soussigné, président du club ES Messelmoun, me suis efforcé dans la mesure du possible de produire une histoire chronologique aussi complète que possible de l'histoire d'enregistrement du joueur susmentionné depuis la saison de son 12ème anniversaire et déclare, au nom du club ES Messelmoun que les détails fournis dans ce document sont à ma connaissance fiable et exactes.",
        'rows_data': rows_data,
    }

