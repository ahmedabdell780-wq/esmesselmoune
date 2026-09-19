"""
TurniQ Teams — Full CRUD Views for Teams and Players.
Includes Arabic/French support, search, and permission checks.
"""
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import Team, Player
from .forms import TeamForm, PlayerForm, PlayerSearchForm


# ─── Permission Mixin ────────────────────────────────────────────────────────
class CanManageTeamMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow admin/organizer OR the team's own manager."""

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.role in ('admin', 'organizer'):
            return True
        if user.role == 'manager':
            # Check if we are dealing with a Team or a Player
            pk = self.kwargs.get('pk')
            team_pk = self.kwargs.get('team_pk')
            
            if team_pk:
                return Team.objects.filter(pk=team_pk, manager=user).exists()
            
            if pk:
                # Is it a team?
                if Team.objects.filter(pk=pk).exists():
                    return Team.objects.filter(pk=pk, manager=user).exists()
                # Is it a player?
                player = Player.objects.filter(pk=pk).first()
                if player:
                    return player.team.manager == user
                    
        return False

    def handle_no_permission(self):
        messages.error(self.request, _('Vous n\'avez pas la permission d\'accéder à cette ressource.'))
        return redirect('teams:list')


class AdminOrOrgMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Only admin or organizer."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def handle_no_permission(self):
        messages.error(self.request, _('Action réservée aux administrateurs.'))
        return redirect('teams:list')


class CanCreateTeamMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow admin, organizer, OR manager (to create their team)."""

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        return user.role in ('admin', 'organizer', 'manager')

    def handle_no_permission(self):
        messages.error(self.request, _('Vous n\'avez pas la permission de créer une équipe.'))
        return redirect('teams:list')


# ─── TEAM VIEWS ──────────────────────────────────────────────────────────────

class TeamListView(ListView):
    model = Team
    template_name = 'teams/list.html'
    context_object_name = 'teams'
    ordering = ['name']

    def get_queryset(self):
        qs = Team.objects.filter(is_active=True).annotate(
            player_count=Count('players', filter=Q(players__is_active=True))
        )
        q = self.request.GET.get('q', '').strip()
        tournament_id = self.request.GET.get('tournament', '')

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(neighborhood__icontains=q))
            
        if tournament_id:
            qs = qs.filter(
                tournament_teams__tournament_id=tournament_id,
                tournament_teams__is_confirmed=True
            )
            
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.tournaments.models import Tournament
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['selected_tournament'] = self.request.GET.get('tournament', '')
        ctx['tournaments'] = Tournament.objects.all().order_by('-year', '-edition')
        ctx['can_manage']   = (
            self.request.user.is_authenticated and
            self.request.user.role in ('admin', 'organizer')
        )
        return ctx


class TeamDetailView(DetailView):
    model = Team
    template_name = 'teams/detail.html'
    context_object_name = 'team'

    def get_queryset(self):
        return Team.objects.prefetch_related('players')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.matches.models import Goal, Match
        team = self.object

        ctx['goalkeepers']  = team.players.filter(position='GK',  is_active=True)
        ctx['defenders']    = team.players.filter(position='DEF', is_active=True)
        ctx['midfielders']  = team.players.filter(position='MID', is_active=True)
        ctx['forwards']     = team.players.filter(position='FWD', is_active=True)
        ctx['inactive_players'] = team.players.filter(is_active=False)
        
        ctx['can_manage'] = (
            self.request.user.is_authenticated and (
                self.request.user.role in ('admin', 'organizer') or
                (self.request.user.role == 'manager' and team.manager == self.request.user)
            )
        )

        ctx['top_scorer'] = (
            Goal.objects.filter(team=team).exclude(goal_type='own_goal')
            .values('player__id', 'player__first_name', 'player__last_name')
            .annotate(goals=Count('id')).order_by('-goals').first()
        )
        ctx['recent_matches'] = (
            Match.objects
            .filter(Q(team1=team) | Q(team2=team), status=Match.Status.FINISHED)
            .select_related('team1', 'team2').order_by('-match_date')[:5]
        )
        ctx['can_manage'] = (
            self.request.user.is_authenticated and (
                self.request.user.role in ('admin', 'organizer') or
                (self.request.user.role == 'manager' and
                 getattr(team, 'manager', None) == self.request.user)
            )
        )
        ctx['total_goals'] = Goal.objects.filter(
            team=team).exclude(goal_type='own_goal').count()
            
        # Match statistics
        team_matches = Match.objects.filter(Q(team1=team) | Q(team2=team), status=Match.Status.FINISHED)
        ctx['total_matches'] = team_matches.count()
        ctx['win_count'] = sum(1 for m in team_matches if m.winner == team)
        ctx['draw_count'] = sum(1 for m in team_matches if m.result == 'draw')
        ctx['loss_count'] = ctx['total_matches'] - ctx['win_count'] - ctx['draw_count']
        
        return ctx


class TeamCreateView(CanCreateTeamMixin, CreateView):
    model = Team
    form_class = TeamForm
    template_name = 'teams/form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'manager':
            # Check if manager already has a team
            team = Team.objects.filter(manager=request.user).first()
            if team:
                messages.info(request, _('Vous avez déjà créé votre équipe.'))
                return redirect('teams:detail', pk=team.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('teams:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        if self.request.user.role == 'manager':
            form.instance.manager = self.request.user
        messages.success(self.request, f'✅ Équipe « {form.instance.name} » créée avec succès!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = _('Nouvelle équipe / فريق جديد')
        ctx['action']     = 'create'
        return ctx


class TeamUpdateView(CanManageTeamMixin, UpdateView):
    model = Team
    form_class = TeamForm
    template_name = 'teams/form.html'

    def get_success_url(self):
        return reverse('teams:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'✅ Équipe « {form.instance.name} » mise à jour!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = _('Modifier l\'équipe / تعديل الفريق')
        ctx['action']     = 'update'
        return ctx


class TeamDeleteView(CanManageTeamMixin, DeleteView):
    model = Team
    template_name = 'teams/confirm_delete.html'
    success_url = reverse_lazy('teams:list')

    def form_valid(self, form):
        name = self.object.name
        messages.success(self.request, f'🗑️ Équipe « {name} » supprimée.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['object_type'] = _('l\'équipe / الفريق')
        return ctx


# ─── PLAYER VIEWS ────────────────────────────────────────────────────────────

class PlayerListView(ListView):
    """All players in a team — with search + filter."""
    model = Player
    template_name = 'teams/player_list.html'
    context_object_name = 'players'

    def get_queryset(self):
        self.team = get_object_or_404(Team, pk=self.kwargs['team_pk'])
        qs = self.team.players.select_related('team').order_by('position', 'jersey_number')

        q        = self.request.GET.get('q', '').strip()
        position = self.request.GET.get('position', '')
        status   = self.request.GET.get('status', '')

        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                Q(national_id__icontains=q)
            )
        if position:
            qs = qs.filter(position=position)
        if status == 'active':
            qs = qs.filter(is_active=True)
        elif status == 'suspended':
            qs = qs.filter(is_suspended=True)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['team']       = self.team
        ctx['search_form']= PlayerSearchForm(self.request.GET)
        ctx['can_manage'] = (
            self.request.user.is_authenticated and (
                self.request.user.role in ('admin', 'organizer') or
                (self.request.user.role == 'manager' and
                 self.team.manager == self.request.user)
            )
        )
        ctx['position_counts'] = {
            'GK':  self.team.players.filter(position='GK',  is_active=True).count(),
            'DEF': self.team.players.filter(position='DEF', is_active=True).count(),
            'MID': self.team.players.filter(position='MID', is_active=True).count(),
            'FWD': self.team.players.filter(position='FWD', is_active=True).count(),
        }
        return ctx


class PlayerDetailView(DetailView):
    model = Player
    template_name = 'teams/player_detail.html'
    context_object_name = 'player'

    def get_queryset(self):
        return Player.objects.select_related('team')

    def get_context_data(self, **kwargs):
        from apps.matches.models import Goal, Card, Injury, Match
        from apps.tournaments.models import Tournament, TournamentTeam
        ctx = super().get_context_data(**kwargs)
        player = self.object
        
        # Stats
        ctx['goals_count']   = Goal.objects.filter(player=player).exclude(goal_type='own_goal').count()
        ctx['assists_count'] = Goal.objects.filter(assist_player=player).count()
        ctx['yellow_cards']  = Card.objects.filter(player=player, card_type='yellow').count()
        ctx['red_cards']     = Card.objects.filter(player=player, card_type__in=['red', 'yellow_red']).count()
        ctx['injuries']      = Injury.objects.filter(player=player).order_by('-injury_date')
        
        # Career History (Tournaments where his team participated)
        # We assume the player was in the team during those tournaments.
        # For a more precise history, we would need a TournamentPlayer model, 
        # but using team history is a good approximation for this app.
        ctx['tournament_history'] = (
            TournamentTeam.objects.filter(team=player.team, is_confirmed=True)
            .select_related('tournament')
            .order_by('-tournament__year', '-tournament__edition')
        )
        
        # Championships won by his team
        ctx['trophies_won'] = Tournament.objects.filter(winner=player.team, status=Tournament.Status.FINISHED)
        
        ctx['recent_goals']  = (
            Goal.objects.filter(player=player)
            .select_related('match__team1', 'match__team2', 'match__tournament')
            .order_by('-match__match_date')[:5]
        )
        
        ctx['can_manage'] = (
            self.request.user.is_authenticated and (
                self.request.user.role in ('admin', 'organizer') or
                (self.request.user.role == 'manager' and
                 player.team.manager == self.request.user)
            )
        )
        return ctx


class PlayerCreateView(CanManageTeamMixin, CreateView):
    model = Player
    form_class = PlayerForm
    template_name = 'teams/player_form.html'

    def get_team(self):
        return get_object_or_404(Team, pk=self.kwargs['team_pk'])

    # Pass team_pk as pk for permission check
    def test_func(self):
        self.kwargs['pk'] = self.kwargs.get('team_pk')
        return super().test_func()

    def form_valid(self, form):
        team = self.get_team()
        form.instance.team = team
        messages.success(
            self.request,
            f'✅ Joueur « {form.instance.full_name} » ajouté à {team.name}!'
        )
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.initial['team'] = self.get_team()
        return form

    def get_success_url(self):
        return reverse('teams:player_list', kwargs={'team_pk': self.kwargs['team_pk']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['team']       = self.get_team()
        ctx['page_title'] = _('Nouveau joueur / لاعب جديد')
        ctx['action']     = 'create'
        return ctx


class PlayerUpdateView(CanManageTeamMixin, UpdateView):
    model = Player
    form_class = PlayerForm
    template_name = 'teams/player_form.html'

    def get_success_url(self):
        return reverse('teams:player_list', kwargs={'team_pk': self.object.team.pk})

    def form_valid(self, form):
        messages.success(self.request, f'✅ Joueur « {form.instance.full_name} » mis à jour!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['team']       = self.object.team
        ctx['page_title'] = _('Modifier le joueur / تعديل اللاعب')
        ctx['action']     = 'update'
        return ctx


class PlayerDeleteView(CanManageTeamMixin, DeleteView):
    model = Player
    template_name = 'teams/confirm_delete.html'

    def get_success_url(self):
        return reverse('teams:player_list', kwargs={'team_pk': self.object.team.pk})

    def form_valid(self, form):
        name = self.object.full_name
        messages.success(self.request, f'🗑️ Joueur « {name} » supprimé.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['object_type'] = _('le joueur / اللاعب')
        return ctx


class PlayerToggleSuspendView(LoginRequiredMixin, View):
    """Quick toggle suspension status via POST."""

    def post(self, request, pk):
        player = get_object_or_404(Player, pk=pk)
        user   = request.user
        if not (user.role in ('admin', 'organizer') or
                (user.role == 'manager' and player.team.manager == user)):
            return JsonResponse({'error': 'Permission refusée'}, status=403)

        player.is_suspended = not player.is_suspended
        player.save(update_fields=['is_suspended'])
        status_label = 'suspendu' if player.is_suspended else 'actif'
        messages.success(request, f'Joueur {player.full_name} est maintenant {status_label}.')
        return JsonResponse({
            'is_suspended': player.is_suspended,
            'label': status_label,
        })


class PlayerToggleCaptainView(LoginRequiredMixin, View):
    """Quick toggle captain status via POST."""

    def post(self, request, pk):
        player = get_object_or_404(Player, pk=pk)
        user   = request.user
        if not (user.role in ('admin', 'organizer') or
                (user.role == 'manager' and player.team.manager == user)):
            return JsonResponse({'error': 'Permission refusée'}, status=403)

        player.is_captain = not player.is_captain
        player.save()  # Full save to run the custom captain exclusivity check

        status_label = 'capitaine' if player.is_captain else 'non-capitaine'
        if player.is_captain:
            messages.success(request, f'Joueur {player.full_name} est maintenant le capitaine de l\'équipe.')
        else:
            messages.success(request, f'Joueur {player.full_name} n\'est plus le capitaine.')

        return JsonResponse({
            'is_captain': player.is_captain,
            'label': status_label,
        })


class TeamRegistrationView(LoginRequiredMixin, UpdateView):
    """Public-facing team registration/update for active tournaments."""
    model = Team
    form_class = TeamForm
    template_name = 'teams/registration.html'

    def get_object(self, queryset=None):
        """If manager has a team, return it for editing. Otherwise return None for creation."""
        if self.request.user.role == 'manager':
            return Team.objects.filter(manager=self.request.user).first()
        return None

    def get_tournament(self):
        from apps.tournaments.models import Tournament
        # Get the latest tournament that is open for registration
        tournament = Tournament.objects.filter(
            status=Tournament.Status.REGISTRATION
        ).order_by('-year', '-edition').first()
        return tournament

    def dispatch(self, request, *args, **kwargs):
        tournament = self.get_tournament()
        if not tournament or not tournament.is_registration_open:
            messages.warning(request, _('Les inscriptions sont actuellement fermées.'))
            return redirect('teams:list')
        
        # Check authentication first
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
            
        # Check if user is a manager or admin
        if request.user.role not in ('manager', 'admin', 'organizer'):
            messages.error(request, _('Seuls les responsables d\'équipe peuvent inscrire une équipe.'))
            return redirect('teams:list')

        # If they already have a confirmed participation in this tournament, redirect
        team = self.get_object()
        if team:
            from apps.tournaments.models import TournamentTeam
            if TournamentTeam.objects.filter(tournament=tournament, team=team, is_confirmed=True).exists():
                messages.info(request, _('Votre équipe est déjà inscrite et confirmée pour ce tournoi.'))
                return redirect('teams:detail', pk=team.pk)

        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # If it's a create case (no object), we don't pass instance
        if not self.get_object():
            kwargs.pop('instance', None)
        return kwargs

    def form_valid(self, form):
        from apps.tournaments.models import TournamentTeam
        from apps.notifications.models import Notification
        from apps.accounts.models import User
        
        tournament = self.get_tournament()
        
        # Set manager if new team
        if not self.object and self.request.user.role == 'manager':
            form.instance.manager = self.request.user
        
        response = super().form_valid(form)
        
        # Register/Update team participation in tournament (as pending)
        tt, created = TournamentTeam.objects.get_or_create(
            tournament=tournament,
            team=self.object
        )
        if not tt.is_confirmed:
            tt.notes = self.request.POST.get('registration_notes', '')
            tt.save()
        
        # Notify Admins
        admins = User.objects.filter(role='admin')
        action_label = _('mise à jour') if not created else _('nouvelle')
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                notif_type=Notification.Type.TEAM_REGISTRATION,
                title=_('Inscription %s : %s') % (action_label, self.object.name),
                message=_('Le club « %s » (%s) a soumis une demande pour %s. Veuillez valider.') % (
                    self.object.name, self.object.neighborhood, tournament.name
                ),
                link=reverse('tournaments:admin_panel')
            )
        
        messages.success(self.request, _('✅ Votre demande a été enregistrée ! En attente de validation par l\'administrateur.'))
        return response

    def get_success_url(self):
        return reverse('teams:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tournament'] = self.get_tournament()
        ctx['page_title'] = _('Inscription / Mise à jour d\'équipe')
        ctx['is_update'] = self.object is not None
        return ctx


class PlayerPrintView(CanManageTeamMixin, DetailView):
    """Clean, print-optimized view of a team's player list."""
    model = Team
    template_name = 'teams/player_print.html'
    context_object_name = 'team'
    pk_url_kwarg = 'team_pk'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        team = self.object
        ctx['players'] = team.players.filter(is_active=True).order_by('jersey_number')
        
        # Get active tournament
        from apps.tournaments.models import Tournament, TournamentTeam
        
        tournament_id = self.request.GET.get('tournament')
        if tournament_id:
            ctx['tournament'] = Tournament.objects.filter(pk=tournament_id).first()
        else:
            # 1. Get the most recent tournament this team is participating in
            tt = TournamentTeam.objects.filter(
                team=team, is_confirmed=True
            ).select_related('tournament').order_by('-tournament__year', '-tournament__edition').first()
            
            if tt:
                ctx['tournament'] = tt.tournament
            else:
                # 2. Fallback to the latest active tournament
                ctx['tournament'] = Tournament.objects.filter(
                    status__in=['registration', 'group_stage', 'knockout']
                ).order_by('-year', '-edition').first()
        
        return ctx


