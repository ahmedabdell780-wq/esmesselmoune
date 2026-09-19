from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Goal, Card
from apps.teams.models import Player

class MatchEventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.match = kwargs.pop('match')
        super().__init__(*args, **kwargs)
        
        # Filter players to only those in the two teams playing this match
        players = Player.objects.filter(team__in=[self.match.team1, self.match.team2]).select_related('team')
        self.fields['player'].queryset = players
        
        # Customize the display to show the team name next to the player
        self.fields['player'].label_from_instance = lambda obj: f"{obj.full_name} ({obj.team.name})"

class GoalForm(MatchEventForm):
    class Meta:
        model = Goal
        fields = ['minute', 'player', 'goal_type', 'assist_player', 'is_extra_time']
        widgets = {
            'minute': forms.NumberInput(attrs={'class': 'cinematic-input', 'placeholder': 'Ex: 45'}),
            'player': forms.Select(attrs={'class': 'cinematic-input'}),
            'goal_type': forms.Select(attrs={'class': 'cinematic-input'}),
            'assist_player': forms.Select(attrs={'class': 'cinematic-input'}),
            'is_extra_time': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'assist_player' in self.fields:
            self.fields['assist_player'].queryset = self.fields['player'].queryset
            self.fields['assist_player'].label_from_instance = lambda obj: f"{obj.full_name} ({obj.team.name})"
            self.fields['assist_player'].required = False

class CardForm(MatchEventForm):
    class Meta:
        model = Card
        fields = ['minute', 'player', 'card_type', 'suspension_matches', 'reason']
        widgets = {
            'minute': forms.NumberInput(attrs={'class': 'cinematic-input', 'placeholder': 'Ex: 75'}),
            'player': forms.Select(attrs={'class': 'cinematic-input'}),
            'card_type': forms.Select(attrs={'class': 'cinematic-input'}),
            'suspension_matches': forms.NumberInput(attrs={'class': 'cinematic-input', 'placeholder': 'عدد مباريات الإيقاف (افتراضي: 1)', 'min': '1', 'value': '1'}),
            'reason': forms.TextInput(attrs={'class': 'cinematic-input', 'placeholder': 'Faute, anti-jeu...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'suspension_matches' in self.fields:
            self.fields['suspension_matches'].required = False
            self.fields['suspension_matches'].initial = 1

    def clean_suspension_matches(self):
        val = self.cleaned_data.get('suspension_matches')
        if not val:
            return 1
        return val

from .models import MatchMedia

class MatchMediaForm(forms.ModelForm):
    class Meta:
        model = MatchMedia
        fields = ['media_type', 'title', 'file', 'url']
        widgets = {
            'media_type': forms.Select(attrs={'class': 'cinematic-input'}),
            'title': forms.TextInput(attrs={'class': 'cinematic-input', 'placeholder': 'Titre ou description (optionnel)'}),
            'file': forms.ClearableFileInput(attrs={'class': 'cinematic-input'}),
            'url': forms.URLInput(attrs={'class': 'cinematic-input', 'placeholder': 'Lien YouTube (optionnel)'}),
        }

