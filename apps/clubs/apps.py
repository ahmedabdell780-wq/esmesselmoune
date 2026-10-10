from django.apps import AppConfig


class ClubsConfig(AppConfig):
    def ready(self):
        import apps.clubs.signals
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.clubs'