class TeamApprovalListView(AdminOrOrgMixin, ListView):
    """List of teams waiting for approval."""
    model = Team
    template_name = 'teams/approval_list.html'
    context_object_name = 'pending_teams'

    def get_queryset(self):
        return Team.objects.filter(is_active=False).order_by('-created_at')


class TeamApprovalActionView(AdminOrOrgMixin, View):
    """Approve or Reject a team."""

    def post(self, request, pk):
        team = get_object_or_404(Team, pk=pk)
        action = request.POST.get('action')

        if action == 'approve':
            team.is_active = True
            team.save(update_fields=['is_active'])
            messages.success(request, _('✅ L\'équipe « %s » a été activée.') % team.name)
            # Notify manager
            if team.manager:
                from apps.notifications.models import Notification
                Notification.objects.create(
                    recipient=team.manager,
                    notif_type=Notification.Type.TOURNAMENT,
                    title=_('Équipe activée !'),
                    message=_('Bonne nouvelle ! Votre équipe « %s » a été validée par l\'administrateur.') % team.name
                )
        elif action == 'reject':
            name = team.name
            team.delete()
            messages.warning(request, _('🗑️ L\'inscription de « %s » a été rejetée et supprimée.') % name)

        return redirect('teams:approval_list')


# ─── GLOBAL SEARCH ───────────────────────────────────────────────────────────

