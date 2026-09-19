from rest_framework import serializers
from apps.tournaments.models import Tournament, Group, GroupStanding
from apps.teams.api.serializers import TeamListSerializer


class GroupStandingSerializer(serializers.ModelSerializer):
    team_name   = serializers.CharField(source='team.name', read_only=True)
    team_logo   = serializers.ImageField(source='team.logo',  read_only=True)
    team_color  = serializers.CharField(source='team.color_primary', read_only=True)
    goal_difference = serializers.ReadOnlyField()

    class Meta:
        model  = GroupStanding
        fields = [
            'team', 'team_name', 'team_logo', 'team_color',
            'played', 'won', 'drawn', 'lost',
            'goals_for', 'goals_against', 'goal_difference', 'points',
        ]


class GroupSerializer(serializers.ModelSerializer):
    teams     = TeamListSerializer(many=True, read_only=True)
    standings = GroupStandingSerializer(
        source='groupstanding_set', many=True, read_only=True
    )

    class Meta:
        model  = Group
        fields = ['id', 'name', 'tournament', 'teams', 'standings']


class TournamentSerializer(serializers.ModelSerializer):
    registered_team_count = serializers.ReadOnlyField()
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    format_display  = serializers.CharField(source='get_format_display', read_only=True)
    winner_name     = serializers.CharField(source='winner.name', read_only=True, default=None)

    class Meta:
        model  = Tournament
        fields = [
            'id', 'name', 'edition', 'year', 'description',
            'format', 'format_display', 'status', 'status_display',
            'max_teams', 'num_groups', 'teams_advancing_per_group',
            'points_win', 'points_draw', 'points_loss',
            'start_date', 'end_date', 'location', 'banner',
            'winner', 'winner_name', 'registered_team_count',
        ]


class TournamentDetailSerializer(TournamentSerializer):
    groups = GroupSerializer(many=True, read_only=True)

    class Meta(TournamentSerializer.Meta):
        fields = TournamentSerializer.Meta.fields + ['groups']
