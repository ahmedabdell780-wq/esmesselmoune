"""
Global template context processors for TurniQ.
Injected into every template via TEMPLATES settings.
"""
from apps.tournaments.models import Tournament
from apps.core.models import SiteSettings

def app_settings(request):
    """Inject appearance settings into every template."""
    return {
        'appearance': getattr(request, 'appearance', None),
        'site_settings': SiteSettings.load(),
    }


def active_tournament(request):
    """Inject the currently active tournament (if any) into every template."""
    tournament = (
        Tournament.objects
        .filter(status__in=[
            Tournament.Status.GROUP_STAGE,
            Tournament.Status.KNOCKOUT,
        ])
        .order_by('-year', '-edition')
        .first()
    )
    return {
        'active_tournament': tournament,
    }
def registration_tournament(request):
    """Inject the tournament currently open for registration (if any)."""
    tournament = (
        Tournament.objects
        .filter(status=Tournament.Status.REGISTRATION)
        .order_by('-year', '-edition')
        .first()
    )
    return {
        'registration_open_tournament': tournament if (tournament and tournament.is_registration_open) else None,
    }

def pending_requests(request):
    """Count pending team registrations and user approvals for admins."""
    team_count = 0
    user_count = 0
    if request.user.is_authenticated and request.user.role in ('admin', 'organizer'):
        from apps.teams.models import Team
        from apps.accounts.models import User
        team_count = Team.objects.filter(is_active=False).count()
        user_count = User.objects.filter(is_active=False).count()
        
    return {
        'pending_teams_count': team_count,
        'pending_users_count': user_count,
        'total_pending_count': team_count + user_count,
    }

def unread_notifications(request):
    """Inject the unread notifications for the current user."""
    if request.user.is_authenticated:
        from apps.notifications.models import Notification
        notifs = Notification.objects.filter(recipient=request.user, is_read=False).order_by('-created_at')[:10]
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return {
            'unread_notifications': notifs,
            'unread_notifications_count': count,
        }
    return {}
