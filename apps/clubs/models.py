from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class Category(models.Model):
    """الفئات العمرية للنادي"""
    CATEGORY_CHOICES = [
        ('U6', 'U6 (أقل من 6 سنوات)'),
        ('U7', 'U7 (أقل من 7 سنوات)'),
        ('U8', 'U8 (أقل من 8 سنوات)'),
        ('U9', 'U9 (أقل من 9 سنوات)'),
        ('U10', 'U10 (أقل من 10 سنوات)'),
        ('U11', 'U11 (أقل من 11 سنة)'),
        ('U12', 'U12 (أقل من 12 سنة)'),
        ('U13', 'U13 (أقل من 13 سنة)'),
        ('U14', 'U14 (أقل من 14 سنة)'),
        ('U15', 'U15 (أقل من 15 سنة)'),
        ('U17', 'U17 (أقل من 17 سنة)'),
        ('U19', 'U19 (أقل من 19 سنة)'),
        ('U20', 'U20 (أقل من 20 سنة)'),
        ('U21', 'U21 (أقل من 21 سنة)'),
        ('U23', 'U23 (أقل من 23 سنة)'),
        ('Seniors', 'Seniors (أكابر)'),
        ('Féminines', 'Féminines (إناث)'),
        ('École de Football', 'École de Football (مدرسة كروية)'),
    ]

    name = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name=_('Nom de la catégorie (اسم الفئة العمرية)'))
    min_age = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Âge minimum'))
    max_age = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Âge maximum'))
    coach_name = models.CharField(max_length=100, blank=True, null=True, verbose_name=_('Entraîneur (اسم المدرب)'))
    coach_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Téléphone de l\'entraîneur (رقم هاتف المدرب)'))
    description = models.TextField(blank=True, verbose_name=_('Description'))

    class Meta:
        verbose_name = _('Catégorie')
        verbose_name_plural = _('Catégories')
        ordering = ['min_age', 'name']

    def __str__(self):
        return self.name

    @property
    def coach_display(self):
        if self.coach_name and self.coach_name.strip():
            return self.coach_name.strip()
        try:
            assigned_staff = self.staff.filter(role='COACH', is_active=True).first()
            if assigned_staff:
                return f"{assigned_staff.first_name} {assigned_staff.last_name}"
        except Exception:
            pass
        return "غير محدد"