class GlobalSearchView(View):
    """Live JSON search for teams, players, tournaments, and matches."""

    def get(self, request):
        q = request.GET.get('q', '').strip()
        if len(q) < 2:
            return JsonResponse({'teams': [], 'players': [], 'tournaments': [], 'matches': []})

        from apps.tournaments.models import Tournament
        from apps.matches.models import Match
        from django.db.models import Value
        from django.db.models.functions import Concat

        teams = list(
            Team.objects.filter(
                Q(name__icontains=q) | Q(neighborhood__icontains=q),
                is_active=True
            ).values('id', 'name', 'neighborhood', 'color_primary')[:5]
        )
        players = list(
            Player.objects.annotate(
                full_name=Concat('first_name', Value(' '), 'last_name')
            ).filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(full_name__icontains=q) | Q(jersey_number__icontains=q),
                is_active=True
            ).select_related('team')
            .values('id', 'first_name', 'last_name', 'position', 'jersey_number', 'team__name')[:5]
        )
        tournaments = list(
            Tournament.objects.filter(
                Q(name__icontains=q) | Q(year__icontains=q) | Q(location__icontains=q)
            ).values('id', 'name', 'year', 'edition', 'status')[:4]
        )

        matches_qs = Match.objects.filter(
            team1__isnull=False,
            team2__isnull=False
        ).filter(
            Q(team1__name__icontains=q) | Q(team2__name__icontains=q) | Q(venue__icontains=q)
        ).select_related('team1', 'team2', 'tournament')

        matches = []
        for m in matches_qs[:4]:
            matches.append({
                'id': m.id,
                'team1__name': m.team1.name if m.team1 else '',
                'team2__name': m.team2.name if m.team2 else '',
                'score_team1': m.score_team1,
                'score_team2': m.score_team2,
                'status': m.status,
                'tournament__name': m.tournament.name if m.tournament else ''
            })

        return JsonResponse({
            'teams': teams,
            'players': players,
            'tournaments': tournaments,
            'matches': matches
        })


