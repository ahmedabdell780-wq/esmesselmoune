from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    Tournament, TournamentTeam, Group, GroupStanding,
    TournamentExpense, TournamentRevenue, TeamPaymentTransaction,
    CommitteeMember,
)


class TournamentTeamInline(admin.TabularInline):
    model = TournamentTeam
    extra = 0
    fields = ('team', 'is_confirmed', 'seed', 'eliminated_at_stage')
    show_change_link = False
    ordering = ('seed', 'team__name')


class GroupInline(admin.TabularInline):
    model = Group
    extra = 0
    fields = ('name',)
    show_change_link = True


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'year', 'edition', 'format', 'status_badge',
                     'registered_teams', 'winner_display', 'start_date')
    list_filter   = ('status', 'format', 'year')
    search_fields = ('name', 'location')
    ordering      = ('-year', '-edition')
    inlines       = [TournamentTeamInline, GroupInline]
    readonly_fields = ('created_at', 'updated_at', 'banner_preview',
                       'registered_team_count')
    actions = ['open_registration', 'start_group_stage', 'start_knockout', 'finish']

    fieldsets = (
        ('Informations', {
            'fields': ('name', 'edition', 'year', 'description', 'banner', 'banner_preview')
        }),
        ('Format', {
            'fields': ('format', 'status', 'num_groups',
                       'teams_advancing_per_group', 'max_teams')
        }),
        ('Système de points', {
            'fields': ('points_win', 'points_draw', 'points_loss'),
            'classes': ('collapse',),
        }),
        ('Dates & Lieu', {
            'fields': ('registration_start_date', 'registration_deadline', 'start_date', 'end_date', 'location'),
        }),
        ('Résultats', {
            'fields': ('winner', 'runner_up'),
        }),
        ('Stats', {
            'fields': ('registered_team_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'draft':        '#6b7280',
            'registration': '#3b82f6',
            'group_stage':  '#f59e0b',
            'knockout':     '#ef4444',
            'finished':     '#10b981',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:11px;font-weight:bold">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Statut'

    def registered_teams(self, obj):
        n = obj.tournament_teams.filter(is_confirmed=True).count()
        total = obj.max_teams
        return format_html('<strong>{}</strong> / {}', n, total)
    registered_teams.short_description = 'Équipes'

    def winner_display(self, obj):
        if obj.winner:
            return format_html('🏆 <strong>{}</strong>', obj.winner.name)
        return '—'
    winner_display.short_description = 'Vainqueur'

    def banner_preview(self, obj):
        if obj.banner:
            return format_html('<img src="{}" height="80" style="border-radius:8px"/>', obj.banner.url)
        return '—'
    banner_preview.short_description = 'Bannière'

    @admin.action(description='📋 Ouvrir les inscriptions')
    def open_registration(self, req, qs):
        qs.update(status='registration')

    @admin.action(description='⚽ Démarrer phase de groupes')
    def start_group_stage(self, req, qs):
        qs.update(status='group_stage')

    @admin.action(description='🏆 Démarrer phase finale')
    def start_knockout(self, req, qs):
        qs.update(status='knockout')

    @admin.action(description='✅ Terminer le tournoi')
    def finish(self, req, qs):
        qs.update(status='finished')


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display  = ('name', 'tournament', 'team_count')
    list_filter   = ('tournament',)
    filter_horizontal = ('teams',)

    def team_count(self, obj):
        return obj.teams.count()
    team_count.short_description = 'Équipes'


@admin.register(GroupStanding)
class GroupStandingAdmin(admin.ModelAdmin):
    list_display  = ('team', 'group', 'played', 'won', 'drawn', 'lost',
                     'goals_for', 'goals_against', 'goal_difference', 'points')
    list_filter   = ('group__tournament', 'group')
    ordering      = ('-points', '-goals_for')
    readonly_fields = ('goal_difference',)

    def goal_difference(self, obj):
        gd = obj.goal_difference
        color = '#10b981' if gd > 0 else '#ef4444' if gd < 0 else '#6b7280'
        prefix = '+' if gd > 0 else ''
        return format_html('<strong style="color:{}">{}{}</strong>', color, prefix, gd)
    goal_difference.short_description = 'DB'


@admin.register(TournamentExpense)
class TournamentExpenseAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'tournament', 'date')
    list_filter = ('tournament', 'date')
    search_fields = ('title', 'notes')


@admin.register(TournamentRevenue)
class TournamentRevenueAdmin(admin.ModelAdmin):
    list_display = ('title', 'amount', 'tournament', 'date')
    list_filter = ('tournament', 'date')
    search_fields = ('title', 'notes')


@admin.register(TeamPaymentTransaction)
class TeamPaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('tournament_team', 'amount', 'date', 'notes')
    list_filter = ('tournament_team__tournament', 'date')
    search_fields = ('tournament_team__team__name', 'notes')


class CommitteeMemberInline(admin.TabularInline):
    model = CommitteeMember
    extra = 1
    fields = ('order', 'full_name', 'role', 'photo', 'phone', 'email')
    ordering = ('order',)


@admin.register(CommitteeMember)
class CommitteeMemberAdmin(admin.ModelAdmin):
    list_display  = ('order', 'photo_thumb', 'full_name', 'role_badge', 'tournament', 'phone', 'card_link')
    list_filter   = ('tournament', 'role')
    search_fields = ('full_name', 'phone', 'email', 'id_number')
    ordering      = ('tournament', 'order', 'full_name')
    list_display_links = ('full_name',)

    fieldsets = (
        ('معلومات أساسية / Informations', {
            'fields': ('tournament', 'full_name', 'role', 'order', 'photo'),
        }),
        ('تفاصيل الاتصال / Contact', {
            'fields': ('phone', 'email'),
            'classes': ('collapse',),
        }),
        ('بيانات البطاقة / ID Card', {
            'fields': ('birth_date', 'join_date', 'id_number'),
            'classes': ('collapse',),
        }),
        ('ملاحظات / Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html('<img src="{}" height="40" width="40" style="border-radius:50%;object-fit:cover;"/>', obj.photo.url)
        return format_html('<div style="width:40px;height:40px;background:#e2e8f0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;">👤</div>')
    photo_thumb.short_description = 'Photo'

    def role_badge(self, obj):
        colors = {
            'president':      '#C5A028',
            'vice_president': '#1a5c2a',
            'treasurer':      '#2563eb',
            'secretary':      '#7c3aed',
            'technical':      '#0891b2',
            'media':          '#db2777',
            'security':       '#dc2626',
            'member':         '#6b7280',
        }
        color = colors.get(obj.role, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:bold">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = 'Rôle / المنصب'

    def card_link(self, obj):
        url = reverse('tournaments:committee_card', args=[obj.pk])
        return format_html('<a href="{}" target="_blank" style="color:#C5A028;font-weight:bold">🪪 Bطاقة</a>', url)
    card_link.short_description = 'Carte ID'
