from .mixins import ClubWriteAccessMixin, ClubReadAccessMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from .models import Category, ClubPlayer, TrainingSession, ClubMatch

class ClubDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'clubs/dashboard.html'

    def get_context_data(self, **kwargs):
        from .models import ClubSettings
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        context['categories'] = Category.objects.all()
        context['total_players'] = ClubPlayer.objects.filter(is_active=True).count()
        context['upcoming_trainings'] = TrainingSession.objects.order_by('date', 'start_time')[:5]
        context['recent_matches'] = ClubMatch.objects.order_by('-date')[:5]
        return context

class StandingsGeneratorView(LoginRequiredMixin, TemplateView):
    template_name = 'clubs/standings_generator.html'

    def get_context_data(self, **kwargs):
        from .models import ClubSettings, Category
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        context['categories'] = Category.objects.all()
        return context

def sort_players_by_position(players):
    def get_pos_order(player):
        pos = (player.position or '').strip().lower()
        if 'حارس' in pos or 'gk' in pos or 'gardien' in pos:
            return 1
        elif 'مدافع' in pos or 'df' in pos or 'défenseur' in pos or 'دفاع' in pos:
            return 2
        elif 'وسط' in pos or 'mf' in pos or 'milieu' in pos:
            return 3
        elif 'مهاجم' in pos or 'fw' in pos or 'st' in pos or 'attaquant' in pos or 'هجوم' in pos:
            return 4
        return 5

    players_list = list(players)
    players_list.sort(key=lambda p: (
        p.category.min_age if p.category and p.category.min_age is not None else 99,
        get_pos_order(p),
        p.jersey_number if p.jersey_number is not None else 999,
        p.last_name,
        p.first_name
    ))
    return players_list

class PlayerListView(LoginRequiredMixin, ListView):
    model = ClubPlayer
    template_name = 'clubs/player_list.html'
    context_object_name = 'players'
    
    def get_queryset(self):
        from .normalization import smart_player_search
        qs = super().get_queryset().filter(is_active=True).select_related('category', 'passport').prefetch_related('subscriptions')
        category_id = self.request.GET.get('category')
        position_filter = self.request.GET.get('position')
        q = (self.request.GET.get('q') or '').strip()
        
        if category_id:
            qs = qs.filter(category_id=category_id)
            
        if position_filter:
            qs = qs.filter(position=position_filter)
            
        if q:
            players_list = smart_player_search(qs, q)
        else:
            players_list = sort_players_by_position(qs)
            
        season_months = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
        
        def get_month_index(m):
            if m in (7, 8):
                return 0
            return m - 9 if m >= 9 else m + 3
            
        for player in players_list:
            paid_months = {sub.month.month: sub.is_paid for sub in player.subscriptions.all()}
            player.payment_tracking = []
            
            joined_month = player.joined_date.month if player.joined_date else 9
            joined_idx = get_month_index(joined_month) if player.joined_date and player.joined_date.year >= 2026 else 0
                
            for m in season_months:
                idx = get_month_index(m)
                if idx < joined_idx:
                    status = 'not_joined'
                else:
                    status = 'paid' if paid_months.get(m, False) else 'unpaid'
                
                player.payment_tracking.append({
                    'month': m,
                    'status': status
                })
                
        return players_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['positions'] = ClubPlayer.POSITION_CHOICES
        context['search_query'] = (self.request.GET.get('q') or '').strip()
        return context

class PlayerDetailView(LoginRequiredMixin, DetailView):
    model = ClubPlayer
    template_name = 'clubs/player_detail.html'
    context_object_name = 'player'

class PlayerCardsPrintView(LoginRequiredMixin, ListView):
    model = ClubPlayer
    template_name = 'clubs/player_cards_print.html'
    context_object_name = 'players'
    
    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        category_param = self.request.GET.get('category')
        position_filter = self.request.GET.get('position')
        ids = self.request.GET.get('ids')
        if ids:
            id_list = [int(i.strip()) for i in ids.split(',') if i.strip().isdigit()]
            if id_list:
                qs = qs.filter(id__in=id_list)
        elif self.request.GET.getlist('player_ids'):
            qs = qs.filter(id__in=self.request.GET.getlist('player_ids'))

        if category_param and category_param not in ['all', 'ALL', 'الكل']:
            if category_param.isdigit():
                qs = qs.filter(category_id=category_param)
            else:
                qs = qs.filter(category__name__iexact=category_param)
        if position_filter:
            qs = qs.filter(position=position_filter)
        return sort_players_by_position(qs)

    def get_context_data(self, **kwargs):
        from .models import ClubSettings
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        
        category_param = self.request.GET.get('category')
        category_obj = None
        if category_param and category_param not in ['all', 'ALL', 'الكل']:
            if category_param.isdigit():
                category_obj = Category.objects.filter(id=category_param).first()
            else:
                category_obj = Category.objects.filter(name__iexact=category_param).first()
        context['current_category'] = category_obj
        
        # All available players in this category (or club) to populate the selection modal
        all_available_qs = ClubPlayer.objects.filter(is_active=True)
        if category_obj:
            all_available_qs = all_available_qs.filter(category=category_obj)
        context['all_category_players'] = sort_players_by_position(all_available_qs)
        
        # Chunk players into pages of 8 cards per A4 page
        players_list = list(context['players'])
        player_pages = [players_list[i:i + 8] for i in range(0, len(players_list), 8)]
        context['player_pages'] = player_pages
        context['total_selected_count'] = len(players_list)
        context['selected_ids_list'] = [p.id for p in players_list]
        context['selected_ids_csv'] = ','.join(str(p.id) for p in players_list)
        return context

class PlayerListPrintView(LoginRequiredMixin, ListView):
    model = ClubPlayer
    template_name = 'clubs/player_list_print.html'
    context_object_name = 'players'
    
    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset().filter(is_active=True)
        category_param = self.request.GET.get('category')
        position_filter = self.request.GET.get('position')
        if category_param and category_param not in ['all', 'ALL', 'الكل']:
            if category_param.isdigit():
                qs = qs.filter(category_id=category_param)
            else:
                qs = qs.filter(category__name__iexact=category_param)
        if position_filter:
            qs = qs.filter(position=position_filter)
            
        # Optional filter: exclude players missing date_of_birth OR place_of_birth
        require_birth = self.request.GET.get('require_birth') == '1'
        if require_birth:
            qs = qs.exclude(
                Q(date_of_birth__isnull=True) |
                Q(place_of_birth__isnull=True) |
                Q(place_of_birth__exact='') |
                Q(place_of_birth__regex=r'^\s*$')
            )
            
        return sort_players_by_position(qs)

    def get_context_data(self, **kwargs):
        from django.db.models import Q
        from .models import ClubSettings, Category, StaffMember
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        
        # Order categories logically (U9, U11, U13, U15, U17, U20, etc.)
        categories = list(Category.objects.all())
        cat_order = {'U9': 1, 'U11': 2, 'U13': 3, 'U15': 4, 'U17': 5, 'U20': 6, 'SENIOR': 7}
        categories.sort(key=lambda c: cat_order.get(c.name.upper().strip(), 99))
        context['categories'] = categories
        
        is_blank = self.request.GET.get('blank') == '1'
        context['is_blank'] = is_blank
        
        require_birth = self.request.GET.get('require_birth') == '1'
        context['require_birth'] = require_birth
        
        category_param = self.request.GET.get('category')
        context['selected_filter'] = category_param or 'all'
        
        # Calculate count of incomplete players for UI badge
        base_qs = ClubPlayer.objects.filter(is_active=True)
        if category_param and category_param not in ['all', 'ALL', 'الكل']:
            if category_param.isdigit():
                base_qs = base_qs.filter(category_id=category_param)
            else:
                base_qs = base_qs.filter(category__name__iexact=category_param)
        if self.request.GET.get('position'):
            base_qs = base_qs.filter(position=self.request.GET.get('position'))
        context['incomplete_birth_count'] = base_qs.filter(
            Q(date_of_birth__isnull=True) |
            Q(place_of_birth__isnull=True) |
            Q(place_of_birth__exact='') |
            Q(place_of_birth__regex=r'^\s*$')
        ).count()
        
        coach = None
        if category_param and category_param not in ['all', 'ALL', 'الكل']:
            category = None
            if category_param.isdigit():
                category = Category.objects.filter(id=category_param).first()
            else:
                category = Category.objects.filter(name__iexact=category_param).first()
            if category:
                context['selected_category'] = category
                coach = StaffMember.objects.filter(category_assigned=category, role='COACH').first()
                if not coach:
                    coach = StaffMember.objects.filter(category_assigned=category).first()
        context['coach'] = coach
        if coach:
            context['coach_name'] = f"{coach.first_name} {coach.last_name}".strip()
        else:
            context['coach_name'] = ""
                
        # Configurable Page Size (defaults to 30 players per page to eliminate empty space)
        page_size_param = self.request.GET.get('page_size')
        if page_size_param and page_size_param.isdigit():
            PAGE_SIZE = max(15, min(45, int(page_size_param)))
        else:
            PAGE_SIZE = 30
        context['page_size'] = PAGE_SIZE
        
        fill_param = self.request.GET.get('fill')
        fill_empty = fill_param == '1'
        context['fill_empty'] = fill_empty
        
        players_list = list(context['players'])
        total_players = len(players_list)
        context['total_players_count'] = total_players
        
        if is_blank or total_players == 0:
            context['player_pages'] = [
                {
                    'page_num': 1,
                    'total_pages': 1,
                    'is_last_page': True,
                    'items': [{'counter': i, 'player': None, 'is_empty_row': True} for i in range(1, PAGE_SIZE + 1)]
                }
            ]
        else:
            total_pages = (total_players + PAGE_SIZE - 1) // PAGE_SIZE
            pages = []
            for p_idx in range(total_pages):
                start = p_idx * PAGE_SIZE
                end = start + PAGE_SIZE
                chunk = players_list[start:end]
                is_last = (p_idx + 1 == total_pages)
                
                page_items = []
                for i, player in enumerate(chunk):
                    counter = start + i + 1
                    page_items.append({
                        'counter': counter,
                        'player': player,
                        'is_empty_row': False
                    })
                
                # On intermediate pages, ensure full PAGE_SIZE rows; on last page only if fill_empty is True
                if (not is_last or fill_empty) and len(chunk) < PAGE_SIZE:
                    for i in range(len(chunk), PAGE_SIZE):
                        counter = start + i + 1
                        page_items.append({
                            'counter': counter,
                            'player': None,
                            'is_empty_row': True
                        })
                
                pages.append({
                    'page_num': p_idx + 1,
                    'total_pages': total_pages,
                    'is_last_page': is_last,
                    'items': page_items,
                })
            context['player_pages'] = pages
                
        return context

