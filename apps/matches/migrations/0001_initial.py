from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('teams', '0001_initial'),
        ('tournaments', '0001_initial'),
        ('accounts', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='Referee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('license_number', models.CharField(blank=True, max_length=50)),
                ('experience_years', models.PositiveIntegerField(default=0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='referee_profile', to='accounts.user')),
            ],
            options={'verbose_name': 'Arbitre'},
        ),
        migrations.CreateModel(
            name='Match',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('stage', models.CharField(choices=[('GROUP','Phase de groupes'),('R16','Huitièmes de finale'),('QF','Quarts de finale'),('SF','Demi-finales'),('TP','Match pour la 3e place'),('FINAL','Finale')], default='GROUP', max_length=10)),
                ('match_day', models.PositiveIntegerField(default=1)),
                ('round_number', models.PositiveIntegerField(default=1)),
                ('score_team1', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('score_team2', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('penalties_team1', models.PositiveIntegerField(blank=True, null=True)),
                ('penalties_team2', models.PositiveIntegerField(blank=True, null=True)),
                ('match_date', models.DateTimeField()),
                ('venue', models.CharField(default='Stade Communal', max_length=200)),
                ('status', models.CharField(choices=[('scheduled','Programmé'),('live','En cours'),('finished','Terminé'),('postponed','Reporté'),('cancelled','Annulé')], default='scheduled', max_length=15)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='matches', to='tournaments.tournament')),
                ('group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matches', to='tournaments.group')),
                ('team1', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='home_matches', to='teams.team')),
                ('team2', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='away_matches', to='teams.team')),
                ('referee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='matches', to='matches.referee')),
                ('next_match', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='previous_matches', to='matches.match')),
            ],
            options={'verbose_name': 'Match', 'ordering': ['match_date']},
        ),
        migrations.CreateModel(
            name='Goal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('goal_type', models.CharField(choices=[('normal','Normal'),('own_goal','But contre son camp'),('penalty','Penalty'),('free_kick','Coup franc direct'),('header','Tête')], default='normal', max_length=15)),
                ('minute', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('is_extra_time', models.BooleanField(default=False)),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals', to='matches.match')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals', to='teams.player')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='goals_scored', to='teams.team')),
                ('assist_player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assists', to='teams.player')),
            ],
            options={'verbose_name': 'But', 'ordering': ['match', 'minute']},
        ),
        migrations.CreateModel(
            name='Card',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('card_type', models.CharField(choices=[('yellow','Carton jaune'),('red','Carton rouge'),('yellow_red','2ème jaune → rouge')], max_length=15)),
                ('minute', models.PositiveIntegerField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('results_in_suspension', models.BooleanField(default=False)),
                ('match', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cards', to='matches.match')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cards', to='teams.player')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cards_received', to='teams.team')),
            ],
            options={'verbose_name': 'Carton', 'ordering': ['match', 'minute']},
        ),
        migrations.CreateModel(
            name='Injury',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('injury_type', models.CharField(choices=[('muscle','Musculaire'),('ligament','Ligamentaire'),('bone','Osseuse (fracture)'),('contusion','Contusion'),('head','Crâne / tête'),('other','Autre')], max_length=15)),
                ('severity', models.CharField(choices=[('minor','Mineure (< 1 sem.)'),('moderate','Modérée (1-4 sem.)'),('severe','Grave (> 4 sem.)'),('career','Fin de saison')], max_length=10)),
                ('body_part', models.CharField(blank=True, max_length=100)),
                ('injury_date', models.DateField()),
                ('expected_return', models.DateField(blank=True, null=True)),
                ('absence_weeks', models.PositiveIntegerField(blank=True, null=True)),
                ('description', models.TextField(blank=True)),
                ('is_recovered', models.BooleanField(default=False)),
                ('actual_return', models.DateField(blank=True, null=True)),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='injuries', to='teams.player')),
                ('match', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='injuries', to='matches.match')),
            ],
            options={'verbose_name': 'Blessure', 'ordering': ['-injury_date']},
        ),
    ]
