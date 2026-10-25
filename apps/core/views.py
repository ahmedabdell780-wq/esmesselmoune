from django.shortcuts import render
from django.views.generic import TemplateView
from django.utils import timezone
from django.db.models import Count, Q
from apps.tournaments.models import Tournament, GroupStanding
from apps.matches.models import Match, Goal
from apps.teams.models import Team
from apps.clubs.models import ClubMatch


def category_matches(request, category_name):
    """Partial view to render matches for a specific category (U15, U17, U20)."""
    matches = (
        ClubMatch.objects
        .filter(category__name__iexact=category_name)
        .order_by('-date', '-time')[:5]
    )
    return render(request, 'core/partials/category_matches.html', {'matches': matches})


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        tournament = (
            Tournament.objects
            .filter(status__in=[
                Tournament.Status.GROUP_STAGE,
                Tournament.Status.KNOCKOUT,
                Tournament.Status.FINISHED,
            ])
            .order_by('-year', '-edition')
            .first()
        )

        ctx['tournament'] = tournament

        # Add manager's team context for onboarding flow
        if self.request.user.is_authenticated and self.request.user.role == 'manager':
            ctx['manager_team'] = self.request.user.teams_managed.first()

        if tournament:
            # Upcoming match (hero card uses only the first match)
            ctx['upcoming_matches'] = (
                Match.objects
                .filter(tournament=tournament, status=Match.Status.SCHEDULED,
                        match_date__gte=timezone.now())
                .select_related('team1', 'team2')
                .order_by('match_date')[:1]
            )

            # First group with sorted standings for mini-table
            first_group = tournament.groups.first()
            if first_group:
                standings = list(
                    GroupStanding.objects
                    .filter(group=first_group)
                    .select_related('team')
                    .order_by('-points', '-goal_difference', '-goals_for')[:4]
                )
                first_group._precomputed_standings = standings
                ctx['groups'] = [first_group]
            else:
                ctx['groups'] = []

            # Aggregated Stats
            match_counts = Match.objects.filter(tournament=tournament).aggregate(
                total=Count('id'),
                finished=Count('id', filter=Q(status=Match.Status.FINISHED)),
            )
            total_goals = Goal.objects.filter(match__tournament=tournament).count()

            ctx['stats'] = {
                'total_teams': tournament.registered_team_count,
                'total_matches': match_counts['total'] or 0,
                'finished_matches': match_counts['finished'] or 0,
                'total_goals': total_goals,
            }

        # Category matches default tab (U15)
        ctx['u15_matches'] = (
            ClubMatch.objects
            .filter(category__name__iexact='U15')
            .order_by('-date', '-time')[:5]
        )

        # Past Tournaments (Hall of Fame) - single query with select_related
        past_list = list(
            Tournament.objects
            .filter(status=Tournament.Status.FINISHED)
            .select_related('winner')
            .order_by('-year', '-edition')
        )
        defending_champ = past_list[0] if past_list else None
        ctx['defending_champion_tournament'] = defending_champ
        ctx['defending_champion'] = defending_champ.winner if defending_champ else None

        if tournament and defending_champ and defending_champ.id == tournament.id:
            ctx['past_tournaments'] = [t for t in past_list if t.id != tournament.id]
        else:
            ctx['past_tournaments'] = past_list

        return ctx


import os
from django.conf import settings
from django.http import HttpResponse, Http404


def service_worker(request):
    """Serve the root Service Worker script with unrestricted root scope."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    if os.path.exists(sw_path):
        with open(sw_path, 'r', encoding='utf-8') as f:
            content = f.read()
        response = HttpResponse(content, content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    raise Http404("Service Worker not found")


def manifest_json(request):
    """Serve the Web App Manifest from the site root."""
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
        response = HttpResponse(content, content_type='application/manifest+json')
        response['Cache-Control'] = 'public, max-age=86400'
        return response
    raise Http404("Manifest not found")


class OfflineView(TemplateView):
    """Fallback offline view displayed by Service Worker when network fails."""
    template_name = 'offline.html'
