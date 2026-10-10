from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

class ClubWriteAccessMixin(LoginRequiredMixin):
    """
    Mixin that restricts access to the view.
    Only ADMIN or COACH roles are allowed to work (write).
    If the user is a COACH and is assigned to a specific category,
    we can enforce that they only edit objects in their category.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Must be Admin or Coach
        if request.user.role not in [request.user.Role.ADMIN, request.user.Role.COACH]:
            raise PermissionDenied("Seul l'administrateur ou l'entraneur peut effectuer cette action (ajouter, modifier, supprimer).")
        
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # For ModelForms that have 'category' field, we could restrict the choices
        # but for now we just restrict at the form validation or queryset level.
        return kwargs

    def form_valid(self, form):
        # Enforce category restriction if user is a coach tied to a category
        if self.request.user.role == self.request.user.Role.COACH and self.request.user.coach_category:
            if hasattr(form.instance, 'category'):
                form.instance.category = self.request.user.coach_category
            elif hasattr(form.instance, 'player'):
                if form.instance.player.category != self.request.user.coach_category:
                    raise PermissionDenied("Vous ne pouvez grer que les joueurs de votre catgorie.")
            elif hasattr(form.instance, 'session'):
                if hasattr(form.instance.session, 'category') and form.instance.session.category != self.request.user.coach_category:
                    raise PermissionDenied("Vous ne pouvez grer que votre catgorie.")
        return super().form_valid(form)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Prevent accessing edit/delete pages of objects outside coach's category
        if self.request.user.role == self.request.user.Role.COACH and self.request.user.coach_category_id:
            category_id = None
            if hasattr(obj, 'category_id'):
                category_id = obj.category_id
            elif hasattr(obj, 'player') and hasattr(obj.player, 'category_id'):
                category_id = obj.player.category_id
            elif hasattr(obj, 'session') and hasattr(obj.session, 'category_id'):
                category_id = obj.session.category_id
            elif obj.__class__.__name__ == 'Category':
                category_id = obj.id
                
            if category_id and self.request.user.coach_category_id != category_id:
                raise PermissionDenied("ليس لديك الصلاحية لتعديل أو مسح بيانات فئة أخرى.")
        return obj




from django.contrib import messages
from django.shortcuts import redirect

class ClubReadAccessMixin(LoginRequiredMixin):
    """
    Mixin that restricts READ access.
    Viewers (Spectateur) cannot access the academy at all.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if request.user.role == getattr(request.user.Role, 'VIEWER', 'viewer'):
            messages.error(request, "Accs refus. Les spectateurs n'ont pas accs  l'acadmie. / عذراً، المتفرج لا يملك صلاحية الدخول للأكاديمية.")
            return redirect('core:home')
            
        return super().dispatch(request, *args, **kwargs)
