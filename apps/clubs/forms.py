from django import forms
from .models import ClubPlayer

class AcademyRegistrationForm(forms.ModelForm):
    class Meta:
        model = ClubPlayer
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'place_of_birth', 'photo',
            'school_level', 'category', 'position', 'preferred_foot', 'jersey_number', 'previous_club',
            'parent_relation', 'parent_name', 'parent_phone', 'emergency_phone', 'parent_email', 'parent_profession',
            'address', 'height', 'weight', 'blood_type', 'medical_history', 'medical_certificate'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'required': 'required'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'required': 'required'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-input'}),
            'school_level': forms.TextInput(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-input', 'required': 'required'}),
            'position': forms.Select(attrs={'class': 'form-input'}),
            'preferred_foot': forms.Select(attrs={'class': 'form-input'}),
            'jersey_number': forms.NumberInput(attrs={'class': 'form-input'}),
            'previous_club': forms.TextInput(attrs={'class': 'form-input'}),
            
            'parent_relation': forms.Select(attrs={'class': 'form-input'}),
            'parent_name': forms.TextInput(attrs={'class': 'form-input', 'required': 'required'}),
            'parent_phone': forms.TextInput(attrs={'class': 'form-input', 'required': 'required'}),
            'emergency_phone': forms.TextInput(attrs={'class': 'form-input'}),
            'parent_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'parent_profession': forms.TextInput(attrs={'class': 'form-input'}),
            'address': forms.TextInput(attrs={'class': 'form-input'}),
            
            'height': forms.NumberInput(attrs={'class': 'form-input'}),
            'weight': forms.NumberInput(attrs={'class': 'form-input'}),
            'blood_type': forms.Select(attrs={'class': 'form-input'}),
            'medical_history': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'photo': forms.FileInput(attrs={'class': 'form-input'}),
            'medical_certificate': forms.FileInput(attrs={'class': 'form-input'}),
        }
