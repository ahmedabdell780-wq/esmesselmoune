"""
TurniQ Matches — Match, Goal, Card, Injury models.
Full statistics tracking per match.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.templatetags.static import static
from apps.teams.models import Team, Player
from apps.tournaments.models import Tournament, Group
from apps.accounts.models import User


class Referee(models.Model):
    """Match referee."""
    user            = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='referee_profile', verbose_name=_('Utilisateur'),
    )
    license_number  = models.CharField(max_length=50, blank=True, verbose_name=_('N° Licence'))
    experience_years = models.PositiveIntegerField(default=0, verbose_name=_('Années d\'expérience'))
    photo           = models.ImageField(
        upload_to='referees/', blank=True, null=True, 
        verbose_name=_('Photo / الصورة')
    )

    class Meta:
        verbose_name = _('Arbitre')
        verbose_name_plural = _('Arbitres')

    def __str__(self):
        return f"Arbitre {self.user.get_full_name() or self.user.username}"

    @property
    def photo_url(self):
        if self.photo:
            return self.photo.url
        if self.user and self.user.avatar:
            return self.user.avatar.url
        # Custom premium referee default avatar
        return static('img/default_referee.jpg')


class Match(models.Model):
    """
    Core match entity.
    Supports group stage and all knockout rounds.
    """

    class Stage(models.TextChoices):
        GROUP        = 'GROUP',   _('Phase de groupes')
        ROUND_OF_16  = 'R16',    _('Huitièmes de finale')
        QUARTER_FINAL= 'QF',     _('Quarts de finale')
        SEMI_FINAL   = 'SF',     _('Demi-finales')
        THIRD_PLACE  = 'TP',     _('Match pour la 3e place')
        FINAL        = 'FINAL',  _('Finale')

    class Status(models.TextChoices):
        SCHEDULED  = 'scheduled',  _('Programmé')
        LIVE       = 'live',       _('En cours')
        FINISHED   = 'finished',   _('Terminé')
        POSTPONED  = 'postponed',  _('Reporté')
        CANCELLED  = 'cancelled',  _('Annulé')

    # ─── Tournament context ───────────────────────────────────────────────────
    tournament  = models.ForeignKey(
        Tournament, on_delete=models.CASCADE,
        related_name='matches', verbose_name=_('Tournoi'),
    )
    group       = models.ForeignKey(
        Group, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='matches', verbose_name=_('Groupe'),
    )
    stage       = models.CharField(
        max_length=10, choices=Stage.choices,
        default=Stage.GROUP, verbose_name=_('Phase'),
    )
    match_day   = models.PositiveIntegerField(default=1, verbose_name=_('Journée'))
    round_number = models.PositiveIntegerField(default=1, verbose_name=_('Tour'))

    # ─── Teams ───────────────────────────────────────────────────────────────
    team1       = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, blank=True,
        related_name='home_matches', verbose_name=_('Équipe 1 (domicile)'),
    )
    team2       = models.ForeignKey(
        Team, on_delete=models.CASCADE, null=True, blank=True,
        related_name='away_matches', verbose_name=_('Équipe 2 (extérieur)'),
    )

    # ─── Score ───────────────────────────────────────────────────────────────
    score_team1 = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_('Score Éq. 1'),
    )
    score_team2 = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_('Score Éq. 2'),
    )
    # Penalty shootout (for knockout)
    penalties_team1 = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('TAB Éq. 1'))
    penalties_team2 = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('TAB Éq. 2'))

    # ─── Schedule ────────────────────────────────────────────────────────────
    match_date  = models.DateTimeField(verbose_name=_('Date et heure'))
    venue       = models.CharField(max_length=200, default='Stade Communal', verbose_name=_('Lieu'))
    referee     = models.ForeignKey(
        Referee, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='matches', verbose_name=_('Arbitre'),
    )

    # ─── Status ──────────────────────────────────────────────────────────────
    class ForfeitType(models.TextChoices):
        NONE  = 'NONE',  _('Aucun / مباراة عادية')
        TEAM1 = 'TEAM1', _('Forfait Équipe 1 / غياب الفريق الأول (فوز الفريق 2 بنتيجة 3-0)')
        TEAM2 = 'TEAM2', _('Forfait Équipe 2 / غياب الفريق الثاني (فوز الفريق 1 بنتيجة 3-0)')
        BOTH  = 'BOTH',  _('Forfait Double / غياب الفريقين معاً (خسارة كلا الفريقين 0-0)')

    status      = models.CharField(
        max_length=15, choices=Status.choices,
        default=Status.SCHEDULED, verbose_name=_('Statut'),
    )
    forfeit_type = models.CharField(
        max_length=10, choices=ForfeitType.choices,
        default=ForfeitType.NONE, verbose_name=_('Type de forfait / نوع الغياب والاعتذار')
    )
    forfeit_reason = models.TextField(blank=True, verbose_name=_('Motif du forfait / سبب الأعتذار أو الغياب'))
    official_report_notes = models.TextField(blank=True, verbose_name=_('Remarques officielles / ملاحظات تقرير الحكم واللجنة المنظمة'))

    # Featured Players for UI (Posters)
    featured_player1 = models.ForeignKey(
        Player, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='featured_in_matches_home',
        verbose_name=_('Joueur vedette (Éq. 1)'),
    )
    featured_player2 = models.ForeignKey(
        Player, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='featured_in_matches_away',
        verbose_name=_('Joueur vedette (Éq. 2)'),
    )
    man_of_the_match = models.ForeignKey(
        Player, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='man_of_the_match_awards',
        verbose_name=_('Homme du match / رجل المباراة'),
    )

    notes       = models.TextField(blank=True, verbose_name=_('Notes'))
    promo_config = models.JSONField(default=dict, blank=True, verbose_name=_('Config Promo'))

    # ─── Knockout: next match ─────────────────────────────────────────────────
    next_match  = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='previous_matches',
        verbose_name=_('Match suivant (bracket)'),
    )

    # ─── Live Ticker Stats ────────────────────────────────────────────────────
    current_period = models.CharField(
        max_length=20, default='1H',
        choices=[
            ('1H', _('1ère Mi-temps / الشوط الأول')),
            ('HT', _('Mi-temps / الاستراحة')),
            ('2H', _('2ème Mi-temps / الشوط الثاني')),
            ('OT', _('Prolongation / الشوط الإضافي')),
            ('PK', _('Tirs au but / ركلات الترجيح')),
        ],
        verbose_name=_('Période actuelle')
    )
    current_minute = models.PositiveIntegerField(default=0, verbose_name=_('Minute actuelle'))

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Match')
        verbose_name_plural = _('Matchs')
        ordering = ['match_date']

    def __str__(self):
        score = self.score_display
        return f"{self.team1} vs {self.team2} {score} [{self.get_stage_display()}]"

    @property
    def is_forfeit(self):
        return self.forfeit_type != self.ForfeitType.NONE

    @property
    def forfeit_legal_text(self):
        if self.forfeit_type == self.ForfeitType.TEAM1:
            t1 = self.team1.name if self.team1 else "الفريق الأول"
            t2 = self.team2.name if self.team2 else "الفريق الثاني"
            return f"تطبيق أحكام المادة 15 من لائحة المسابقات والانضباط: ثبوت غياب/عدم حضور ({t1}). تقرر رسمياً إعلان فوز ({t2}) بنتيجة (3 - 0) قانوناً وحصوله على نقاط الفوز كاملة (3 نقاط)."
        if self.forfeit_type == self.ForfeitType.TEAM2:
            t1 = self.team1.name if self.team1 else "الفريق الأول"
            t2 = self.team2.name if self.team2 else "الفريق الثاني"
            return f"تطبيق أحكام المادة 15 من لائحة المسابقات والانضباط: ثبوت غياب/عدم حضور ({t2}). تقرر رسمياً إعلان فوز ({t1}) بنتيجة (3 - 0) قانوناً وحصوله على نقاط الفوز كاملة (3 نقاط)."
        if self.forfeit_type == self.ForfeitType.BOTH:
            t1 = self.team1.name if self.team1 else "الفريق الأول"
            t2 = self.team2.name if self.team2 else "الفريق الثاني"
            return f"تطبيق أحكام المادة 16 من لائحة المسابقات والانضباط: ثبوت غياب كلا الفريقين معاً ({t1}) و ({t2}). تقرر اعتماد الخسارة المزدوجة بنتيجة (0 - 0) ومصادرة نقاط المباراة كلياً (0 نقطة لكل منهما)."
        return ""

    @property
    def score_display(self):
        if self.forfeit_type == self.ForfeitType.TEAM1:
            return '0 : 3 (غياب إداري)'
        if self.forfeit_type == self.ForfeitType.TEAM2:
            return '3 : 0 (غياب إداري)'
        if self.forfeit_type == self.ForfeitType.BOTH:
            return '0 : 0 (غياب الفريقين)'
        if self.score_team1 is None:
            return '- : -'
        return f"{self.score_team1} : {self.score_team2}"

    @property
    def result(self):
        """Return 'team1_win', 'team2_win', 'draw', or 'double_forfeit'. None if not finished."""
        if self.forfeit_type == self.ForfeitType.TEAM1:
            return 'team2_win'
        if self.forfeit_type == self.ForfeitType.TEAM2:
            return 'team1_win'
        if self.forfeit_type == self.ForfeitType.BOTH:
            return 'double_forfeit'
        if self.score_team1 is None or self.score_team2 is None:
            return None
        if self.score_team1 > self.score_team2:
            return 'team1_win'
        if self.score_team2 > self.score_team1:
            return 'team2_win'
        # Penalties decide in knockout
        if self.penalties_team1 is not None and self.penalties_team2 is not None:
            if self.penalties_team1 > self.penalties_team2:
                return 'team1_win'
            if self.penalties_team2 > self.penalties_team1:
                return 'team2_win'
        return 'draw'

    @property
    def winner(self):
        """Return the winning Team object, or None."""
        r = self.result
        if r == 'team1_win':
            return self.team1
        if r == 'team2_win':
            return self.team2
        return None

    @property
    def loser(self):
        """Return the losing Team object, or None."""
        r = self.result
        if r == 'team1_win':
            return self.team2
        if r == 'team2_win':
            return self.team1
        return None

    @property
    def is_finished(self):
        return self.status == self.Status.FINISHED

    @property
    def has_penalties(self):
        return self.penalties_team1 is not None and self.penalties_team2 is not None


class Goal(models.Model):
    """Tracks every goal: scorer, minute, type."""

    class GoalType(models.TextChoices):
        NORMAL   = 'normal',    _('Normal')
        OWN_GOAL = 'own_goal',  _('But contre son camp')
        PENALTY  = 'penalty',   _('Penalty')
        FREE_KICK= 'free_kick', _('Coup franc direct')
        HEADER   = 'header',    _('Tête')

    match       = models.ForeignKey(
        Match, on_delete=models.CASCADE,
        related_name='goals', verbose_name=_('Match'),
    )
    player      = models.ForeignKey(
        Player, on_delete=models.CASCADE,
        related_name='goals', verbose_name=_('Buteur'),
    )
    team        = models.ForeignKey(
        Team, on_delete=models.CASCADE,
        related_name='goals_scored', verbose_name=_('Équipe'),
    )
    goal_type   = models.CharField(
        max_length=15, choices=GoalType.choices,
        default=GoalType.NORMAL, verbose_name=_('Type de but'),
    )
    minute      = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_('Minute'),
    )
    is_extra_time = models.BooleanField(default=False, verbose_name=_('Prolongation'))
    assist_player = models.ForeignKey(
        Player, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assists', verbose_name=_('Passeur décisif'),
    )

    class Meta:
        verbose_name = _('But')
        verbose_name_plural = _('Buts')
        ordering = ['match', 'minute']

    def __str__(self):
        return (
            f"⚽ {self.player.full_name} ({self.team.name})"
            f" {self.minute}' — {self.match}"
        )


class Card(models.Model):
    """Yellow/Red card per player per match."""

    class CardType(models.TextChoices):
        YELLOW = 'yellow', _('Carton jaune')
        RED    = 'red',    _('Carton rouge')
        YELLOW_RED = 'yellow_red', _('2ème jaune → rouge')

    match       = models.ForeignKey(
        Match, on_delete=models.CASCADE,
        related_name='cards', verbose_name=_('Match'),
    )
    player      = models.ForeignKey(
        Player, on_delete=models.CASCADE,
        related_name='cards', verbose_name=_('Joueur'),
    )
    team        = models.ForeignKey(
        Team, on_delete=models.CASCADE,
        related_name='cards_received', verbose_name=_('Équipe'),
    )
    card_type   = models.CharField(
        max_length=15, choices=CardType.choices,
        verbose_name=_('Type'),
    )
    minute      = models.PositiveIntegerField(verbose_name=_('Minute'))
    reason      = models.CharField(max_length=200, blank=True, verbose_name=_('Raison'))
    results_in_suspension = models.BooleanField(
        default=False, verbose_name=_('Entraîne une suspension'),
    )
    suspension_matches = models.PositiveIntegerField(
        default=1, verbose_name=_('Nombre de matchs de suspension')
    )

    class Meta:
        verbose_name = _('Carton')
        verbose_name_plural = _('Cartons')
        ordering = ['match', 'minute']

    def save(self, *args, **kwargs):
        if not self.suspension_matches:
            self.suspension_matches = 1
        super().save(*args, **kwargs)

    def __str__(self):
        emoji = '🟨' if self.card_type == 'yellow' else '🟥'
        return f"{emoji} {self.player.full_name} {self.minute}' — {self.match}"


class Injury(models.Model):
    """Player injury record tracked per match or training."""

    class InjuryType(models.TextChoices):
        MUSCLE   = 'muscle',   _('Musculaire')
        LIGAMENT = 'ligament', _('Ligamentaire')
        BONE     = 'bone',     _('Osseuse (fracture)')
        CONTUSION= 'contusion',_('Contusion')
        HEAD     = 'head',     _('Crâne / tête')
        OTHER    = 'other',    _('Autre')

    class Severity(models.TextChoices):
        MINOR    = 'minor',    _('Mineure (< 1 sem.)')
        MODERATE = 'moderate', _('Modérée (1-4 sem.)')
        SEVERE   = 'severe',   _('Grave (> 4 sem.)')
        CAREER   = 'career',   _('Fin de saison')

    player      = models.ForeignKey(
        Player, on_delete=models.CASCADE,
        related_name='injuries', verbose_name=_('Joueur'),
    )
    match       = models.ForeignKey(
        Match, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='injuries', verbose_name=_('Lors du match'),
    )
    injury_type = models.CharField(
        max_length=15, choices=InjuryType.choices,
        verbose_name=_('Type d\'blessure'),
    )
    severity    = models.CharField(
        max_length=10, choices=Severity.choices,
        verbose_name=_('Gravité'),
    )
    body_part   = models.CharField(max_length=100, blank=True, verbose_name=_('Partie du corps'))
    injury_date = models.DateField(verbose_name=_('Date de blessure'))
    expected_return = models.DateField(null=True, blank=True, verbose_name=_('Retour estimé'))
    absence_weeks = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name=_('Semaines d\'absence estimées'),
    )
    description = models.TextField(blank=True, verbose_name=_('Description'))
    is_recovered = models.BooleanField(default=False, verbose_name=_('Guéri'))
    actual_return = models.DateField(null=True, blank=True, verbose_name=_('Retour effectif'))

    class Meta:
        verbose_name = _('Blessure')
        verbose_name_plural = _('Blessures')
        ordering = ['-injury_date']

    def __str__(self):
        return (
            f"{self.player.full_name} — "
            f"{self.get_injury_type_display()} ({self.get_severity_display()})"
        )

    @property
    def is_currently_injured(self):
        if self.is_recovered:
            return False
        from django.utils import timezone
        if self.expected_return:
            return self.expected_return >= timezone.now().date()
        return True


class MatchMedia(models.Model):
    """Media (photos/videos) uploaded for a specific match."""
    
    class MediaType(models.TextChoices):
        IMAGE = 'image', _('Image/Photo')
        VIDEO = 'video', _('Vidéo')
        LINK  = 'link',  _('Lien (YouTube, etc.)')

    match       = models.ForeignKey(
        Match, on_delete=models.CASCADE,
        related_name='media', verbose_name=_('Match'),
    )
    media_type  = models.CharField(
        max_length=10, choices=MediaType.choices,
        default=MediaType.IMAGE, verbose_name=_('Type')
    )
    title       = models.CharField(max_length=200, blank=True, verbose_name=_('Titre / Description'))
    file        = models.FileField(upload_to='match_media/%Y/%m/', blank=True, null=True, verbose_name=_('Fichier'))
    url         = models.URLField(blank=True, null=True, verbose_name=_('Lien externe'))
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Date d\'ajout'))

    class Meta:
        verbose_name = _('Média du match')
        verbose_name_plural = _('Médias des matchs')
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_media_type_display()} - {self.title or self.match}"

class PlayerMatchPerformance(models.Model):
    """Referees' rating and individual stats for a player in a specific match."""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='performances')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='performances')
    rating = models.DecimalField(
        max_digits=4, decimal_places=2, default=6.0,
        verbose_name=_('Note de l\'arbitre'),
        help_text=_('Note de 0 à 10')
    )
    is_starter = models.BooleanField(default=False, verbose_name=_('Titulaire'))
    position_name = models.CharField(max_length=50, blank=True, verbose_name=_('Poste (ex: GK, LW)'))
    
    # Coordinates for Tactical View (0-100 percentage)
    x_pos = models.FloatField(default=50.0, verbose_name=_('Position X (%)'))
    y_pos = models.FloatField(default=50.0, verbose_name=_('Position Y (%)'))

    notes = models.TextField(blank=True, verbose_name=_('Commentaires'))

    class Meta:
        verbose_name = _('Performance joueur')
        verbose_name_plural = _('Performances joueurs')
        unique_together = [['match', 'player']]

    def __str__(self):
        return f"{self.player.full_name} @ {self.match} ({self.rating}/10)"


