from django.db import migrations, models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False)),
                ('username', models.CharField(max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()])),
                ('first_name', models.CharField(blank=True, max_length=150)),
                ('last_name', models.CharField(blank=True, max_length=150)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('is_staff', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('role', models.CharField(choices=[('admin','Administrateur / مدير'),('organizer','Organisateur / منظم'),('manager',"Responsable d'équipe / مسؤول فريق"),('viewer','Spectateur / متفرج')], default='viewer', max_length=20)),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('avatar', models.ImageField(blank=True, null=True, upload_to='avatars/')),
                ('neighborhood', models.CharField(blank=True, max_length=120)),
                ('bio', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('groups', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'Utilisateur',
                'verbose_name_plural': 'Utilisateurs',
                'ordering': [],
            },
            managers=[
                ('objects', django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='AppearanceSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('theme', models.CharField(choices=[('dark','Sombre / داكن'),('light','Clair / فاتح'),('emerald','Émeraude / زمردي'),('ocean','Océan / أزرق')], default='dark', max_length=10)),
                ('primary_color', models.CharField(default='#C5A028', max_length=7)),
                ('font_size', models.CharField(choices=[('xs','Très petit / صغير جداً'),('sm','Petit / صغير'),('base','Normal / عادي'),('lg','Grand / كبير'),('xl','Très grand / كبير جداً')], default='base', max_length=4)),
                ('font_family', models.CharField(choices=[('cairo','Cairo (افتراضي)'),('noto','Noto Arabic'),('amiri','Amiri (خط عربي كلاسيكي)'),('inter','Inter (لاتيني)'),('roboto','Roboto (لاتيني)'),('bebas','Bebas Neue (عناوين)')], default='cairo', max_length=10)),
                ('language', models.CharField(choices=[('fr','Français'),('ar','العربية')], default='fr', max_length=5)),
                ('show_stats_sidebar', models.BooleanField(default=True)),
                ('notifications_enabled', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='appearance', to='accounts.user')),
            ],
            options={'verbose_name': 'Apparence'},
        ),
    ]
