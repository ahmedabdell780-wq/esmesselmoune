from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
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
        from django.db.models import Q
        qs = super().get_queryset().filter(is_active=True).prefetch_related('subscriptions')
        category_id = self.request.GET.get('category')
        position_filter = self.request.GET.get('position')
        q = self.request.GET.get('q')
        
        if category_id:
            qs = qs.filter(category_id=category_id)
            
        if position_filter:
            qs = qs.filter(position=position_filter)
            
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(position__icontains=q)
            )
            
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
        category_id = self.request.GET.get('category')
        position_filter = self.request.GET.get('position')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if position_filter:
            qs = qs.filter(position=position_filter)
        return sort_players_by_position(qs)

    def get_context_data(self, **kwargs):
        from .models import ClubSettings
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        
        # Chunk players into pages of 8 cards per A4 page
        players_list = list(context['players'])
        player_pages = [players_list[i:i + 8] for i in range(0, len(players_list), 8)]
        context['player_pages'] = player_pages
        return context

class PlayerListPrintView(LoginRequiredMixin, ListView):
    model = ClubPlayer
    template_name = 'clubs/player_list_print.html'
    context_object_name = 'players'
    
    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        category_id = self.request.GET.get('category')
        position_filter = self.request.GET.get('position')
        if category_id:
            qs = qs.filter(category_id=category_id)
        if position_filter:
            qs = qs.filter(position=position_filter)
        return sort_players_by_position(qs)

    def get_context_data(self, **kwargs):
        from .models import ClubSettings, Category, StaffMember
        context = super().get_context_data(**kwargs)
        context['settings'] = ClubSettings.get_settings()
        
        is_blank = self.request.GET.get('blank') == '1'
        context['is_blank'] = is_blank
        if is_blank:
            context['blank_rows'] = range(1, 36)
        
        category_id = self.request.GET.get('category')
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                context['selected_category'] = category
                context['coach'] = StaffMember.objects.filter(category_assigned=category, role='COACH').first()
            except Category.DoesNotExist:
                pass
                
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
        fields = ['category', 'first_name', 'last_name', 'date_of_birth', 'place_of_birth', 'photo', 'blood_type', 'medical_certificate', 'parent_name', 'parent_phone', 'player_phone', 'address', 'position', 'jersey_number']
        widgets = {
            'date_of_birth': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
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

class StaffListView(LoginRequiredMixin, ListView):
    model = StaffMember
    template_name = 'clubs/staff_list.html'
    context_object_name = 'staff_members'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class StaffCreateView(LoginRequiredMixin, CreateView):
    model = StaffMember
    fields = ['first_name', 'last_name', 'role', 'phone', 'photo', 'category_assigned']
    template_name = 'clubs/generic_form.html'
    success_url = reverse_lazy('clubs:staff_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Nouveau Membre du Staff (إضافة عضو للطاقم)"
        context['icon'] = "fas fa-user-tie"
        return context

    def form_valid(self, form):
        messages.success(self.request, "Membre du staff ajouté / تم الإضافة بنجاح!")
        return super().form_valid(form)

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

class AcademyRegistrationView(LoginRequiredMixin, CreateView):
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


from django.views.generic import ListView, DetailView
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


class SubscriptionListView(LoginRequiredMixin, ListView):
    model = Subscription
    template_name = 'clubs/subscription_list.html'
    context_object_name = 'subscriptions'

    def get_queryset(self):
        # Admin can see all subscriptions, others can't see this view (or only see their kids, but this is admin view)
        return Subscription.objects.select_related('player').all().order_by('-month', 'player__last_name')

class ParentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'clubs/parent_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch the players linked to this parent
        kids = ClubPlayer.objects.filter(parent_user=self.request.user)
        context['kids'] = kids
        return context


class MedicalRecordListView(LoginRequiredMixin, ListView):
    model = MedicalRecord
    template_name = 'clubs/medical_list.html'
    context_object_name = 'records'
    
    def get_queryset(self):
        return MedicalRecord.objects.select_related('player').order_by('-date_of_injury')

class PlayerEvaluationListView(LoginRequiredMixin, ListView):
    model = PlayerEvaluation
    template_name = 'clubs/evaluation_list.html'
    context_object_name = 'evaluations'
    
    def get_queryset(self):
        return PlayerEvaluation.objects.select_related('player', 'evaluator').order_by('-date_evaluated')

class PlayerEquipmentListView(LoginRequiredMixin, ListView):
    model = PlayerEquipment
    template_name = 'clubs/equipment_list.html'
    context_object_name = 'equipments'
    
    def get_queryset(self):
        return PlayerEquipment.objects.select_related('player').order_by('player__last_name')

class TrainingAttendanceListView(LoginRequiredMixin, ListView):
    model = TrainingSession
    template_name = 'clubs/attendance_list.html'
    context_object_name = 'sessions'
    
    def get_queryset(self):
        return TrainingSession.objects.order_by('-date', '-start_time')



class CoachDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'clubs/coach_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if hasattr(self.request.user, 'staff_profile'):
            staff = self.request.user.staff_profile
            context['staff'] = staff
            if staff.category_assigned:
                context['players'] = ClubPlayer.objects.filter(category=staff.category_assigned)
                # Get upcoming sessions for this category
                
                
                # Match stats
                matches = ClubMatch.objects.filter(category=staff.category_assigned, is_played=True)
                wins = 0
                draws = 0
                losses = 0
                for match in matches:
                    if match.our_score > match.opponent_score: wins += 1
                    elif match.our_score == match.opponent_score: draws += 1
                    else: losses += 1
                context['wins'] = wins
                context['draws'] = draws
                context['losses'] = losses
        return context

class TakeAttendanceView(LoginRequiredMixin, TemplateView):
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
