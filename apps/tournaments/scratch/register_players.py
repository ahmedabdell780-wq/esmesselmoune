import os
import django
from datetime import datetime

# Setup Django environment
import sys
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')
django.setup()

from apps.teams.models import Team, Player

def register_players():
    team_id = 53
    try:
        team = Team.objects.get(pk=team_id)
        print(f"Adding players to team: {team.name}")
    except Team.DoesNotExist:
        print(f"Error: Team with ID {team_id} does not exist.")
        return

    players_data = [
        {"fn": "يوسف", "ln": "حطالي", "jersey": 1, "pos": "MID", "dob": None, "id": "ESM000006"},
        {"fn": "سفيان", "ln": "موساوي", "jersey": 2, "pos": "MID", "dob": "1984-01-01", "id": "ESM000001"},
        {"fn": "جمال", "ln": "قوشي", "jersey": 5, "pos": "MID", "dob": None, "id": "ESM000008"},
        {"fn": "عبد الرحمان", "ln": "داود", "jersey": 6, "pos": "MID", "dob": "1978-02-24", "id": "ESM000005"},
        {"fn": "محمد", "ln": "بلعيدي", "jersey": 7, "pos": "MID", "dob": "1978-01-01", "id": "ESM000004"},
        {"fn": "ابراهيم", "ln": "بونعيمي", "jersey": 8, "pos": "MID", "dob": "1975-06-21", "id": "ESM000002"},
        {"fn": "محمد", "ln": "بيرم", "jersey": 10, "pos": "MID", "dob": "1973-04-02", "id": "ESM000003"},
        {"fn": "يوسف", "ln": "بشير", "jersey": 11, "pos": "MID", "dob": None, "id": "ESM000007"},
        {"fn": "إياد", "ln": "بوعبدالله", "jersey": 16, "pos": "MID", "dob": None, "id": "ESM000010-026"},
    ]

    for p in players_data:
        try:
            dob = datetime.strptime(p["dob"], "%Y-%m-%d").date() if p["dob"] else None
            player, created = Player.objects.get_or_create(
                national_id=p["id"],
                defaults={
                    "team": team,
                    "first_name": p["fn"],
                    "last_name": p["ln"],
                    "jersey_number": p["jersey"],
                    "position": p["pos"],
                    "date_of_birth": dob,
                }
            )
            if created:
                print(f"Registered: {p['fn']} {p['ln']} (#{p['jersey']})")
            else:
                print(f"Already exists: {p['fn']} {p['ln']} (ID: {p['id']})")
        except Exception as e:
            print(f"Error adding {p['fn']} {p['ln']}: {e}")

if __name__ == "__main__":
    register_players()