class PlayerSimpleListPrintView(LoginRequiredMixin, ListView):
    """
    طباعة قائمة بسيطة للاعبين أو الطاقم الفني والإداري (Liste Simple):
    تحتوي فقط على: العنوان، شعار النادي، وجدول المعلومات البسيطة (الرقم، اللقب والاسم، الصفة، تاريخ ومكان الازدياد، والملاحظة).
    بدون أي إمضاءات، وبدون أدوات معقدة.
    """
    model = ClubPlayer
    template_name = 'clubs/player_simple_list_print.html'
    context_object_name = 'players'
    
    def get_queryset(self):
        category_param = self.request.GET.get('category')
        if category_param in ['staff', 'STAFF', 'طاقم', 'الطاقم'] or self.request.GET.get('staff') == '1':
            return ClubPlayer.objects.none()
        qs = super().get_queryset().filter(is_active=True).select_related('category')
        if category_param and category_param not in ['all', 'ALL', 'الكل']:
            if category_param.isdigit():
                qs = qs.filter(category_id=category_param)
            else:
                qs = qs.filter(category__name__iexact=category_param)
        return qs.order_by('last_name', 'first_name')

    def get_context_data(self, **kwargs):
        from .models import ClubSettings, Category, StaffMember
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        
        # Categories list
        categories = list(Category.objects.all())
        cat_order = {'U9': 1, 'U11': 2, 'U13': 3, 'U15': 4, 'U17': 5, 'U20': 6, 'SENIOR': 7}
        categories.sort(key=lambda c: cat_order.get(c.name.upper().strip(), 99))
        context['categories'] = categories
        
        total_staff_all = StaffMember.objects.filter(is_active=True).count()
        context['total_staff_count'] = total_staff_all
        
        category_param = self.request.GET.get('category')
        is_staff = category_param in ['staff', 'STAFF', 'طاقم', 'الطاقم'] or self.request.GET.get('staff') == '1'
        context['is_staff'] = is_staff
        context['selected_filter'] = category_param or ('staff' if is_staff else 'all')
        
        PAGE_SIZE = 30
        
        if is_staff:
            staff_qs = StaffMember.objects.filter(is_active=True).select_related('category_assigned').order_by('role', 'last_name', 'first_name')
            role_param = self.request.GET.get('role')
            if role_param:
                staff_qs = staff_qs.filter(role=role_param)
            staff_list = list(staff_qs)
            total_count = len(staff_list)
            context['total_items_count'] = total_count
            context['total_players_count'] = total_count
            context['doc_title'] = "قائمة الطاقم الفني والإداري"
            context['doc_badge'] = "الطاقم الفني والإداري"
            
            if total_count == 0:
                context['pages'] = [
                    {
                        'page_num': 1,
                        'total_pages': 1,
                        'items': [{'counter': i, 'member': None, 'is_empty_row': True} for i in range(1, PAGE_SIZE + 1)]
                    }
                ]
            else:
                total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
                pages = []
                for p_idx in range(total_pages):
                    start = p_idx * PAGE_SIZE
                    end = start + PAGE_SIZE
                    chunk = staff_list[start:end]
                    page_items = []
                    for i, member in enumerate(chunk):
                        page_items.append({
                            'counter': start + i + 1,
                            'member': member,
                            'is_empty_row': False
                        })
                    pages.append({
                        'page_num': p_idx + 1,
                        'total_pages': total_pages,
                        'items': page_items,
                    })
                context['pages'] = pages
        else:
            selected_category = None
            if category_param and category_param not in ['all', 'ALL', 'الكل']:
                if category_param.isdigit():
                    selected_category = Category.objects.filter(id=category_param).first()
                else:
                    selected_category = Category.objects.filter(name__iexact=category_param).first()
            context['selected_category'] = selected_category
            
            players_list = list(context['players'])
            total_players = len(players_list)
            context['total_players_count'] = total_players
            context['total_items_count'] = total_players
            cat_label = f"فئة {selected_category.name}" if selected_category else "كافة الفئات"
            context['doc_title'] = f"قائمة اللاعبين - {cat_label}"
            context['doc_badge'] = cat_label
            
            if total_players == 0:
                context['pages'] = [
                    {
                        'page_num': 1,
                        'total_pages': 1,
                        'items': [{'counter': i, 'player': None, 'is_empty_row': True} for i in range(1, PAGE_SIZE + 1)]
                    }
                ]
            else:
                total_pages = (total_players + PAGE_SIZE - 1) // PAGE_SIZE
                pages = []
                for p_idx in range(total_pages):
                    start = p_idx * PAGE_SIZE
                    end = start + PAGE_SIZE
                    chunk = players_list[start:end]
                    page_items = []
                    for i, player in enumerate(chunk):
                        page_items.append({
                            'counter': start + i + 1,
                            'player': player,
                            'is_empty_row': False
                        })
                    pages.append({
                        'page_num': p_idx + 1,
                        'total_pages': total_pages,
                        'items': page_items,
                    })
                context['pages'] = pages
                
        # backward compatibility
        context['player_pages'] = context['pages']
        return context

# --- Create Views ---

from django import forms

