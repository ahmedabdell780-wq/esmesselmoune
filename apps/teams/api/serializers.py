from rest_framework import serializers
from apps.teams.models import Team, Player


class PlayerSerializer(serializers.ModelSerializer):
    full_name        = serializers.ReadOnlyField()
    age              = serializers.ReadOnlyField()
    position_display = serializers.CharField(source='get_position_display', read_only=True)
    team_name        = serializers.CharField(source='team.name', read_only=True)

    class Meta:
        model  = Player
        fields = [
            'id', 'full_name', 'first_name', 'last_name', 'age',
            'team', 'team_name', 'jersey_number', 'position', 'position_display',
            'preferred_foot', 'height_cm', 'weight_kg',
            'photo', 'is_active', 'is_suspended',
        ]


class TeamListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view."""
    active_player_count = serializers.ReadOnlyField()

    class Meta:
        model  = Team
        fields = ['id', 'name', 'neighborhood', 'city', 'logo',
                  'color_primary', 'color_secondary', 'active_player_count']


class TeamSerializer(serializers.ModelSerializer):
    """Full serializer with nested players."""
    players             = PlayerSerializer(many=True, read_only=True)
    active_player_count = serializers.ReadOnlyField()
    manager_name        = serializers.CharField(
        source='manager.get_full_name', read_only=True, default=None
    )

    class Meta:
        model  = Team
        fields = [
            'id', 'name', 'neighborhood', 'city', 'wilaya',
            'logo', 'color_primary', 'color_secondary',
            'manager', 'manager_name', 'founded_year',
            'contact_phone', 'contact_email', 'description',
            'is_active', 'active_player_count', 'players',
            'created_at',
        ]
        read_only_fields = ['created_at']
