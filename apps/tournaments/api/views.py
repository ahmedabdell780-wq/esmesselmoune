"""Tournaments API — ViewSets for Tournament, Group, Standings, Stats."""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.tournaments.models import Tournament, Group, GroupStanding
from .serializers import (
    TournamentSerializer, GroupSerializer,
    GroupStandingSerializer, TournamentDetailSerializer
)


class TournamentViewSet(viewsets.ModelViewSet):
    queryset = Tournament.objects.all().prefetch_related('groups', 'teams')
    serializer_class = TournamentSerializer

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return TournamentDetailSerializer
        return TournamentSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    @action(detail=True, methods=['post'], url_path='generate-groups',
            permission_classes=[permissions.IsAdminUser])
    def generate_groups(self, request, pk=None):
        """Automatically seed teams into groups."""
        from apps.tournaments.services.scheduler import GroupSeeder
        tournament = self.get_object()
        try:
            seeder = GroupSeeder(tournament)
            groups = seeder.seed_groups()
            tournament.status = Tournament.Status.GROUP_STAGE
            tournament.save(update_fields=['status'])
            return Response({
                'message': f'{len(groups)} groupes créés.',
                'groups': [g.name for g in groups]
            })
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='generate-schedule',
            permission_classes=[permissions.IsAdminUser])
    def generate_schedule(self, request, pk=None):
        """Generate group stage match schedule."""
        from apps.tournaments.services.scheduler import MatchScheduler
        tournament = self.get_object()
        scheduler = MatchScheduler(tournament)
        matches = scheduler.generate_group_stage()
        return Response({'matches_created': len(matches)})

    @action(detail=True, methods=['post'], url_path='generate-knockout',
            permission_classes=[permissions.IsAdminUser])
    def generate_knockout(self, request, pk=None):
        """Generate knockout bracket from group advancing teams."""
        tournament = self.get_object()
        if tournament.format == Tournament.Format.ROUND_ROBIN:
            return Response({'error': 'Ce tournoi est un Championnat aller-retour. Pas de phase finale.'}, status=status.HTTP_400_BAD_REQUEST)
        from apps.tournaments.services.scheduler import (
            MatchScheduler, StandingsCalculator
        )
        calc = StandingsCalculator(tournament)
        advancing = calc.get_all_advancing_teams()
        scheduler = MatchScheduler(tournament)
        matches = scheduler.generate_knockout_bracket(advancing)
        tournament.status = Tournament.Status.KNOCKOUT
        tournament.save(update_fields=['status'])
        return Response({
            'message': f'Phase finale générée avec {len(advancing)} équipes.',
            'matches_created': len(matches)
        })

    @action(detail=True, methods=['get'], url_path='standings')
    def standings(self, request, pk=None):
        """All group standings for this tournament."""
        tournament = self.get_object()
        groups = tournament.groups.prefetch_related('groupstanding_set__team')
        data = {}
        for group in groups:
            standings = GroupStanding.objects.filter(group=group).select_related('team') \
                .order_by('-points', '-goals_for', 'goals_against')
            data[group.name] = GroupStandingSerializer(standings, many=True).data
        return Response(data)

    @action(detail=True, methods=['get'], url_path='top-scorers')
    def top_scorers(self, request, pk=None):
        from django.db.models import Count
        from apps.matches.models import Goal
        tournament = self.get_object()
        qs = (
            Goal.objects
            .filter(match__tournament=tournament)
            .exclude(goal_type='own_goal')
            .values('player__id', 'player__first_name', 'player__last_name',
                    'player__jersey_number', 'team__name', 'team__logo')
            .annotate(goals=Count('id'))
            .order_by('-goals')[:10]
        )
        return Response(list(qs))

    @action(detail=True, methods=['get'], url_path='bracket')
    def bracket(self, request, pk=None):
        """Return knockout bracket structure."""
        from apps.matches.models import Match as M
        from apps.matches.api.serializers import MatchSerializer
        tournament = self.get_object()
        stages_order = ['R16', 'QF', 'SF', 'TP', 'FINAL']
        bracket = {}
        for stage_code in stages_order:
            matches = M.objects.filter(
                tournament=tournament, stage=stage_code
            ).select_related('team1', 'team2')
            if matches.exists():
                bracket[stage_code] = MatchSerializer(
                    matches, many=True, context={'request': request}
                ).data
        return Response(bracket)


class GroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all().prefetch_related('teams', 'groupstanding_set__team')
    serializer_class = GroupSerializer
    filterset_fields = ['tournament']
