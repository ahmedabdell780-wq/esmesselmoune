from rest_framework import serializers
from apps.matches.models import Match, Goal, Card, Injury


class GoalSerializer(serializers.ModelSerializer):
    player_name    = serializers.CharField(source='player.full_name', read_only=True)
    team_name      = serializers.CharField(source='team.name', read_only=True)
    assist_name    = serializers.CharField(source='assist_player.full_name', read_only=True, default=None)
    goal_type_display = serializers.CharField(source='get_goal_type_display', read_only=True)

    class Meta:
        model  = Goal
        fields = [
            'id', 'match', 'player', 'player_name', 'team', 'team_name',
            'goal_type', 'goal_type_display', 'minute', 'is_extra_time',
            'assist_player', 'assist_name',
        ]


class CardSerializer(serializers.ModelSerializer):
    player_name    = serializers.CharField(source='player.full_name', read_only=True)
    team_name      = serializers.CharField(source='team.name',   read_only=True)
    card_type_display = serializers.CharField(source='get_card_type_display', read_only=True)

    class Meta:
        model  = Card
        fields = [
            'id', 'match', 'player', 'player_name', 'team', 'team_name',
            'card_type', 'card_type_display', 'minute', 'reason',
            'results_in_suspension',
        ]


class MatchSerializer(serializers.ModelSerializer):
    team1_name   = serializers.CharField(source='team1.name',  read_only=True)
    team2_name   = serializers.CharField(source='team2.name',  read_only=True)
    team1_logo   = serializers.ImageField(source='team1.logo', read_only=True)
    team2_logo   = serializers.ImageField(source='team2.logo', read_only=True)
    score_display = serializers.ReadOnlyField()
    result        = serializers.ReadOnlyField()
    winner_name   = serializers.SerializerMethodField()
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    status_display= serializers.CharField(source='get_status_display', read_only=True)
    goals         = GoalSerializer(many=True, read_only=True)
    cards         = CardSerializer(many=True, read_only=True)

    class Meta:
        model  = Match
        fields = [
            'id', 'tournament', 'group', 'stage', 'stage_display',
            'match_day', 'round_number',
            'team1', 'team1_name', 'team1_logo',
            'team2', 'team2_name', 'team2_logo',
            'score_team1', 'score_team2', 'score_display',
            'penalties_team1', 'penalties_team2',
            'result', 'winner_name',
            'match_date', 'venue',
            'status', 'status_display',
            'goals', 'cards',
        ]

    def get_winner_name(self, obj):
        w = obj.winner
        return w.name if w else None


class MatchWriteSerializer(serializers.ModelSerializer):
    """Used for POST/PATCH — no nested read-only fields."""
    class Meta:
        model  = Match
        fields = [
            'tournament', 'group', 'stage', 'match_day', 'round_number',
            'team1', 'team2',
            'score_team1', 'score_team2',
            'penalties_team1', 'penalties_team2',
            'match_date', 'venue', 'referee', 'status', 'notes', 'next_match',
        ]


class InjurySerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source='player.full_name', read_only=True)
    team_name   = serializers.CharField(source='player.team.name', read_only=True)

    class Meta:
        model  = Injury
        fields = [
            'id', 'player', 'player_name', 'team_name', 'match',
            'injury_type', 'severity', 'body_part',
            'injury_date', 'expected_return', 'absence_weeks',
            'description', 'is_recovered', 'actual_return',
        ]
