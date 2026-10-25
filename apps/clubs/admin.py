from django.contrib import admin
from .models import Category, ClubPlayer, TrainingSession, TrainingAttendance, ClubMatch

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_age', 'max_age')
    search_fields = ('name',)

@admin.register(ClubPlayer)
class ClubPlayerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'category', 'date_of_birth', 'position', 'is_active')
    list_filter = ('category', 'is_active', 'position')
    search_fields = ('first_name', 'last_name', 'parent_phone', 'player_phone')
    date_hierarchy = 'joined_date'
    readonly_fields = ('card_number',)

class TrainingAttendanceInline(admin.TabularInline):
    model = TrainingAttendance
    extra = 1

@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ('category', 'date', 'start_time', 'location')
    list_filter = ('category', 'date')
    date_hierarchy = 'date'
    inlines = [TrainingAttendanceInline]

@admin.register(ClubMatch)
class ClubMatchAdmin(admin.ModelAdmin):
    list_display = ('category', 'date', 'opponent', 'is_home', 'our_score', 'their_score')
    list_filter = ('category', 'is_home', 'date')
    date_hierarchy = 'date'
    search_fields = ('opponent',)

from .models import ClubSettings, ClubNews, StaffMember, Subscription, MedicalRecord

@admin.register(ClubSettings)
class ClubSettingsAdmin(admin.ModelAdmin):
    pass

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'role', 'category_assigned', 'is_active')
    list_filter = ('role', 'is_active', 'category_assigned')
    search_fields = ('first_name', 'last_name', 'phone')

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('player', 'month', 'amount', 'is_paid', 'paid_date')
    list_filter = ('is_paid', 'month')
    search_fields = ('player__first_name', 'player__last_name')
    date_hierarchy = 'month'

@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('player', 'injury_type', 'date_of_injury', 'expected_return', 'is_recovered')
    list_filter = ('is_recovered', 'date_of_injury')
    search_fields = ('player__first_name', 'player__last_name', 'injury_type')

@admin.register(ClubNews)
class ClubNewsAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_published', 'created_at')
    list_filter = ('is_published', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}

from .models import LeagueTeam, LeagueMatch, LeagueStanding

@admin.register(LeagueTeam)
class LeagueTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')

@admin.register(LeagueMatch)
class LeagueMatchAdmin(admin.ModelAdmin):
    list_display = ('category', 'round_number', 'home_team', 'home_score', 'away_score', 'away_team', 'is_played', 'date')
    list_filter = ('category', 'round_number', 'is_played')
    search_fields = ('home_team__name', 'away_team__name')
    list_editable = ('home_score', 'away_score', 'is_played')

@admin.register(LeagueStanding)
class LeagueStandingAdmin(admin.ModelAdmin):
    list_display = ('team', 'category', 'points', 'played', 'won', 'drawn', 'lost', 'goals_for', 'goals_against')
    list_filter = ('category',)
    ordering = ('-points', '-goals_for')


from .models import Session, Attendance, Guardian, Announcement, Receipt

class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('team', 'date', 'kind', 'total_players_count', 'recorded_attendances_count', 'present_count', 'absent_count')
    list_filter = ('team', 'kind', 'date')
    date_hierarchy = 'date'
    inlines = [AttendanceInline]

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('player', 'session', 'status', 'note', 'recorded_at')
    list_filter = ('status', 'session__team', 'session__kind', 'session__date')
    search_fields = ('player__first_name', 'player__last_name', 'note')
    date_hierarchy = 'recorded_at'


@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('user', 'relationship', 'phone', 'get_players_count', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'phone')
    filter_horizontal = ('players',)

    def get_players_count(self, obj):
        return obj.players.count()
    get_players_count.short_description = "عدد الأبناء المسجلين"


class ReceiptInline(admin.TabularInline):
    model = Receipt
    extra = 0
    readonly_fields = ('guardian', 'read_at')
    can_delete = False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'team', 'author', 'created_at', 'read_count', 'target_guardians_count')
    list_filter = ('team', 'created_at')
    search_fields = ('title', 'body')
    date_hierarchy = 'created_at'
    inlines = [ReceiptInline]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('announcement', 'guardian', 'read_at')
    list_filter = ('announcement__team', 'read_at')
    search_fields = ('announcement__title', 'guardian__user__first_name', 'guardian__user__last_name')
    date_hierarchy = 'read_at'




