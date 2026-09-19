from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.teams.models import Team, Player
from .serializers import TeamSerializer, TeamListSerializer, PlayerSerializer


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.filter(is_active=True).prefetch_related('players')
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields   = ['name', 'neighborhood', 'city']
    filterset_fields = ['city', 'wilaya', 'is_active']
    ordering_fields  = ['name', 'created_at']
    ordering         = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return TeamListSerializer
        return TeamSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    @action(detail=True, methods=['get'])
    def players(self, request, pk=None):
        team = self.get_object()
        qs   = team.players.filter(is_active=True)
        serializer = PlayerSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        from django.db.models import Count, Sum
        from apps.matches.models import Goal, Card
        team = self.get_object()
        goals_scored = Goal.objects.filter(team=team).exclude(goal_type='own_goal').count()
        goals_own    = Goal.objects.filter(team=team, goal_type='own_goal').count()
        yellow_cards = Card.objects.filter(team=team, card_type='yellow').count()
        red_cards    = Card.objects.filter(team=team, card_type__in=['red','yellow_red']).count()
        return Response({
            'team': team.name,
            'goals_scored': goals_scored,
            'own_goals': goals_own,
            'yellow_cards': yellow_cards,
            'red_cards': red_cards,
            'players_active': team.active_player_count,
        })


class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.filter(is_active=True).select_related('team')
    serializer_class = PlayerSerializer
    filter_backends  = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields    = ['first_name', 'last_name', 'national_id']
    filterset_fields = ['team', 'position', 'is_suspended']
    ordering_fields  = ['last_name', 'jersey_number']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        from apps.matches.models import Goal, Card, Injury
        player = self.get_object()
        return Response({
            'player': player.full_name,
            'team': player.team.name,
            'goals': Goal.objects.filter(player=player).exclude(goal_type='own_goal').count(),
            'assists': Goal.objects.filter(assist_player=player).count(),
            'yellow_cards': Card.objects.filter(player=player, card_type='yellow').count(),
            'red_cards': Card.objects.filter(player=player, card_type__in=['red','yellow_red']).count(),
            'injuries': Injury.objects.filter(player=player).count(),
        })
