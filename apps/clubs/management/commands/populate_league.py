from django.core.management.base import BaseCommand
from apps.clubs.models import ClubMatch, Category
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Populates ONLY Wifak matches into ClubMatch'

    def handle(self, *args, **kwargs):
        # Order of opponents for Wifak in the 11 rounds
        # According to the previous schedule:
        # 1. Away vs THD (تحدي الداموس)
        # 2. Home vs USM (اتحاد مناصر)
        # 3. Away vs WBM (ونام بوجبرون)
        # 4. Home vs EBH (نجمة حجوط)
        # 5. Away vs USJK (اتحاد القليعة)
        # 6. Home vs MCG (مولودية قوراية)
        # 7. Away vs WH (وفاق حجوط)
        # 8. Away vs MCM (مولودية مراد)
        # 9. Home vs ESA (أمل سيدي عمر)
        # 10. Away vs NF (نخبة فجانة)
        # 11. Home vs JSH (شبيبة حجوط)
        
        wifak_schedule = [
            {"opponent": "تحدي الداموس", "is_home": False},
            {"opponent": "اتحاد مناصر", "is_home": True},
            {"opponent": "ونام بوجبرون", "is_home": False},
            {"opponent": "نجمة حجوط", "is_home": True},
            {"opponent": "اتحاد القليعة", "is_home": False},
            {"opponent": "مولودية قوراية", "is_home": True},
            {"opponent": "وفاق حجوط", "is_home": False},
            {"opponent": "مولودية مراد", "is_home": False},
            {"opponent": "أمل سيدي عمر", "is_home": True},
            {"opponent": "نخبة فجانة", "is_home": False},
            {"opponent": "شبيبة حجوط", "is_home": True},
        ]
        
        # Clear existing ClubMatches if any (to avoid duplicates if run multiple times)
        ClubMatch.objects.filter(notes="Auto-generated Wifak Match").delete()
        
        start_date = date.today()
        
        matches_to_create = []
        for cat_name in ["U15", "U17", "U20"]:
            cat, _ = Category.objects.get_or_create(name=cat_name)
            
            for i, match_data in enumerate(wifak_schedule):
                match_date = start_date + timedelta(days=i*7) # One match per week roughly
                
                matches_to_create.append(ClubMatch(
                    category=cat,
                    opponent=match_data["opponent"],
                    is_home=match_data["is_home"],
                    location="الملعب البلدي" if match_data["is_home"] else "ملعب الخصم",
                    date=match_date,
                    notes="Auto-generated Wifak Match"
                ))
                
        ClubMatch.objects.bulk_create(matches_to_create)
        self.stdout.write("Success")
