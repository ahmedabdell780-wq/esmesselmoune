"""
TurniQ Tournaments — Tournament, Group, GroupStanding models.
Includes intelligent auto-seeding and standings logic.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from apps.teams.models import Team


class Tournament(models.Model):
    """Main tournament entity — orchestrates the full competition lifecycle."""

    class Status(models.TextChoices):
        DRAFT        = 'draft',        _('Brouillon')
        REGISTRATION = 'registration', _('Inscriptions ouvertes')
        GROUP_STAGE  = 'group_stage',  _('Phase de groupes')
        KNOCKOUT     = 'knockout',     _('Phase finale')
        FINISHED     = 'finished',     _('Terminé')

    class Format(models.TextChoices):
        GROUP_KNOCKOUT = 'group_knockout', _('Groupes + Élimination directe')
        ROUND_ROBIN    = 'round_robin',    _('Championnat aller-retour')
        SINGLE_KNOCKOUT= 'single_knockout',_('Élimination directe')

    # ─── Core ────────────────────────────────────────────────────────────────
    name        = models.CharField(max_length=200, verbose_name=_('Nom'))
    edition     = models.PositiveIntegerField(default=1, verbose_name=_('Édition'))
    year        = models.PositiveIntegerField(verbose_name=_('Année'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    banner      = models.ImageField(upload_to='banners/', blank=True, null=True, verbose_name=_('Bannière'))

    # ─── Format ──────────────────────────────────────────────────────────────
    format      = models.CharField(
        max_length=20, choices=Format.choices,
        default=Format.GROUP_KNOCKOUT, verbose_name=_('Format'),
    )
    status      = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name=_('Statut'),
    )

    # ─── Teams ───────────────────────────────────────────────────────────────
    teams       = models.ManyToManyField(
        Team, through='TournamentTeam',
        related_name='tournaments', verbose_name=_('Équipes'),
    )
    max_teams   = models.PositiveIntegerField(default=16, verbose_name=_('Nb. max équipes'))
    num_groups  = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1)],
        verbose_name=_('Nombre de groupes'),
    )
    teams_advancing_per_group = models.PositiveIntegerField(
        default=2, verbose_name=_('Équipes qualifiées/groupe'),
    )

    # ─── Points system ───────────────────────────────────────────────────────
    points_win  = models.PositiveIntegerField(default=3, verbose_name=_('Points victoire'))
    points_draw = models.PositiveIntegerField(default=1, verbose_name=_('Points nul'))
    points_loss = models.PositiveIntegerField(default=0, verbose_name=_('Points défaite'))

    # ─── Finance system ──────────────────────────────────────────────────────
    subscription_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=_('Frais d\'inscription / مبلغ الاشتراك')
    )

    # ─── Schedule ────────────────────────────────────────────────────────────
    registration_start_date = models.DateField(null=True, blank=True, verbose_name=_('Début inscriptions'))
    registration_deadline = models.DateField(null=True, blank=True, verbose_name=_('Clôture inscriptions'))
    start_date  = models.DateField(null=True, blank=True, verbose_name=_('Date de début'))
    end_date    = models.DateField(null=True, blank=True, verbose_name=_('Date de fin'))
    location    = models.CharField(max_length=200, default='Stade Communal', verbose_name=_('Lieu'))

    # ─── Winner ──────────────────────────────────────────────────────────────
    winner      = models.ForeignKey(
        Team, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='trophies',
        verbose_name=_('Vainqueur'),
    )
    runner_up   = models.ForeignKey(
        Team, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='runner_up_tournaments',
        verbose_name=_('Finaliste'),
    )

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Tournoi')
        verbose_name_plural = _('Tournois')
        ordering = ['-year', '-edition']

    def __str__(self):
        return f"{self.name} {self.year} (Éd. {self.edition})"

    @property
    def is_active(self):
        return self.status in (self.Status.GROUP_STAGE, self.Status.KNOCKOUT)

    @property
    def is_registration_open(self):
        from django.utils import timezone
        today = timezone.now().date()
        
        # Check status
        if self.status != self.Status.REGISTRATION:
            return False
            
        # Check start date (if set)
        if self.registration_start_date and today < self.registration_start_date:
            return False
            
        # Check deadline (if set)
        if self.registration_deadline and today > self.registration_deadline:
            return False
            
        return True

    @property
    def registered_team_count(self):
        return self.tournament_teams.filter(is_confirmed=True).count()

    @property
    def can_generate_groups(self):
        return (
            self.status == self.Status.REGISTRATION
            and self.registered_team_count >= 2
            and self.num_groups >= 1
        )


class TournamentTeam(models.Model):
    """Pivot: Team ↔ Tournament with registration metadata."""
    tournament      = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='tournament_teams')
    team            = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='tournament_teams')
    registration_date = models.DateTimeField(auto_now_add=True)
    is_confirmed    = models.BooleanField(default=False, verbose_name=_('Confirmée'))
    seed            = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Tête de série'))
    notes           = models.TextField(blank=True, verbose_name=_('Notes/Motif'))
    eliminated_at_stage = models.CharField(max_length=20, blank=True, verbose_name=_('Éliminée en'))

    # ─── Finance details ─────────────────────────────────────────────────────
    amount_paid     = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=_('Montant payé / المبلغ المدفوع')
    )
    payment_confirmed = models.BooleanField(
        default=False,
        verbose_name=_('Paiement validé / تم تأكيد الدفع')
    )

    class Meta:
        unique_together = [['tournament', 'team']]
        verbose_name = _('Participation')
        verbose_name_plural = _('Participations')
        ordering = ['seed', 'team__name']

    def __str__(self):
        return f"{self.team.name} → {self.tournament.name}"


class Group(models.Model):
    """A group within a tournament's group stage."""
    tournament  = models.ForeignKey(
        Tournament, on_delete=models.CASCADE,
        related_name='groups', verbose_name=_('Tournoi'),
    )
    name        = models.CharField(max_length=50, verbose_name=_('Nom'))  # ex: "Groupe A"
    teams       = models.ManyToManyField(
        Team, related_name='groups', verbose_name=_('Équipes'),
    )

    class Meta:
        verbose_name = _('Groupe')
        verbose_name_plural = _('Groupes')
        ordering = ['name']
        unique_together = [['tournament', 'name']]

    def __str__(self):
        return f"{self.tournament.name} — {self.name}"

    @property
    def sorted_standings(self):
        """Sorted standings for this group using official tie-breakers."""
        from .services.scheduler import StandingsCalculator
        calc = StandingsCalculator(self.tournament)
        return calc.get_sorted_standings(self)


