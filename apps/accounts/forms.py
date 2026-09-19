from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from .models import User, AppearanceSettings
from apps.core.models import SiteSettings


class RegisterForm(UserCreationForm):
    email      = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name  = forms.CharField(max_length=50, required=True)
    
    ROLE_CHOICES = [
        (User.Role.TEAM_MANAGER, _('Responsable d\'équipe / مسؤول فريق')),
        (User.Role.ORGANIZER, _('Organisateur / منظم')),
        (User.Role.VIEWER, _('Spectateur / متفرج')),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True, initial=User.Role.VIEWER, label=_("Rôle souhaité / الدور المطلوب"))

    class Meta:
        model  = User
        fields = ('username','first_name','last_name','email',
                  'phone','neighborhood','role','password1','password2')


class AppearanceForm(forms.ModelForm):
    class Meta:
        model  = AppearanceSettings
        fields = ('theme','primary_color','font_size','font_family',
                  'language','show_stats_sidebar','notifications_enabled')
        widgets = {
            'primary_color': forms.TextInput(attrs={'type':'color'}),
        }


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ('app_background',)
