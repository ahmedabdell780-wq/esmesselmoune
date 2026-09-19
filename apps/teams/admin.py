from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from .models import Team, Player


class PlayerInline(admin.TabularInline):
    model = Player
    extra = 0
    fields = ('jersey_number', 'first_name', 'last_name', 'position',
              'is_active', 'is_suspended')
    show_change_link = True
    ordering = ('jersey_number',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display  = ('logo_thumb', 'name', 'neighborhood', 'city',
                     'manager', 'player_count', 'is_active')
    list_filter   = ('is_active', 'wilaya', 'city')
    search_fields = ('name', 'neighborhood', 'manager__username')
    list_editable = ('is_active',)
    inlines       = [PlayerInline]
    readonly_fields = ('created_at', 'updated_at', 'logo_preview')
    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'french_name', 'abbreviation', 'neighborhood', 'city', 'wilaya', 'description')
        }),
        ('Visuel', {
            'fields': ('logo', 'logo_preview', 'color_primary', 'color_secondary')
        }),
        ('Contact', {
            'fields': ('manager', 'founded_year', 'contact_phone', 'contact_email')
        }),
        ('Statut', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _player_count=Count('players', distinct=True)
        )

    def logo_thumb(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="40" height="40" '
                'style="border-radius:50%;object-fit:cover;border:2px solid #006233"/>',
                obj.logo.url
            )
        initials = obj.name[:2].upper()
        color = obj.color_primary
        return format_html(
            '<div style="width:40px;height:40px;border-radius:50%;background:{};'
            'display:flex;align-items:center;justify-content:center;'
            'color:#fff;font-weight:bold;font-size:14px">{}</div>',
            color, initials
        )
    logo_thumb.short_description = ''

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" height="120" style="border-radius:8px"/>', obj.logo.url)
        return '—'
    logo_preview.short_description = 'Aperçu logo'

    def player_count(self, obj):
        n = getattr(obj, '_player_count', 0)
        return format_html('<span style="font-weight:bold">{}</span>', n)
    player_count.short_description = 'Joueurs'
    player_count.admin_order_field = '_player_count'


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display  = ('photo_thumb', 'full_name_display', 'team', 'jersey_number',
                     'position', 'age', 'is_active', 'is_suspended')
    list_filter   = ('team', 'position', 'is_active', 'is_suspended', 'preferred_foot')
    search_fields = ('first_name', 'last_name', 'national_id', 'team__name')
    list_editable = ('is_suspended',)
    readonly_fields = ('created_at', 'updated_at', 'photo_preview')
    fieldsets = (
        ('Identité', {
            'fields': ('first_name', 'last_name', 'date_of_birth', 'national_id')
        }),
        ('Équipe & Poste', {
            'fields': ('team', 'jersey_number', 'position', 'preferred_foot')
        }),
        ('Physique', {
            'fields': ('height_cm', 'weight_kg', 'photo', 'photo_preview')
        }),
        ('Statut & Sanctions', {
            'fields': ('is_active', 'is_suspended', 'suspension_matches_count', 'suspension_reason', 'notes', 'created_at', 'updated_at')
        }),
    )

    def photo_thumb(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" width="36" height="36" '
                'style="border-radius:50%;object-fit:cover"/>',
                obj.photo.url
            )
        pos_colors = {'GK': '#f59e0b', 'DEF': '#3b82f6', 'MID': '#10b981', 'FWD': '#ef4444'}
        color = pos_colors.get(obj.position, '#6b7280')
        return format_html(
            '<div style="width:36px;height:36px;border-radius:50%;background:{};'
            'display:flex;align-items:center;justify-content:center;'
            'color:#fff;font-weight:bold;font-size:11px">{}</div>',
            color, obj.position
        )
    photo_thumb.short_description = ''

    def full_name_display(self, obj):
        suspended = ' 🚫' if obj.is_suspended else ''
        return format_html('<strong>{}</strong>{}', obj.full_name, suspended)
    full_name_display.short_description = 'Joueur'

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" height="120" style="border-radius:8px"/>', obj.photo.url)
        return '—'
    photo_preview.short_description = 'Aperçu photo'