class GroupStanding(models.Model):
    """
    Live standings row per team per group.
    Updated atomically after every finished group match.
    """
    group       = models.ForeignKey(
        Group, on_delete=models.CASCADE,
        related_name='groupstanding_set',
        verbose_name=_('Groupe'),
    )
    team        = models.ForeignKey(
        Team, on_delete=models.CASCADE,
        related_name='standings', verbose_name=_('Équipe'),
    )
    played      = models.PositiveIntegerField(default=0, verbose_name=_('J'))
    won         = models.PositiveIntegerField(default=0, verbose_name=_('G'))
    drawn       = models.PositiveIntegerField(default=0, verbose_name=_('N'))
    lost        = models.PositiveIntegerField(default=0, verbose_name=_('P'))
    goals_for     = models.PositiveIntegerField(default=0, verbose_name=_('BP'))
    goals_against = models.PositiveIntegerField(default=0, verbose_name=_('BC'))
    goal_difference = models.IntegerField(default=0, verbose_name=_('DB'))
    points         = models.IntegerField(default=0, verbose_name=_('Pts'))

    class Meta:
        verbose_name = _('Classement groupe')
        verbose_name_plural = _('Classements groupes')
        unique_together = [['group', 'team']]
        ordering = ['-points', '-goal_difference', '-goals_for', 'id']

    def __str__(self):
        return f"{self.team.name} — {self.group.name} : {self.points} pts"

    def reset(self):
        """Reset all counters to zero."""
        self.played = self.won = self.drawn = self.lost = 0
        self.goals_for = self.goals_against = self.goal_difference = self.points = 0


class TournamentExpense(models.Model):
    """Tracks financial expenditures for a tournament."""
    tournament  = models.ForeignKey(
        Tournament, on_delete=models.CASCADE,
        related_name='expenses', verbose_name=_('Tournoi')
    )
    title       = models.CharField(max_length=200, verbose_name=_('Titre / المصاريف'))
    amount      = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Montant / المبلغ'))
    date        = models.DateField(auto_now_add=True, verbose_name=_('Date / التاريخ'))
    notes       = models.TextField(blank=True, verbose_name=_('Notes / ملاحظات'))

    class Meta:
        verbose_name = _('Dépense Tournoi')
        verbose_name_plural = _('Dépenses Tournois')
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} — {self.amount} DZD ({self.tournament.name})"


class TournamentRevenue(models.Model):
    """Tracks financial revenues/incomes (sponsors, donations, ads) for a tournament."""
    tournament  = models.ForeignKey(
        Tournament, on_delete=models.CASCADE,
        related_name='revenues', verbose_name=_('Tournoi')
    )
    title       = models.CharField(max_length=200, verbose_name=_('Source / الإيرادات'))
    amount      = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Montant / المبلغ'))
    date        = models.DateField(auto_now_add=True, verbose_name=_('Date / التاريخ'))
    notes       = models.TextField(blank=True, verbose_name=_('Notes / ملاحظات'))

    class Meta:
        verbose_name = _('Recette Tournoi')
        verbose_name_plural = _('Recettes Tournois')
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} — {self.amount} DZD ({self.tournament.name})"