class ClubPlayer(models.Model):
    """لاعب في النادي"""
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='players', verbose_name=_('Catégorie'))
    
    # Informations Personnelles
    first_name = models.CharField(max_length=50, verbose_name=_('Prénom'))
    last_name = models.CharField(max_length=50, verbose_name=_('Nom'))
    date_of_birth = models.DateField(verbose_name=_('Date de naissance'))
    place_of_birth = models.CharField(max_length=100, blank=True, verbose_name=_('Lieu de naissance'))
    photo = models.ImageField(upload_to='clubs/players/', blank=True, null=True, verbose_name=_('Photo'))
    
    BLOOD_TYPE_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    blood_type = models.CharField(max_length=5, choices=BLOOD_TYPE_CHOICES, blank=True, verbose_name=_('Groupe sanguin'))
    medical_certificate = models.FileField(upload_to='clubs/medical/', blank=True, null=True, verbose_name=_('Certificat médical'))
    school_level = models.CharField(max_length=100, blank=True, verbose_name=_('Niveau Scolaire (المستوى الدراسي)'))
    
    # Contact (Parents pour les mineurs)
    PARENT_RELATION_CHOICES = [
        ('أب', 'أب (Père)'),
        ('أم', 'أم (Mère)'),
        ('وصي شرعي', 'وصي شرعي (Tuteur Légal)'),
    ]
    parent_relation = models.CharField(max_length=30, choices=PARENT_RELATION_CHOICES, blank=True, verbose_name=_('Lien de parenté (صلة القرابة)'))
    parent_name = models.CharField(max_length=100, blank=True, verbose_name=_('Nom du tuteur (Parent)'))
    parent_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone du tuteur'))
    emergency_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone d\'urgence (هاتف الطوارئ)'))
    parent_email = models.EmailField(blank=True, verbose_name=_('Email du tuteur (البريد الإلكتروني)'))
    parent_profession = models.CharField(max_length=150, blank=True, verbose_name=_('Profession et lieu de travail (المهنة ومقر العمل)'))
    
    player_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone du joueur'))
    address = models.TextField(blank=True, verbose_name=_('Adresse'))
    
    POSITION_CHOICES = [
        ('حارس مرمى', 'حارس مرمى (Gardien de but)'),
        ('مدافع', 'مدافع (Défenseur)'),
        ('وسط ميدان', 'وسط ميدان (Milieu de terrain)'),
        ('مهاجم', 'مهاجم (Attaquant)'),
    ]
    FOOT_CHOICES = [
        ('يمنى', 'يمنى (Droitier)'),
        ('يسرى', 'يسرى (Gaucher)'),
        ('كلاهما', 'كلاهما (Ambidextre)'),
    ]
    
    # Sportif
    position = models.CharField(max_length=50, choices=POSITION_CHOICES, blank=True, verbose_name=_('Poste (المركز التكتيكي)'))
    preferred_foot = models.CharField(max_length=20, choices=FOOT_CHOICES, blank=True, verbose_name=_('Pied Fort (القدم المفضلة)'))
    previous_club = models.CharField(max_length=150, blank=True, verbose_name=_('Club précédent (النادي أو المدرسة السابقة)'))
    jersey_number = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Numéro de maillot'))
    joined_date = models.DateField(auto_now_add=True, verbose_name=_("Date d'inscription"))
    
    # Biometrie / Medical Ext
    height = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Taille en cm (القامة)'))
    weight = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Poids en kg (الوزن)'))
    medical_history = models.TextField(blank=True, verbose_name=_('Antécédents médicaux (الأمراض المزمنة أو السوابق الجراحية)'))
    
    # Système
    is_active = models.BooleanField(default=True, verbose_name=_('Actif'))
    card_number = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name=_('Numéro de carte'))
    
    class Meta:
        verbose_name = _('Joueur du Club')
        verbose_name_plural = _('Joueurs du Club')
        ordering = ['category', 'last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.category})"
        
    @property
    def generated_card_number(self):
        cat_name = self.category.name if self.category else "U0"
        cat_clean = "".join(cat_name.split())
        year = self.joined_date.year if self.joined_date else 2024
        pk_num = self.id if self.id else 0
        return f"{cat_clean}{year}{pk_num:03d}"

    @property
    def total_attendances(self):
        return self.attendances.count()
        
    @property
    def present_count(self):
        return self.attendances.filter(is_present=True).count()
        
    @property
    def absent_count(self):
        return self.attendances.filter(is_present=False).count()

class TrainingSession(models.Model):
    """حصة تدريبية"""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='trainings', verbose_name=_('Catégorie'))
    date = models.DateField(verbose_name=_('Date'))
    start_time = models.TimeField(verbose_name=_('Heure de début'))
    end_time = models.TimeField(verbose_name=_('Heure de fin'))
    location = models.CharField(max_length=100, default='Stade Communal', verbose_name=_('Lieu'))
    notes = models.TextField(blank=True, verbose_name=_('Notes / Objectifs'))

    class Meta:
        verbose_name = _('Séance d\'entraînement')
        verbose_name_plural = _('Séances d\'entraînement')
        ordering = ['-date', '-start_time']

    def __str__(self):
        return f"{self.category} - {self.date}"


class ClubMatch(models.Model):
    """مباريات النادي"""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='matches', verbose_name=_('Catégorie'))
    date = models.DateField(verbose_name=_('Date du match'))
    time = models.TimeField(null=True, blank=True, verbose_name=_('Heure'))
    opponent = models.CharField(max_length=100, verbose_name=_('Adversaire'))
    location = models.CharField(max_length=100, verbose_name=_('Lieu'))
    is_home = models.BooleanField(default=True, verbose_name=_('À domicile'))
    
    our_score = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Notre score'))
    their_score = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Leur score'))
    
    notes = models.TextField(blank=True, verbose_name=_('Compte-rendu'))

    class Meta:
        verbose_name = _('Match du Club')
        verbose_name_plural = _('Matchs du Club')
        ordering = ['-date', '-time']

    def __str__(self):
        home_team = "Wifaq Messelmoune" if self.is_home else self.opponent
        away_team = self.opponent if self.is_home else "Wifaq Messelmoune"
        return f"[{self.category}] {home_team} vs {away_team} - {self.date}"

