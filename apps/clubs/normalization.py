# -*- coding: utf-8 -*-
"""
Smart Arabic normalization, automated category determination, and duplicate detection
for Club Players in ES Messelmoun / TurniQ.
"""
import re
from datetime import date
from django.utils.translation import gettext_lazy as _

def normalize_arabic_text(text: str) -> str:
    """
    Normalizes Arabic text to handle spelling and typographic variations:
    - Removes Tashkeel (harakat), Tanween, Shadda, and Tatweel/Kashida (ـ).
    - Unifies Alef forms: [إ, أ, آ, ٱ] -> ا.
    - Unifies Yaa and Alef Maqsura: [ى] -> ي.
    - Unifies Hamza variants: [ؤ] -> و, [ئ] -> ي, [ء] -> removed.
    - Unifies Taa Marbuta: [ة] -> ه.
    - Strips all punctuation, dashes, and extra spaces.
    """
    if not text:
        return ''
    # Remove tashkeel and tatweel
    s = re.sub(r'[\u064B-\u065F\u0670\u0640]', '', str(text))
    # Unify Alef variants
    s = re.sub(r'[إأآٱ]', 'ا', s)
    # Unify Yaa / Alef Maqsura
    s = re.sub(r'[ى]', 'ي', s)
    # Unify Taa Marbuta
    s = re.sub(r'[ة]', 'ه', s)
    # Unify Hamza on Waw / Nabira / isolated
    s = re.sub(r'[ؤ]', 'و', s)
    s = re.sub(r'[ئ]', 'ي', s)
    s = re.sub(r'[ء]', '', s)
    # Remove non-alphanumeric (except whitespace)
    s = re.sub(r'[^\w\s]', '', s)
    return s.strip().lower()

def get_name_keys(first_name: str, last_name: str):
    """
    Returns multiple normalized representations to catch all spacing, spelling,
    and name order (swapped first/last) variations:
    1. direct_compact: first+last without any spaces
    2. reverse_compact: last+first without any spaces
    3. tokens_sorted: all words normalized, sorted, and concatenated
    """
    fn_norm = normalize_arabic_text(first_name)
    ln_norm = normalize_arabic_text(last_name)
    
    # Strip all whitespace
    fn_compact = re.sub(r'\s+', '', fn_norm)
    ln_compact = re.sub(r'\s+', '', ln_norm)
    
    direct_compact = fn_compact + ln_compact
    reverse_compact = ln_compact + fn_compact
    
    # Word tokens
    words = [w for w in (fn_norm + ' ' + ln_norm).split() if w]
    tokens_sorted = ''.join(sorted(words))
    
    return direct_compact, reverse_compact, tokens_sorted

def are_names_matching(fn1: str, ln1: str, fn2: str, ln2: str) -> bool:
    """
    Returns True if the two names are considered the same person,
    ignoring alef/hamza variations, yaa/alef maqsura, taa marbuta,
    spaces between compound words ('ضياء الدين' vs 'ضياءالدين'),
    and inverted first/last name order.
    """
    d1, r1, t1 = get_name_keys(fn1, ln1)
    d2, r2, t2 = get_name_keys(fn2, ln2)
    
    if not (d1 or r1 or t1) or not (d2 or r2 or t2):
        return False

    # 1. Direct compact match (no spaces)
    if d1 and (d1 == d2 or d1 == r2):
        return True
    if r1 and (r1 == d2 or r1 == r2):
        return True
        
    # 2. Token-sorted match (any word order permutation)
    if t1 and t1 == t2:
        return True
        
    return False

def get_category_for_dob(dob):
    """
    Automatically determine the appropriate youth/club Category for a player
    based on date of birth (current season 2026/2027 in Ligue Tipaza / FAF):
    - Born <= 2009 (2006, 2007, 2008, 2009): U20
    - Born 2010, 2011: U17
    - Born 2012, 2013: U15
    - Born 2014: U13
    - Born 2015, 2016: U11
    - Born >= 2017 (2017, 2018, 2019, 2020+): U9
    """
    if not dob:
        return None
    from apps.clubs.models import Category
    
    year = dob.year if hasattr(dob, 'year') else None
    if not year:
        return None
        
    target_name = None
    if year <= 2009:
        target_name = 'U20'
    elif year in (2010, 2011):
        target_name = 'U17'
    elif year in (2012, 2013):
        target_name = 'U15'
    elif year == 2014:
        target_name = 'U13'
    elif year in (2015, 2016):
        target_name = 'U11'
    elif year >= 2017:
        target_name = 'U9'
        
    if target_name:
        cat = Category.objects.filter(name__iexact=target_name).first()
        if cat:
            return cat
            
    # Fallback to age range in Category model if available
    ref_year = 2026
    age = ref_year - year
    for cat in Category.objects.all():
        if cat.min_age is not None and cat.max_age is not None:
            if cat.min_age <= age <= cat.max_age:
                return cat
                
    return None

