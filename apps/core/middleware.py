from django.db import models
from django.core.exceptions import ObjectDoesNotExist

class AppearanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                request.appearance = request.user.appearance
            except (AttributeError, ObjectDoesNotExist):
                from apps.accounts.models import AppearanceSettings
                request.appearance = AppearanceSettings.get_or_create_for(request.user)
        else:
            request.appearance = _DefaultAppearance()
        return self.get_response(request)


class _DefaultAppearance:
    theme         = 'dark'
    primary_color = '#C5A028'
    font_size     = 'base'
    font_family   = 'cairo'
    language      = 'fr'
    show_stats_sidebar    = True
    notifications_enabled = False


import re
from django.shortcuts import redirect

class ForceTeamCreationMiddleware:
    """
    Forces users with 'manager' role to create a team before they can browse the rest of the application.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_paths = [
            r'^/$',                  # Home (Onboarding screen)
            r'^/teams/create/$',     # Create team form
            r'^/accounts/',          # Login, logout, profile
            r'^/static/',            # Static files
            r'^/media/',             # Media files
            r'^/admin/',             # Django admin
        ]
        self.allowed_regexes = [re.compile(p) for p in self.allowed_paths]

    def __call__(self, request):
        path = request.path_info
        
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        user = request.user
        if user.is_authenticated and user.role == 'manager':
            is_allowed = any(regex.match(path) for regex in self.allowed_regexes)
            
            if not is_allowed:
                if not user.teams_managed.exists():
                    from django.contrib import messages
                    messages.warning(request, '⛔ يجب عليك إنشاء فريقك أولاً قبل تصفح باقي أقسام التطبيق.')
                    return redirect('core:home')
                    
        return self.get_response(request)
