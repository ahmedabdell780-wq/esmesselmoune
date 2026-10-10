from django.views.generic import TemplateView
from django.utils import timezone
from apps.tournaments.models import Tournament
from apps.matches.models import Match, Goal
from apps.teams.models import Team


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.clubs.models import ClubNews, ClubPlayer, ClubMatch
        
        ctx['recent_news'] = ClubNews.objects.filter(is_published=True).order_by('-created_at')[:3]
        ctx['stats'] = {
            'total_players': ClubPlayer.objects.filter(is_active=True).count()
        }
        
        # Get next match for Wifak
        teams_data = {
            "وفاق حجوط": "wh", "أمل سيدي عمر": "esa", "ونام بوجبرون": "wbm",
            "مولودية مراد": "mcm", "اتحاد مناصر": "usm", "الوفاق مسلمون": "esms",
            "تحدي الداموس": "thd", "مولودية قوراية": "mcg", "شبيبة حجوط": "jsh",
            "اتحاد القليعة": "usjk", "نخبة فجانة": "nf", "نجمة حجوط": "ebh"
        }
        next_matches = []
        for cat in ["U15", "U17", "U20"]:
            match = ClubMatch.objects.filter(category__name__icontains=cat, our_score__isnull=True).order_by('date').first()
            if match:
                match.opponent_code = teams_data.get(match.opponent, "thd") # default to thd if not found
                if match.opponent == "اتحاد مناصر":
                    match.opponent_code = "esm" # exception handled in generator
                next_matches.append(match)
                
        ctx['next_matches'] = next_matches

        # --- FULL SCHEDULE & STATS ---
        schedule_data = []
        for cat in ["U15", "U17", "U20"]:
            cat_matches = []
            stats = {'played': 0, 'won': 0, 'drawn': 0, 'lost': 0, 'gf': 0, 'ga': 0, 'pts': 0, 'gd': 0}
            matches = ClubMatch.objects.filter(category__name__icontains=cat).order_by('date', 'time')
            for match in matches:
                match.opponent_code = teams_data.get(match.opponent, "thd")
                if match.opponent == "اتحاد مناصر":
                    match.opponent_code = "esm"
                cat_matches.append(match)
                if match.our_score is not None and match.opponent_score is not None:
                    stats['played'] += 1
                    stats['gf'] += match.our_score
                    stats['ga'] += match.opponent_score
                    if match.our_score > match.opponent_score:
                        stats['won'] += 1
                        stats['pts'] += 3
                    elif match.our_score == match.opponent_score:
                        stats['drawn'] += 1
                        stats['pts'] += 1
                    else:
                        stats['lost'] += 1
            stats['gd'] = stats['gf'] - stats['ga']
            
            schedule_data.append({
                'category': cat,
                'matches': cat_matches,
                'stats': stats
            })
            
        ctx['schedule_data'] = schedule_data

        return ctx


from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from apps.accounts.models import AppearanceSettings

@require_POST
def update_appearance(request):
    if request.user.is_authenticated:
        appearance, _ = AppearanceSettings.objects.get_or_create(user=request.user)
        
        # update theme
        theme = request.POST.get('theme')
        if theme in dict(AppearanceSettings.Theme.choices):
            appearance.theme = theme
            
        # update language
        language = request.POST.get('language')
        if language in ['fr', 'ar']:
            appearance.language = language
            
        appearance.save()
    
    next_url = request.POST.get('next', request.META.get('HTTP_REFERER', '/'))
    return redirect(next_url)


class AboutUsView(TemplateView):
    template_name = 'core/about.html'