class TeamPaymentTransaction(models.Model):
    """Tracks detailed payment history (installments) for a team in a tournament."""
    tournament_team = models.ForeignKey(
        TournamentTeam, on_delete=models.CASCADE,
        related_name='transactions', verbose_name=_('Participation')
    )
    amount      = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Montant / المبلغ'))
    date        = models.DateTimeField(auto_now_add=True, verbose_name=_('Date / التاريخ'))
    notes       = models.CharField(max_length=200, blank=True, verbose_name=_('Notes / ملاحظات'))

    class Meta:
        verbose_name = _('Transaction de paiement')
        verbose_name_plural = _('Transactions de paiement')
        ordering = ['-date']

    def __str__(self):
        return f"{self.tournament_team.team.name} — +{self.amount} DZD ({self.date.strftime('%d/%m/%Y')})"


class CommitteeMember(models.Model):
    """Member of the organizing committee for a tournament."""

    class Role(models.TextChoices):
        PRESIDENT        = 'president',        _('رئيس اللجنة / Président')
        VICE_PRESIDENT   = 'vice_president',   _('نائب الرئيس / Vice-Président')
        TREASURER        = 'treasurer',        _('أمين المال / Trésorier')
        VICE_TREASURER   = 'vice_treasurer',   _('نائب أمين المال / Vice-Trésorier')
        SECRETARY        = 'secretary',        _('الكاتب العام / Secrétaire Général')
        VICE_SECRETARY   = 'vice_secretary',   _('نائب الكاتب العام / Vice-Secrétaire')
        TECHNICAL        = 'technical',        _('المدير التقني / Directeur Technique')
        MEDIA            = 'media',            _('مسؤول الإعلام / Chargé Médias')
        SECURITY         = 'security',         _('مسؤول الأمن / Responsable Sécurité')
        MEDICAL          = 'medical',          _('مسؤول طبي / Responsable Médical')
        MEMBER           = 'member',           _('عضو / Membre')

    tournament  = models.ForeignKey(
        Tournament, on_delete=models.CASCADE,
        related_name='committee_members', verbose_name=_('Tournoi / الدورة'),
    )
    full_name   = models.CharField(max_length=200, verbose_name=_('Nom complet / الاسم الكامل'))
    role        = models.CharField(
        max_length=30, choices=Role.choices,
        default=Role.MEMBER, verbose_name=_('Rôle / المنصب'),
    )
    photo       = models.ImageField(
        upload_to='committee/', blank=True, null=True,
        verbose_name=_('Photo / الصورة'),
    )
    phone       = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone / الهاتف'))
    email       = models.EmailField(blank=True, verbose_name=_('Email / البريد الإلكتروني'))
    birth_date  = models.DateField(null=True, blank=True, verbose_name=_('Date de naissance / تاريخ الميلاد'))
    join_date   = models.DateField(null=True, blank=True, verbose_name=_('Date d\'adhésion / تاريخ الانضمام'))
    id_number   = models.CharField(max_length=50, blank=True, verbose_name=_('N° Identité / رقم الهوية'))
    order       = models.PositiveIntegerField(default=0, verbose_name=_('Ordre / الترتيب'))
    notes       = models.TextField(blank=True, verbose_name=_('Notes / ملاحظات'))

    class Meta:
        verbose_name = _('Membre du comité / عضو اللجنة')
        verbose_name_plural = _('Membres du comité / أعضاء اللجنة')
        ordering = ['order', 'full_name']

    def __str__(self):
        return f"{self.full_name} — {self.get_role_display()} ({self.tournament.name})"


# ─── Signals ─────────────────────────────────────────────────────────────────
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

@receiver(post_save, sender=Tournament)
def notify_users_on_registration_open(sender, instance, created, **kwargs):
    """Notify all active users when a tournament moves to registration status."""
    if instance.status == Tournament.Status.REGISTRATION:
        from apps.accounts.models import User
        from apps.notifications.models import Notification
        
        reg_url = reverse('teams:registration')
        
        users = User.objects.filter(is_active=True)
        notifs = [
            Notification(
                recipient=user,
                notif_type=Notification.Type.TOURNAMENT,
                title=_('Nouveau tournoi : %s') % instance.name,
                message=_('Les inscriptions sont ouvertes pour %s. Cliquez pour participer !') % instance.name,
                link=reg_url
            ) for user in users
        ]
        Notification.objects.bulk_create(notifs)
