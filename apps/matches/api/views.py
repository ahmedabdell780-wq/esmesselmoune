"""
TurniQ Matches API — MatchViewSet, GoalViewSet, CardViewSet, InjuryViewSet.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from apps.matches.models import Match, Goal, Card, Injury
from .serializers import (
    MatchSerializer, MatchWriteSerializer,
    GoalSerializer, CardSerializer, InjurySerializer,
)


class IsAdminOrOrganizer(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user.is_authenticated and
            request.user.role in ('admin', 'organizer')
        )


class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all().select_related(
        'team1', 'team2', 'tournament', 'group', 'referee__user'
    ).prefetch_related('goals__player', 'cards__player')
    filter_backends  = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tournament', 'group', 'stage', 'status', 'match_day']
    ordering_fields  = ['match_date', 'match_day']
    ordering         = ['match_date']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MatchWriteSerializer
        return MatchSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'enter_score', 'add_goal', 'add_card'):
            return [IsAdminOrOrganizer()]
        return [permissions.AllowAny()]

    # ── Custom actions ────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='enter-score')
    def enter_score(self, request, pk=None):
        """
        POST /api/v1/matches/{id}/enter-score/
        Body: { "score_team1": 2, "score_team2": 1 }
        Triggers signal → standings recalc / winner propagation.
        """
        match = self.get_object()
        s1 = request.data.get('score_team1')
        s2 = request.data.get('score_team2')
        if s1 is None or s2 is None:
            return Response(
                {'error': 'score_team1 et score_team2 sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            match.score_team1 = int(s1)
            match.score_team2 = int(s2)
        except (ValueError, TypeError):
            return Response({'error': 'Les scores doivent être des entiers.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Optional penalties
        p1 = request.data.get('penalties_team1')
        p2 = request.data.get('penalties_team2')
        if p1 is not None and p2 is not None:
            match.penalties_team1 = int(p1)
            match.penalties_team2 = int(p2)

        match.status = Match.Status.FINISHED
        match.save()  # → fires post_save signal
        return Response(MatchSerializer(match, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='add-goal')
    def add_goal(self, request, pk=None):
        """Add a goal event to this match."""
        match = self.get_object()
        data  = request.data.copy()
        data['match'] = match.pk
        ser = GoalSerializer(data=data)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='add-card')
    def add_card(self, request, pk=None):
        """Add a card event to this match."""
        match = self.get_object()
        data  = request.data.copy()
        data['match'] = match.pk
        ser = CardSerializer(data=data)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='live')
    def live(self, request):
        """Return all matches currently in LIVE status."""
        qs = self.get_queryset().filter(status=Match.Status.LIVE)
        return Response(MatchSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='upcoming')
    def upcoming(self, request):
        """Return next N scheduled matches."""
        from django.utils import timezone
        limit = int(request.query_params.get('limit', 5))
        qs = (
            self.get_queryset()
            .filter(status=Match.Status.SCHEDULED, match_date__gte=timezone.now())
            .order_by('match_date')[:limit]
        )
        return Response(MatchSerializer(qs, many=True, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='results')
    def results(self, request):
        """Return last N finished matches."""
        limit = int(request.query_params.get('limit', 10))
        qs = (
            self.get_queryset()
            .filter(status=Match.Status.FINISHED)
            .order_by('-match_date')[:limit]
        )
        return Response(MatchSerializer(qs, many=True, context={'request': request}).data)


class GoalViewSet(viewsets.ModelViewSet):
    queryset = Goal.objects.all().select_related('player', 'team', 'match')
    serializer_class = GoalSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['match', 'player', 'team', 'goal_type']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrOrganizer()]
        return [permissions.AllowAny()]


class CardViewSet(viewsets.ModelViewSet):
    queryset = Card.objects.all().select_related('player', 'team', 'match')
    serializer_class = CardSerializer
    filter_backends  = [DjangoFilterBackend]
    filterset_fields = ['match', 'player', 'team', 'card_type', 'results_in_suspension']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrOrganizer()]
        return [permissions.AllowAny()]


class InjuryViewSet(viewsets.ModelViewSet):
    queryset = Injury.objects.all().select_related('player__team', 'match')
    serializer_class = InjurySerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['player__team', 'injury_type', 'severity', 'is_recovered']
    search_fields    = ['player__first_name', 'player__last_name']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrOrganizer()]
        return [permissions.AllowAny()]
