from django.views.generic import TemplateView
from django.utils import timezone
from apps.tournaments.models import Tournament
from apps.matches.models import Match, Goal
from apps.teams.models import Team


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        from apps.clubs.models import ClubNews, ClubPlayer
        
        ctx['recent_news'] = ClubNews.objects.filter(is_published=True).order_by('-created_at')[:3]
        ctx['stats'] = {
            'total_players': ClubPlayer.objects.filter(is_active=True).count()
        }
        
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
