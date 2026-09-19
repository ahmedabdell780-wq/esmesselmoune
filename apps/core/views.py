from django.views.generic import TemplateView
from django.utils import timezone
from apps.tournaments.models import Tournament
from apps.matches.models import Match, Goal
from apps.teams.models import Team


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
            from django.db.models import Count
            # Upcoming matches
            ctx['upcoming_matches'] = (
                Match.objects
                .filter(tournament=tournament, status=Match.Status.SCHEDULED,
                        match_date__gte=timezone.now())
                .select_related('team1', 'team2', 'group')
                .order_by('match_date')[:4]
            )
            # Recent results
            ctx['recent_matches'] = (
                Match.objects
                .filter(tournament=tournament, status=Match.Status.FINISHED)
                .select_related('team1', 'team2')
                .prefetch_related('goals')
                .order_by('-match_date')[:4]
            )
            # Top scorers
            ctx['top_scorers'] = (
                Goal.objects
                .filter(match__tournament=tournament)
                .exclude(goal_type='own_goal')
                .values('player__id', 'player__first_name', 'player__last_name',
                        'player__jersey_number', 'team__name', 'team__logo',
                        'team__color_primary')
                .annotate(goals=Count('id'))
                .order_by('-goals')[:5]
            )
            # Recent Media (Photos/Videos)
            from apps.matches.models import MatchMedia
            ctx['recent_media'] = (
                MatchMedia.objects
                .filter(match__tournament=tournament)
                .select_related('match__team1', 'match__team2')
                .order_by('-uploaded_at')[:6]
            )
            # Groups summary
            ctx['groups'] = (
                tournament.groups.prefetch_related(
                    'groupstanding_set__team',
                    'teams',
                )
            )
            # Stats
            ctx['stats'] = {
                'total_teams': tournament.registered_team_count,
                'total_matches': Match.objects.filter(tournament=tournament).count(),
                'finished_matches': Match.objects.filter(
                    tournament=tournament, status=Match.Status.FINISHED).count(),
                'total_goals': Goal.objects.filter(
                    match__tournament=tournament).count(),
            }

        # Past Tournaments (Hall of Fame)
        past_qs = Tournament.objects.filter(status=Tournament.Status.FINISHED).order_by('-year', '-edition')
        
        ctx['defending_champion_tournament'] = past_qs.first()
        ctx['defending_champion'] = past_qs.first().winner if past_qs.exists() else None

        if tournament:
            past_qs = past_qs.exclude(id=tournament.id)
            
        ctx['past_tournaments'] = past_qs.select_related('winner')

        return ctx
