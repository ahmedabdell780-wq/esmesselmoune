from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core import validators
from django.utils.deconstruct import deconstructible


@deconstructible
class CustomUnicodeUsernameValidator(validators.RegexValidator):
    regex = r"^[\w.@+\- ]+\Z"
    message = _(
        "Saisissez un nom d'utilisateur valide. Il ne peut contenir que des lettres, des nombres, des espaces ou les caractères « @ », « . », « + », « - » et « _ »."
    )
    flags = 0


class User(AbstractUser):
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        help_text=_(
            "Requis. 150 caractères maximum. Uniquement des lettres, nombres, espaces et les caractères « @ », « . », « + », « - » et « _ »."
        ),
        validators=[CustomUnicodeUsernameValidator()],
        error_messages={
            "unique": _("Un utilisateur avec ce nom d'utilisateur existe déjà."),
        },
    )
    class Role(models.TextChoices):
        ADMIN        = 'admin',    _('Administrateur / مدير')
        ORGANIZER    = 'organizer',_('Organisateur / منظم')
        TEAM_MANAGER = 'manager',  _('Responsable d\'équipe / مسؤول فريق')
        VIEWER       = 'viewer',   _('Spectateur / متفرج')

    role         = models.CharField(max_length=20, choices=Role.choices,
                                    default=Role.VIEWER, verbose_name=_('Rôle'))
    phone        = models.CharField(max_length=20, blank=True)
    avatar       = models.ImageField(upload_to='avatars/', blank=True, null=True)
    neighborhood = models.CharField(max_length=120, blank=True)
    bio          = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Utilisateur')
        verbose_name_plural = _('Utilisateurs')

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):    return self.role == self.Role.ADMIN
    @property
    def is_organizer(self):     return self.role in (self.Role.ADMIN, self.Role.ORGANIZER)
    @property
    def is_team_manager(self):  return self.role == self.Role.TEAM_MANAGER
    @property
    def can_edit_matches(self): return self.role in (self.Role.ADMIN, self.Role.ORGANIZER)


class AppearanceSettings(models.Model):
    class Theme(models.TextChoices):
        DARK    = 'dark',    _('Sombre / داكن')
        LIGHT   = 'light',   _('Clair / فاتح')
        EMERALD = 'emerald', _('Émeraude / زمردي')
        OCEAN   = 'ocean',   _('Océan / أزرق')

    class FontSize(models.TextChoices):
        XS   = 'xs',   _('Très petit / صغير جداً')
        SM   = 'sm',   _('Petit / صغير')
        BASE = 'base', _('Normal / عادي')
        LG   = 'lg',   _('Grand / كبير')
        XL   = 'xl',   _('Très grand / كبير جداً')

    class FontFamily(models.TextChoices):
        CAIRO  = 'cairo',  _('Cairo (افتراضي)')
        NOTO   = 'noto',   _('Noto Arabic')
        AMIRI  = 'amiri',  _('Amiri (خط عربي كلاسيكي)')
        INTER  = 'inter',  _('Inter (لاتيني)')
        ROBOTO = 'roboto', _('Roboto (لاتيني)')
        BEBAS  = 'bebas',  _('Bebas Neue (عناوين)')

    user          = models.OneToOneField(User, on_delete=models.CASCADE,
                                         related_name='appearance')
    theme         = models.CharField(max_length=10, choices=Theme.choices,
                                     default=Theme.DARK)
    primary_color = models.CharField(max_length=7, default='#C5A028')
    font_size     = models.CharField(max_length=4, choices=FontSize.choices,
                                     default=FontSize.BASE)
    font_family   = models.CharField(max_length=10, choices=FontFamily.choices,
                                     default=FontFamily.CAIRO)
    language      = models.CharField(max_length=5, default='fr',
                                     choices=[('fr','Français'),('ar','العربية')])
    show_stats_sidebar    = models.BooleanField(default=True)
    notifications_enabled = models.BooleanField(default=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Apparence')

    def __str__(self):
        return f"Apparence de {self.user.username}"

    @classmethod
    def get_or_create_for(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj
