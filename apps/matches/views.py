from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from django.utils.translation import gettext as _

from apps.matches.models import Match, Goal, Card, Injury, PlayerMatchPerformance, Referee, MatchEvent
from apps.teams.models import Team, Player
from apps.tournaments.models import Tournament


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class MatchCalendarView(TemplateView):
    template_name = 'matches/calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tournament_id = self.request.GET.get('tournament')
        stage  = self.request.GET.get('stage', '')
        group_id = self.request.GET.get('group', '')
        day    = self.request.GET.get('day', '')

        if tournament_id:
            tournament = get_object_or_404(Tournament, pk=tournament_id)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.GROUP_STAGE,
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition').first()
            )

        ctx['tournament'] = tournament
        ctx['tournaments'] = Tournament.objects.order_by('-year', '-edition')

        if tournament:
            # Participating Teams
            ctx['participating_teams'] = (
                tournament.tournament_teams
                .filter(is_confirmed=True)
                .select_related('team')
                .order_by('team__name')
            )
            
            # Tournament Groups
            from django.db.models import Prefetch
            from apps.tournaments.models import GroupStanding
            
            ctx['groups'] = (
                tournament.groups.prefetch_related(
                    'groupstanding_set__team'
                )
            )

            qs = (
                Match.objects
                .filter(tournament=tournament)
                .select_related('team1', 'team2', 'group')
                .prefetch_related('goals', 'cards')
                .order_by('match_date')
            )
            if stage:
                qs = qs.filter(stage=stage)
            if group_id:
                qs = qs.filter(group_id=group_id)
            if day:
                qs = qs.filter(match_day=day)

            ctx['matches']      = qs
            ctx['stages']       = Match.Stage.choices
            ctx['match_days']   = (
                Match.objects.filter(tournament=tournament)
                .values_list('match_day', flat=True)
                .distinct()
                .order_by('match_day')
            )
            ctx['selected_stage'] = stage
            ctx['selected_group'] = group_id
            ctx['selected_day']   = day

            # Bracket Logic
            knockout_qs = (
                Match.objects.filter(tournament=tournament)
                .exclude(stage=Match.Stage.GROUP)
                .select_related('team1', 'team2')
            )
            
            # Define round order for the bracket
            round_order = ['R16', 'QF', 'SF', 'FINAL', 'TP']
            bracket = {}
            for r_code in round_order:
                stage_matches = [m for m in knockout_qs if m.stage == r_code]
                if stage_matches:
                    label = dict(Match.Stage.choices).get(r_code, r_code)
                    bracket[r_code] = {
                        'label': label,
                        'matches': sorted(stage_matches, key=lambda x: x.match_date)
                    }
            ctx['bracket'] = bracket
        return ctx


class MatchDetailView(DetailView):
    model = Match
    template_name = 'matches/detail.html'
    context_object_name = 'match'

    def get_queryset(self):
        return (
            Match.objects
            .select_related(
                'team1', 'team2', 'tournament', 'group', 'referee__user'
            )
            .prefetch_related(
                'goals__player', 'goals__team', 'goals__assist_player',
                'cards__player', 'cards__team',
                'injuries__player',
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        match = self.object
        ctx['team1_goals'] = match.goals.filter(team=match.team1).exclude(goal_type='own_goal')
        ctx['team2_goals'] = match.goals.filter(team=match.team2).exclude(goal_type='own_goal')
        ctx['team1_cards'] = match.cards.filter(team=match.team1)
        ctx['team2_cards'] = match.cards.filter(team=match.team2)
        can_edit = (
            self.request.user.is_authenticated and
            self.request.user.role in ('admin', 'organizer')
        )
        ctx['can_edit'] = can_edit
        
        if can_edit:
            from .forms import GoalForm, CardForm, MatchMediaForm
            ctx['goal_form'] = GoalForm(match=match)
            ctx['card_form'] = CardForm(match=match)
            ctx['media_form'] = MatchMediaForm()
            from .models import Referee
            ctx['all_referees'] = Referee.objects.select_related('user').all()
            ctx['team1_players'] = match.team1.players.filter(is_active=True)
            ctx['team2_players'] = match.team2.players.filter(is_active=True)
            
        ctx['media'] = match.media.all()
        from .services.suspension import get_suspended_players_for_match
        ctx['suspended_players'] = get_suspended_players_for_match(match)

        # Build unified timeline
        goals = list(match.goals.all())
        for g in goals: g.type = 'goal'
        
        cards = list(match.cards.all())
        for c in cards: c.type = 'card'

        generic_events = list(match.timeline_events.all())
        for e in generic_events: e.type = 'generic_event'
        
        ctx['all_events'] = sorted(
            goals + cards + generic_events,
            key=lambda x: (x.minute, getattr(x, 'created_at', None) or x.id)
        )
        
        # Tactical Lineup
        ctx['performances'] = match.performances.select_related('player', 'player__team').all()
        ctx['team1_lineup'] = ctx['performances'].filter(player__team=match.team1)
        ctx['team2_lineup'] = ctx['performances'].filter(player__team=match.team2)
        
        # Players available (not in lineup)
        ctx['team1_available'] = Player.objects.filter(team=match.team1).exclude(performances__match=match)
        ctx['team2_available'] = Player.objects.filter(team=match.team2).exclude(performances__match=match)
        
        # All active players for forms (goals, cards, etc.)
        ctx['team1_all_players'] = Player.objects.filter(team=match.team1, is_active=True).order_by('jersey_number')
        ctx['team2_all_players'] = Player.objects.filter(team=match.team2, is_active=True).order_by('jersey_number')
        
        # Fan Voting Calculations
        ip = get_client_ip(self.request)
        ctx['has_voted'] = match.votes.filter(user_ip=ip).exists()
        
        from django.db.models import Count
        total_votes = match.votes.count()
        ctx['total_votes'] = total_votes
        
        votes_by_player = (
            match.votes.values('player_id')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        votes_dict = {v['player_id']: v['count'] for v in votes_by_player}
        
        performances_with_votes = []
        for perf in ctx['performances']:
            p_votes = votes_dict.get(perf.player_id, 0)
            pct = (p_votes / total_votes * 100) if total_votes > 0 else 0
            perf.vote_count = p_votes
            perf.vote_percent = round(pct, 1)
            performances_with_votes.append(perf)
            
        ctx['performances_with_votes'] = sorted(performances_with_votes, key=lambda x: x.vote_count, reverse=True)
        
        return ctx


class EnterScoreView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to submit match score from the web UI."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        s1_raw = request.POST.get('score_team1', '').strip()
        s2_raw = request.POST.get('score_team2', '').strip()

        if not s1_raw and not s2_raw:
            messages.error(request, 'Veuillez saisir au moins un score / يرجى إدخال نتيجة واحدة على الأقل.')
            return redirect('matches:detail', pk=pk)

        try:
            # Handle possible float strings or empty values
            s1 = int(float(s1_raw)) if s1_raw else 0
            s2 = int(float(s2_raw)) if s2_raw else 0
            
            if s1 < 0 or s2 < 0:
                raise ValueError("Negative score")
                
        except (ValueError, TypeError):
            messages.error(request, 'Scores invalides (entrez des nombres entiers positifs) / نتائج غير صالحة (أدخل أرقاماً صحيحة).')
            return redirect('matches:detail', pk=pk)

        match.score_team1 = s1
        match.score_team2 = s2
        match.status = Match.Status.FINISHED
        match.save()

        # Recalculate group standings if in group
        if match.group:
            from apps.tournaments.services.scheduler import StandingsCalculator
            calc = StandingsCalculator(match.tournament)
            calc.recalculate_group(match.group)

        messages.success(request, f'✅ Score enregistré : {match.score_display} / تم حفظ النتيجة بنجاح')
        return redirect('matches:detail', pk=pk)


class SetForfeitView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST view to declare match forfeiture (TEAM1, TEAM2, or BOTH)."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        forfeit_type = request.POST.get('forfeit_type', 'NONE').strip()
        reason = request.POST.get('forfeit_reason', '').strip()
        official_notes = request.POST.get('official_report_notes', '').strip()

        if forfeit_type not in dict(Match.ForfeitType.choices):
            messages.error(request, '❌ نوع الغياب أو الاعتذار غير صالحة')
            return redirect('matches:detail', pk=pk)

        match.forfeit_type = forfeit_type
        match.forfeit_reason = reason
        match.official_report_notes = official_notes

        if forfeit_type == Match.ForfeitType.NONE:
            messages.success(request, '✅ تم إلغاء قرار الاعتذار/الغياب وإعادة المباراة للوضع العادي.')
        else:
            match.status = Match.Status.FINISHED
            if forfeit_type == Match.ForfeitType.TEAM1:
                match.score_team1 = 0
                match.score_team2 = 3
            elif forfeit_type == Match.ForfeitType.TEAM2:
                match.score_team1 = 3
                match.score_team2 = 0
            elif forfeit_type == Match.ForfeitType.BOTH:
                match.score_team1 = 0
                match.score_team2 = 0

            messages.success(
                request,
                f'⚖️ تم توثيق القرار الإداري والرسمي ({match.get_forfeit_type_display()}) بنجاح!'
            )

        match.save()

        # Recalculate group standings if match is in group stage
        if match.group:
            from apps.tournaments.services.scheduler import StandingsCalculator
            calc = StandingsCalculator(match.tournament)
            calc.recalculate_group(match.group)

        return redirect('matches:detail', pk=pk)


class AddGoalView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to add a goal to a match."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        from .forms import GoalForm
        form = GoalForm(request.POST, match=match)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.match = match
            # If it's an own goal, the scoring team is the opponent
            if goal.goal_type == Goal.GoalType.OWN_GOAL:
                goal.team = match.team1 if goal.player.team == match.team2 else match.team2
            else:
                goal.team = goal.player.team
            goal.save()
            messages.success(request, '⚽ الهدف مسجل! / But ajouté avec succès !')
        else:
            messages.error(request, '❌ Error: ' + str(form.errors))
        return redirect('matches:detail', pk=pk)


class AddCardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to add a card to a match."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        from .forms import CardForm
        form = CardForm(request.POST, match=match)
        if form.is_valid():
            card = form.save(commit=False)
            card.match = match
            card.team = card.player.team
            card.save()
            messages.success(request, '🟨/🟥 بطاقة مسجلة! / Carton ajouté avec succès !')
        else:
            messages.error(request, '❌ Error: ' + str(form.errors))
        return redirect('matches:detail', pk=pk)


class AddMatchMediaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to add media (photo/video) to a match."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        from .forms import MatchMediaForm
        form = MatchMediaForm(request.POST, request.FILES)
        if form.is_valid():
            media = form.save(commit=False)
            media.match = match
            media.save()
            messages.success(request, 'تم رفع الملف بنجاح! / Média ajouté avec succès !')
        else:
            messages.error(request, '❌ Error: ' + str(form.errors))
        return redirect('matches:detail', pk=pk)


class DeleteMatchMediaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to delete media from a match."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        from .models import MatchMedia
        media = get_object_or_404(MatchMedia, pk=pk)
        match_pk = media.match.pk
        media.delete()
        messages.success(request, '🗑️ تم حذف الملف بنجاح! / Média supprimé avec succès !')
        return redirect('matches:detail', pk=match_pk)


class UpdateScheduleView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to update match date and venue."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        new_date = request.POST.get('match_date')
        new_venue = request.POST.get('venue')
        new_referee = request.POST.get('referee')
        
        try:
            if new_date:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(new_date)
                if dt:
                    match.match_date = dt
            if new_venue:
                match.venue = new_venue
            if new_referee:
                if new_referee == 'none':
                    match.referee = None
                else:
                    from .models import Referee
                    match.referee = get_object_or_404(Referee, pk=int(new_referee))
            match.save()
            messages.success(request, '📅 التاريخ والمكان والحكم تم تحديثهم! / Date, Lieu et Arbitre mis à jour !')
        except Exception as e:
            messages.error(request, '❌ حدث خطأ أثناء التحديث / Erreur lors de la mise à jour.')
            
        return redirect('matches:detail', pk=pk)


class UpdatePenaltiesView(LoginRequiredMixin, View):
    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        if match.stage == 'GROUP':
            messages.error(request, '❌ لا توجد ركلات ترجيح في المجموعات.')
            return redirect('matches:detail', pk=pk)
            
        p1 = request.POST.get('penalties_team1')
        p2 = request.POST.get('penalties_team2')
        seq1 = request.POST.get('penalties_seq_team1')
        seq2 = request.POST.get('penalties_seq_team2')
        
        try:
            match.penalties_team1 = int(p1) if p1 else 0
            match.penalties_team2 = int(p2) if p2 else 0
            
            if seq1 and seq2:
                import json
                try:
                    match.promo_config = match.promo_config or {}
                    match.promo_config['penalties_seq_team1'] = json.loads(seq1)
                    match.promo_config['penalties_seq_team2'] = json.loads(seq2)
                except Exception:
                    pass
                    
            match.save()
            messages.success(request, '✅ تم تسجيل ركلات الترجيح / Penalties enregistrés.')
        except ValueError:
            messages.error(request, '❌ قيمة غير صالحة / Valeur invalide.')
            
        return redirect('matches:detail', pk=pk)



class StatsView(TemplateView):
    template_name = 'matches/stats.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Count, Sum, Avg, Q, F
        from apps.teams.models import Player, Team
        from apps.matches.models import Match, Goal, Card, PlayerMatchPerformance, Injury
        from apps.tournaments.models import GroupStanding, Tournament

        tournament_id = self.request.GET.get('tournament')
        if tournament_id:
            tournament = get_object_or_404(Tournament, pk=tournament_id)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.GROUP_STAGE,
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition').first()
            )
            if not tournament:
                tournament = Tournament.objects.order_by('-year', '-edition').first()

        ctx['tournament'] = tournament
        ctx['tournaments'] = Tournament.objects.order_by('-year', '-edition')

        if tournament:
            finished_matches = Match.objects.filter(tournament=tournament, status=Match.Status.FINISHED)
            total_matches_played = finished_matches.count()
            all_tournament_matches = Match.objects.filter(tournament=tournament)
            total_matches_count = all_tournament_matches.count()

            # -------------------------------------------------------------
            # GENERAL TOURNAMENT OVERVIEW (إحصائيات عامة للدورة)
            # -------------------------------------------------------------
            all_goals = Goal.objects.filter(match__tournament=tournament)
            total_goals = all_goals.count()
            avg_goals_per_match = round(total_goals / total_matches_played, 2) if total_matches_played > 0 else 0
            
            all_cards = Card.objects.filter(match__tournament=tournament)
            total_yellow_cards = all_cards.filter(card_type='yellow').count()
            total_red_cards = all_cards.filter(card_type__in=['red', 'yellow_red']).count()
            total_cards = total_yellow_cards + total_red_cards
            avg_cards_per_match = round(total_cards / total_matches_played, 2) if total_matches_played > 0 else 0
            
            total_penalties = all_goals.filter(goal_type='penalty').count()
            
            total_participating_teams = tournament.tournament_teams.filter(is_confirmed=True).count()
            total_participating_players = Player.objects.filter(
                team__tournament_teams__tournament=tournament,
                team__tournament_teams__is_confirmed=True,
                is_active=True
            ).distinct().count()

            draws_count = finished_matches.filter(score_team1=F('score_team2')).count()
            decisive_matches_count = total_matches_played - draws_count
            draw_percentage = round((draws_count / total_matches_played) * 100, 1) if total_matches_played > 0 else 0
            win_percentage = round((decisive_matches_count / total_matches_played) * 100, 1) if total_matches_played > 0 else 0

            ctx['general_overview'] = {
                'total_matches_played': total_matches_played,
                'total_matches_count': total_matches_count,
                'total_goals': total_goals,
                'avg_goals_per_match': avg_goals_per_match,
                'total_yellow_cards': total_yellow_cards,
                'total_red_cards': total_red_cards,
                'total_cards': total_cards,
                'avg_cards_per_match': avg_cards_per_match,
                'total_penalties': total_penalties,
                'total_teams': total_participating_teams,
                'total_players': total_participating_players,
                'draws_count': draws_count,
                'decisive_count': decisive_matches_count,
                'draw_percentage': draw_percentage,
                'win_percentage': win_percentage,
            }

            # -------------------------------------------------------------
            # 1. TEAM STATISTICS (إحصائيات الفرق)
            # -------------------------------------------------------------
            team_standings = GroupStanding.objects.filter(group__tournament=tournament).select_related('team')
            teams_data = []
            
            for st in team_standings:
                team = st.team
                cs_count = finished_matches.filter(
                    Q(team1=team, score_team2=0) | Q(team2=team, score_team1=0)
                ).count()
                
                team_cards_cnt = all_cards.filter(team=team).count()
                w_rate = round((st.won / st.played * 100), 1) if st.played > 0 else 0
                avg_gf = round(st.goals_for / st.played, 2) if st.played > 0 else 0

                # Biggest win for this team
                team_finished = finished_matches.filter(Q(team1=team) | Q(team2=team))
                biggest_win_str = "—"
                max_diff = 0
                for m in team_finished:
                    if m.winner == team:
                        diff = abs(m.score_team1 - m.score_team2)
                        if diff > max_diff:
                            max_diff = diff
                            opp = m.team2 if m.team1 == team else m.team1
                            score_str = f"{m.score_team1}-{m.score_team2}" if m.team1 == team else f"{m.score_team2}-{m.score_team1}"
                            biggest_win_str = f"{score_str} ضد {opp.name}"

                teams_data.append({
                    'team': team,
                    'played': st.played,
                    'won': st.won,
                    'drawn': st.drawn,
                    'lost': st.lost,
                    'goals_for': st.goals_for,
                    'goals_against': st.goals_against,
                    'goal_difference': st.goal_difference,
                    'points': st.points,
                    'win_rate': w_rate,
                    'avg_goals': avg_gf,
                    'clean_sheets': cs_count,
                    'cards_count': team_cards_cnt,
                    'biggest_win': biggest_win_str,
                })

            teams_data.sort(key=lambda x: (x['points'], x['goal_difference'], x['goals_for']), reverse=True)
            ctx['teams_stats'] = teams_data

            # Highlight teams
            best_attack_team = max(teams_data, key=lambda x: x['goals_for']) if teams_data else None
            best_defense_team = min(teams_data, key=lambda x: x['goals_against']) if teams_data else None
            most_carded_team = max(teams_data, key=lambda x: x['cards_count']) if teams_data else None
            fair_play_team = min(teams_data, key=lambda x: x['cards_count']) if teams_data else None

            ctx['team_highlights'] = {
                'best_attack': best_attack_team,
                'best_defense': best_defense_team,
                'most_carded': most_carded_team,
                'fair_play': fair_play_team,
            }

            # -------------------------------------------------------------
            # 2. PLAYER STATISTICS (إحصائيات اللاعبين)
            # -------------------------------------------------------------
            # Top Scorers
            top_scorers = (
                Goal.objects
                .filter(match__tournament=tournament)
                .exclude(goal_type='own_goal')
                .values('player__id', 'player__first_name', 'player__last_name',
                        'player__jersey_number', 'player__photo', 'team__name', 'team__logo',
                        'team__color_primary')
                .annotate(
                    goals=Count('id'),
                    penalties=Count('id', filter=Q(goal_type='penalty'))
                )
                .order_by('-goals', '-penalties')[:15]
            )
            ctx['top_scorers'] = top_scorers

            # Top Assisters
            top_assisters = (
                Goal.objects
                .filter(match__tournament=tournament, assist_player__isnull=False)
                .values('assist_player__id', 'assist_player__first_name',
                        'assist_player__last_name', 'assist_player__jersey_number',
                        'assist_player__photo', 'team__name', 'team__color_primary')
                .annotate(assists=Count('id'))
                .order_by('-assists')[:15]
            )
            ctx['top_assisters'] = top_assisters

            # Most MOTM (Man of the Match)
            from apps.matches.models import MatchVote
            most_motm = (
                MatchVote.objects
                .filter(match__tournament=tournament)
                .values('player__id', 'player__first_name', 'player__last_name', 'player__jersey_number', 'player__photo', 'player__team__name', 'player__team__logo')
                .annotate(motm_count=Count('id'))
                .order_by('-motm_count')[:10]
            )
            if not most_motm.exists():
                most_motm = (
                    PlayerMatchPerformance.objects
                    .filter(match__tournament=tournament, rating__gte=7.5)
                    .values('player__id', 'player__first_name', 'player__last_name', 'player__jersey_number', 'player__photo', 'player__team__name', 'player__team__logo')
                    .annotate(motm_count=Count('id'))
                    .order_by('-motm_count')[:10]
                )
            ctx['most_motm'] = most_motm

            # Player discipline (Most carded players)
            most_carded_players = (
                Card.objects
                .filter(match__tournament=tournament)
                .values('player__id', 'player__first_name', 'player__last_name', 'player__jersey_number', 'player__photo', 'team__name')
                .annotate(
                    yellows=Count('id', filter=Q(card_type='yellow')),
                    reds=Count('id', filter=Q(card_type__in=['red', 'yellow_red'])),
                    total=Count('id')
                )
                .order_by('-reds', '-yellows', '-total')[:10]
            )
            ctx['most_carded_players'] = most_carded_players
            ctx['most_carded'] = most_carded_players

            # Goalkeepers Clean Sheets & Rating
            gks = Player.objects.filter(position='GK', team__tournament_teams__tournament=tournament).distinct()
            gk_clean_sheets = []
            for gk in gks:
                sheets = finished_matches.filter(
                    Q(team1=gk.team, score_team2=0) | Q(team2=gk.team, score_team1=0)
                ).count()
                conceded = finished_matches.filter(team1=gk.team).aggregate(c=Sum('score_team2'))['c'] or 0
                conceded += finished_matches.filter(team2=gk.team).aggregate(c=Sum('score_team1'))['c'] or 0
                m_played = finished_matches.filter(Q(team1=gk.team) | Q(team2=gk.team)).count()
                
                if sheets > 0 or m_played > 0:
                    gk_clean_sheets.append({
                        'player': gk,
                        'player__id': gk.id,
                        'player__first_name': gk.first_name,
                        'player__last_name': gk.last_name,
                        'player__jersey_number': gk.jersey_number,
                        'player__photo': gk.photo.name if gk.photo else None,
                        'team__name': gk.team.name,
                        'team__logo': gk.team.logo,
                        'team__color_primary': gk.team.color_primary,
                        'sheets': sheets,
                        'conceded': conceded,
                        'matches': m_played,
                    })
            gk_clean_sheets.sort(key=lambda x: (x['sheets'], -x['conceded']), reverse=True)
            ctx['clean_sheets'] = gk_clean_sheets[:10]

            ctx['injuries'] = (
                Injury.objects
                .filter(match__tournament=tournament)
                .select_related('player__team')
                .order_by('-injury_date')[:10]
            )

            # -------------------------------------------------------------
            # 3. MATCH STATISTICS (إحصائيات المباريات)
            # -------------------------------------------------------------
            highest_scoring_match = finished_matches.annotate(
                total_goals_match=F('score_team1') + F('score_team2')
            ).order_by('-total_goals_match').first()

            biggest_margin_match = None
            max_margin = 0
            for m in finished_matches:
                margin = abs(m.score_team1 - m.score_team2)
                if margin > max_margin:
                    max_margin = margin
                    biggest_margin_match = m

            comeback_matches_count = finished_matches.filter(penalties_team1__isnull=False, penalties_team2__isnull=False).count()

            ctx['match_stats'] = {
                'highest_scoring_match': highest_scoring_match,
                'biggest_margin_match': biggest_margin_match,
                'max_margin': max_margin,
                'comeback_matches_count': comeback_matches_count,
            }

            # -------------------------------------------------------------
            # 4. GOAL TIMING STATISTICS (توقيت الأهداف)
            # -------------------------------------------------------------
            interval_definitions = [
                ('0 – 10 دقيقة', 1, 10, 'bg-primary', 'text-primary'),
                ('11 – 20 دقيقة', 11, 20, 'bg-blue-500', 'text-blue-400'),
                ('21 – 30 دقيقة', 21, 30, 'bg-green-500', 'text-green-400'),
                ('31 – 40 دقيقة', 31, 40, 'bg-yellow-500', 'text-yellow-400'),
                ('41 – 50 دقيقة', 41, 50, 'bg-purple-500', 'text-purple-400'),
                ('51+ (الوقت الإضافي)', 51, 200, 'bg-red-500', 'text-red-400'),
            ]

            interval_list = []
            max_count = -1
            peak_label = '0 – 10 دقيقة'
            for label, min_m, max_m, bg_color, text_color in interval_definitions:
                cnt = all_goals.filter(minute__gte=min_m, minute__lte=max_m).count()
                pct = round((cnt / total_goals * 100), 1) if total_goals > 0 else 0
                if cnt > max_count:
                    max_count = cnt
                    peak_label = label
                interval_list.append({
                    'label': label,
                    'count': cnt,
                    'pct': pct,
                    'bg_color': bg_color,
                    'text_color': text_color,
                })

            first_half_goals = all_goals.filter(minute__lte=25).count()
            second_half_goals = total_goals - first_half_goals

            ctx['goal_timing'] = {
                'interval_list': interval_list,
                'peak_interval': peak_label,
                'peak_count': max_count if max_count > 0 else 0,
                'first_half_goals': first_half_goals,
                'second_half_goals': second_half_goals,
                'first_half_pct': round((first_half_goals / total_goals * 100), 1) if total_goals > 0 else 0,
                'second_half_pct': round((second_half_goals / total_goals * 100), 1) if total_goals > 0 else 0,
            }

            # -------------------------------------------------------------
            # 5. OFFENSIVE GOAL TYPES (أنواع الأهداف)
            # -------------------------------------------------------------
            goal_types = {
                'normal': all_goals.filter(goal_type='normal').count(),
                'free_kick': all_goals.filter(goal_type='free_kick').count(),
                'penalty': all_goals.filter(goal_type='penalty').count(),
                'header': all_goals.filter(goal_type='header').count(),
                'own_goal': all_goals.filter(goal_type='own_goal').count(),
            }
            ctx['goal_types'] = goal_types

            # -------------------------------------------------------------
            # 7. AWARDS & TOURNAMENT HONORS (الجوائز والإحصائيات النهائية)
            # -------------------------------------------------------------
            top_scorer_obj = top_scorers.first() if top_scorers.exists() else None
            top_assister_obj = top_assisters.first() if top_assisters.exists() else None
            best_gk_obj = gk_clean_sheets[0] if gk_clean_sheets else None
            most_motm_obj = most_motm.first() if most_motm.exists() else None

            best_player_perf = (
                PlayerMatchPerformance.objects
                .filter(match__tournament=tournament)
                .values('player__id', 'player__first_name', 'player__last_name', 'player__jersey_number', 'player__photo', 'player__team__name')
                .annotate(avg_rating=Avg('rating'), matches_cnt=Count('id'))
                .order_by('-avg_rating', '-matches_cnt')
                .first()
            )

            ctx['awards'] = {
                'top_scorer': top_scorer_obj,
                'top_assister': top_assister_obj,
                'best_gk': best_gk_obj,
                'most_motm': most_motm_obj,
                'best_player': best_player_perf,
                'best_attack': best_attack_team,
                'best_defense': best_defense_team,
                'fair_play': fair_play_team,
            }

            # Team stats for chart.js
            ctx['team_stats'] = list(
                GroupStanding.objects.filter(group__tournament=tournament)
                .select_related('team')
                .values('team__name', 'goals_for', 'goals_against', 'points')
            )

        return ctx


class MatchSheetView(DetailView):
    """View to print a physical Match Sheet (Feuille de Match) for referees."""
    model = Match
    template_name = 'matches/match_sheet.html'
    context_object_name = 'match'

    def get_queryset(self):
        return Match.objects.select_related(
            'team1', 'team2', 'tournament', 'group', 'referee__user'
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        match = self.object
        from apps.matches.services.suspension import get_player_suspension_status, get_suspended_players_for_match
        
        # Get active players for both teams (with safety check for null teams)
        team1_players = list(match.team1.players.filter(is_active=True).order_by('-is_starter', 'jersey_number')) if match.team1 else []
        team2_players = list(match.team2.players.filter(is_active=True).order_by('-is_starter', 'jersey_number')) if match.team2 else []
        
        for p in team1_players:
            p.suspension_status = get_player_suspension_status(p, match)
        for p in team2_players:
            p.suspension_status = get_player_suspension_status(p, match)

        ctx['team1_players'] = team1_players
        ctx['team2_players'] = team2_players
        ctx['suspended_players'] = get_suspended_players_for_match(match)
        
        return ctx
class MatchPromoView(DetailView):
    """View to generate a cinematic vertical 'Match Day' promo story."""
    model = Match
    template_name = 'matches/promo.html'
    context_object_name = 'match'

    def get_queryset(self):
        return Match.objects.select_related('team1', 'team2', 'tournament')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        match = self.object
        ctx['team1_players'] = match.team1.players.filter(is_active=True) if match.team1 else []
        ctx['team2_players'] = match.team2.players.filter(is_active=True) if match.team2 else []
        ctx['all_referees'] = Referee.objects.select_related('user').all()
        return ctx

class ManOfTheMatchView(DetailView):
    """View to generate a high-fidelity 'Man of the Match' certificate and save official MOTM award."""
    model = Match
    template_name = 'matches/man_of_the_match.html'
    context_object_name = 'match'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        match = self.object
        
        team1_players = list(match.team1.players.filter(is_active=True)) if match.team1 else []
        team2_players = list(match.team2.players.filter(is_active=True)) if match.team2 else []
        ctx['team1_players'] = team1_players
        ctx['team2_players'] = team2_players
        ctx['all_players'] = team1_players + team2_players
        ctx['saved_motm'] = match.man_of_the_match

        player_id = self.request.GET.get('player')
        if player_id:
            ctx['player'] = get_object_or_404(Player, pk=player_id)
        elif match.man_of_the_match:
            ctx['player'] = match.man_of_the_match
        else:
            perf = match.performances.order_by('-rating').first()
            if perf:
                ctx['player'] = perf.player
            elif team1_players:
                ctx['player'] = team1_players[0]
            elif team2_players:
                ctx['player'] = team2_players[0]
        return ctx

    def post(self, request, *args, **kwargs):
        from django.http import JsonResponse
        from django.shortcuts import redirect
        from django.contrib import messages

        match = self.get_object()
        player_id = request.POST.get('player_id')
        
        if not player_id:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': 'لم يتم اختيار لاعب'}, status=400)
            messages.error(request, 'لم يتم اختيار لاعب رجل المباراة.')
            return redirect('matches:motm', pk=match.pk)

        player = get_object_or_404(Player, pk=player_id)
        match.man_of_the_match = player
        match.save(update_fields=['man_of_the_match'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'message': f'تم تسجيل وتثبيت {player.full_name} كرجل المباراة رسمياً 🏅',
                'player_id': player.pk,
                'player_name': player.full_name,
                'team_name': player.team.name if player.team else ''
            })

        messages.success(request, f'تم تسجيل وتثبيت {player.full_name} كرجل المباراة رسمياً 🏅')
        return redirect(f"{request.path}?player={player.pk}")

class BestGoalkeeperView(DetailView):
    """View to generate a high-fidelity 'Best Goalkeeper' certificate."""
    model = Match
    template_name = 'matches/best_goalkeeper.html'
    context_object_name = 'match'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        player_id = self.request.GET.get('player')
        if player_id:
            ctx['player'] = get_object_or_404(Player, pk=player_id)
        else:
            # Fallback to goalkeeper (GK) from either team
            match = self.object
            gks = Player.objects.filter(team__in=[match.team1, match.team2], position='GK', is_active=True)
            if gks.exists():
                ctx['player'] = gks.first()
            else:
                # Fallback to highest rated player if exists
                perf = self.object.performances.order_by('-rating').first()
                if perf:
                    ctx['player'] = perf.player
        return ctx


class RefereeCertificateView(DetailView):
    """View to generate a high-fidelity 'Referee' certificate."""
    model = Match
    template_name = 'matches/referee_certificate.html'
    context_object_name = 'match'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        referee_id = self.request.GET.get('referee')
        if referee_id:
            ctx['referee'] = get_object_or_404(Referee, pk=referee_id)
        else:
            ctx['referee'] = self.object.referee
        return ctx


class RefereeReportView(DetailView):
    """View to generate and download the official Match Referee Report (تقرير حكم المباراة)."""
    model = Match
    template_name = 'matches/referee_report.html'
    context_object_name = 'match'

    def get_queryset(self):
        return (
            Match.objects
            .select_related(
                'team1', 'team2', 'tournament', 'group', 'referee__user'
            )
            .prefetch_related(
                'goals__player', 'goals__team', 'goals__assist_player',
                'cards__player', 'cards__team',
                'injuries__player',
                'timeline_events__team', 'timeline_events__player1', 'timeline_events__player2',
                'performances__player',
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        match = self.object

        referee_id = self.request.GET.get('referee')
        if referee_id:
            ctx['referee'] = get_object_or_404(Referee, pk=referee_id)
        else:
            ctx['referee'] = match.referee

        ctx['team1_players'] = match.team1.players.filter(is_active=True).order_by('-is_starter', 'jersey_number') if match.team1 else []
        ctx['team2_players'] = match.team2.players.filter(is_active=True).order_by('-is_starter', 'jersey_number') if match.team2 else []

        ctx['team1_goals'] = match.goals.filter(team=match.team1).order_by('minute')
        ctx['team2_goals'] = match.goals.filter(team=match.team2).order_by('minute')
        ctx['all_goals'] = match.goals.all().order_by('minute')

        ctx['team1_cards'] = match.cards.filter(team=match.team1).order_by('minute')
        ctx['team2_cards'] = match.cards.filter(team=match.team2).order_by('minute')
        ctx['all_cards'] = match.cards.all().order_by('minute')

        ctx['all_events'] = match.timeline_events.all().order_by('minute', 'created_at')

        return ctx


class HonoraryCertificateView(DetailView):
    """View to generate a high-fidelity 'Honorary' certificate for personalities."""
    model = Match
    template_name = 'matches/honorary_certificate.html'
    context_object_name = 'match'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx


class UpdateLineupView(LoginRequiredMixin, View):
    """AJAX view to update player positions and starter status."""
    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        if not (request.user.is_staff or request.user.role in ('admin', 'organizer', 'manager')):
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
            
        import json
        data = json.loads(request.body)
        player_id = data.get('player_id')
        x = data.get('x')
        y = data.get('y')
        is_starter = data.get('is_starter', True)
        
        player = get_object_or_404(Player, pk=player_id)
        perf, created = PlayerMatchPerformance.objects.get_or_create(
            match=match, player=player
        )
        perf.x_pos = x
        perf.y_pos = y
        perf.is_starter = is_starter
        perf.save()
        
        return JsonResponse({'status': 'success'})

class RemoveFromLineupView(LoginRequiredMixin, View):
    """AJAX view to remove player from match lineup."""
    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        if not (request.user.is_staff or request.user.role in ('admin', 'organizer', 'manager')):
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
            
        import json
        data = json.loads(request.body)
        player_id = data.get('player_id')
        PlayerMatchPerformance.objects.filter(match=match, player_id=player_id).delete()
        return JsonResponse({'status': 'success'})

class ProcessCutoutView(View):
    """AJAX view to process a raw image and return a background-removed PNG as Base64."""
    def post(self, request):
        from django.http import JsonResponse
        if not request.FILES.get('image'):
            return JsonResponse({'status': 'error', 'message': 'No image provided'}, status=400)
            
        try:
            from apps.teams.utils import remove_player_background
            import base64
            
            image_file = request.FILES['image']
            processed_content = remove_player_background(image_file)
            
            if processed_content:
                encoded_string = base64.b64encode(processed_content.read()).decode('utf-8')
                return JsonResponse({
                    'status': 'success', 
                    'image': f"data:image/png;base64,{encoded_string}"
                })
            else:
                return JsonResponse({'status': 'error', 'message': 'Processing failed'}, status=500)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

class SavePromoConfigView(LoginRequiredMixin, View):
    """AJAX view to save the promo configuration for a match."""
    def post(self, request, pk):
        if not (request.user.is_staff or request.user.role in ('admin', 'organizer')):
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
            
        import json
        try:
            data = json.loads(request.body)
            match = get_object_or_404(Match, pk=pk)
            config_data = data.get('config', {})
            match.promo_config = config_data
            
            referee_id = config_data.get('referee_id')
            if referee_id is not None:
                if str(referee_id) in ('none', '', 'null'):
                    match.referee = None
                else:
                    try:
                        match.referee_id = int(referee_id)
                    except (ValueError, TypeError):
                        match.referee = None
            
            match.save()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class MatchVoteView(View):
    """View to allow fans to vote for Man of the Match (MOTM)."""
    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        player_id = request.POST.get('player_id')
        if not player_id:
            return JsonResponse({'status': 'error', 'message': _('Veuillez sélectionner un joueur / الرجاء اختيار لاعب')}, status=400)
            
        player = get_object_or_404(Player, pk=player_id)
        ip = get_client_ip(request)
        
        # Check if already voted
        from apps.matches.models import MatchVote
        if MatchVote.objects.filter(match=match, user_ip=ip).exists():
            return JsonResponse({'status': 'error', 'message': _('Vous avez déjà voté pour ce match / لقد قمت بالتصويت بالفعل لهذه المباراة')}, status=400)
            
        MatchVote.objects.create(match=match, player=player, user_ip=ip)
        
        # Return updated voting results block for HTMX
        if request.headers.get('HX-Request') or request.META.get('HTTP_HX_REQUEST'):
            from django.db.models import Count
            total_votes = match.votes.count()
            votes_by_player = (
                match.votes.values('player_id')
                .annotate(count=Count('id'))
                .order_by('-count')
            )
            votes_dict = {v['player_id']: v['count'] for v in votes_by_player}
            
            performances = match.performances.select_related('player', 'player__team').all()
            performances_with_votes = []
            for perf in performances:
                p_votes = votes_dict.get(perf.player_id, 0)
                pct = (p_votes / total_votes * 100) if total_votes > 0 else 0
                perf.vote_count = p_votes
                perf.vote_percent = round(pct, 1)
                performances_with_votes.append(perf)
                
            performances_with_votes.sort(key=lambda x: x.vote_count, reverse=True)
            
            from django.shortcuts import render
            return render(request, 'matches/partials/vote_results.html', {
                'match': match,
                'has_voted': True,
                'total_votes': total_votes,
                'performances_with_votes': performances_with_votes,
            })
            
        return JsonResponse({'status': 'success'})


class AddGenericEventView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to add generic match events (kickoff, substitution, VAR, etc.)."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        event_type = request.POST.get('event_type')
        minute = request.POST.get('minute')
        team_id = request.POST.get('team')
        player1_id = request.POST.get('player1')
        player2_id = request.POST.get('player2')
        description = request.POST.get('description', '')
        description_ar = request.POST.get('description_ar', '')

        try:
            min_val = int(minute) if minute else 0
        except ValueError:
            messages.error(request, 'Minute invalide.')
            return redirect('matches:detail', pk=pk)

        team = None
        if team_id and team_id != 'none' and team_id != '':
            team = get_object_or_404(Team, pk=int(team_id))

        player1 = None
        if player1_id and player1_id != 'none' and player1_id != '':
            player1 = get_object_or_404(Player, pk=int(player1_id))

        player2 = None
        if player2_id and player2_id != 'none' and player2_id != '':
            player2 = get_object_or_404(Player, pk=int(player2_id))

        # Automatically generate descriptive text if empty
        event_labels_fr = dict(MatchEvent.EventType.choices)
        
        if event_type == 'substitution':
            if team:
                subs = MatchEvent.objects.filter(match=match, team=team, event_type='substitution')
                if subs.count() >= 5:
                    messages.error(request, '❌ لا يمكن إجراء التبديل: استنفد الفريق التغييرات الخمسة (5/5) المسموح بها! / L\'équipe a épuisé ses 5 remplacements !')
                    return redirect('matches:detail', pk=pk)
                
                # Check windows (max 3 windows, excluding halftime which we assume is minute 45)
                sub_minutes = set(subs.values_list('minute', flat=True))
                windows = {m for m in sub_minutes if m != 45}
                
                if len(windows) >= 3 and min_val not in windows and min_val != 45:
                    messages.error(request, '❌ لا يمكن إجراء التبديل: استنفد الفريق فترات التوقف الثلاث (3/3) المسموح بها! (التغييرات بين الشوطين لا تحتسب من الفترات) / 3 fenêtres épuisées !')
                    return redirect('matches:detail', pk=pk)

            if player1 and player2:
                if not description:
                    description = f"Changement : {player2.full_name} remplace {player1.full_name}"
                if not description_ar:
                    description_ar = f"تبديل: دخول {player2.full_name} خروج {player1.full_name}"
                
                # Add the incoming player to match performances so they can be rated
                from .models import PlayerMatchPerformance
                PlayerMatchPerformance.objects.get_or_create(
                    match=match, player=player2,
                    defaults={'is_starter': False, 'rating': 6.0}
                )
        elif event_type == 'kickoff':
            if not description:
                description = "Coup d'envoi du match !"
            if not description_ar:
                description_ar = "ركلة بداية اللقاء!"
        elif event_type == 'halftime':
            if not description:
                description = "Fin de la première période / Mi-temps"
            if not description_ar:
                description_ar = "نهاية الشوط الأول / الاستراحة"
        elif event_type == 'second_half':
            if not description:
                description = "Début de la seconde période"
            if not description_ar:
                description_ar = "بداية الشوط الثاني"
        elif event_type == 'fulltime':
            if not description:
                description = f"Fin du match ! Score final : {match.score_display}"
            if not description_ar:
                description_ar = f"نهاية المباراة! النتيجة النهائية: {match.score_display}"

        MatchEvent.objects.create(
            match=match,
            event_type=event_type,
            minute=min_val,
            team=team,
            player1=player1,
            player2=player2,
            description=description,
            description_ar=description_ar
        )

        # Trigger automatic status changes on match if applicable
        if event_type == 'kickoff':
            match.status = Match.Status.LIVE
            match.current_period = '1H'
            match.current_minute = 0
            match.save()
        elif event_type == 'halftime':
            match.current_period = 'HT'
            match.current_minute = 45
            match.save()
        elif event_type == 'second_half':
            match.current_period = '2H'
            match.current_minute = 46
            match.save()
        elif event_type == 'fulltime':
            match.status = Match.Status.FINISHED
            match.current_period = '2H'
            match.current_minute = 90
            match.save()

        messages.success(request, '✅ Événement ajouté avec succès ! / تم تسجيل الحدث بنجاح')
        return redirect('matches:detail', pk=pk)


class UpdateLiveTimerView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to update live match timer, minute and period."""

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        match = get_object_or_404(Match, pk=pk)
        status = request.POST.get('status')
        period = request.POST.get('period')
        minute = request.POST.get('minute')

        if status:
            match.status = status
        if period:
            match.current_period = period
        if minute is not None and minute != '':
            try:
                match.current_minute = int(minute)
            except ValueError:
                pass
        match.save()
        
        # If HTMX request, we can just return success or return the updated scoreboard capsule
        if request.headers.get('HX-Request') or request.META.get('HTTP_HX_REQUEST'):
            return JsonResponse({'status': 'success', 'minute': match.current_minute, 'period': match.get_current_period_display()})
            
        messages.success(request, '📅 Timer mis à jour ! / تم تحديث توقيت المباراة')
        return redirect('matches:detail', pk=pk)


class DeleteGoalView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to delete a goal directly from match detail timeline."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        goal = get_object_or_404(Goal, pk=pk)
        match_pk = goal.match.pk
        match = goal.match
        
        # Deduct score if match is saved
        if goal.team == match.team1 and match.score_team1 and match.score_team1 > 0:
            match.score_team1 -= 1
        elif goal.team == match.team2 and match.score_team2 and match.score_team2 > 0:
            match.score_team2 -= 1
        
        player_name = goal.player.full_name
        goal.delete()
        match.save()
        messages.success(request, f'🗑️ تم حذف هدف اللاعب «{player_name}» بنجاح / But supprimé.')
        return redirect('matches:detail', pk=match_pk)


class EditGoalView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to edit a goal directly from match detail timeline."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        goal = get_object_or_404(Goal, pk=pk)
        match_pk = goal.match.pk
        
        player_id = request.POST.get('player')
        minute = request.POST.get('minute')
        goal_type = request.POST.get('goal_type')
        assist_id = request.POST.get('assist_player')

        try:
            if player_id:
                goal.player = get_object_or_404(Player, pk=player_id)
                goal.team = goal.player.team
            if minute:
                goal.minute = int(minute)
            if goal_type:
                goal.goal_type = goal_type
            if assist_id is not None:
                if assist_id in ('none', '', 'null'):
                    goal.assist_player = None
                else:
                    goal.assist_player = get_object_or_404(Player, pk=assist_id)
            goal.save()
            messages.success(request, f'✅ تم تعديل بيانات الهدف بنجاح / But modifié.')
        except Exception as e:
            messages.error(request, f'❌ حدث خطأ أثناء التعديل: {e}')

        return redirect('matches:detail', pk=match_pk)


class DeleteCardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to delete a card directly from match detail timeline."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        card = get_object_or_404(Card, pk=pk)
        match_pk = card.match.pk
        player_name = card.player.full_name
        card.delete()
        messages.success(request, f'🗑️ تم حذف بطاقة اللاعب «{player_name}» / Carton supprimé.')
        return redirect('matches:detail', pk=match_pk)


class EditCardView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to edit a card directly from match detail timeline."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        card = get_object_or_404(Card, pk=pk)
        match_pk = card.match.pk
        
        player_id = request.POST.get('player')
        minute = request.POST.get('minute')
        card_type = request.POST.get('card_type')
        reason = request.POST.get('reason')

        try:
            if player_id:
                card.player = get_object_or_404(Player, pk=player_id)
                card.team = card.player.team
            if minute:
                card.minute = int(minute)
            if card_type:
                card.card_type = card_type
            if reason is not None:
                card.reason = reason
            card.save()
            messages.success(request, f'✅ تم تعديل بيانات البطاقة بنجاح / Carton modifié.')
        except Exception as e:
            messages.error(request, f'❌ حدث خطأ أثناء التعديل: {e}')

        return redirect('matches:detail', pk=match_pk)


class DeleteGenericEventView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to delete a generic event directly from match detail timeline."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        event = get_object_or_404(MatchEvent, pk=pk)
        match_pk = event.match.pk
        event.delete()
        messages.success(request, '🗑️ تم حذف الحدث بنجاح / Événement supprimé.')
        return redirect('matches:detail', pk=match_pk)