class ClubSettings(models.Model):
    """إعدادات النادي للتحكم في واجهة المستخدم"""
    club_name = models.CharField(max_length=100, default='نادي الوفاق الرياضي', verbose_name=_('Nom du Club'))
    club_subtitle = models.CharField(max_length=100, default='أكاديمية كرة القدم - مسلمون', verbose_name=_('Sous-titre'))
    club_abbreviation = models.CharField(max_length=10, default='WRM', verbose_name=_('Abréviation'))
    president_name = models.CharField(max_length=100, default='بيرم نصرالدين', verbose_name=_('اسم رئيس النادي'))
    
    logo = models.ImageField(upload_to='clubs/settings/', blank=True, null=True, verbose_name=_('Logo du Club'))
    cover_image = models.ImageField(upload_to='clubs/settings/', blank=True, null=True, verbose_name=_('Image de couverture'))
    
    gradient_start = models.CharField(max_length=20, default='from-primary/80', verbose_name=_('Couleur de début (Gradient)'))
    gradient_end = models.CharField(max_length=20, default='to-black/90', verbose_name=_('Couleur de fin (Gradient)'))
    
    academy_registration_open = models.BooleanField(default=False, verbose_name=_('Ouverture des inscriptions (فتح التسجيلات)'))
    
    class Meta:
        verbose_name = _('Paramètres du Club')
        verbose_name_plural = _('Paramètres du Club')

    def __str__(self):
        return "Paramètres de l'Académie"
    
    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(id=1)
        return settings

# --- Nouvelles Fonctionnalités (Staff, Médical, Financier) ---

class StaffMember(models.Model):
    """الطاقم الفني والإداري"""
    class Role(models.TextChoices):
        COACH = 'COACH', _('Entraîneur (مدرب)')
        ADMIN = 'ADMIN', _('Administrateur (إداري)')
        MEDICAL = 'MEDIC', _('Staff Médical (طبيب/معالج)')
        KITMAN = 'KITMAN', _('Responsable Matériel (مكلف بالعتاد)')
        
    first_name = models.CharField(max_length=50, verbose_name=_('Prénom'))
    last_name = models.CharField(max_length=50, verbose_name=_('Nom'))
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.COACH, verbose_name=_('Rôle'))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone'))
    photo = models.ImageField(upload_to='clubs/staff/', blank=True, null=True, verbose_name=_('Photo'))
    category_assigned = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff', verbose_name=_('Catégorie Assignée (Optionnel)'))
    is_active = models.BooleanField(default=True, verbose_name=_('Actif'))

    class Meta:
        verbose_name = _('Membre du Staff')
        verbose_name_plural = _('Membres du Staff')
        ordering = ['role', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_role_display()}"

class Subscription(models.Model):
    """الاشتراكات الشهرية"""
    player = models.ForeignKey(ClubPlayer, on_delete=models.CASCADE, related_name='subscriptions', verbose_name=_('Joueur'))
    month = models.DateField(verbose_name=_('Mois (ex: 2026-09-01 pour Septembre)'), help_text=_('Sélectionnez le 1er jour du mois concerné'))
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=1500.00, verbose_name=_('Montant (DA)'))
    is_paid = models.BooleanField(default=False, verbose_name=_('Payé ?'))
    paid_date = models.DateField(null=True, blank=True, verbose_name=_('Date de paiement'))
    notes = models.TextField(blank=True, verbose_name=_('Notes'))

    class Meta:
        verbose_name = _('Abonnement Mensuel')
        verbose_name_plural = _('Abonnements Mensuels')
        unique_together = [['player', 'month']]
        ordering = ['-month', 'player__last_name']

    def __str__(self):
        return f"{self.player} - {self.month.strftime('%Y/%m')} ({'Payé' if self.is_paid else 'Non Payé'})"

class MedicalRecord(models.Model):
    """السجل الطبي وإصابات الملاعب"""
    player = models.ForeignKey(ClubPlayer, on_delete=models.CASCADE, related_name='medical_records', verbose_name=_('Joueur'))
    injury_type = models.CharField(max_length=100, verbose_name=_('Type de blessure'))
    date_of_injury = models.DateField(verbose_name=_('Date de blessure'))
    expected_return = models.DateField(null=True, blank=True, verbose_name=_('Retour prévu le'))
    is_recovered = models.BooleanField(default=False, verbose_name=_('Rétabli ?'))
    notes = models.TextField(blank=True, verbose_name=_('Diagnostic et traitement'))

    class Meta:
        verbose_name = _('Dossier Médical (Blessure)')
        verbose_name_plural = _('Dossiers Médicaux (Blessures)')
        ordering = ['-date_of_injury']

    def __str__(self):
        return f"{self.player} - {self.injury_type} ({'Rétabli' if self.is_recovered else 'En traitement'})"

