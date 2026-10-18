from django.contrib import admin
from .models import SiteSettings

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'app_name')
    
    def has_add_permission(self, request):
        # Only allow one settings object
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