class MatchVote(models.Model):
    """Fan vote for the Man of the Match (MOTM)."""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='votes')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='match_votes')
    user_ip = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Vote Match')
        verbose_name_plural = _('Votes Matchs')
        constraints = [
            models.UniqueConstraint(fields=['match', 'user_ip'], name='unique_ip_vote_per_match')
        ]

    def __str__(self):
        return f"Vote for {self.player.full_name} in {self.match}"


class MatchEvent(models.Model):
    """Tracks generic match events (Kickoff, Halftime, Fulltime, Substitution, VAR, Penalty Missed, Commentary)."""
    
    class EventType(models.TextChoices):
        KICKOFF     = 'kickoff',      _('Coup d\'envoi / ركلة البداية')
        HALFTIME    = 'halftime',     _('Mi-temps / الاستراحة')
        SECOND_HALF = 'second_half',  _('Seconde période / الشوط الثاني')
        FULLTIME    = 'fulltime',     _('Fin du match / نهاية المباراة')
        SUBSTITUTION= 'substitution', _('Changement / تبديل')
        VAR         = 'var',          _('Décision VAR / قرار الفار')
        PENALTY_MISSED = 'penalty_missed', _('Penalty manqué / ركلة جزاء ضائعة')
        COMMENTARY  = 'commentary',   _('Commentaire / تعليق')

    match       = models.ForeignKey(
        Match, on_delete=models.CASCADE,
        related_name='timeline_events', verbose_name=_('Match'),
    )
    event_type  = models.CharField(
        max_length=20, choices=EventType.choices,
        default=EventType.COMMENTARY, verbose_name=_('Type d\'événement')
    )
    minute      = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name=_('Minute'),
    )
    team        = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='match_events', verbose_name=_('Équipe')
    )
    player1     = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='events_primary', verbose_name=_('Joueur principal')
    )
    player2     = models.ForeignKey(
        Player, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='events_secondary', verbose_name=_('Joueur secondaire (ex: entrant)')
    )
    description = models.CharField(max_length=255, blank=True, verbose_name=_('Description (FR)'))
    description_ar = models.CharField(max_length=255, blank=True, verbose_name=_('Description (AR)'))
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Événement de match')
        verbose_name_plural = _('Événements de match')
        ordering = ['minute', 'created_at']

    def __str__(self):
        return f"{self.get_event_type_display()} ({self.minute}') — {self.match}"