class TrainingAttendance(models.Model):
    """حضور وغياب اللاعبين في التدريبات"""
    session = models.ForeignKey('TrainingSession', on_delete=models.CASCADE, related_name='attendances', verbose_name=_('Séance d\'entraînement'))
    player = models.ForeignKey(ClubPlayer, on_delete=models.CASCADE, related_name='attendances', verbose_name=_('Joueur'))
    is_present = models.BooleanField(default=True, verbose_name=_('Présent ?'))
    reason_for_absence = models.CharField(max_length=200, blank=True, verbose_name=_('Motif d\'absence'))

    class Meta:
        verbose_name = _('Présence à l\'entraînement')
        verbose_name_plural = _('Présences aux entraînements')
        unique_together = [['session', 'player']]
        ordering = ['session__date', 'player__last_name']

    def __str__(self):
        return f"{self.player} - {self.session.date} - {'Présent' if self.is_present else 'Absent'}"

class PlayerEvaluation(models.Model):
    """التقييم الفني والبدني للاعب (كشف النقاط)"""
    player = models.ForeignKey(ClubPlayer, on_delete=models.CASCADE, related_name='evaluations', verbose_name=_('Joueur'))
    date_evaluated = models.DateField(auto_now_add=True, verbose_name=_('Date d\'évaluation'))
    evaluator = models.ForeignKey('StaffMember', on_delete=models.SET_NULL, null=True, verbose_name=_('Évaluateur'))
    
    # Metrics out of 10
    physical_fitness = models.IntegerField(default=5, verbose_name=_('Condition Physique /10'))
    speed = models.IntegerField(default=5, verbose_name=_('Vitesse /10'))
    passing = models.IntegerField(default=5, verbose_name=_('Passes & Contrôle /10'))
    tactical_awareness = models.IntegerField(default=5, verbose_name=_('Sens Tactique /10'))
    discipline = models.IntegerField(default=5, verbose_name=_('Discipline & Assiduité /10'))
    
    coach_remarks = models.TextField(blank=True, verbose_name=_('Remarques du Coach'))

    class Meta:
        verbose_name = _('Évaluation du Joueur')
        verbose_name_plural = _('Évaluations des Joueurs')
        ordering = ['-date_evaluated']

    def __str__(self):
        return f"Évaluation {self.player} ({self.date_evaluated})"
        
    def total_score(self):
        return self.physical_fitness + self.speed + self.passing + self.tactical_awareness + self.discipline

class PlayerEquipment(models.Model):
    """إدارة العتاد والألبسة الرياضية"""
    player = models.ForeignKey(ClubPlayer, on_delete=models.CASCADE, related_name='equipment', verbose_name=_('Joueur'))
    
    received_training_kit = models.BooleanField(default=False, verbose_name=_('Tenue d\'entraînement reçue'))
    training_kit_date = models.DateField(null=True, blank=True, verbose_name=_('Date tenue entraînement'))
    
    received_tracksuit = models.BooleanField(default=False, verbose_name=_('Survêtement (Parade) reçu'))
    tracksuit_date = models.DateField(null=True, blank=True, verbose_name=_('Date survêtement'))
    
    received_bag = models.BooleanField(default=False, verbose_name=_('Sac de sport reçu'))
    bag_date = models.DateField(null=True, blank=True, verbose_name=_('Date sac'))
    
    notes = models.TextField(blank=True, verbose_name=_('Notes sur l\'équipement'))

    class Meta:
        verbose_name = _('Équipement du Joueur')
        verbose_name_plural = _('Équipements des Joueurs')

    def __str__(self):
        return f"Équipements de {self.player}"


class ClubNews(models.Model):
    title = models.CharField(max_length=200, verbose_name=_('Titre / العنوان'))
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    content = models.TextField(verbose_name=_('Contenu / المحتوى'))
    image = models.ImageField(upload_to='clubs/news/', blank=True, null=True, verbose_name=_('Image / صورة'))
    is_published = models.BooleanField(default=True, verbose_name=_('Publie / منشور'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Actualite du Club')
        verbose_name_plural = _('Actualites du Club')
        ordering = ['-created_at']

    def __str__(self):
        return self.title
