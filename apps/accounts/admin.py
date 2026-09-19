from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, AppearanceSettings


class AppearanceInline(admin.StackedInline):
    model = AppearanceSettings
    can_delete = False
    extra = 0
    fields = ('theme', 'primary_color', 'font_size', 'language',
              'show_stats_sidebar', 'notifications_enabled')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [AppearanceInline]
    list_display  = ('avatar_thumb', 'username', 'full_name', 'role',
                     'email', 'is_active', 'date_joined')
    list_filter   = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering      = ('-date_joined',)
    list_editable = ('role',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Profil TurniQ', {
            'fields': ('role', 'phone', 'avatar', 'neighborhood', 'bio')
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Profil TurniQ', {
            'fields': ('role', 'phone', 'neighborhood')
        }),
    )

    def avatar_thumb(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" width="36" height="36" '
                'style="border-radius:50%;object-fit:cover"/>',
                obj.avatar.url
            )
        initials = (obj.first_name[:1] + obj.last_name[:1]).upper() or obj.username[:2].upper()
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:#006233;'
            'display:flex;align-items:center;justify-content:center;'
            'color:#fff;font-weight:bold;font-size:12px">{}</div>',
            initials
        )
    avatar_thumb.short_description = ''

    def full_name(self, obj):
        return obj.get_full_name() or '—'
    full_name.short_description = 'Nom complet'


@admin.register(AppearanceSettings)
class AppearanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'primary_color', 'font_size', 'language')
    list_filter  = ('theme', 'font_size', 'language')