def find_duplicate_player(first_name: str, last_name: str, date_of_birth, exclude_id=None):
    """
    Finds if an existing player matches the given identity.
    Checks:
    1. Exact or normalized matching on date_of_birth AND (first_name + last_name)
       with resilient Arabic normalization and space tolerance.
    Returns the matching ClubPlayer instance, or None.
    """
    if not first_name or not last_name:
        return None
        
    from apps.clubs.models import ClubPlayer
    
    # 1. Check exact date of birth first (definite match)
    if date_of_birth:
        qs = ClubPlayer.objects.filter(date_of_birth=date_of_birth)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        for candidate in qs:
            if are_names_matching(first_name, last_name, candidate.first_name, candidate.last_name):
                return candidate

        # 2. Check same birth year (handles potential slight typo in day/month)
        year = date_of_birth.year if hasattr(date_of_birth, 'year') else None
        if year:
            same_year_qs = ClubPlayer.objects.filter(date_of_birth__year=year)
            if exclude_id:
                same_year_qs = same_year_qs.exclude(pk=exclude_id)
            for candidate in same_year_qs:
                if are_names_matching(first_name, last_name, candidate.first_name, candidate.last_name):
                    return candidate
                    
    return None


def latin_to_arabic_phonetic(latin_str: str) -> str:
    """
    Converts French/Latin Algerian spelling to phonetic normalized Arabic.
    Handles common prefixes (bou, ben, abdel) and digraphs (ch, kh, gh, dj, ou, etc.).
    """
    if not latin_str:
        return ''
    s = latin_str.lower().strip()
    s = re.sub(r'\bbou\b', 'بو ', s)
    s = re.sub(r'\bben\b', 'بن ', s)
    s = re.sub(r'\babdel\b', 'عبد ال', s)
    s = re.sub(r'\babde\b', 'عبد ', s)

    replacements = [
        ('ch', 'ش'), ('sh', 'ش'), ('kh', 'خ'), ('gh', 'غ'),
        ('dj', 'ج'), ('dh', 'ض'), ('th', 'ث'), ('ou', 'و'),
        ('oo', 'و'), ('ee', 'ي'), ('ai', 'ي'), ('ei', 'ي'),
        ('ph', 'ف'),
    ]
    for lat, ar in replacements:
        s = s.replace(lat, ar)

    single_map = {
        'a': 'ا', 'b': 'ب', 'c': 'ك', 'd': 'د', 'e': 'ي', 'f': 'ف',
        'g': 'ج', 'h': 'ه', 'i': 'ي', 'j': 'ج', 'k': 'ك', 'l': 'ل',
        'm': 'م', 'n': 'ن', 'o': 'و', 'p': 'ب', 'q': 'ق', 'r': 'ر',
        's': 'س', 't': 'ت', 'u': 'و', 'v': 'ف', 'w': 'و', 'x': 'كس',
        'y': 'ي', 'z': 'ز',
    }
    res = [single_map.get(ch, ch) for ch in s]
    return normalize_arabic_text(''.join(res))


