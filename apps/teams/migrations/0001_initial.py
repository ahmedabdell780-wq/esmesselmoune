from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import apps.teams.models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('accounts', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, verbose_name='Nom')),
                ('neighborhood', models.CharField(max_length=120, verbose_name='Quartier')),
                ('city', models.CharField(default='MESSLMOUNE', max_length=100, verbose_name='Commune')),
                ('wilaya', models.CharField(default='Tipaza', max_length=100, verbose_name='Wilaya')),
                ('logo', models.ImageField(blank=True, null=True, upload_to=apps.teams.models.team_logo_path, verbose_name='Logo du club')),
                ('color_primary', models.CharField(default='#006233', max_length=7, verbose_name='Couleur principale')),
                ('color_secondary', models.CharField(default='#FFFFFF', max_length=7, verbose_name='Couleur secondaire')),
                ('founded_year', models.PositiveIntegerField(blank=True, null=True, verbose_name='Année de fondation')),
                ('contact_phone', models.CharField(blank=True, max_length=20, verbose_name='Téléphone')),
                ('contact_email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('manager', models.ForeignKey(blank=True, limit_choices_to={'role': 'manager'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='teams_managed', to='accounts.user', verbose_name='Responsable')),
            ],
            options={'verbose_name': 'Équipe', 'verbose_name_plural': 'Équipes', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Player',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('first_name', models.CharField(max_length=50, verbose_name='Prénom')),
                ('last_name', models.CharField(max_length=50, verbose_name='Nom')),
                ('date_of_birth', models.DateField(blank=True, null=True, verbose_name='Date de naissance')),
                ('national_id', models.CharField(blank=True, max_length=20, unique=True, verbose_name='N° Carte nationale')),
                ('position', models.CharField(choices=[('GK','Gardien de but'),('DEF','Défenseur'),('MID','Milieu'),('FWD','Attaquant')], default='MID', max_length=3, verbose_name='Poste')),
                ('jersey_number', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(99)], verbose_name='Numéro de maillot')),
                ('preferred_foot', models.CharField(choices=[('L','Gauche'),('R','Droite'),('B','Les deux')], default='R', max_length=1, verbose_name='Pied préféré')),
                ('photo', models.ImageField(blank=True, null=True, upload_to=apps.teams.models.player_photo_path, verbose_name='Photo')),
                ('height_cm', models.PositiveIntegerField(blank=True, null=True, verbose_name='Taille (cm)')),
                ('weight_kg', models.PositiveIntegerField(blank=True, null=True, verbose_name='Poids (kg)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Actif')),
                ('is_suspended', models.BooleanField(default=False, verbose_name='Suspendu')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='players', to='teams.team', verbose_name='Équipe')),
            ],
            options={'verbose_name': 'Joueur', 'verbose_name_plural': 'Joueurs', 'ordering': ['last_name', 'first_name'], 'unique_together': {('team', 'jersey_number')}},
        ),
    ]
