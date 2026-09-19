import os
from django.core.management.base import BaseCommand
from apps.teams.models import Player, Team
from apps.teams.utils import remove_player_background

class Command(BaseCommand):
    help = 'Process all player photos and team logos to remove backgrounds professionally.'

    def handle(self, *args, **options):
        # 1. Process Players
        players = Player.objects.filter(photo__isnull=False).exclude(photo='')
        self.stdout.write(f"Found {players.count()} players with photos.")
        
        for player in players:
            name_safe = player.full_name.encode('ascii', 'ignore').decode('ascii') or "Player"
            if '_cutout' in player.photo.name:
                self.stdout.write(self.style.WARNING(f"Skipping {name_safe} (already processed)"))
                continue
            
            self.stdout.write(f"Processing background for: {name_safe}...")
            processed_image = remove_player_background(player.photo)
            
            if processed_image:
                orig_name = os.path.basename(player.photo.name)
                name_parts = orig_name.rsplit('.', 1)
                new_name = f"{name_parts[0]}_cutout.png"
                
                # We save with save=True to trigger the database update
                player.photo.save(new_name, processed_image, save=True)
                self.stdout.write(self.style.SUCCESS(f"Successfully processed {player.full_name}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to process {player.full_name}"))

        # 2. Process Teams
        teams = Team.objects.filter(logo__isnull=False).exclude(logo='')
        self.stdout.write(f"\nFound {teams.count()} teams with logos.")
        
        for team in teams:
            name_safe = team.name.encode('ascii', 'ignore').decode('ascii') or "Team"
            if '_cutout' in team.logo.name:
                self.stdout.write(self.style.WARNING(f"Skipping {name_safe} (already processed)"))
                continue
            
            self.stdout.write(f"Processing background for team logo: {name_safe}...")
            processed_image = remove_player_background(team.logo)
            
            if processed_image:
                orig_name = os.path.basename(team.logo.name)
                name_parts = orig_name.rsplit('.', 1)
                new_name = f"{name_parts[0]}_logo_cutout.png"
                
                team.logo.save(new_name, processed_image, save=True)
                self.stdout.write(self.style.SUCCESS(f"Successfully processed logo for {team.name}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to process logo for {team.name}"))

        self.stdout.write(self.style.SUCCESS("\nAll processing completed!"))
