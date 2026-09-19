"""
TurniQ Teams — Forms for Team and Player CRUD operations.
Supports Arabic and French with full validation.
"""
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Team, Player


class TeamForm(forms.ModelForm):
    """Complete form for creating/editing a team."""

    class Meta:
        model = Team
        fields = [
            'name', 'neighborhood', 'city', 'wilaya',
            'logo', 'cover_photo', 'banner_height', 'cover_offset_y',
            'color_primary', 'color_secondary',
            'contact_phone', 'contact_email',
            'founded_year', 'description',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': _('Ex: Hay El Wiam'),
            }),
            'neighborhood': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': _('Ex: Cité El Wiam'),
            }),
            'city': forms.TextInput(attrs={'class': 'form-input'}),
            'wilaya': forms.TextInput(attrs={'class': 'form-input'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'cover_photo': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'banner_height': forms.NumberInput(attrs={'class': 'form-input', 'min': 200, 'max': 1000, 'step': 50}),
            'cover_offset_y': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100, 'type': 'range'}),
            'color_primary': forms.TextInput(attrs={'type': 'color', 'class': 'form-color'}),
            'color_secondary': forms.TextInput(attrs={'type': 'color', 'class': 'form-color'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0555 xx xx xx'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'founded_year': forms.NumberInput(attrs={'class': 'form-input', 'min': 1900, 'max': 2030}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 2:
            raise forms.ValidationError(_('Le nom doit contenir au moins 2 caractères.'))
        qs = Team.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(_('Une équipe avec ce nom existe déjà.'))
        return name


class PlayerForm(forms.ModelForm):
    """Complete form for creating/editing a player."""

    class Meta:
        model = Player
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'national_id', 'jersey_number', 'position',
            'preferred_foot', 'height_cm', 'weight_kg',
            'photo', 'is_active', 'is_suspended', 'is_captain', 'notes',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Prénom / الاسم'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nom / اللقب'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'national_id': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'رقم بطاقة التعريف'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 99}),
            'position': forms.Select(attrs={'class': 'form-input'}),
            'preferred_foot': forms.Select(attrs={'class': 'form-input'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-input', 'min': 140, 'max': 220}),
            'weight_kg': forms.NumberInput(attrs={'class': 'form-input', 'min': 40, 'max': 120}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_suspended': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_captain': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_jersey_number(self):
        num = self.cleaned_data.get('jersey_number')
        if num is None:
            return num
        # Check uniqueness within team
        team = self.initial.get('team') or (self.instance.team if self.instance.pk else None)
        if team:
            qs = Player.objects.filter(team=team, jersey_number=num)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    _(f'Le numéro {num} est déjà utilisé dans cette équipe.')
                )
        return num


class PlayerSearchForm(forms.Form):
    """Quick search + filter form for player list."""
    q        = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-input', 'placeholder': 'Rechercher un joueur... / ابحث عن لاعب'
    }))
    position = forms.ChoiceField(
        required=False,
        choices=[('', _('Tous postes'))] + list(Player.Position.choices),
        widget=forms.Select(attrs={'class': 'form-input'})
    )
    status   = forms.ChoiceField(
        required=False,
        choices=[
            ('', _('Tous')),
            ('active', _('Actifs')),
            ('suspended', _('Suspendus')),
        ],
        widget=forms.Select(attrs={'class': 'form-input'})
    )