def smart_player_search(qs, query_str: str):
    """
    Intelligent multi-attribute, bilingual, and permutation-resilient player search:
    - Trims and normalizes all Arabic & Latin input.
    - Matches across: first_name, last_name, full_name (in any order),
      passport.full_name_fr, jersey_number, position, category,
      phones, card_number, birth year, and place of birth.
    - Handles spaces inside compound names ('بوعبد الله' vs 'بوعبدالله').
    - Ranks results by relevance score.
    """
    if not query_str:
        return list(qs)
        
    raw_query = str(query_str).strip()
    if not raw_query:
        return list(qs)

    tokens = [t for t in re.split(r'[\s,\-_/]+', raw_query) if t]
    if not tokens:
        return list(qs)

    players = list(qs.select_related('category', 'passport').prefetch_related('subscriptions'))
    results = []

    for p in players:
        # Arabic names
        fn_raw = p.first_name or ''
        ln_raw = p.last_name or ''
        fn_norm = normalize_arabic_text(fn_raw)
        ln_norm = normalize_arabic_text(ln_raw)
        full_name_ar = f"{fn_norm} {ln_norm}"
        full_name_rev = f"{ln_norm} {fn_norm}"
        compact_full = full_name_ar.replace(' ', '')

        # French / Passport names
        passport = getattr(p, 'passport', None)
        passport_fn_fr = (passport.full_name_fr or '').lower().strip() if passport else ''
        player_ln_fr = (p.last_name_fr or '').lower().strip()
        player_fn_fr = (p.first_name_fr or '').lower().strip()
        player_full_fr = f"{player_ln_fr} {player_fn_fr}".strip()
        player_full_fr_rev = f"{player_fn_fr} {player_ln_fr}".strip()
        fn_fr = f"{passport_fn_fr} {player_full_fr} {player_full_fr_rev}".strip()
        lic_no = (passport.license_number or '').lower().strip() if passport else ''
        pob_fr = (passport.place_of_birth_fr or '').lower().strip() if passport else ''
        if not pob_fr and p.place_of_birth:
            pob_fr = p.place_of_birth.lower().strip()

        # Attributes
        jersey = str(p.jersey_number) if p.jersey_number is not None else ''
        card_no = str(p.card_number or '').lower()
        gen_card = str(p.generated_card_number or '').lower()
        cat_name = (p.category.name if p.category else '').lower()
        pos_raw = p.position or ''
        pos_norm = normalize_arabic_text(pos_raw)
        dob_year = str(p.date_of_birth.year) if p.date_of_birth else ''
        pob_ar = normalize_arabic_text(p.place_of_birth or '')
        phones = [
            (p.player_phone or '').replace(' ', '').replace('-', ''),
            (p.parent_phone or '').replace(' ', '').replace('-', ''),
            (p.emergency_phone or '').replace(' ', '').replace('-', '')
        ]

        player_matches = True
        match_score = 0

        for tok in tokens:
            tok_norm = normalize_arabic_text(tok)
            tok_compact = tok_norm.replace(' ', '')
            tok_lower = tok.lower()
            tok_latin_ar = latin_to_arabic_phonetic(tok) if re.search(r'[a-zA-Z]', tok) else ''

            tok_matched = False

            # 1. Exact or substring match in Arabic Name
            if tok_norm and (tok_norm in full_name_ar or tok_norm in full_name_rev or tok_compact in compact_full):
                tok_matched = True
                if tok_norm == fn_norm or tok_norm == ln_norm:
                    match_score += 50
                elif full_name_ar.startswith(tok_norm) or full_name_rev.startswith(tok_norm):
                    match_score += 35
                else:
                    match_score += 20
            # 2. Match in French Passport Name
            elif tok_lower and fn_fr and tok_lower in fn_fr:
                tok_matched = True
                if fn_fr.startswith(tok_lower) or f" {tok_lower}" in fn_fr:
                    match_score += 45
                else:
                    match_score += 25
            # 3. Phonetic Latin -> Arabic match
            elif tok_latin_ar and (tok_latin_ar in compact_full or tok_latin_ar in full_name_ar):
                tok_matched = True
                match_score += 30
            # 4. Jersey Number match (e.g. "10", "#10")
            elif tok.lstrip('#').isdigit() and jersey == tok.lstrip('#'):
                tok_matched = True
                match_score += 40
            # 5. Category match (e.g. "U20", "u17", "u9")
            elif tok_lower and cat_name and tok_lower == cat_name:
                tok_matched = True
                match_score += 20
            # 6. Position match (e.g. "دفاع", "مدافع", "حارس", "وسط", "هجوم")
            elif tok_norm and pos_norm and (tok_norm in pos_norm or pos_norm in tok_norm):
                tok_matched = True
                match_score += 20
            # 7. Card / ID / License number
            elif tok_lower and (tok_lower in gen_card or (len(tok) >= 4 and tok_lower in card_no) or (len(tok) >= 3 and tok_lower in lic_no)):
                tok_matched = True
                match_score += 35
            # 8. Phone number
            elif len(tok) >= 4 and any(tok in ph for ph in phones if ph):
                tok_matched = True
                match_score += 35
            # 9. Birth Year (e.g. "2008", "2009")
            elif len(tok) == 4 and tok.isdigit() and tok == dob_year:
                tok_matched = True
                match_score += 25
            # 10. Place of birth (e.g. "مسلمون", "سيدي غيلاس", "Messelmoun")
            elif tok_norm and pob_ar and (tok_norm in pob_ar or pob_ar in tok_norm):
                tok_matched = True
                match_score += 15
            elif tok_lower and pob_fr and tok_lower in pob_fr:
                tok_matched = True
                match_score += 15

            if not tok_matched:
                player_matches = False
                break

        if player_matches:
            results.append((match_score, p))

    # Sort descending by relevance score
    results.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in results]


def get_next_available_jersey_number(category, exclude_player_id=None, max_num=100):
    """
    Finds the smallest available jersey number between 1 and max_num (inclusive)
    for a given category (strictly <= 100 for U9, U11, U13).
    """
    if not category:
        return None
    from apps.clubs.models import ClubPlayer
    qs = ClubPlayer.objects.filter(category=category, jersey_number__isnull=False)
    if exclude_player_id:
        qs = qs.exclude(pk=exclude_player_id)
    used_numbers = set(qs.values_list('jersey_number', flat=True))
    for num in range(1, max_num + 1):
        if num not in used_numbers:
            return num
    return None
