"""
TurniQ Teams — Team and Player models.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User


from django.utils.text import slugify

def team_logo_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    safe_name = slugify(instance.name)[:20] or "team"
    return f'logos/team_{instance.pk or "new"}_{safe_name}.{ext}'


def player_photo_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    safe_name = slugify(instance.last_name)[:20] or "player"
    return f'photos/player_{instance.pk or "new"}_{safe_name}.{ext}'


class Team(models.Model):
    """Football team representing a neighborhood."""

    name        = models.CharField(max_length=100, verbose_name=_('Nom'))
    french_name = models.CharField(max_length=100, blank=True, verbose_name=_('Nom en Français'))
    abbreviation= models.CharField(max_length=10, blank=True, verbose_name=_('Abréviation'))
    neighborhood = models.CharField(max_length=120, verbose_name=_('Quartier'))
    city        = models.CharField(max_length=100, default='MESSLMOUNE', blank=True, verbose_name=_('Commune'))
    wilaya      = models.CharField(max_length=100, default='Tipaza', blank=True, verbose_name=_('Wilaya'))

    # Visuals
    logo        = models.ImageField(
        upload_to=team_logo_path,
        blank=True, null=True,
        verbose_name=_('Logo du club'),
        help_text=_('Format recommandé : carré, PNG/JPG, 200×200px minimum'),
    )
    cover_photo = models.ImageField(
        upload_to='teams/covers/',
        blank=True, null=True,
        verbose_name=_('Photo de couverture'),
        help_text=_('Format recommandé : paysage, PNG/JPG, 1920×1080px minimum (Optionnel)'),
    )
    banner_height   = models.PositiveIntegerField(default=550, verbose_name=_('Hauteur de la bannière (px)'))
    cover_offset_y  = models.IntegerField(default=50, verbose_name=_('Position verticale de l\'image (%)'), help_text='0=Haut, 50=Centre, 100=Bas')
    color_primary   = models.CharField(max_length=7, default='#006233', verbose_name=_('Couleur principale'))
    color_secondary = models.CharField(max_length=7, default='#FFFFFF', verbose_name=_('Couleur secondaire'))

    # Management
    manager     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='teams_managed',
        limit_choices_to={'role': User.Role.TEAM_MANAGER},
        verbose_name=_('Responsable'),
    )
    founded_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Année de fondation'))
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone'))
    contact_email = models.EmailField(blank=True, verbose_name=_('Email'))
    description  = models.TextField(blank=True, verbose_name=_('Description'))

    # Tactics
    preferred_formation = models.CharField(
        max_length=10, default='4-3-3',
        verbose_name=_('Formation préférée'),
        help_text=_('Ex: 4-3-3, 4-4-2, 3-5-2')
    )

    is_active   = models.BooleanField(default=False, verbose_name=_('Active'))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        import os
        is_new_logo = False
        if self.pk:
            try:
                from .models import Team as TModel
                old_logo = TModel.objects.filter(pk=self.pk).values_list('logo', flat=True).first()
                if old_logo != self.logo:
                    is_new_logo = True
            except:
                pass
        elif self.logo:
            is_new_logo = True

        if is_new_logo and self.logo:
            try:
                from .utils import remove_player_background
                if '_cutout' not in self.logo.name:
                    processed_image = remove_player_background(self.logo)
                    if processed_image:
                        orig_name = os.path.basename(self.logo.name)
                        name_parts = orig_name.rsplit('.', 1)
                        new_name = f"{name_parts[0]}_logo_cutout.png"
                        self.logo.save(new_name, processed_image, save=False)
            except:
                pass
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Équipe')
        verbose_name_plural = _('Équipes')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.neighborhood})"

    @property
    def active_player_count(self):
        return self.players.filter(is_active=True).count()

    @property
    def logo_url(self):
        if self.logo:
            return self.logo.url
        return None


class Player(models.Model):
    """Individual player belonging to a team."""

    class Position(models.TextChoices):
        GK  = 'GK',  _('Gardien de but')
        DEF = 'DEF', _('Défenseur')
        MID = 'MID', _('Milieu')
        FWD = 'FWD', _('Attaquant')

    class Foot(models.TextChoices):
        LEFT  = 'L', _('Gauche')
        RIGHT = 'R', _('Droite')
        BOTH  = 'B', _('Les deux')

    team        = models.ForeignKey(
        Team, on_delete=models.CASCADE,
        related_name='players',
        verbose_name=_('Équipe'),
    )
    first_name  = models.CharField(max_length=50, verbose_name=_('Prénom'))
    last_name   = models.CharField(max_length=50, verbose_name=_('Nom'))
    date_of_birth = models.DateField(null=True, blank=True, verbose_name=_('Date de naissance'))
    national_id = models.CharField(
        max_length=20, unique=True, blank=True,
        verbose_name=_('N° Carte nationale'),
    )
    position    = models.CharField(
        max_length=3, choices=Position.choices, default=Position.MID,
        verbose_name=_('Poste'),
    )
    jersey_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(99)],
        verbose_name=_('Numéro de maillot'),
    )
    preferred_foot = models.CharField(
        max_length=1, choices=Foot.choices, default=Foot.RIGHT,
        verbose_name=_('Pied préféré'),
    )
    photo       = models.ImageField(
        upload_to=player_photo_path, blank=True, null=True,
        verbose_name=_('Photo'),
    )
    height_cm   = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Taille (cm)'))
    weight_kg   = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Poids (kg)'))
    is_active   = models.BooleanField(default=True, verbose_name=_('Actif'))
    is_suspended = models.BooleanField(default=False, verbose_name=_('Suspendu'))
    suspension_matches_count = models.PositiveIntegerField(default=0, verbose_name=_('Nombre de matchs de suspension'))
    suspension_reason = models.CharField(max_length=255, blank=True, verbose_name=_('Raison de la suspension'))
    is_captain  = models.BooleanField(default=False, verbose_name=_('Capitaine'))
    
    # Lineup Positioning (0-100 percentage of the field)
    lineup_x    = models.FloatField(default=50.0, verbose_name=_('Position X'))
    lineup_y    = models.FloatField(default=50.0, verbose_name=_('Position Y'))
    is_starter  = models.BooleanField(default=False, verbose_name=_('Titulaire'))

    notes       = models.TextField(blank=True, verbose_name=_('Notes'))
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        import os
        # Check if photo has changed or is new
        is_new_photo = False
        if self.pk:
            try:
                from .models import Player as PModel
                old_photo = PModel.objects.filter(pk=self.pk).values_list('photo', flat=True).first()
                if old_photo != self.photo:
                    is_new_photo = True
            except:
                pass
        elif self.photo:
            is_new_photo = True

        if is_new_photo and self.photo:
            try:
                from .utils import remove_player_background
                if '_cutout' not in self.photo.name:
                    processed_image = remove_player_background(self.photo)
                    if processed_image:
                        orig_name = os.path.basename(self.photo.name)
                        name_parts = orig_name.rsplit('.', 1)
                        new_name = f"{name_parts[0]}_cutout.png"
                        self.photo.save(new_name, processed_image, save=False)
            except Exception as e:
                print(f"Background removal failed: {e}")

        # Ensure at most one captain per team
        if self.is_captain:
            # Set is_captain=False for all other players in the same team
            Player.objects.filter(team=self.team, is_captain=True).exclude(pk=self.pk).update(is_captain=False)

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('Joueur')
        verbose_name_plural = _('Joueurs')
        unique_together = [['team', 'jersey_number']]
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} — #{self.jersey_number} ({self.team.name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        from django.utils import timezone
        today = timezone.now().date()
        today = timezone.now().date()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def is_injured(self):
        """Check if player has any active injuries."""
        try:
            from django.utils import timezone
            today = timezone.now().date()
            active_injuries = self.injuries.filter(is_recovered=False)
            for injury in active_injuries:
                if not injury.expected_return or injury.expected_return >= today:
                    return True
        except Exception:
            pass
        return False
        
    @property
    def display_national_id(self):
        if not self.national_id or '-' in self.national_id:
            return "(N°......... )"
        return self.national_id