class TeamLineupView(CanManageTeamMixin, DetailView):
    """Visual lineup manager for team managers."""
    model = Team
    template_name = 'teams/lineup_manager.html'
    context_object_name = 'team'

    def post(self, request, *args, **kwargs):
        """Save player positions and starter status."""
        team = self.get_object()
        import json
        try:
            data = json.loads(request.body)
            formation = data.get('formation')
            lineup = data.get('lineup', []) # List of {id, x, y, is_starter}

            if formation:
                team.preferred_formation = formation
                team.save(update_fields=['preferred_formation'])

            # Validate lineup: no suspended players as starters
            from django.db.models import Q
            from apps.matches.models import Match
            from apps.matches.services.suspension import get_player_suspension_status
            next_match = Match.objects.filter(
                Q(team1=team) | Q(team2=team),
                status__in=[Match.Status.SCHEDULED, Match.Status.LIVE]
            ).order_by('match_date', 'id').first()

            for item in lineup:
                is_starter = item.get('is_starter', True)
                if is_starter:
                    player = Player.objects.filter(id=item['id'], team=team).first()
                    if player:
                        st = get_player_suspension_status(player, next_match) if next_match else {'is_suspended': player.is_suspended, 'reason': 'معاقب', 'short_reason': 'معاقب'}
                        if st['is_suspended']:
                            reason_txt = st.get('short_reason') or st.get('reason') or 'معاقب'
                            return JsonResponse({
                                'status': 'error', 
                                'message': _("اللاعب %s معاقب (%s) ولا يمكن وضعه في التشكيلة الأساسية.") % (player.full_name, reason_txt)
                            }, status=400)

            # Update positions and starters
            for item in lineup:
                Player.objects.filter(id=item['id'], team=team).update(
                    lineup_x=item['x'],
                    lineup_y=item['y'],
                    is_starter=item.get('is_starter', True)
                )
            
            # Mark others as not starters
            player_ids = [item['id'] for item in lineup]
            team.players.exclude(id__in=player_ids).update(is_starter=False)

            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        team = self.object
        from django.db.models import Q
        from apps.matches.models import Match
        from apps.matches.services.suspension import get_player_suspension_status
        next_match = Match.objects.filter(
            Q(team1=team) | Q(team2=team),
            status__in=[Match.Status.SCHEDULED, Match.Status.LIVE]
        ).order_by('match_date', 'id').first()

        players = list(team.players.filter(is_active=True))
        for p in players:
            p.suspension_status = get_player_suspension_status(p, next_match) if next_match else {'is_suspended': p.is_suspended, 'reason': 'معاقب' if p.is_suspended else None}

        ctx['next_match'] = next_match
        ctx['players'] = players
        ctx['starters'] = [p for p in players if p.is_starter]
        ctx['bench'] = [p for p in players if not p.is_starter]
        ctx['formations'] = ['4-3-3', '4-4-2', '3-5-2', '4-2-3-1', '5-3-2', '3-4-3']
        return ctx

class GlobalRankingView(ListView):
    """Public page to show the global ranking of all teams based on trophies and match stats."""
    model = Team
    template_name = 'teams/global_ranking.html'
    context_object_name = 'teams'

    def get_queryset(self):
        from apps.tournaments.models import Tournament
        from django.db.models import Count, Q
        
        return Team.objects.filter(is_active=True).annotate(
            trophies_count=Count('trophies', filter=Q(trophies__status=Tournament.Status.FINISHED)),
            participations_count=Count('tournament_teams', filter=Q(tournament_teams__is_confirmed=True))
        ).order_by('-trophies_count', '-participations_count', 'name')
