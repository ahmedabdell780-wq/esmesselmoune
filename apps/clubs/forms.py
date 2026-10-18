from django import forms
from .models import ClubPlayer

class AcademyRegistrationForm(forms.ModelForm):
    class Meta:
        model = ClubPlayer
        fields = [
            'first_name', 'last_name', 'first_name_fr', 'last_name_fr', 'date_of_birth', 'place_of_birth', 'photo',
            'school_level', 'category', 'position', 'preferred_foot', 'jersey_number', 'previous_club',
            'parent_relation', 'parent_name', 'parent_phone', 'emergency_phone', 'parent_email', 'parent_profession',
            'address', 'height', 'weight', 'blood_type', 'medical_history', 'medical_certificate', 'id_card'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'required': 'required'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'required': 'required'}),
            'first_name_fr': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: Yakoub (اختياري)'}),
            'last_name_fr': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: MOUKHTARI (اختياري)'}),
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
            'id_card': forms.FileInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'first_name_fr' in self.fields:
            self.fields['first_name_fr'].required = False
            self.fields['first_name_fr'].label = "الاسم بالفرنسية (Prénom en français - اختياري)"
        if 'last_name_fr' in self.fields:
            self.fields['last_name_fr'].required = False
            self.fields['last_name_fr'].label = "اللقب بالفرنسية (Nom en français - اختياري)"
        # Category can be auto-assigned if omitted by user
        if 'category' in self.fields:
            self.fields['category'].required = False
            self.fields['category'].help_text = "يتم تحديد الفئة تلقائياً حسب تاريخ الميلاد إذا تركت فارغة."
        if 'jersey_number' in self.fields:
            self.fields['jersey_number'].help_text = "اختياري للفئات U9 و U11 و U13 (يتم تعيين رقم تلقائي ≤ 100 في حال تركه فارغاً)."

    def clean(self):
        cleaned_data = super().clean()
        from .normalization import get_category_for_dob, find_duplicate_player
        
        first_name = (cleaned_data.get('first_name') or '').strip()
        last_name = (cleaned_data.get('last_name') or '').strip()
        date_of_birth = cleaned_data.get('date_of_birth')
        category = cleaned_data.get('category')
        jersey_number = cleaned_data.get('jersey_number')

        # 1. Automatic category determination by date of birth if not selected
        if not category and date_of_birth:
            category = get_category_for_dob(date_of_birth)
            cleaned_data['category'] = category
            self.instance.category = category

        # 2. Auto-assign jersey number for U9, U11, U13 if left empty (<= 100)
        cat_name = (category.name if category else '').upper().strip()
        if cat_name in ['U9', 'U11', 'U13']:
            if jersey_number is None or jersey_number == '':
                from .normalization import get_next_available_jersey_number
                auto_num = get_next_available_jersey_number(category, exclude_player_id=self.instance.pk, max_num=100)
                if auto_num:
                    cleaned_data['jersey_number'] = auto_num
                    self.instance.jersey_number = auto_num
                    jersey_number = auto_num
            elif jersey_number > 100:
                self.add_error('jersey_number', "رقم القميص للفئات U9 و U11 و U13 لا يجب أن يتجاوز 100.")

        # 3. Jersey number uniqueness within category
        if category and jersey_number is not None:
            qs = ClubPlayer.objects.filter(category=category, jersey_number=jersey_number, is_active=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                self.add_error('jersey_number', f"رقم القميص #{jersey_number} مستعمل بالفعل في فئة {category.name} للاعب ({existing.first_name} {existing.last_name})!")

        # 3. Resilient Duplicate Player Check (tolerant to spaces, hamza, taa marbuta, etc.)
        if first_name and last_name and date_of_birth:
            duplicate = find_duplicate_player(first_name, last_name, date_of_birth, exclude_id=self.instance.pk)
            if duplicate:
                cat_str = duplicate.category.name if duplicate.category else 'بدون فئة'
                err_msg = (
                    f"⚠️ تنبيه لمنع التكرار: يوجد لاعب مسجل بالفعل بهذا الاسم وتاريخ الميلاد: "
                    f"({duplicate.first_name} {duplicate.last_name} - فئة {cat_str} - تاريخ الازدياد: {duplicate.date_of_birth})! "
                    f"تم كشف التطابق لتفادي التكرار والخلط (رغم اختلاف الهمزة، الفراغات، أو التشكيل)."
                )
                self.add_error('first_name', err_msg)
                self.add_error('date_of_birth', "تاريخ الميلاد مطابق للاعب مسجل مسبقاً بنفس الاسم.")

        return cleaned_data
