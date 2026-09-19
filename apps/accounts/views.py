from django.views.generic import CreateView, UpdateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from .models import User, AppearanceSettings
from .forms import RegisterForm, AppearanceForm


from django.contrib.auth import views as auth_views
from django.contrib.auth import authenticate, login
from django.utils.translation import gettext as _

class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    
    def form_valid(self, form):
        user = form.get_user()
        if not user.is_active:
            messages.error(self.request, _('⚠️ Votre compte est en attente de validation par l\'administrateur. / حسابك قيد المراجعة من قبل المسؤول.'))
            return self.form_invalid(form)
        return super().form_valid(form)


class RegisterView(CreateView):
    model      = User
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url   = reverse_lazy('accounts:login')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False  # Inactive by default until approved
        user.save()
        messages.warning(self.request, _('✅ Inscription réussie ! Votre compte doit être validé par un administrateur. / تم التسجيل بنجاح! يجب مراجعة حسابك من طرف المسؤول.'))
        
        # Send notification to admins
        admins = User.objects.filter(role='admin')
        from apps.notifications.models import Notification
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                notif_type=Notification.Type.SYSTEM,
                title=_('Nouvel utilisateur en attente'),
                message=_('L\'utilisateur %s s\'est inscrit et attend votre validation.') % user.username
            )
        
        return redirect(self.success_url)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('core:home')
        return super().dispatch(request, *args, **kwargs)


from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class PendingUserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'accounts/pending_users.html'
    context_object_name = 'pending_users'

    def test_func(self):
        return self.request.user.role == 'admin'

    def get_queryset(self):
        return User.objects.filter(is_active=False).order_by('-created_at')


class UserApprovalActionView(LoginRequiredMixin, UserPassesTestMixin, redirect_view := __import__('django.views.generic', fromlist=['View']).View):
    def test_func(self):
        return self.request.user.role == 'admin'

    def post(self, request, pk):
        user_to_approve = get_object_or_404(User, pk=pk)
        action = request.POST.get('action')

        if action == 'approve':
            user_to_approve.is_active = True
            user_to_approve.save(update_fields=['is_active'])
            messages.success(request, _('✅ L\'utilisateur %s a été activé.') % user_to_approve.username)
        elif action == 'reject':
            username = user_to_approve.username
            user_to_approve.delete()
            messages.warning(request, _('🗑️ L\'inscription de %s a été rejetée.') % username)

        return redirect('accounts:pending_users')


class ProfileView(LoginRequiredMixin, UpdateView):
    model       = User
    fields      = ['first_name','last_name','email','phone',
                   'neighborhood','bio','avatar']
    template_name = 'accounts/profile.html'
    success_url   = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, '✅ Profil mis à jour / تم تحديث الملف الشخصي')
        return super().form_valid(form)


from apps.core.models import SiteSettings
from .forms import RegisterForm, AppearanceForm, SiteSettingsForm

class AppearanceView(LoginRequiredMixin, UpdateView):
    model       = AppearanceSettings
    form_class  = AppearanceForm
    template_name = 'accounts/appearance.html'
    success_url   = reverse_lazy('accounts:appearance')

    def get_object(self):
        return AppearanceSettings.get_or_create_for(self.request.user)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_staff:
            context['site_form'] = SiteSettingsForm(instance=SiteSettings.load())
        return context

    def post(self, request, *args, **kwargs):
        # Handle quick AJAX theme change from the navbar which only sends 'theme'
        if request.headers.get('Content-Type') == 'application/x-www-form-urlencoded' and 'theme' in request.POST and len(request.POST) <= 2:
            obj = self.get_object()
            obj.theme = request.POST.get('theme')
            obj.save(update_fields=['theme'])
            return redirect(self.success_url)
            
        # Process the main form
        self.object = self.get_object()
        form = self.get_form()
        
        # Process site settings form if user is staff
        site_form_valid = True
        if request.user.is_staff:
            site_form = SiteSettingsForm(request.POST, request.FILES, instance=SiteSettings.load())
            if site_form.is_valid():
                site_form.save()
            else:
                site_form_valid = False
                
        if form.is_valid() and site_form_valid:
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, '🎨 Paramètres mis à jour / تم تحديث الإعدادات')
        return super().form_valid(form)
