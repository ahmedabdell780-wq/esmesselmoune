"""TurniQ — Main URL Configuration."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# ─── DRF Router ──────────────────────────────────────────────────────────────
router = DefaultRouter()

# Teams
from apps.teams.api.views import TeamViewSet, PlayerViewSet
router.register(r'teams', TeamViewSet, basename='team')
router.register(r'players', PlayerViewSet, basename='player')

# Tournaments
from apps.tournaments.api.views import TournamentViewSet, GroupViewSet
router.register(r'tournaments', TournamentViewSet, basename='tournament')
router.register(r'groups', GroupViewSet, basename='group')

# Matches
from apps.matches.api.views import MatchViewSet, GoalViewSet, CardViewSet
router.register(r'matches', MatchViewSet, basename='match')
router.register(r'goals', GoalViewSet, basename='goal')
router.register(r'cards', CardViewSet, basename='card')

# ─── URL Patterns ─────────────────────────────────────────────────────────────
urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # i18n
    path('i18n/', include('django.conf.urls.i18n')),

    # Auth
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),

    # Main app
    path('', include('apps.core.urls', namespace='core')),
    path('teams/', include('apps.teams.urls', namespace='teams')),
    path('tournaments/', include('apps.tournaments.urls', namespace='tournaments')),
    path('matches/', include('apps.matches.urls', namespace='matches')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),
    path('club/', include('apps.clubs.urls', namespace='clubs')),

    # REST API v1
    path('api/v1/', include(router.urls)),
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/', include('rest_framework.urls')),

    # Standings & Stats API
    path('api/v1/', include('apps.tournaments.api.urls')),
    path('api/v1/', include('apps.matches.api.urls')),
]

# ─── Media in development ─────────────────────────────────────────────────────
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ─── Admin customization ──────────────────────────────────────────────────────
admin.site.site_header = 'TurniQ Administration'
admin.site.site_title = 'TurniQ'
admin.site.index_title = 'Tableau de bord'

# Global search
from apps.teams.views import GlobalSearchView
urlpatterns += [path('search/', GlobalSearchView.as_view(), name='global_search')]
