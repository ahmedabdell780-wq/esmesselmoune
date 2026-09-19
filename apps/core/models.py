from django.db import models
from django.utils.translation import gettext_lazy as _

class SiteSettings(models.Model):
    """
    Global settings for the application (Singleton).
    """
    app_name = models.CharField(
        max_length=100, 
        default='TurniQ', 
        verbose_name=_('Nom de l\'application / اسم التطبيق')
    )
    app_logo = models.ImageField(
        upload_to='logos/', 
        null=True, 
        blank=True,
        verbose_name=_('Logo de l\'application / شعار التطبيق')
    )
    app_background = models.ImageField(
        upload_to='backgrounds/', 
        null=True, 
        blank=True,
        verbose_name=_('Image de fond / خلفية التطبيق')
    )

    class Meta:
        verbose_name = _('Paramètres du site')
        verbose_name_plural = _('Paramètres du site')

    def __str__(self):
        return "Paramètres globaux du site"

    def save(self, *args, **kwargs):
        self.pk = 1
        if hasattr(self.__class__, '_cached_obj'):
            delattr(self.__class__, '_cached_obj')
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        if not hasattr(cls, '_cached_obj'):
            obj, created = cls.objects.get_or_create(pk=1)
            cls._cached_obj = obj
        return cls._cached_obj
