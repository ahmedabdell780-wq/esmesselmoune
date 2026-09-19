from django.apps import AppConfig


class MatchesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.matches'
    verbose_name = 'Matchs'

    def ready(self):
        import apps.matches.signals  # noqa: F401
