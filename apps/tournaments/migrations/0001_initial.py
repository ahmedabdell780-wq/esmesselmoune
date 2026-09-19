from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('teams', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='Tournament',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200, verbose_name='Nom')),
                ('edition', models.PositiveIntegerField(default=1, verbose_name='Édition')),
                ('year', models.PositiveIntegerField(verbose_name='Année')),
                ('description', models.TextField(blank=True)),
                ('banner', models.ImageField(blank=True, null=True, upload_to='banners/')),
                ('format', models.CharField(choices=[('group_knockout','Groupes + Élimination directe'),('round_robin','Championnat aller-retour'),('single_knockout','Élimination directe')], default='group_knockout', max_length=20)),
                ('status', models.CharField(choices=[('draft','Brouillon'),('registration','Inscriptions ouvertes'),('group_stage','Phase de groupes'),('knockout','Phase finale'),('finished','Terminé')], default='draft', max_length=20)),
                ('max_teams', models.PositiveIntegerField(default=16)),
                ('num_groups', models.PositiveIntegerField(default=4, validators=[django.core.validators.MinValueValidator(1)])),
                ('teams_advancing_per_group', models.PositiveIntegerField(default=2)),
                ('points_win', models.PositiveIntegerField(default=3)),
                ('points_draw', models.PositiveIntegerField(default=1)),
                ('points_loss', models.PositiveIntegerField(default=0)),
                ('registration_deadline', models.DateField(blank=True, null=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('location', models.CharField(default='Stade Communal', max_length=200)),
                ('winner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='trophies', to='teams.team')),
                ('runner_up', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='runner_up_tournaments', to='teams.team')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'verbose_name': 'Tournoi', 'ordering': ['-year', '-edition']},
        ),
        migrations.CreateModel(
            name='TournamentTeam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('registration_date', models.DateTimeField(auto_now_add=True)),
                ('is_confirmed', models.BooleanField(default=False)),
                ('seed', models.PositiveIntegerField(blank=True, null=True)),
                ('eliminated_at_stage', models.CharField(blank=True, max_length=20)),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tournaments.tournament')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='teams.team')),
            ],
            options={'unique_together': {('tournament', 'team')}},
        ),
        migrations.AddField(
            model_name='tournament',
            name='teams',
            field=models.ManyToManyField(related_name='tournaments', through='tournaments.TournamentTeam', to='teams.team'),
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=50)),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groups', to='tournaments.tournament')),
                ('teams', models.ManyToManyField(related_name='groups', to='teams.team')),
            ],
            options={'verbose_name': 'Groupe', 'ordering': ['name'], 'unique_together': {('tournament', 'name')}},
        ),
        migrations.CreateModel(
            name='GroupStanding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('played', models.PositiveIntegerField(default=0)),
                ('won', models.PositiveIntegerField(default=0)),
                ('drawn', models.PositiveIntegerField(default=0)),
                ('lost', models.PositiveIntegerField(default=0)),
                ('goals_for', models.PositiveIntegerField(default=0)),
                ('goals_against', models.PositiveIntegerField(default=0)),
                ('points', models.IntegerField(default=0)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='groupstanding_set', to='tournaments.group')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='standings', to='teams.team')),
            ],
            options={'unique_together': {('group', 'team')}},
        ),
    ]
