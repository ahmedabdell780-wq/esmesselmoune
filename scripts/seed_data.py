"""
TurniQ v3 — Seed Script
Run: python scripts/seed_data.py
"""
import os, sys, django, random
from datetime import date, timedelta

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

try:
    django.setup()
except RuntimeError:
    pass

random.seed(42)

from apps.accounts.models import User
from apps.teams.models import Team, Player
from apps.tournaments.models import Tournament, TournamentTeam
from apps.tournaments.services.scheduler import GroupSeeder, MatchScheduler

print("🌱 TurniQ v3 — Seeding...")
print("=" * 50)

# ── 1. ADMIN ──────────────────────────────────────────────────────────────────
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin', email='admin@turniq.dz',
        password='admin123', role=User.Role.ADMIN,
        first_name='Admin', last_name='TurniQ'
    )
    print("✅ Admin créé : admin / admin123")
else:
    print("ℹ️  Admin existe déjà")

# ── 2. TEAMS ──────────────────────────────────────────────────────────────────
TEAMS = [
    ('Hay El Wiam',      'Cité El Wiam',    '#006233'),
    ('Quartier El Nour', 'Cité El Nour',    '#D21034'),
    ('Hay El Amel',      'Cité El Amel',    '#003087'),
    ('Cité El Fath',     'Quartier El Fath','#7B2D8B'),
    ('Hay El Hilal',     'Cité El Hilal',   '#C5A028'),
    ('Quartier Erraha',  'Cité Erraha',     '#0d9488'),
    ('Hay El Badr',      'Cité El Badr',    '#ea580c'),
    ('Cité Nedjma',      'Quartier Nedjma', '#7c3aed'),
]

FIRSTS = ['يوسف','رشيد','مهدي','كريم','أمين','بلال','سمير','خالد','نسيم','عمر',
          'Youcef','Rachid','Mehdi','Karim','Amine']
LASTS  = ['عمراني','بوزيد','قاسي','مسعود','شريف','حمدي','بوعلي','رزيق',
          'Amrani','Bouzid','Kaci','Messaoud','Cherif','Hamdi']
POS    = ['GK','DEF','DEF','MID','MID','FWD']

teams_list = []
for name, neighborhood, color in TEAMS:
    team, created = Team.objects.get_or_create(
        name=name,
        defaults=dict(
            neighborhood=neighborhood, city='MESSLMOUNE', wilaya='Tipaza',
            color_primary=color, color_secondary='#FFFFFF', is_active=True
        )
    )
    teams_list.append(team)
    status = "✅ créée" if created else "ℹ️  existe"
    print(f"  {status} : {team.name}")

    if created or not team.players.exists():
        for j, pos in enumerate(POS):
            try:
                Player.objects.get_or_create(
                    team=team, jersey_number=j+1,
                    defaults=dict(
                        first_name=random.choice(FIRSTS),
                        last_name=random.choice(LASTS),
                        position=pos, preferred_foot='R', is_active=True,
                        national_id=f"DZ{teams_list.index(team):02d}{j:02d}{random.randint(1000,9999)}",
                        date_of_birth=date(1995+random.randint(0,10),
                                           random.randint(1,12),
                                           random.randint(1,28)),
                    )
                )
            except Exception:
                pass
        print(f"    👥 {len(POS)} joueurs ajoutés → {team.name}")

# ── 3. TOURNAMENT ─────────────────────────────────────────────────────────────
t, created = Tournament.objects.get_or_create(
    name="بطولة أحياء مسلمون 2025 / Tournoi Inter-Quartiers MESSLMOUNE",
    year=2025,
    defaults=dict(
        edition=1,
        format=Tournament.Format.GROUP_KNOCKOUT,
        status=Tournament.Status.REGISTRATION,
        max_teams=8, num_groups=2, teams_advancing_per_group=2,
        points_win=3, points_draw=1, points_loss=0,
        start_date=date.today() + timedelta(days=7),
        end_date=date.today() + timedelta(days=35),
        location='الملعب البلدي — مسلمون / Stade Communal, MESSLMOUNE',
        description='البطولة السنوية لكرة القدم بين أحياء بلدية مسلمون، ولاية تيبازة.',
    )
)
print(f"\n🏆 Tournoi : {t}" + (" (nouveau)" if created else " (existe)"))

# ── 4. REGISTER TEAMS ────────────────────────────────────────────────────────
for i, team in enumerate(teams_list):
    tt, created = TournamentTeam.objects.get_or_create(
        tournament=t, team=team,
        defaults={'is_confirmed': True, 'seed': i+1}
    )
    if created:
        print(f"  ✅ Inscrite : {team.name}")

# ── 5. GROUPS + SCHEDULE ─────────────────────────────────────────────────────
from apps.matches.models import Match

if not t.groups.exists():
    t.status = Tournament.Status.REGISTRATION
    t.save()
    groups = GroupSeeder(t).seed_groups()
    t.status = Tournament.Status.GROUP_STAGE
    t.save()
    print(f"\n📦 Groupes : {[g.name for g in groups]}")

if not t.matches.exists():
    matches = MatchScheduler(t).generate_group_stage(
        start_date=date.today() + timedelta(days=7),
        match_time='17:00', gap_days=2
    )
    print(f"📅 Matchs générés : {len(matches)}")
else:
    print(f"ℹ️  Matchs existants : {t.matches.count()}")

print("\n" + "=" * 50)
print("🎉 Terminé !")
print("   🌐 http://127.0.0.1:8000/")
print("   👤 admin / admin123")
print("=" * 50)
