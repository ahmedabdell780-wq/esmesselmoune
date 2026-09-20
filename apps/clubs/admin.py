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