class DateInputMixin:
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        date_fields = ['date_of_birth', 'date', 'month', 'paid_date', 'date_of_injury', 'expected_return']
        time_fields = ['start_time', 'end_time', 'time']
        for field in date_fields:
            if field in form.fields:
                form.fields[field].widget = forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'})
        for field in time_fields:
            if field in form.fields:
                form.fields[field].widget = forms.TimeInput(format='%H:%M', attrs={'type': 'time'})
        return form

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    fields = ['name', 'min_age', 'max_age', 'coach_name', 'coach_phone', 'description']
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:dashboard')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nouvelle Catégorie (إضافة فئة عمرية)"
        context['icon'] = "fas fa-layer-group"
        return context
    
    def form_valid(self, form):
        messages.success(self.request, "Catégorie ajoutée avec succès / تم إضافة الفئة بنجاح!")
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    fields = ['name', 'min_age', 'max_age', 'coach_name', 'coach_phone', 'description']
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Modifier Catégorie (تعديل الفئة العمرية)"
        context['icon'] = "fas fa-edit"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Catégorie mise à jour / تم تحديث بيانات الفئة بنجاح!")
        return super().form_valid(form)

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = 'clubs/confirm_delete.html'
    success_url = reverse_lazy('clubs:dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Supprimer la Catégorie (حذف الفئة العمرية)"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Catégorie supprimée avec succès / تم حذف الفئة بنجاح!")
        return super().form_valid(form)

class ClubPlayerForm(forms.ModelForm):
    class Meta:
        model = ClubPlayer
        fields = [
            'category', 'first_name', 'last_name', 'first_name_fr', 'last_name_fr',
            'date_of_birth', 'place_of_birth', 'photo', 'id_card', 'blood_type',
            'medical_certificate', 'parent_name', 'parent_phone', 'player_phone',
            'address', 'position', 'jersey_number'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'first_name_fr': forms.TextInput(attrs={'placeholder': 'Ex: Yakoub (اختياري)'}),
            'last_name_fr': forms.TextInput(attrs={'placeholder': 'Ex: MOUKHTARI (اختياري)'}),
            'blood_type': forms.Select(choices=[
                ('', '-- اختر فصيلة الدم / Groupe sanguin --'),
                ('A+', 'A+'),
                ('A-', 'A-'),
                ('B+', 'B+'),
                ('B-', 'B-'),
                ('AB+', 'AB+'),
                ('AB-', 'AB-'),
                ('O+', 'O+'),
                ('O-', 'O-'),
            ]),
            'position': forms.Select(choices=[
                ('', '-- اختر المركز / Poste --'),
                ('حارس مرمى', 'حارس مرمى (Gardien de but)'),
                ('مدافع', 'مدافع (Défenseur)'),
                ('وسط ميدان', 'وسط ميدان (Milieu de terrain)'),
                ('مهاجم', 'مهاجم (Attaquant)'),
            ]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'first_name_fr' in self.fields:
            self.fields['first_name_fr'].required = False
            self.fields['first_name_fr'].label = "الاسم بالفرنسية (Prénom en français - اختياري)"
        if 'last_name_fr' in self.fields:
            self.fields['last_name_fr'].required = False
            self.fields['last_name_fr'].label = "اللقب بالفرنسية (Nom en français - اختياري)"
        if 'category' in self.fields:
            self.fields['category'].required = False
            self.fields['category'].help_text = "يتم تحديد الفئة تلقائياً حسب تاريخ الميلاد إذا تركت فارغة."
        if 'jersey_number' in self.fields:
            self.fields['jersey_number'].help_text = "اختياري للفئات U9 و U11 و U13 (يتم تعيين رقم تلقائي ≤ 100 في حال تركه فارغاً)."

    def clean(self):
        cleaned_data = super().clean()
        from .normalization import get_category_for_dob, find_duplicate_player
        
        category = cleaned_data.get('category')
        jersey_number = cleaned_data.get('jersey_number')
        first_name = (cleaned_data.get('first_name') or '').strip()
        last_name = (cleaned_data.get('last_name') or '').strip()
        date_of_birth = cleaned_data.get('date_of_birth')

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

class CheckDuplicatePlayerView(View):
    """API endpoint to check for duplicate players and suggest category in real time"""
    def get(self, request, *args, **kwargs):
        from django.http import JsonResponse
        from datetime import datetime
        from .normalization import get_category_for_dob, find_duplicate_player

        fn = request.GET.get('first_name', '').strip()
        ln = request.GET.get('last_name', '').strip()
        dob_str = request.GET.get('date_of_birth', '').strip()
        exclude_id = request.GET.get('exclude_id', '').strip()
        exclude_pk = int(exclude_id) if exclude_id.isdigit() else None

        dob = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
            except ValueError:
                dob = None

        suggested_category = None
        if dob:
            cat = get_category_for_dob(dob)
            if cat:
                suggested_category = {
                    'id': cat.id,
                    'name': cat.name,
                }

        duplicate_data = None
        if fn and ln and dob:
            dup = find_duplicate_player(fn, ln, dob, exclude_id=exclude_pk)
            if dup:
                duplicate_data = {
                    'id': dup.id,
                    'name': f"{dup.first_name} {dup.last_name}",
                    'category': dup.category.name if dup.category else 'بدون فئة',
                    'date_of_birth': str(dup.date_of_birth),
                }

        return JsonResponse({
            'is_duplicate': duplicate_data is not None,
            'duplicate': duplicate_data,
            'suggested_category': suggested_category,
        })

class ClubPlayerCreateView(LoginRequiredMixin, DateInputMixin, CreateView):
    model = ClubPlayer
    form_class = ClubPlayerForm
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:player_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nouveau Joueur (تسجيل لاعب جديد)"
        context['icon'] = "fas fa-user-plus"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Joueur ajouté avec succès / تم تسجيل اللاعب بنجاح!")
        if '_add_another' in self.request.POST:
            self.object = form.save()
            return redirect(self.request.path)
        return super().form_valid(form)

from django.views.generic import UpdateView, DeleteView

class ClubPlayerUpdateView(LoginRequiredMixin, DateInputMixin, UpdateView):
    model = ClubPlayer
    form_class = ClubPlayerForm
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:player_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Modifier Joueur (تعديل بيانات اللاعب)"
        context['icon'] = "fas fa-user-edit"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Données mises à jour / تم تحديث بيانات اللاعب بنجاح!")
        return super().form_valid(form)

class ClubPlayerDeleteView(LoginRequiredMixin, DeleteView):
    model = ClubPlayer
    template_name = 'clubs/confirm_delete.html'
    success_url = reverse_lazy('clubs:player_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Supprimer Joueur (حذف اللاعب)"
        context['message'] = f"Êtes-vous sûr de vouloir supprimer le joueur {self.object.first_name} {self.object.last_name} ? هل أنت متأكد من حذف اللاعب؟"
        return context

class TrainingSessionCreateView(LoginRequiredMixin, DateInputMixin, CreateView):
    model = TrainingSession
    fields = ['category', 'date', 'start_time', 'end_time', 'location', 'notes']
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nouvelle Séance (برمجة حصة تدريبية)"
        context['icon'] = "fas fa-running"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Séance programmée / تم برمجة الحصة بنجاح!")
        return super().form_valid(form)

class ClubMatchCreateView(LoginRequiredMixin, DateInputMixin, CreateView):
    model = ClubMatch
    fields = ['category', 'date', 'time', 'opponent', 'location', 'is_home', 'our_score', 'their_score', 'notes']
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nouveau Match (إضافة مباراة)"
        context['icon'] = "fas fa-futbol"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Match enregistré / تم تسجيل المباراة بنجاح!")
        return super().form_valid(form)

from django.views.generic import UpdateView
class ClubSettingsUpdateView(LoginRequiredMixin, UpdateView):
    from .models import ClubSettings
    model = ClubSettings
    fields = ['academy_registration_open', 'club_name', 'club_subtitle', 'club_abbreviation', 'president_name', 'logo', 'cover_image', 'gradient_start', 'gradient_end']
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:dashboard')

    def get_object(self):
        from .models import ClubSettings
        return ClubSettings.get_settings()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Paramètres de l'Académie (إعدادات الأكاديمية)"
        context['icon'] = "fas fa-cog"
        return context

from .models import StaffMember, Subscription, MedicalRecord, PlayerEvaluation, PlayerEquipment, TrainingAttendance

class StaffMemberForm(forms.ModelForm):
    class Meta:
        model = StaffMember
        fields = ['first_name', 'last_name', 'role', 'function_title', 'category_assigned', 'date_of_birth', 'place_of_birth', 'id_card', 'phone', 'notes', 'photo']
        widgets = {
            'date_of_birth': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

class StaffListView(LoginRequiredMixin, ListView):
    model = StaffMember
    template_name = 'clubs/staff_list.html'
    context_object_name = 'staff_members'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('category_assigned')

    def get_context_data(self, **kwargs):
        from .models import Category
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

class StaffCreateView(LoginRequiredMixin, DateInputMixin, CreateView):
    model = StaffMember
    form_class = StaffMemberForm
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:staff_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nouveau Membre du Staff (إضافة عضو للطاقم)"
        context['icon'] = "fas fa-user-tie"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Membre du staff ajouté / تم إضافة العضو بنجاح!")
        return super().form_valid(form)

class StaffUpdateView(LoginRequiredMixin, DateInputMixin, UpdateView):
    model = StaffMember
    form_class = StaffMemberForm
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:staff_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Modifier Membre du Staff (تعديل بيانات العضو)"
        context['icon'] = "fas fa-user-edit"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Données mises à jour / تم تحديث بيانات العضو بنجاح!")
        return super().form_valid(form)

class StaffDeleteView(LoginRequiredMixin, DeleteView):
    model = StaffMember
    template_name = 'clubs/confirm_delete.html'
    success_url = reverse_lazy('clubs:staff_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Supprimer Membre du Staff (حذف عضو الطاقم)"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Membre supprimé / تم حذف العضو بنجاح!")
        return super().form_valid(form)

class StaffListPrintView(LoginRequiredMixin, ListView):
    model = StaffMember
    template_name = 'clubs/staff_list_print.html'
    context_object_name = 'staff_members'

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('category_assigned')
        category_param = self.request.GET.get('category', 'admin')
        
        if category_param in ['admin', 'ADMIN', 'إداري', 'اداري']:
            from django.db.models import Q
            qs = qs.filter(Q(role='ADMIN') | Q(category_assigned__isnull=True))
        elif category_param in ['all', 'ALL', 'الكل']:
            pass
        elif category_param:
            if category_param.isdigit():
                qs = qs.filter(category_assigned_id=category_param)
            else:
                qs = qs.filter(category_assigned__name__iexact=category_param)
        return qs.order_by('role', 'last_name', 'first_name')

    def get_context_data(self, **kwargs):
        from .models import ClubSettings, Category
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        context['categories'] = Category.objects.all()

        category_param = self.request.GET.get('category', 'admin')
        context['selected_filter'] = category_param
        
        if category_param in ['admin', 'ADMIN', 'إداري', 'اداري']:
            context['doc_title'] = "قائمة الطاقم الإداري"
            context['badge_label'] = "الإدارة العامة للنادي"
            context['is_admin'] = True
        elif category_param in ['all', 'ALL', 'الكل']:
            context['doc_title'] = "قائمة الطاقم الفني والإداري العام"
            context['badge_label'] = "كافة الفئات والإدارة"
            context['is_admin'] = False
        else:
            cat_obj = Category.objects.filter(name__iexact=category_param).first()
            if not cat_obj and category_param.isdigit():
                cat_obj = Category.objects.filter(id=category_param).first()
            if cat_obj:
                context['selected_category'] = cat_obj
                context['doc_title'] = f"قائمة الطاقم الفني والإداري لفئة {cat_obj.name}"
                context['badge_label'] = f"فئة {cat_obj.name}"
            else:
                context['doc_title'] = f"قائمة طاقم فئة {category_param}"
                context['badge_label'] = f"فئة {category_param}"
            context['is_admin'] = False

        staff_list = list(context['staff_members'])
        total_staff = len(staff_list)
        context['total_staff_count'] = total_staff

        items = []
        for i, member in enumerate(staff_list):
            items.append({
                'counter': i + 1,
                'member': member
            })
        context['items'] = items
        return context

class SubscriptionCreateView(LoginRequiredMixin, DateInputMixin, CreateView):
    model = Subscription
    fields = ['player', 'month', 'amount', 'is_paid', 'paid_date', 'notes']
    template_name = 'clubs/generic_form.html'
    
    def get_success_url(self):
        return reverse_lazy('clubs:player_detail', kwargs={'pk': self.object.player.id})

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if 'player' in form.fields:
            league_categories = ['U15', 'U16', 'U17', 'U19', 'U21', 'Seniors', 'Veterans']
            form.fields['player'].queryset = form.fields['player'].queryset.exclude(category__name__in=league_categories)
        return form

    def get_initial(self):
        initial = super().get_initial()
        player_id = self.request.GET.get('player')
        if player_id:
            initial['player'] = player_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Paiement Mensuel (تسديد اشتراك شهري)"
        context['icon'] = "fas fa-money-bill-wave"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Paiement enregistré / تم تسجيل الدفع بنجاح!")
        return super().form_valid(form)

class SubscriptionUpdateView(LoginRequiredMixin, DateInputMixin, UpdateView):
    model = Subscription
    fields = ['month', 'amount', 'is_paid', 'paid_date', 'notes']
    template_name = 'clubs/generic_form.html'
    
    def get_success_url(self):
        return reverse_lazy('clubs:player_detail', kwargs={'pk': self.object.player.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "تعديل الاشتراك المالي"
        context['icon'] = "fas fa-edit"
        return context

    def form_valid(self, form):
        messages.success(self.request, "تم تعديل الاشتراك بنجاح!")
        return super().form_valid(form)

class SubscriptionDeleteView(LoginRequiredMixin, DeleteView):
    model = Subscription
    template_name = 'clubs/generic_confirm_delete.html'
    
    def get_success_url(self):
        return reverse_lazy('clubs:player_detail', kwargs={'pk': self.object.player.id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "حذف الاشتراك"
        context['message'] = f"هل أنت متأكد من أنك تريد حذف اشتراك شهر {self.object.month.strftime('%Y-%m')}؟"
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, "تم حذف الاشتراك بنجاح!")
        return super().delete(request, *args, **kwargs)

class MedicalRecordCreateView(LoginRequiredMixin, DateInputMixin, CreateView):
    model = MedicalRecord
    fields = ['player', 'injury_type', 'date_of_injury', 'expected_return', 'is_recovered', 'notes']
    template_name = 'clubs/generic_form.html'
    
    def get_success_url(self):
        return reverse_lazy('clubs:player_detail', kwargs={'pk': self.object.player.id})

    def get_initial(self):
        initial = super().get_initial()
        player_id = self.request.GET.get('player')
        if player_id:
            initial['player'] = player_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Dossier Médical (إضافة سجل طبي أو إصابة)"
        context['icon'] = "fas fa-briefcase-medical"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Dossier médical mis à jour / تم تحديث السجل الطبي!")
        return super().form_valid(form)

class PlayerEvaluationCreateView(LoginRequiredMixin, CreateView):
    model = PlayerEvaluation
    fields = ['player', 'evaluator', 'physical_fitness', 'speed', 'passing', 'tactical_awareness', 'discipline', 'coach_remarks']
    template_name = 'clubs/generic_form.html'
    
    def get_success_url(self):
        return reverse_lazy('clubs:player_detail', kwargs={'pk': self.object.player.id})

    def get_initial(self):
        initial = super().get_initial()
        player_id = self.request.GET.get('player')
        if player_id:
            initial['player'] = player_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "تقييم اللاعب الفني والبدني"
        context['icon'] = "fas fa-chart-line"
        return context

    def form_valid(self, form):
        messages.success(self.request, "تم إضافة التقييم بنجاح!")
        return super().form_valid(form)

class PlayerEquipmentUpdateView(LoginRequiredMixin, DateInputMixin, UpdateView):
    model = PlayerEquipment
    fields = ['received_training_kit', 'training_kit_date', 'received_tracksuit', 'tracksuit_date', 'received_bag', 'bag_date', 'notes']
    template_name = 'clubs/generic_form.html'
    
    def get_object(self, queryset=None):
        player_id = self.kwargs.get('player_id')
        obj, created = PlayerEquipment.objects.get_or_create(player_id=player_id)
        return obj

    def get_success_url(self):
        return reverse_lazy('clubs:player_detail', kwargs={'pk': self.object.player.id})

# --- Academy Registration Views ---

from apps.clubs.forms import AcademyRegistrationForm

class AcademyRegistrationView(CreateView):
    model = ClubPlayer
    form_class = AcademyRegistrationForm
    template_name = 'clubs/academy_registration.html'
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.clubs.models import ClubSettings
        ctx['settings'] = ClubSettings.get_settings()
        return ctx

    def form_valid(self, form):
        form.instance.is_active = False 
        response = super().form_valid(form)
        messages.success(self.request, "تم تسجيل اللاعب بنجاح! يمكنك الآن طباعة استمارة التسجيل الرسمية وتقديمها للإدارة.")
        return response

    def get_success_url(self):
        return reverse_lazy('clubs:academy_print_form', kwargs={'pk': self.object.pk})

class AcademyRegistrationPrintView(DetailView):
    model = ClubPlayer
    template_name = 'clubs/academy_registration_print.html'
    context_object_name = 'player'
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.clubs.models import ClubSettings
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


# --- Player Passport (Ligue Wilaya de Football - Tipaza) Views ---

class PlayerPassportView(LoginRequiredMixin, View):
    """عرض، تعديل، وطباعة جواز اللاعب (Passeport du Joueur)"""
    def get(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        
        category = player.category
        siblings = []
        prev_player = None
        next_player = None
        if category:
            siblings = list(ClubPlayer.objects.filter(category=category, is_active=True).order_by('last_name', 'first_name'))
            try:
                curr_idx = siblings.index(player)
                if curr_idx > 0:
                    prev_player = siblings[curr_idx - 1]
                if curr_idx < len(siblings) - 1:
                    next_player = siblings[curr_idx + 1]
            except ValueError:
                pass
                
        all_eligible = ClubPlayer.objects.filter(
            category__name__in=['U15', 'U17', 'U20'],
            is_active=True
        ).select_related('category').order_by('category__name', 'last_name', 'first_name')
        
        from .models import ClubSettings, Category
        context = {
            'player': player,
            'passport': passport,
            'rows': passport.rows_data,
            'siblings': siblings,
            'prev_player': prev_player,
            'next_player': next_player,
            'all_eligible': all_eligible,
            'categories': Category.objects.filter(name__in=['U15', 'U17', 'U20']).order_by('name'),
            'settings': ClubSettings.get_settings(),
            'is_edit_mode': request.GET.get('edit') == '1',
        }
        return render(request, 'clubs/player_passport.html', context)

    def post(self, request, pk):
        import json
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json' or
                   request.GET.get('ajax') == '1')
        
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}
        else:
            data = request.POST

        if 'full_name_fr' in data:
            passport.full_name_fr = data['full_name_fr'].strip()
        if 'license_number' in data:
            passport.license_number = data['license_number'].strip()
        if 'place_of_birth_fr' in data:
            passport.place_of_birth_fr = data['place_of_birth_fr'].strip()
        if 'nationality' in data:
            passport.nationality = data['nationality'].strip()
        if 'club_name' in data:
            passport.club_name = data['club_name'].strip()
        if 'ligue_name' in data:
            passport.ligue_name = data['ligue_name'].strip()
        if 'declaration_text' in data:
            passport.declaration_text = data['declaration_text'].strip()
            
        if 'date_of_birth' in data and data['date_of_birth']:
            try:
                from datetime import datetime
                passport.date_of_birth = datetime.strptime(data['date_of_birth'].strip(), '%Y-%m-%d').date()
            except Exception:
                pass

        if 'rows_data' in data and isinstance(data['rows_data'], list):
            passport.rows_data = data['rows_data']
        else:
            rows = []
            for i in range(12):
                age = data.get(f'row_{i}_age', f'{12 + i} ans')
                season = data.get(f'row_{i}_season', '')
                status = data.get(f'row_{i}_status', 'Amateur')
                loan_permanent = data.get(f'row_{i}_loan_permanent', 'Permanent')
                period = data.get(f'row_{i}_period', '01/07 - 30/06')
                club = data.get(f'row_{i}_club', 'ES Messelmoun')
                league = data.get(f'row_{i}_league', 'Ligue Wilaya de Football - Tipaza')
                rows.append({
                    'age': age,
                    'season': season,
                    'status': status,
                    'loan_permanent': loan_permanent,
                    'period': period,
                    'club': club,
                    'league': league,
                })
            passport.rows_data = rows

        passport.save()
        
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم حفظ بيانات الجواز بنجاح!'})
        
        messages.success(request, 'تم حفظ بيانات الجواز بنجاح!')
        return redirect('clubs:player_passport', pk=player.pk)


class PlayerPassportCategoryListView(LoginRequiredMixin, TemplateView):
    """قائمة وفهرس جوازات اللاعبين حسب الفئة (U15, U17, U20)"""
    template_name = 'clubs/player_passport_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import Category, ClubPlayer, ClubSettings
        
        category_name = self.request.GET.get('category', 'U17').strip()
        if category_name not in ['U15', 'U17', 'U20']:
            category_name = 'U17'
            
        ctx['selected_category'] = category_name
        ctx['categories'] = ['U15', 'U17', 'U20']
        
        # Category counts
        ctx['u15_count'] = ClubPlayer.objects.filter(category__name='U15', is_active=True).count()
        ctx['u17_count'] = ClubPlayer.objects.filter(category__name='U17', is_active=True).count()
        ctx['u20_count'] = ClubPlayer.objects.filter(category__name='U20', is_active=True).count()
        
        players = ClubPlayer.objects.filter(
            category__name=category_name,
            is_active=True
        ).order_by('last_name', 'first_name')
        
        passport_items = []
        for p in players:
            passp = p.get_passport()
            passport_items.append({
                'player': p,
                'passport': passp,
            })
            
        ctx['passport_items'] = passport_items
        ctx['total_count'] = len(passport_items)
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


class PlayerPassportBatchPrintView(LoginRequiredMixin, TemplateView):
    """طباعة جماعية لجميع جوازات لاعبي الفئة المحددة"""
    template_name = 'clubs/player_passport_batch_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import Category, ClubPlayer, ClubSettings
        
        category_name = self.request.GET.get('category', 'U17').strip()
        ctx['selected_category'] = category_name
        
        qs = ClubPlayer.objects.filter(is_active=True)
        if category_name in ['U15', 'U17', 'U20']:
            qs = qs.filter(category__name=category_name)
        else:
            qs = qs.filter(category__name__in=['U15', 'U17', 'U20'])
            
        players = list(qs.order_by('category__name', 'last_name', 'first_name'))
        
        items = []
        for p in players:
            passp = p.get_passport()
            items.append({
                'player': p,
                'passport': passp,
                'rows': passp.rows_data,
            })
            
        ctx['items'] = items
        ctx['total_count'] = len(items)
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


# ─── Official League Forms: Demande de Licence & Certificat Médical ───

def get_safe_forms_data(passport, player=None):
    fd = dict(passport.forms_data or {}) if (passport and passport.forms_data) else {}
    defaults = {
        'father_name': player.parent_name if player and player.parent_name else '',
        'id_card_number': player.id_card if player and player.id_card else '',
        'id_card_date': '',
        'last_license_club': '',
        'last_license_expiry': '',
        'last_license_number': passport.license_number if passport and passport.license_number else '',
        'parent_name': player.parent_name if player and player.parent_name else '',
        'parent_dob_pob': '',
        'parent_id_number': '',
        'parent_id_date': '',
        'parent_id_issuer': '',
        'parent_address': player.address if player and player.address else '',
        'parent_commune': 'مسلمون',
        'parent_wilaya': 'تيبازة',
        'doctor_name': '',
        'doctor_reg_number': '',
        'exam_place': 'مسلمون',
        'exam_date': '',
        'season': '2026/2027',
    }
    for k, v in defaults.items():
        if k not in fd or fd[k] is None:
            fd[k] = v
    if fd.get('exam_place') in ['سيدي غيلاس', 'Sidi Ghiles', '']:
        fd['exam_place'] = 'مسلمون'
    return fd


class PlayerLicenseFormView(LoginRequiredMixin, View):
    """عرض، تعديل، وطباعة طلب رخصة اللاعب مع الرخصة الأبوية"""
    def get(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        is_blank = request.GET.get('blank') == '1'
        
        category = player.category
        category_name = category.name if category else 'U17'
        
        siblings = []
        prev_player = None
        next_player = None
        if category:
            siblings = list(ClubPlayer.objects.filter(category=category, is_active=True).order_by('last_name', 'first_name'))
            try:
                curr_idx = siblings.index(player)
                if curr_idx > 0:
                    prev_player = siblings[curr_idx - 1]
                if curr_idx < len(siblings) - 1:
                    next_player = siblings[curr_idx + 1]
            except ValueError:
                pass
                
        full_name_fr = (passport.full_name_fr or f"{player.last_name} {player.first_name}").strip()
        parts = full_name_fr.split()
        last_name_fr = parts[0] if parts else ''
        first_name_fr = ' '.join(parts[1:]) if len(parts) > 1 else ''
        
        dob_str = player.date_of_birth.strftime('%d/%m/%Y') if player.date_of_birth else ''
        pob_fr = passport.place_of_birth_fr or player.place_of_birth or ''
        
        from .models import ClubSettings
        context = {
            'player': player,
            'passport': passport,
            'is_blank': is_blank,
            'category_name': category_name,
            'season': '2026/2027',
            'club_name': passport.club_name or 'ES Messelmoun',
            'full_name_fr': full_name_fr,
            'last_name_fr': last_name_fr,
            'first_name_fr': first_name_fr,
            'dob': dob_str,
            'pob_fr': pob_fr,
            'forms_data': get_safe_forms_data(passport, player),
            'siblings': siblings,
            'prev_player': prev_player,
            'next_player': next_player,
            'settings': ClubSettings.get_settings(),
            'is_edit_mode': request.GET.get('edit') == '1',
        }
        return render(request, 'clubs/player_license_form.html', context)

    def post(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json' or
                   request.GET.get('ajax') == '1')
        
        data = request.POST
        forms_data = dict(passport.forms_data or {})
        
        fields_to_store = [
            'father_name', 'id_card_number', 'id_card_date',
            'last_license_club', 'last_license_expiry', 'last_license_number',
            'parent_name', 'parent_dob_pob', 'parent_id_number', 'parent_id_date',
            'parent_id_issuer', 'parent_address', 'parent_commune', 'parent_wilaya',
            'season'
        ]
        for f in fields_to_store:
            if f in data:
                forms_data[f] = data[f].strip()
                
        passport.forms_data = forms_data
        
        if 'last_name_fr' in data and 'first_name_fr' in data:
            ln = data['last_name_fr'].strip().upper()
            fn = data['first_name_fr'].strip().upper()
            passport.full_name_fr = f"{ln} {fn}".strip()
        if 'pob_fr' in data and data['pob_fr']:
            passport.place_of_birth_fr = data['pob_fr'].strip().upper()
        if 'last_license_number' in data and data['last_license_number']:
            passport.license_number = data['last_license_number'].strip()
        if 'dob' in data and data['dob']:
            try:
                from datetime import datetime
                passport.date_of_birth = datetime.strptime(data['dob'].strip(), '%d/%m/%Y').date()
                player.date_of_birth = passport.date_of_birth
            except Exception:
                pass
        if 'id_card_number' in data and data['id_card_number']:
            player.id_card = data['id_card_number'].strip()
        if 'parent_name' in data and data['parent_name']:
            player.parent_name = data['parent_name'].strip()
        if 'parent_address' in data and data['parent_address']:
            player.address = data['parent_address'].strip()
            
        player.save()
        passport.save()
        
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم حفظ بيانات طلب الرخصة بنجاح!'})
        messages.success(request, 'تم حفظ بيانات طلب الرخصة بنجاح!')
        return redirect('clubs:player_license_form', pk=player.pk)


class PlayerMedicalCertificateView(LoginRequiredMixin, View):
    """عرض، تعديل، وطباعة شهادة الأهلية الطبية مع تعهد النادي"""
    def get(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        is_blank = request.GET.get('blank') == '1'
        
        category = player.category
        category_name = category.name if category else 'U17'
        
        siblings = []
        prev_player = None
        next_player = None
        if category:
            siblings = list(ClubPlayer.objects.filter(category=category, is_active=True).order_by('last_name', 'first_name'))
            try:
                curr_idx = siblings.index(player)
                if curr_idx > 0:
                    prev_player = siblings[curr_idx - 1]
                if curr_idx < len(siblings) - 1:
                    next_player = siblings[curr_idx + 1]
            except ValueError:
                pass
                
        full_name_fr = (passport.full_name_fr or f"{player.last_name} {player.first_name}").strip()
        dob_str = player.date_of_birth.strftime('%d/%m/%Y') if player.date_of_birth else ''
        pob_fr = passport.place_of_birth_fr or player.place_of_birth or ''
        
        from .models import ClubSettings
        context = {
            'player': player,
            'passport': passport,
            'is_blank': is_blank,
            'category_name': category_name,
            'season': '2026/2027',
            'club_name': passport.club_name or 'ES Messelmoun',
            'full_name_fr': full_name_fr,
            'dob': dob_str,
            'pob_fr': pob_fr,
            'forms_data': get_safe_forms_data(passport, player),
            'siblings': siblings,
            'prev_player': prev_player,
            'next_player': next_player,
            'settings': ClubSettings.get_settings(),
            'is_edit_mode': request.GET.get('edit') == '1',
        }
        return render(request, 'clubs/player_medical_certificate.html', context)

    def post(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json' or
                   request.GET.get('ajax') == '1')
        
        data = request.POST
        forms_data = dict(passport.forms_data or {})
        
        fields_to_store = ['doctor_name', 'doctor_reg_number', 'exam_place', 'exam_date', 'season']
        for f in fields_to_store:
            if f in data:
                forms_data[f] = data[f].strip()
                
        passport.forms_data = forms_data
        
        if 'full_name_fr' in data and data['full_name_fr']:
            passport.full_name_fr = data['full_name_fr'].strip().upper()
        if 'pob_fr' in data and data['pob_fr']:
            passport.place_of_birth_fr = data['pob_fr'].strip().upper()
        if 'dob' in data and data['dob']:
            try:
                from datetime import datetime
                passport.date_of_birth = datetime.strptime(data['dob'].strip(), '%d/%m/%Y').date()
                player.date_of_birth = passport.date_of_birth
                player.save()
            except Exception:
                pass
                
        passport.save()
        
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم حفظ بيانات الشهادة الطبية بنجاح!'})
        messages.success(request, 'تم حفظ بيانات الشهادة الطبية بنجاح!')
        return redirect('clubs:player_medical_certificate', pk=player.pk)


class BlankLicenseFormView(LoginRequiredMixin, TemplateView):
    """عرض وطباعة طلب رخصة فارغ"""
    template_name = 'clubs/player_license_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import ClubSettings
        cat = self.request.GET.get('category', 'U17').strip()
        ctx['is_blank'] = True
        ctx['player'] = None
        ctx['category_name'] = cat
        ctx['season'] = '2026/2027'
        ctx['club_name'] = 'ES Messelmoun'
        ctx['last_name_fr'] = ''
        ctx['first_name_fr'] = ''
        ctx['full_name_fr'] = ''
        ctx['dob'] = ''
        ctx['pob_fr'] = ''
        ctx['forms_data'] = get_safe_forms_data(None, None)
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


class BlankMedicalCertificateView(LoginRequiredMixin, TemplateView):
    """عرض وطباعة شهادة طبية فارغة"""
    template_name = 'clubs/player_medical_certificate.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import ClubSettings
        cat = self.request.GET.get('category', 'U17').strip()
        ctx['is_blank'] = True
        ctx['player'] = None
        ctx['category_name'] = cat
        ctx['season'] = '2026/2027'
        ctx['club_name'] = 'ES Messelmoun'
        ctx['full_name_fr'] = ''
        ctx['dob'] = ''
        ctx['pob_fr'] = ''
        ctx['forms_data'] = get_safe_forms_data(None, None)
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


class PlayerLicenseFormBatchPrintView(LoginRequiredMixin, TemplateView):
    """طباعة جماعية لطلبات رخص فئة محددة"""
    template_name = 'clubs/player_license_form_batch_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import ClubPlayer, ClubSettings
        
        cat = self.request.GET.get('category', 'U17').strip()
        is_blank = self.request.GET.get('blank') == '1'
        
        ctx['category_name'] = cat
        ctx['is_blank'] = is_blank
        ctx['season'] = '2026/2027'
        ctx['club_name'] = 'ES Messelmoun'
        
        if is_blank:
            try:
                count = int(self.request.GET.get('count', 1))
            except ValueError:
                count = 1
            items = []
            for _ in range(count):
                items.append({
                    'player': None,
                    'is_blank': True,
                    'category_name': cat,
                    'season': '2026/2027',
                    'club_name': 'ES Messelmoun',
                    'last_name_fr': '',
                    'first_name_fr': '',
                    'full_name_fr': '',
                    'dob': '',
                    'pob_fr': '',
                    'forms_data': get_safe_forms_data(None, None),
                })
            ctx['items'] = items
            ctx['total_count'] = len(items)
        else:
            qs = ClubPlayer.objects.filter(is_active=True)
            if cat in ['U15', 'U17', 'U20']:
                qs = qs.filter(category__name=cat)
            else:
                qs = qs.filter(category__name__in=['U15', 'U17', 'U20'])
                
            players = list(qs.order_by('category__name', 'last_name', 'first_name'))
            items = []
            for p in players:
                passp = p.get_passport()
                full_name = (passp.full_name_fr or f"{p.last_name} {p.first_name}").strip()
                parts = full_name.split()
                ln = parts[0] if parts else ''
                fn = ' '.join(parts[1:]) if len(parts) > 1 else ''
                dob_str = p.date_of_birth.strftime('%d/%m/%Y') if p.date_of_birth else ''
                items.append({
                    'player': p,
                    'passport': passp,
                    'is_blank': False,
                    'category_name': p.category.name if p.category else cat,
                    'season': '2026/2027',
                    'club_name': passp.club_name or 'ES Messelmoun',
                    'last_name_fr': ln,
                    'first_name_fr': fn,
                    'full_name_fr': full_name,
                    'dob': dob_str,
                    'pob_fr': passp.place_of_birth_fr or p.place_of_birth or '',
                    'forms_data': get_safe_forms_data(passp, p),
                })
            ctx['items'] = items
            ctx['total_count'] = len(items)
            
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


class PlayerMedicalCertificateBatchPrintView(LoginRequiredMixin, TemplateView):
    """طباعة جماعية لشهادات الأهلية الطبية لفئة محددة"""
    template_name = 'clubs/player_medical_certificate_batch_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import ClubPlayer, ClubSettings
        
        cat = self.request.GET.get('category', 'U17').strip()
        is_blank = self.request.GET.get('blank') == '1'
        
        ctx['category_name'] = cat
        ctx['is_blank'] = is_blank
        ctx['season'] = '2026/2027'
        ctx['club_name'] = 'ES Messelmoun'
        
        if is_blank:
            try:
                count = int(self.request.GET.get('count', 1))
            except ValueError:
                count = 1
            items = []
            for _ in range(count):
                items.append({
                    'player': None,
                    'is_blank': True,
                    'category_name': cat,
                    'season': '2026/2027',
                    'club_name': 'ES Messelmoun',
                    'full_name_fr': '',
                    'dob': '',
                    'pob_fr': '',
                    'forms_data': get_safe_forms_data(None, None),
                })
            ctx['items'] = items
            ctx['total_count'] = len(items)
        else:
            qs = ClubPlayer.objects.filter(is_active=True)
            if cat in ['U15', 'U17', 'U20']:
                qs = qs.filter(category__name=cat)
            else:
                qs = qs.filter(category__name__in=['U15', 'U17', 'U20'])
                
            players = list(qs.order_by('category__name', 'last_name', 'first_name'))
            items = []
            for p in players:
                passp = p.get_passport()
                full_name = (passp.full_name_fr or f"{p.last_name} {p.first_name}").strip()
                dob_str = p.date_of_birth.strftime('%d/%m/%Y') if p.date_of_birth else ''
                items.append({
                    'player': p,
                    'passport': passp,
                    'is_blank': False,
                    'category_name': p.category.name if p.category else cat,
                    'season': '2026/2027',
                    'club_name': passp.club_name or 'ES Messelmoun',
                    'full_name_fr': full_name,
                    'dob': dob_str,
                    'pob_fr': passp.place_of_birth_fr or p.place_of_birth or '',
                    'forms_data': get_safe_forms_data(passp, p),
                })
            ctx['items'] = items
            ctx['total_count'] = len(items)
            
        ctx['settings'] = ClubSettings.get_settings()
        return ctx


# ─── Anti-Doping Negative Medical Test Certificate (الكشف عن تعاطي المخدرات) ───

def get_safe_doping_data(forms_data, target_obj=None, is_staff=False):
    fd = dict(forms_data or {})
    doping_nested = fd.get('anti_doping', {})
    if isinstance(doping_nested, dict):
        for k, v in doping_nested.items():
            if k not in fd:
                fd[k] = v

    id_card_val = target_obj.id_card if (target_obj and hasattr(target_obj, 'id_card') and target_obj.id_card) else ''
    defaults = {
        'labo_name': fd.get('doping_lab_name', 'مخبر التحاليل الطبية والبيولوجية المعتمد - ولاية تيبازة'),
        'labo_address': fd.get('doping_lab_address', 'حي 05 جويلية، سيدي غيلاس - ولاية تيبازة'),
        'labo_phone': fd.get('doping_lab_phone', '024 43 12 89'),
        'labo_email': fd.get('doping_lab_email', 'contact@labo-tipaza.dz'),
        'sample_type': fd.get('doping_sample_type', 'بول (Urine)'),
        'id_card': fd.get('doping_id_card', id_card_val),
        'requesting_party': fd.get('doping_requester', 'النادي الرياضي الهاوي نجم مسلمون (ES Messelmoun)'),
        'test_date': fd.get('doping_exam_date', '15 / 10 / 2026'),
        'sign_date': fd.get('doping_sign_date', '15/10/2026'),
        'doping_result': fd.get('doping_result', 'negative'),
    }
    for k, v in defaults.items():
        if k not in fd or not fd[k]:
            fd[k] = v
        fd[f'doping_{k}'] = fd[k]
    return fd


class PlayerAntiDopingView(LoginRequiredMixin, View):
    """عرض، تعديل، وطباعة شهادة الكشف عن تعاطي المخدرات للاعب"""
    def get(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        is_blank = request.GET.get('blank') == '1'
        
        category = player.category
        category_name = category.name if category else 'U20'
        
        siblings = []
        prev_player = None
        next_player = None
        if category:
            siblings = list(ClubPlayer.objects.filter(category=category, is_active=True).order_by('last_name', 'first_name'))
            try:
                curr_idx = siblings.index(player)
                if curr_idx > 0:
                    prev_player = siblings[curr_idx - 1]
                if curr_idx < len(siblings) - 1:
                    next_player = siblings[curr_idx + 1]
            except ValueError:
                pass
                
        full_name = f"{player.last_name} {player.first_name}"
        if passport.full_name_fr:
            full_name = f"{player.last_name} {player.first_name} / {passport.full_name_fr}"
            
        dob_str = player.date_of_birth.strftime('%d/%m/%Y') if player.date_of_birth else ''
        pob_str = (player.place_of_birth or passport.place_of_birth_fr or '').strip()
        
        context = {
            'is_staff': False,
            'player': player,
            'passport': passport,
            'full_name': full_name,
            'dob': dob_str,
            'pob': pob_str,
            'id_card': player.id_card or passport.license_number or '',
            'category_name': category_name,
            'forms_data': get_safe_doping_data(passport.forms_data, player, is_staff=False),
            'siblings': siblings,
            'prev_item': prev_player,
            'next_item': next_player,
            'is_blank': is_blank,
            'exam_date_default': '15/10/2026',
        }
        return render(request, 'clubs/anti_doping_form.html', context)

    def post(self, request, pk):
        player = get_object_or_404(ClubPlayer, pk=pk)
        passport = player.get_passport()
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json' or
                   request.GET.get('ajax') == '1')
        
        if request.content_type == 'application/json':
            try:
                body_data = json.loads(request.body.decode('utf-8'))
                data = body_data.get('doping_data', body_data)
            except Exception:
                data = {}
        else:
            data = request.POST

        forms_data = dict(passport.forms_data or {})
        for k in ['labo_name', 'labo_address', 'labo_phone', 'labo_email', 'sample_type', 
                  'id_card', 'requesting_party', 'test_date', 'sign_date', 'doping_result',
                  'doping_lab_name', 'doping_lab_address', 'doping_lab_phone', 'doping_lab_email',
                  'doping_sample_type', 'doping_id_card', 'doping_requester', 'doping_exam_date']:
            if k in data:
                forms_data[k] = data[k].strip() if isinstance(data[k], str) else data[k]
                
        passport.forms_data = forms_data
        
        id_card_submitted = data.get('id_card') or data.get('doping_id_card')
        if id_card_submitted and isinstance(id_card_submitted, str):
            player.id_card = id_card_submitted.strip()
            player.save()
            
        passport.save()
        
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم حفظ بيانات كشف تعاطي المخدرات بنجاح!'})
        messages.success(request, 'تم حفظ بيانات كشف تعاطي المخدرات بنجاح!')
        return redirect('clubs:player_anti_doping', pk=player.pk)


class StaffAntiDopingView(LoginRequiredMixin, View):
    """عرض، تعديل، وطباعة شهادة الكشف عن تعاطي المخدرات للمدرب أو عضو الطاقم"""
    def get(self, request, pk):
        from .models import StaffMember
        staff = get_object_or_404(StaffMember, pk=pk)
        is_blank = request.GET.get('blank') == '1'
        
        siblings = list(StaffMember.objects.filter(is_active=True).order_by('role', 'last_name', 'first_name'))
        prev_staff = None
        next_staff = None
        try:
            curr_idx = siblings.index(staff)
            if curr_idx > 0:
                prev_staff = siblings[curr_idx - 1]
            if curr_idx < len(siblings) - 1:
                next_staff = siblings[curr_idx + 1]
        except ValueError:
            pass
            
        full_name = f"{staff.last_name} {staff.first_name}"
        dob_str = staff.date_of_birth.strftime('%d/%m/%Y') if staff.date_of_birth else ''
        pob_str = (staff.place_of_birth or '').strip()
        
        context = {
            'is_staff': True,
            'staff': staff,
            'full_name': full_name,
            'dob': dob_str,
            'pob': pob_str,
            'id_card': staff.id_card or '',
            'category_name': staff.category_assigned.name if staff.category_assigned else 'Staff',
            'forms_data': get_safe_doping_data(staff.forms_data, staff, is_staff=True),
            'siblings': siblings,
            'prev_item': prev_staff,
            'next_item': next_staff,
            'is_blank': is_blank,
            'exam_date_default': '15/10/2026',
        }
        return render(request, 'clubs/anti_doping_form.html', context)

    def post(self, request, pk):
        from .models import StaffMember
        staff = get_object_or_404(StaffMember, pk=pk)
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json' or
                   request.GET.get('ajax') == '1')
        
        if request.content_type == 'application/json':
            try:
                body_data = json.loads(request.body.decode('utf-8'))
                data = body_data.get('doping_data', body_data)
            except Exception:
                data = {}
        else:
            data = request.POST

        forms_data = dict(staff.forms_data or {})
        for k in ['labo_name', 'labo_address', 'labo_phone', 'labo_email', 'sample_type', 
                  'id_card', 'requesting_party', 'test_date', 'sign_date', 'doping_result',
                  'doping_lab_name', 'doping_lab_address', 'doping_lab_phone', 'doping_lab_email',
                  'doping_sample_type', 'doping_id_card', 'doping_requester', 'doping_exam_date']:
            if k in data:
                forms_data[k] = data[k].strip() if isinstance(data[k], str) else data[k]
                
        staff.forms_data = forms_data
        
        id_card_submitted = data.get('id_card') or data.get('doping_id_card')
        if id_card_submitted and isinstance(id_card_submitted, str):
            staff.id_card = id_card_submitted.strip()
            
        staff.save()
        
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'تم حفظ بيانات كشف تعاطي المخدرات للمدرب بنجاح!'})
        messages.success(request, 'تم حفظ بيانات كشف تعاطي المخدرات للمدرب بنجاح!')
        return redirect('clubs:staff_anti_doping', pk=staff.pk)


class BlankAntiDopingView(LoginRequiredMixin, TemplateView):
    """عرض وطباعة كشف تعاطي مخدرات فارغ"""
    template_name = 'clubs/anti_doping_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cat = self.request.GET.get('category', 'U20').strip()
        is_staff = self.request.GET.get('staff') == '1'
        ctx['is_blank'] = True
        ctx['is_staff'] = is_staff
        ctx['player'] = None
        ctx['staff'] = None
        ctx['category_name'] = cat
        ctx['full_name'] = ''
        ctx['dob'] = ''
        ctx['pob'] = ''
        ctx['id_card'] = ''
        ctx['forms_data'] = get_safe_doping_data({}, None)
        ctx['exam_date_default'] = '15/10/2026'
        return ctx


class AntiDopingBatchPrintView(LoginRequiredMixin, TemplateView):
    """طباعة جماعية لكشوف تعاطي المخدرات للاعبي فئة محددة (U20 افتراضياً)"""
    template_name = 'clubs/anti_doping_batch_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import ClubPlayer
        
        cat = self.request.GET.get('category', 'U20').strip()
        is_blank = self.request.GET.get('blank') == '1'
        
        ctx['is_staff'] = False
        ctx['category_name'] = cat
        ctx['is_blank'] = is_blank
        ctx['title_meta'] = f"فئة {cat}"
        
        if is_blank:
            try:
                count = int(self.request.GET.get('count', 1))
            except ValueError:
                count = 1
            items = []
            for _ in range(count):
                items.append({
                    'full_name': '',
                    'dob': '',
                    'pob': '',
                    'id_card': '',
                    'forms_data': get_safe_doping_data({}, None),
                    'is_blank': True,
                })
            ctx['items'] = items
            ctx['total_count'] = len(items)
        else:
            qs = ClubPlayer.objects.filter(is_active=True)
            if cat in ['U15', 'U17', 'U20']:
                qs = qs.filter(category__name=cat)
            else:
                qs = qs.filter(category__name='U20')
                
            players = list(qs.order_by('last_name', 'first_name'))
            items = []
            for p in players:
                passp = p.get_passport()
                fn = f"{p.last_name} {p.first_name}"
                if passp.full_name_fr:
                    fn = f"{p.last_name} {p.first_name} / {passp.full_name_fr}"
                dob_str = p.date_of_birth.strftime('%d/%m/%Y') if p.date_of_birth else ''
                pob_str = (p.place_of_birth or passp.place_of_birth_fr or '').strip()
                
                items.append({
                    'player': p,
                    'full_name': fn,
                    'dob': dob_str,
                    'pob': pob_str,
                    'id_card': p.id_card or passp.license_number or '',
                    'forms_data': get_safe_doping_data(passp.forms_data, p, is_staff=False),
                    'is_blank': False,
                })
            ctx['items'] = items
            ctx['total_count'] = len(items)
            
        return ctx


class StaffAntiDopingBatchPrintView(LoginRequiredMixin, TemplateView):
    """طباعة جماعية لكشوف تعاطي المخدرات للمدربين والطاقم الفني والإداري"""
    template_name = 'clubs/anti_doping_batch_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import StaffMember
        
        ctx['is_staff'] = True
        ctx['is_blank'] = False
        ctx['title_meta'] = "المدربين والطاقم الإداري"
        
        staff_list = list(StaffMember.objects.filter(is_active=True).order_by('role', 'last_name', 'first_name'))
        items = []
        for s in staff_list:
            fn = f"{s.last_name} {s.first_name} ({s.get_role_display()})"
            dob_str = s.date_of_birth.strftime('%d/%m/%Y') if s.date_of_birth else ''
            pob_str = (s.place_of_birth or '').strip()
            
            items.append({
                'staff': s,
                'full_name': fn,
                'dob': dob_str,
                'pob': pob_str,
                'id_card': s.id_card or '',
                'forms_data': get_safe_doping_data(s.forms_data, s, is_staff=True),
                'is_blank': False,
            })
            
        ctx['items'] = items
        ctx['total_count'] = len(items)
        return ctx


def get_clean_function_title(staff):
    """إرجاع المسمى الوظيفي بدون تكرار الفئة العمرية"""
    import re
    raw_func = (staff.function_title or staff.get_role_display() or '').strip()
    cat_name = staff.category_assigned.name if staff.category_assigned else ''
    if cat_name:
        pattern = rf'(\s*—\s*فئة\s+{re.escape(cat_name)})+'
        if re.search(pattern, raw_func):
            raw_func = re.sub(pattern, f' — فئة {cat_name}', raw_func)
        elif f'فئة {cat_name}' not in raw_func and cat_name not in raw_func:
            raw_func = f"{raw_func} — فئة {cat_name}" if raw_func else f"فئة {cat_name}"
    return raw_func


def get_safe_staff_medical_data(staff):
    fd = dict(staff.forms_data or {}) if staff else {}
    med_nested = fd.get('medical_certificate', {})
    if isinstance(med_nested, dict):
        for k, v in med_nested.items():
            if k not in fd:
                fd[k] = v
                
    defaults = {
        'doctor_name': '',
        'doctor_reg_number': '',
        'exam_place': 'مسلمون',
        'exam_date': '15/10/2026',
        'season': '2026/2027',
        'club_name': 'El-Wefaq Sportif messelmoun',
    }
    for k, v in defaults.items():
        if k not in fd or not fd[k]:
            fd[k] = v

    # Fallback to shared doctor info from another active staff member if empty
    if not fd.get('doctor_name'):
        from .models import StaffMember
        exclude_id = staff.pk if (staff and hasattr(staff, 'pk') and staff.pk) else 0
        other_staff = StaffMember.objects.filter(is_active=True).exclude(pk=exclude_id)
        for os_member in other_staff:
            os_fd = os_member.forms_data or {}
            if os_fd.get('doctor_name'):
                fd['doctor_name'] = os_fd.get('doctor_name', '')
                if not fd.get('doctor_reg_number') and os_fd.get('doctor_reg_number'):
                    fd['doctor_reg_number'] = os_fd.get('doctor_reg_number', '')
                break

    if not fd.get('exam_place'):
        fd['exam_place'] = 'مسلمون'
    if not fd.get('exam_date'):
        fd['exam_date'] = '15/10/2026'
    return fd


class StaffMedicalCertificateView(LoginRequiredMixin, View):
    """عرض، تعديل، وطباعة شهادة الأهلية الطبية للمدرب أو عضو الطاقم"""
    def get(self, request, pk):
        from .models import StaffMember, ClubSettings
        staff = get_object_or_404(StaffMember, pk=pk)
        is_blank = request.GET.get('blank') == '1'
        
        siblings = list(StaffMember.objects.filter(is_active=True).order_by('role', 'last_name', 'first_name'))
        prev_staff = None
        next_staff = None
        try:
            curr_idx = siblings.index(staff)
            if curr_idx > 0:
                prev_staff = siblings[curr_idx - 1]
            if curr_idx < len(siblings) - 1:
                next_staff = siblings[curr_idx + 1]
        except ValueError:
            pass
            
        forms_data = get_safe_staff_medical_data(staff)
        full_name = (forms_data.get('full_name') or f"{staff.last_name} {staff.first_name}").strip()
        func = (forms_data.get('function_title') or get_clean_function_title(staff)).strip()
        dob_str = staff.date_of_birth.strftime('%d/%m/%Y') if staff.date_of_birth else (forms_data.get('dob') or '')
        pob_str = (staff.place_of_birth or forms_data.get('pob') or 'سيدي غيلاس').strip()
        
        club_name = forms_data.get('club_name') or 'El-Wefaq Sportif messelmoun'
        season = forms_data.get('season') or '2026/2027'
        
        context = {
            'is_staff': True,
            'staff': staff,
            'full_name': full_name,
            'function_title': func,
            'dob': dob_str,
            'pob': pob_str,
            'season': season,
            'club_name': club_name,
            'forms_data': forms_data,
            'siblings': siblings,
            'prev_staff': prev_staff,
            'next_staff': next_staff,
            'is_blank': is_blank,
            'settings': ClubSettings.get_settings(),
            'is_edit_mode': request.GET.get('edit') == '1',
        }
        return render(request, 'clubs/staff_medical_certificate.html', context)

    def post(self, request, pk):
        import re
        from datetime import datetime
        from .models import StaffMember
        staff = get_object_or_404(StaffMember, pk=pk)
        is_ajax = (request.headers.get('x-requested-with') == 'XMLHttpRequest' or 
                   request.content_type == 'application/json' or
                   request.GET.get('ajax') == '1')
        
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}
        else:
            data = request.POST

        forms_data = dict(staff.forms_data or {})
        fields_to_store = ['doctor_name', 'doctor_reg_number', 'exam_place', 'exam_date', 'season', 'club_name']
        for f in fields_to_store:
            if f in data:
                forms_data[f] = data[f].strip() if isinstance(data[f], str) else data[f]
                
        # 1. Full name
        full_name_val = data.get('full_name') or data.get('full_name_fr')
        if full_name_val is not None:
            fn_val = full_name_val.strip()
            if fn_val:
                parts = fn_val.split(maxsplit=1)
                if len(parts) == 2:
                    staff.last_name = parts[0]
                    staff.first_name = parts[1]
                elif len(parts) == 1:
                    staff.last_name = parts[0]
                    staff.first_name = ''
                forms_data['full_name'] = fn_val
                
        # 2. Function title
        if 'function_title' in data:
            cat_name = staff.category_assigned.name if staff.category_assigned else ''
            raw_func = data['function_title'].strip()
            if cat_name:
                pattern = rf'(\s*—\s*فئة\s+{re.escape(cat_name)})+'
                raw_func = re.sub(pattern, '', raw_func).strip()
            staff.function_title = raw_func
            forms_data['function_title'] = raw_func
            
        # 3. Place of birth
        pob_val = data.get('pob') or data.get('pob_fr')
        if pob_val is not None:
            staff.place_of_birth = pob_val.strip()
            forms_data['pob'] = staff.place_of_birth
            
        # 4. Date of birth
        if 'dob' in data:
            dob_raw = data['dob'].strip()
            forms_data['dob'] = dob_raw
            if dob_raw:
                for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                    try:
                        staff.date_of_birth = datetime.strptime(dob_raw, fmt).date()
                        break
                    except Exception:
                        pass
                    
        staff.forms_data = forms_data
        staff.save()
        
        # 5. Propagate shared medical exam data to other active staff members
        propagate_keys = ['doctor_name', 'doctor_reg_number', 'exam_place', 'exam_date', 'season', 'club_name']
        to_propagate = {k: forms_data[k] for k in propagate_keys if forms_data.get(k)}
        if to_propagate:
            for other_s in StaffMember.objects.filter(is_active=True).exclude(pk=staff.pk):
                o_fd = dict(other_s.forms_data or {})
                changed = False
                for k, v in to_propagate.items():
                    if o_fd.get(k) != v:
                        o_fd[k] = v
                        changed = True
                if changed:
                    other_s.forms_data = o_fd
                    other_s.save(update_fields=['forms_data'])
        
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': 'تم حفظ بيانات الشهادة الطبية للمدرب بنجاح!',
                'full_name': forms_data.get('full_name') or f"{staff.last_name} {staff.first_name}".strip(),
                'function_title': forms_data.get('function_title') or get_clean_function_title(staff),
                'dob': staff.date_of_birth.strftime('%d/%m/%Y') if staff.date_of_birth else forms_data.get('dob', ''),
                'pob': staff.place_of_birth or forms_data.get('pob', 'سيدي غيلاس'),
                'doctor_name': forms_data.get('doctor_name', ''),
                'doctor_reg_number': forms_data.get('doctor_reg_number', ''),
                'exam_place': forms_data.get('exam_place', 'مسلمون'),
                'exam_date': forms_data.get('exam_date', '15/10/2026'),
                'club_name': forms_data.get('club_name', 'El-Wefaq Sportif messelmoun'),
                'season': forms_data.get('season', '2026/2027'),
            })
        messages.success(request, 'تم حفظ بيانات الشهادة الطبية للمدرب بنجاح!')
        return redirect('clubs:staff_medical_certificate', pk=staff.pk)


class StaffMedicalCertificateBatchPrintView(LoginRequiredMixin, TemplateView):
    """طباعة جماعية لشهادات الأهلية الطبية لكافة المدربين وأعضاء الطاقم"""
    template_name = 'clubs/staff_medical_certificate_batch_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import StaffMember, ClubSettings
        
        ctx['is_staff'] = True
        ctx['is_blank'] = False
        ctx['settings'] = ClubSettings.get_settings()
        ctx['club_name'] = 'El-Wefaq Sportif messelmoun'
        ctx['season'] = '2026/2027'
        
        staff_list = list(StaffMember.objects.filter(is_active=True).order_by('role', 'last_name', 'first_name'))
        items = []
        for s in staff_list:
            s_forms = get_safe_staff_medical_data(s)
            fn = (s_forms.get('full_name') or f"{s.last_name} {s.first_name}").strip()
            func = (s_forms.get('function_title') or get_clean_function_title(s)).strip()
            dob_str = s.date_of_birth.strftime('%d/%m/%Y') if s.date_of_birth else (s_forms.get('dob') or '')
            pob_str = (s.place_of_birth or s_forms.get('pob') or 'سيدي غيلاس').strip()
            
            items.append({
                'staff': s,
                'full_name': fn,
                'function_title': func,
                'dob': dob_str,
                'pob': pob_str,
                'forms_data': s_forms,
                'season': s_forms.get('season') or '2026/2027',
                'club_name': s_forms.get('club_name') or 'El-Wefaq Sportif messelmoun',
                'is_blank': False,
            })
            
        ctx['items'] = items
        ctx['total_count'] = len(items)
        return ctx


class BlankStaffMedicalCertificateView(LoginRequiredMixin, TemplateView):
    """عرض وطباعة نموذج فارغ لشهادة الأهلية الطبية للمدربين"""
    template_name = 'clubs/staff_medical_certificate.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import ClubSettings
        ctx['is_staff'] = True
        ctx['is_blank'] = True
        ctx['staff'] = None
        ctx['full_name'] = ''
        ctx['function_title'] = ''
        ctx['dob'] = ''
        ctx['pob'] = ''
        ctx['season'] = '2026/2027'
        ctx['club_name'] = 'El-Wefaq Sportif messelmoun'
        ctx['settings'] = ClubSettings.get_settings()
        ctx['forms_data'] = {
            'exam_place': 'مسلمون',
            'exam_date': '15/10/2026',
            'season': '2026/2027',
        }
        return ctx

from .models import ClubNews

class NewsListView(ListView):
    model = ClubNews
    template_name = 'clubs/news_list.html'
    context_object_name = 'news_list'
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)

class NewsDetailView(DetailView):
    model = ClubNews
    template_name = 'clubs/news_detail.html'
    context_object_name = 'news'

    def get_queryset(self):
        return super().get_queryset().filter(is_published=True)


class SubscriptionListView(ClubReadAccessMixin, ListView):
    model = Subscription
    template_name = 'clubs/subscription_list.html'
    context_object_name = 'subscriptions'

    def get_queryset(self):
        # Admin can see all subscriptions, others can't see this view (or only see their kids, but this is admin view)
        return Subscription.objects.select_related('player').all().order_by('-month', 'player__last_name')

class ParentDashboardView(ClubReadAccessMixin, TemplateView):
    template_name = 'clubs/parent_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['notifications'] = ClubNotification.objects.filter(recipient=self.request.user, is_read=False)[:5]

        # Fetch the players linked to this parent
        kids = ClubPlayer.objects.filter(parent_user=self.request.user)
        context['kids'] = kids
        return context


class MedicalRecordListView(ClubReadAccessMixin, ListView):
    model = MedicalRecord
    template_name = 'clubs/medical_list.html'
    context_object_name = 'records'
    
    def get_queryset(self):
        return MedicalRecord.objects.select_related('player').order_by('-date_of_injury')

class PlayerEvaluationListView(ClubReadAccessMixin, ListView):
    model = PlayerEvaluation
    template_name = 'clubs/evaluation_list.html'
    context_object_name = 'evaluations'
    
    def get_queryset(self):
        return PlayerEvaluation.objects.select_related('player', 'evaluator').order_by('-date_evaluated')

class PlayerEquipmentListView(ClubReadAccessMixin, ListView):
    model = PlayerEquipment
    template_name = 'clubs/equipment_list.html'
    context_object_name = 'equipments'
    
    def get_queryset(self):
        return PlayerEquipment.objects.select_related('player').order_by('player__last_name')

class TrainingAttendanceListView(ClubReadAccessMixin, ListView):
    model = TrainingSession
    template_name = 'clubs/attendance_list.html'
    context_object_name = 'sessions'
    
    def get_queryset(self):
        return TrainingSession.objects.order_by('-date', '-start_time')



class CoachDashboardView(ClubReadAccessMixin, TemplateView):
    template_name = 'clubs/coach_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self.request.user, 'staff_profile'):
            staff = self.request.user.staff_profile
            context['staff'] = staff
            if staff.category_assigned:
                context['players'] = ClubPlayer.objects.filter(category=staff.category_assigned)
                # Get upcoming sessions for this category
                context['sessions'] = TrainingSession.objects.filter(target_categories=staff.category_assigned).order_by('-date')[:5]
                
                # Match stats
                matches = ClubMatch.objects.filter(category=staff.category_assigned, our_score__isnull=False)
                wins = 0
                draws = 0
                losses = 0
                for match in matches:
                    if match.our_score > match.their_score: wins += 1
                    elif match.our_score == match.their_score: draws += 1
                    else: losses += 1
                context['wins'] = wins
                context['draws'] = draws
                context['losses'] = losses
        return context

class TakeAttendanceView(ClubReadAccessMixin, TemplateView):
    template_name = 'clubs/take_attendance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.kwargs.get('session_id')
        session = get_object_or_404(TrainingSession, id=session_id)
        context['session'] = session
        
        # Get players for this session's categories
        categories = session.target_categories.all()
        if categories.exists():
            players = ClubPlayer.objects.filter(category__in=categories)
        else:
            players = ClubPlayer.objects.all()
            
        context['players'] = players
        
        # Get existing attendances
        context['existing_attendances'] = {
            a.player_id: a.is_present 
            for a in TrainingAttendance.objects.filter(session=session)
        }
        return context

    def post(self, request, *args, **kwargs):
        session_id = self.kwargs.get('session_id')
        session = get_object_or_404(TrainingSession, id=session_id)
        
        # The form will submit player_id_1=on/off etc.
        # We can just check which players were submitted
        for key, value in request.POST.items():
            if key.startswith('player_'):
                try:
                    player_id = int(key.split('_')[1])
                    player = ClubPlayer.objects.get(id=player_id)
                    is_present = (value == 'on')
                    
                    # Update or create attendance
                    TrainingAttendance.objects.update_or_create(
                        session=session,
                        player=player,
                        defaults={'is_present': is_present}
                    )
                except (ValueError, ClubPlayer.DoesNotExist):
                    pass
                    
        messages.success(request, 'تم حفظ سجل الحضور بنجاح.')
        return redirect('clubs:coach_dashboard')


class PublicMatchListView(ListView):
    model = ClubMatch
    template_name = 'clubs/public_match_list.html'
    context_object_name = 'matches'
    
    def get_queryset(self):
        return ClubMatch.objects.order_by('-date', '-time')

class PublicCategoryListView(ListView):
    model = Category
    template_name = 'clubs/public_category_list.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        # We can prefetch players or just let the template do it
        return Category.objects.prefetch_related('players', 'staff').all()


from django.db.models import Sum, Count
from django.utils import timezone
from .models import ClubNotification

class FinancialDashboardView(ClubReadAccessMixin, TemplateView):
    template_name = 'clubs/financial_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Admin check
        if not self.request.user.is_staff:
            return context
            
        now = timezone.now()
        subscriptions = Subscription.objects.all()
        
        total_revenue = subscriptions.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        total_players = ClubPlayer.objects.count()
        paid_players = subscriptions.filter(start_date__lte=now, end_date__gte=now).values('player').distinct().count()
        unpaid_players = total_players - paid_players
        
        context['total_revenue'] = total_revenue
        context['total_players'] = total_players
        context['paid_players'] = paid_players
        context['unpaid_players'] = unpaid_players
        return context

class SendNotificationView(ClubWriteAccessMixin, CreateView):
    model = ClubNotification
    fields = ['recipient', 'title', 'message']
    template_name = 'clubs/send_notification.html'
    
    def form_valid(self, form):
        messages.success(self.request, 'تم إرسال الإشعار بنجاح.')
        return super().form_valid(form)
        
    def get_success_url(self):
        return reverse('clubs:dashboard')

class MatchSquadUpdateView(ClubWriteAccessMixin, UpdateView):
    model = ClubMatch
    fields = ['squad']
    template_name = 'clubs/match_squad_form.html'
    
    def get_success_url(self):
        messages.success(self.request, 'تم تحديث قائمة المستدعين للمباراة.')
        return reverse('clubs:coach_dashboard')


class GeneratorView(ClubReadAccessMixin, TemplateView):
    template_name = 'clubs/generator.html'

class LeagueScheduleView(TemplateView):
    template_name = 'clubs/league_schedule.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        raw_rounds = [
            [["نجمة حجوط", "وفاق حجوط"], ["تحدي الداموس", "الوفاق مسلمون"], ["اتحاد مناصر", "مولودية قوراية"], ["شبيبة حجوط", "مولودية مراد"], ["ونام بوجبرون", "اتحاد القليعة"], ["نخبة فجانة", "أمل سيدي عمر"]],
            [["وفاق حجوط", "نخبة فجانة"], ["أمل سيدي عمر", "شبيبة حجوط"], ["مولودية قوراية", "ونام بوجبرون"], ["مولودية مراد", "تحدي الداموس"], ["الوفاق مسلمون", "اتحاد مناصر"], ["اتحاد القليعة", "نجمة حجوط"]],
            [["وفاق حجوط", "اتحاد القليعة"], ["شبيبة حجوط", "نخبة فجانة"], ["تحدي الداموس", "أمل سيدي عمر"], ["ونام بوجبرون", "الوفاق مسلمون"], ["اتحاد مناصر", "مولودية مراد"], ["نجمة حجوط", "مولودية قوراية"]],
            [["شبيبة حجوط", "وفاق حجوط"], ["مولودية قوراية", "اتحاد القليعة"], ["نخبة فجانة", "تحدي الداموس"], ["أمل سيدي عمر", "اتحاد مناصر"], ["مولودية مراد", "ونام بوجبرون"], ["الوفاق مسلمون", "نجمة حجوط"]],
            [["وفاق حجوط", "مولودية قوراية"], ["تحدي الداموس", "شبيبة حجوط"], ["اتحاد القليعة", "الوفاق مسلمون"], ["اتحاد مناصر", "نخبة فجانة"], ["ونام بوجبرون", "أمل سيدي عمر"], ["نجمة حجوط", "مولودية مراد"]],
            [["تحدي الداموس", "وفاق حجوط"], ["الوفاق مسلمون", "مولودية قوراية"], ["شبيبة حجوط", "اتحاد مناصر"], ["اتحاد القليعة", "نخبة فجانة"], ["مولودية مراد", "ونام بوجبرون"], ["أمل سيدي عمر", "نجمة حجوط"]],
            [["وفاق حجوط", "الوفاق مسلمون"], ["مولودية قوراية", "مولودية مراد"], ["اتحاد مناصر", "تحدي الداموس"], ["ونام بوجبرون", "شبيبة حجوط"], ["اتحاد القليعة", "أمل سيدي عمر"], ["نجمة حجوط", "نخبة فجانة"]],
            [["اتحاد مناصر", "وفاق حجوط"], ["مولودية مراد", "الوفاق مسلمون"], ["تحدي الداموس", "ونام بوجبرون"], ["أمل سيدي عمر", "مولودية قوراية"], ["نخبة فجانة", "اتحاد القليعة"], ["شبيبة حجوط", "نجمة حجوط"]],
            [["وفاق حجوط", "مولودية مراد"], ["ونام بوجبرون", "اتحاد مناصر"], ["الوفاق مسلمون", "أمل سيدي عمر"], ["مولودية قوراية", "نخبة فجانة"], ["اتحاد القليعة", "شبيبة حجوط"], ["نجمة حجوط", "تحدي الداموس"]],
            [["ونام بوجبرون", "وفاق حجوط"], ["أمل سيدي عمر", "مولودية مراد"], ["نخبة فجانة", "الوفاق مسلمون"], ["تحدي الداموس", "اتحاد القليعة"], ["شبيبة حجوط", "مولودية قوراية"], ["اتحاد مناصر", "نجمة حجوط"]],
            [["وفاق حجوط", "أمل سيدي عمر"], ["مولودية مراد", "نخبة فجانة"], ["اتحاد القليعة", "اتحاد مناصر"], ["الوفاق مسلمون", "شبيبة حجوط"], ["مولودية قوراية", "تحدي الداموس"], ["نجمة حجوط", "ونام بوجبرون"]]
        ]
        
        team_logos = {
            "وفاق حجوط": "/static/img/teams/wh.jpg",
            "أمل سيدي عمر": "/static/img/teams/esa.jpg",
            "ونام بوجبرون": "/static/img/teams/wbm.jpg",
            "مولودية مراد": "/static/img/teams/mcm.jpg",
            "اتحاد مناصر": "/static/img/teams/esm.jpg",  # mapping to esm as uploaded previously
            "الوفاق مسلمون": "/static/img/teams/esms.jpg",
            "تحدي الداموس": "/static/img/teams/thd.jpg", # may not exist yet, will use fallback
            "مولودية قوراية": "/static/img/teams/mcg.jpg",
            "شبيبة حجوط": "/static/img/teams/jsh.jpg",
            "اتحاد القليعة": "/static/img/teams/usjk.jpg",
            "نخبة فجانة": "/static/img/teams/nf.jpg",
            "نجمة حجوط": "/static/img/teams/ebh.jpg"
        }
        
        formatted_rounds = []
        for round_matches in raw_rounds:
            formatted_matches = []
            for m in round_matches:
                formatted_matches.append({
                    "team1": {"name": m[0], "logo": team_logos.get(m[0], "")},
                    "team2": {"name": m[1], "logo": team_logos.get(m[1], "")}
                })
            formatted_rounds.append(formatted_matches)
            
        context['rounds'] = formatted_rounds
        return context


from django.core.management import call_command
from django.http import HttpResponse

from django.core.management import call_command
from django.http import HttpResponse

def populate_league_view(request):
    if not request.user.is_authenticated:
        return HttpResponse("يرجى تسجيل الدخول أولا", status=401)
        
    try:
        call_command('migrate')
        call_command('populate_league')
        import os
        from django.conf import settings
        fixture_file = os.path.join(settings.BASE_DIR, 'apps', 'clubs', 'fixtures', 'academy_data.json')
        if os.path.exists(fixture_file):
            call_command('loaddata', fixture_file)
        return HttpResponse("نجاح! تم تحديث البطولة ومطابقة بيانات 215 لاعباً والأكاديمية والجوازات بنجاح. يمكنك إغلاق هذه الصفحة.", status=200)
    except Exception as e:
        import traceback
        return HttpResponse(f"ERROR: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status=200)


from django.http import JsonResponse
from apps.clubs.models import ClubMatch, Category

def debug_matches(request):
    data = {}
    data['categories'] = list(Category.objects.values_list('name', flat=True))
    data['all_club_matches'] = ClubMatch.objects.count()
    data['unplayed_club_matches'] = ClubMatch.objects.filter(our_score__isnull=True).count()
    data['matches'] = []
    
    for m in ClubMatch.objects.all().order_by('-id')[:20]:
        data['matches'].append({
            'id': m.id,
            'cat': m.category.name if m.category else None,
            'opponent': m.opponent,
            'is_home': m.is_home,
            'our_score': m.our_score,
            'date': m.date,
        })
        
    return JsonResponse(data)


def test_matches_view(request):
    from django.http import HttpResponse
    from apps.clubs.models import ClubMatch, Category
    
    cats = list(Category.objects.values_list('name', flat=True))
    matches = list(ClubMatch.objects.values('id', 'category__name', 'opponent', 'our_score', 'date'))
    
    html = f"<h3>Categories:</h3><p>{cats}</p>"
    html += f"<h3>Matches ({len(matches)}):</h3><pre>"
    for m in matches:
        html += str(m) + "\n"
    html += "</pre>"
    
    html += "<h3>Next Matches calculation:</h3><pre>"
    for cat in ["U15", "U17", "U20"]:
        match = ClubMatch.objects.filter(category__name__icontains=cat, our_score__isnull=True).order_by('date').first()
        html += f"{cat}: {match}\n"
    html += "</pre>"
        
    return HttpResponse(html)
