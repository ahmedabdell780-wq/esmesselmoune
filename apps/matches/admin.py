from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from .models import Match, Goal, Card, Injury, Referee, PlayerMatchPerformance


class PerformanceInline(admin.TabularInline):
    model = PlayerMatchPerformance
    extra = 0
    autocomplete_fields = ('player',)
    fields = ('player', 'rating', 'is_starter', 'position_name', 'notes')


class GoalInline(admin.TabularInline):
    model = Goal
    extra = 0
    fields = ('minute', 'player', 'team', 'goal_type', 'assist_player', 'is_extra_time')
    ordering = ('minute',)


class CardInline(admin.TabularInline):
    model = Card
    extra = 0
    fields = ('minute', 'player', 'team', 'card_type', 'reason', 'results_in_suspension')
    ordering = ('minute',)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display  = ('match_display', 'score_display_col', 'stage',
                     'match_date', 'status', 'referee', 'goals_count')
    list_filter   = ('tournament', 'stage', 'status', 'match_date')
    search_fields = ('team1__name', 'team2__name', 'venue')
    date_hierarchy = 'match_date'
    ordering      = ('match_date',)
    inlines       = [GoalInline, CardInline, PerformanceInline]
    actions       = ['mark_finished', 'mark_live', 'mark_scheduled']
    readonly_fields = ('created_at', 'updated_at', 'result_display')
    list_select_related = ('team1', 'team2', 'tournament')

    fieldsets = (
        ('Contexte', {
            'fields': ('tournament', 'group', 'stage', 'match_day', 'round_number')
        }),
        ('Équipes & Score', {
            'fields': ('team1', 'team2', 'score_team1', 'score_team2',
                       'penalties_team1', 'penalties_team2', 'result_display')
        }),
        ('Organisation', {
            'fields': ('match_date', 'venue', 'referee', 'status', 'notes')
        }),
        ('Affiche (Poster)', {
            'fields': ('featured_player1', 'featured_player2'),
            'description': _("Sélectionnez les joueurs à afficher sur l'affiche du match (style RSL).")
        }),
        ('Bracket', {
            'fields': ('next_match',),
            'classes': ('collapse',)
        }),
        ('Méta', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "featured_player1":
            match_id = request.resolver_match.kwargs.get('object_id')
            if match_id:
                match = Match.objects.get(pk=match_id)
                if match.team1:
                    kwargs["queryset"] = match.team1.players.all()
                else:
                    from apps.teams.models import Player
                    kwargs["queryset"] = Player.objects.none()
        if db_field.name == "featured_player2":
            match_id = request.resolver_match.kwargs.get('object_id')
            if match_id:
                match = Match.objects.get(pk=match_id)
                if match.team2:
                    kwargs["queryset"] = match.team2.players.all()
                else:
                    from apps.teams.models import Player
                    kwargs["queryset"] = Player.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _goals=Count('goals', distinct=True)
        )

    def match_display(self, obj):
        t1_name = obj.team1.name if obj.team1 else 'TBD'
        t2_name = obj.team2.name if obj.team2 else 'TBD'
        return format_html(
            '<strong>{}</strong> <span style="color:#6b7280">vs</span> <strong>{}</strong>',
            t1_name, t2_name
        )
    match_display.short_description = 'Match'

    def score_display_col(self, obj):
        if obj.score_team1 is None:
            return format_html('<span style="color:#9ca3af">— : —</span>')
        color = '#10b981' if obj.is_finished else '#f59e0b'
        return format_html(
            '<span style="font-weight:bold;font-size:15px;color:{}">{} : {}</span>',
            color, obj.score_team1, obj.score_team2
        )
    score_display_col.short_description = 'Score'

    def result_display(self, obj):
        r = obj.result
        if not r:
            return '—'
        if r == 'team1_win':
            t_name = obj.team1.name if obj.team1 else 'TBD'
            return format_html('🏆 <strong>{}</strong>', t_name)
        if r == 'team2_win':
            t_name = obj.team2.name if obj.team2 else 'TBD'
            return format_html('🏆 <strong>{}</strong>', t_name)
        return 'Match nul'
    result_display.short_description = 'Résultat'

    def goals_count(self, obj):
        return getattr(obj, '_goals', 0)
    goals_count.short_description = '⚽'
    goals_count.admin_order_field = '_goals'

    @admin.action(description='✅ Marquer comme terminé')
    def mark_finished(self, request, queryset):
        queryset.update(status=Match.Status.FINISHED)

    @admin.action(description='🔴 Marquer En cours')
    def mark_live(self, request, queryset):
        queryset.update(status=Match.Status.LIVE)

    @admin.action(description='🕐 Marquer Programmé')
    def mark_scheduled(self, request, queryset):
        queryset.update(status=Match.Status.SCHEDULED)


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ('player', 'team', 'match', 'goal_type', 'minute')
    list_filter  = ('goal_type', 'is_extra_time', 'match__tournament', 'team')
    search_fields = ('player__first_name', 'player__last_name', 'team__name')
    ordering = ('-match__match_date', 'minute')


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display  = ('player', 'team', 'match', 'card_type', 'minute', 'suspension_matches', 'results_in_suspension')
    list_filter   = ('card_type', 'results_in_suspension', 'match__tournament', 'team')
    search_fields = ('player__first_name', 'player__last_name', 'reason')
    list_editable = ('suspension_matches', 'results_in_suspension')
    ordering = ('-match__match_date', 'minute')


@admin.register(Injury)
class InjuryAdmin(admin.ModelAdmin):
    list_display  = ('player', 'injury_type', 'severity', 'injury_date',
                     'absence_weeks', 'expected_return', 'is_recovered')
    list_filter   = ('injury_type', 'severity', 'is_recovered', 'player__team')
    search_fields = ('player__first_name', 'player__last_name', 'body_part')
    list_editable = ('is_recovered',)
    date_hierarchy = 'injury_date'
    fieldsets = (
        ('Joueur', {'fields': ('player', 'match')}),
        ('Blessure', {
            'fields': ('injury_type', 'severity', 'body_part',
                       'injury_date', 'description')
        }),
        ('Suivi', {
            'fields': ('absence_weeks', 'expected_return',
                       'is_recovered', 'actual_return')
        }),
    )


@admin.register(Referee)
class RefereeAdmin(admin.ModelAdmin):
    list_display  = ('photo_preview', 'user', 'license_number', 'experience_years')
    search_fields = ('user__first_name', 'user__last_name', 'license_number')

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="width:36px;height:36px;object-fit:cover;border-radius:50%;border:2px solid #ccc;"/>', obj.photo.url)
        elif obj.user and obj.user.avatar:
            return format_html('<img src="{}" style="width:36px;height:36px;object-fit:cover;border-radius:50%;border:2px solid #ccc;"/>', obj.user.avatar.url)
        return format_html('<div style="width:36px;height:36px;border-radius:50%;background:#e5e7eb;display:flex;align-items:center;justify-content:center;font-size:16px;color:#9ca3af;border:2px solid #e5e7eb;">👤</div>')
    photo_preview.short_description = _('Photo / الصورة')
