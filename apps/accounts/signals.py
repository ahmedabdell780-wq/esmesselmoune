from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, AppearanceSettings


@receiver(post_save, sender=User)
def create_appearance_settings(sender, instance, created, **kwargs):
    """Automatically create AppearanceSettings for every new user."""
    if created:
        AppearanceSettings.objects.get_or_create(user=instance)
