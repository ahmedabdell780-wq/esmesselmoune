from django.db import transaction
from django.views import View
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _

from django.db.models import Count
from apps.tournaments.models import Tournament, Group, GroupStanding, CommitteeMember
from apps.matches.models import Match, Goal, PlayerMatchPerformance
from apps.teams.models import Player, Team


class TournamentListView(ListView):
    model = Tournament
    template_name = 'tournaments/list.html'
    context_object_name = 'tournaments'
    ordering = ['-year', '-edition']


class StandingsView(TemplateView):
    template_name = 'tournaments/standings.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.GROUP_STAGE,
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        if tournament:
            ctx['groups'] = tournament.groups.prefetch_related('teams')
            
            from apps.tournaments.services.scheduler import StandingsCalculator
            calc = StandingsCalculator(tournament)
            all_groups = list(tournament.groups.all())
            
            second_places = []
            third_places = []
            
            for g in all_groups:
                st = calc.get_sorted_standings(g)
                if len(st) >= 2:
                    # Attach the group name to display in the mini standing table
                    st[1].group_name = g.name
                    second_places.append(st[1])
                if len(st) >= 3:
                    st[2].group_name = g.name
                    third_places.append(st[2])
                    
            second_places.sort(key=lambda x: (x.points, x.goal_difference, x.goals_for), reverse=True)
            third_places.sort(key=lambda x: (x.points, x.goal_difference, x.goals_for), reverse=True)
            
            ctx['best_seconds'] = second_places
            ctx['best_thirds'] = third_places
        
        # Pass all tournaments for the dropdown filter
        ctx['tournaments'] = Tournament.objects.all().order_by('-year', '-edition')
        
        return ctx


class StandingsPrintView(TemplateView):
    template_name = 'tournaments/standings_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.GROUP_STAGE,
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        if tournament:
            groups = tournament.groups.prefetch_related('teams')
            
            selected_group = self.request.GET.get('group_id')
            if selected_group:
                try:
                    selected_group_id = int(selected_group)
                    groups = groups.filter(id=selected_group_id)
                except ValueError:
                    selected_group = None
                    
            ctx['groups'] = groups
            ctx['all_groups'] = tournament.groups.all()
            ctx['selected_group'] = selected_group
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        return ctx


class GroupStandingsPosterView(TemplateView):
    """View to generate a high-fidelity Group Standings poster (نموذج ترتيب المجموعة) as an image/print."""
    template_name = 'tournaments/group_standings_poster.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.GROUP_STAGE,
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        if tournament:
            all_groups = list(tournament.groups.all())
            ctx['all_groups'] = all_groups

            selected_group = self.request.GET.get('group_id')
            current_group = None
            if selected_group:
                try:
                    current_group = tournament.groups.get(id=int(selected_group))
                except (ValueError, Group.DoesNotExist):
                    current_group = all_groups[0] if all_groups else None
            else:
                current_group = all_groups[0] if all_groups else None

            ctx['current_group'] = current_group

            if current_group:
                from apps.tournaments.services.scheduler import StandingsCalculator
                calc = StandingsCalculator(tournament)
                ctx['standings'] = calc.get_sorted_standings(current_group)

        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()

        return ctx


class StageSummaryPosterView(TemplateView):
    """View to calculate and generate stage summary poster and statistics report per stage."""
    template_name = 'tournaments/stage_summary_poster.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.GROUP_STAGE,
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        if not tournament:
            return ctx

        # Available stages list with Arabic display names
        stage_choices = [
            ('GROUP', 'دورة المجموعات'),
            ('R16', 'الثمن النهائي (1/8)'),
            ('QF', 'الربع النهائي (1/4)'),
            ('SF', 'النصف النهائي (1/2)'),
            ('TP', 'مباراة المركز الثالث'),
            ('FINAL', 'المباراة النهائية'),
        ]
        ctx['stage_choices'] = stage_choices

        selected_stage = self.request.GET.get('stage')
        if not selected_stage or selected_stage not in dict(stage_choices):
            # Pick latest finished/active stage for this tournament
            latest_match = tournament.matches.filter(status=Match.Status.FINISHED).order_by('-id').first()
            if latest_match:
                selected_stage = latest_match.stage
            else:
                selected_stage = 'GROUP'

        ctx['selected_stage'] = selected_stage
        ctx['selected_stage_display'] = dict(stage_choices).get(selected_stage, 'الملخص')

        # 1. Matches in this stage (excluding dummy Bye matches)
        matches = tournament.matches.filter(stage=selected_stage, team1__isnull=False, team2__isnull=False).select_related('team1', 'team2', 'group').prefetch_related('goals__player', 'cards').order_by('match_date', 'id')
        finished_matches = matches.filter(status=Match.Status.FINISHED)
        ctx['matches'] = matches
        ctx['finished_matches'] = finished_matches
        ctx['total_matches_count'] = matches.count()
        ctx['finished_matches_count'] = finished_matches.count()

        # 2. Stage Goals & Cards Statistics
        total_goals = 0

        # Team stats dictionary for this stage: {team_id: {'team': team, 'goals_for': 0, 'goals_against': 0, 'clean_sheets': 0, 'played': 0, 'won': 0}}
        team_stats = {}

        def get_team_entry(team):
            if team.id not in team_stats:
                team_stats[team.id] = {
                    'team': team,
                    'goals_for': 0,
                    'goals_against': 0,
                    'clean_sheets': 0,
                    'played': 0,
                    'won': 0,
                }
            return team_stats[team.id]

        for m in finished_matches:
            s1 = m.score_team1 or 0
            s2 = m.score_team2 or 0
            total_goals += (s1 + s2)

            if m.team1:
                t1_entry = get_team_entry(m.team1)
                t1_entry['played'] += 1
                t1_entry['goals_for'] += s1
                t1_entry['goals_against'] += s2
                if s2 == 0:
                    t1_entry['clean_sheets'] += 1
                if m.winner == m.team1:
                    t1_entry['won'] += 1

            if m.team2:
                t2_entry = get_team_entry(m.team2)
                t2_entry['played'] += 1
                t2_entry['goals_for'] += s2
                t2_entry['goals_against'] += s1
                if s1 == 0:
                    t2_entry['clean_sheets'] += 1
                if m.winner == m.team2:
                    t2_entry['won'] += 1

        ctx['total_goals'] = total_goals
        ctx['avg_goals'] = round(total_goals / finished_matches.count(), 2) if finished_matches.count() > 0 else 0

        # Cards count in stage
        from apps.matches.models import Card
        cards = Card.objects.filter(match__tournament=tournament, match__stage=selected_stage)
        ctx['yellow_cards_count'] = cards.filter(card_type='yellow').count()
        ctx['red_cards_count'] = cards.filter(card_type='red').count()

        # 3. Stage Top Scorer (هداف المرحلة)
        from apps.matches.models import Goal
        stage_goals = Goal.objects.filter(match__tournament=tournament, match__stage=selected_stage).exclude(goal_type=Goal.GoalType.OWN_GOAL).select_related('player', 'team')
        scorer_map = {}
        for g in stage_goals:
            if g.player:
                p_id = g.player.id
                if p_id not in scorer_map:
                    scorer_map[p_id] = {'player': g.player, 'team': g.team, 'goals_count': 0}
                scorer_map[p_id]['goals_count'] += 1

        top_scorers = sorted(scorer_map.values(), key=lambda x: x['goals_count'], reverse=True)
        ctx['top_scorers'] = top_scorers[:5]
        ctx['stage_top_scorer'] = top_scorers[0] if top_scorers else None

        # 4. Best Attack & Best Defense & Team Stats List (أفضل هجوم وأفضل دفاع وعدد اهداف كل فريق)
        team_stats_list = list(team_stats.values())
        team_stats_list.sort(key=lambda x: (x['goals_for'], -x['goals_against']), reverse=True)
        ctx['team_stats_list'] = team_stats_list

        best_attack = None
        best_defense = None
        best_goalkeeper = None

        if team_stats_list:
            # Best attack: highest goals_for
            max_gf = max(t['goals_for'] for t in team_stats_list)
            best_attack = [t for t in team_stats_list if t['goals_for'] == max_gf]

            # Best defense: lowest goals_against among teams that played
            min_ga = min(t['goals_against'] for t in team_stats_list)
            best_defense = [t for t in team_stats_list if t['goals_against'] == min_ga]

            # Best goalkeeper / clean sheets team
            max_cs = max(t['clean_sheets'] for t in team_stats_list)
            best_cs_teams = [t for t in team_stats_list if t['clean_sheets'] == max_cs]

            goalkeepers = []
            for bt in best_cs_teams:
                gk = bt['team'].players.filter(position__in=['GK', 'حارس', 'Gardien']).first()
                if not gk:
                    gk = bt['team'].players.first()
                if gk:
                    goalkeepers.append({'player': gk, 'team': bt['team'], 'clean_sheets': bt['clean_sheets']})
            best_goalkeeper = goalkeepers[0] if goalkeepers else None

        ctx['best_attack'] = best_attack
        ctx['best_defense'] = best_defense
        ctx['best_goalkeeper'] = best_goalkeeper

        # 5. Advancing / Qualified Teams (الفرق المتأهلة)
        qualified_teams = []
        if selected_stage == 'GROUP':
            # Teams advancing from group stage
            from apps.tournaments.services.scheduler import StandingsCalculator
            calc = StandingsCalculator(tournament)
            teams_per_group = tournament.teams_advancing_per_group or 2
            for g in tournament.groups.all():
                st = calc.get_sorted_standings(g)
                for item in st[:teams_per_group]:
                    qualified_teams.append({'team': item.team, 'group': g.name, 'reason': f"متأهل عن {g.name}"})
        else:
            # Knockout stage winners
            for m in finished_matches:
                w = m.winner
                if w:
                    qualified_teams.append({'team': w, 'reason': f"فائز في {ctx['selected_stage_display']}"})

        ctx['qualified_teams'] = qualified_teams

        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()

        return ctx


class TournamentTeamsPrintView(TemplateView):
    template_name = 'tournaments/teams_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)

        ctx['tournament'] = tournament
        
        # Participating Teams
        participating_teams = list(
            tournament.tournament_teams
            .filter(is_confirmed=True, payment_confirmed=True)
            .select_related('team')
            .order_by('team__name')
        )
        
        chunk_size = 24
        team_chunks = [
            {'teams': participating_teams[i:i + chunk_size], 'start_idx': i}
            for i in range(0, len(participating_teams), chunk_size)
        ]
        
        ctx['participating_teams'] = participating_teams
        ctx['team_chunks'] = team_chunks
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        return ctx


class TournamentDrawSlipsPrintView(TemplateView):
    template_name = 'tournaments/draw_slips_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)

        ctx['tournament'] = tournament
        
        # Participating Teams
        participating_teams = list(
            tournament.tournament_teams
            .filter(is_confirmed=True, payment_confirmed=True)
            .select_related('team')
            .order_by('team__name')
        )
        
        chunk_size = 8
        team_chunks = [
            participating_teams[i:i + chunk_size]
            for i in range(0, len(participating_teams), chunk_size)
        ]
        
        ctx['participating_teams'] = participating_teams
        ctx['team_chunks'] = team_chunks
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        return ctx


class TournamentAllPlayersPrintView(TemplateView):
    template_name = 'tournaments/all_players_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)
        
        ctx['tournament'] = tournament
        
        # Check if a specific team is requested
        team_id = self.request.GET.get('team_id')
        if team_id:
            team_ids = [int(team_id)]
        else:
            # Get all confirmed teams that have paid their subscription
            team_ids = tournament.tournament_teams.filter(is_confirmed=True, payment_confirmed=True).values_list('team_id', flat=True)
        
        # Get all active players for these teams, ordered by team then player name
        players = list(Player.objects.filter(team_id__in=team_ids, is_active=True).select_related('team').order_by('team__name', 'last_name', 'first_name'))
        
        # Chunk players into pages of 24 for PDF generation
        chunk_size = 24
        player_chunks = []
        for i in range(0, len(players), chunk_size):
            chunk_players = players[i:i + chunk_size]
            
            # Calculate rowspan for each team in this chunk
            team_counts = {}
            for p in chunk_players:
                team_counts[p.team_id] = team_counts.get(p.team_id, 0) + 1
            
            # Tag the players for template rendering
            processed_players = []
            seen_teams_in_chunk = set()
            for p in chunk_players:
                is_first = p.team_id not in seen_teams_in_chunk
                if is_first:
                    seen_teams_in_chunk.add(p.team_id)
                    p.chunk_rowspan = team_counts[p.team_id]
                else:
                    p.chunk_rowspan = 0
                
                p.chunk_is_first = is_first
                processed_players.append(p)

            player_chunks.append({
                'players': processed_players,
                'start_idx': i
            })
        ctx['player_chunks'] = player_chunks
        ctx['total_players'] = len(players)
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        return ctx


class MatchesPrintView(TemplateView):
    template_name = 'tournaments/calendar_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .exclude(status=Tournament.Status.DRAFT)
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        if tournament:
            matches_qs = (
                tournament.matches
                .select_related('team1', 'team2', 'group')
                .order_by('match_date')
            )
            
            rounds = tournament.matches.filter(stage='GROUP', match_day__isnull=False).values_list('match_day', flat=True).distinct().order_by('match_day')
            ctx['rounds'] = rounds
            
            selected_round = self.request.GET.get('round')
            selected_stage = self.request.GET.get('stage')
            
            if selected_stage:
                matches_qs = matches_qs.filter(stage=selected_stage)
            elif selected_round:
                try:
                    selected_round = int(selected_round)
                    matches_qs = matches_qs.filter(match_day=selected_round)
                except ValueError:
                    selected_round = None
            
            ctx['selected_round'] = selected_round
            ctx['selected_stage'] = selected_stage
            ctx['matches'] = matches_qs
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        return ctx


class GroupMatchesPrintView(TemplateView):
    template_name = 'tournaments/group_calendar_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .exclude(status=Tournament.Status.DRAFT)
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        ctx['tournament'] = tournament
        if tournament:
            groups = tournament.groups.all().order_by('name')
            ctx['groups'] = groups
            
            selected_group_id = self.request.GET.get('group_id')
            if selected_group_id:
                selected_group = groups.filter(id=selected_group_id).first()
            else:
                selected_group = groups.first()
                
            ctx['selected_group'] = selected_group
            
            if selected_group:
                # Get matches belonging only to the selected group
                ctx['matches'] = (
                    tournament.matches
                    .filter(group=selected_group)
                    .select_related('team1', 'team2', 'group')
                    .order_by('match_date')
                )
            else:
                ctx['matches'] = []
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        return ctx


class BracketView(TemplateView):
    template_name = 'tournaments/bracket.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')

        if pk:
            tournament = get_object_or_404(Tournament, pk=pk)
        else:
            tournament = (
                Tournament.objects
                .filter(status__in=[
                    Tournament.Status.KNOCKOUT,
                    Tournament.Status.FINISHED,
                ])
                .order_by('-year', '-edition')
                .first()
            )

        ctx['tournament'] = tournament
        
        # Pass all tournaments for the dropdown filter
        ctx['tournaments'] = Tournament.objects.all().order_by('-year', '-edition')

        if tournament:
            stage_order = [
                Match.Stage.ROUND_OF_16,
                Match.Stage.QUARTER_FINAL,
                Match.Stage.SEMI_FINAL,
                Match.Stage.THIRD_PLACE,
                Match.Stage.FINAL,
            ]
            bracket = {}
            for stage in stage_order:
                matches = (
                    Match.objects
                    .filter(tournament=tournament, stage=stage)
                    .select_related('team1', 'team2')
                    .order_by('match_day', 'match_date')
                )
                if matches.exists():
                    bracket[stage] = {
                        'label': match_stage_label(stage),
                        'matches': matches,
                    }
            ctx['bracket'] = bracket
            ctx['stage_labels'] = {s: match_stage_label(s) for s in stage_order}

        return ctx


def match_stage_label(stage):
    labels = {
        'R16':   'Huitièmes de finale',
        'QF':    'Quarts de finale',
        'SF':    'Demi-finales',
        'TP':    '3ème place',
        'FINAL': 'Finale',
    }
    return labels.get(stage, stage)


class TournamentTeamsByGroupPrintView(TemplateView):
    template_name = 'tournaments/teams_by_group_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)
        ctx['tournament'] = tournament
        
        # Groups and teams
        groups = tournament.groups.prefetch_related('teams').order_by('name')
        ctx['groups'] = groups
        
        # All teams in tournament for dropdowns
        ctx['all_teams'] = tournament.tournament_teams.filter(is_confirmed=True).select_related('team').order_by('team__name')
        
        return ctx


class TournamentTreePrintView(TemplateView):
    template_name = 'tournaments/tree_print.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk  = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)

        ctx['tournament'] = tournament
        
        # Groups and standings
        groups = tournament.groups.prefetch_related('teams').order_by('name')
        ctx['groups'] = groups

        from apps.tournaments.services.scheduler import StandingsCalculator
        calc = StandingsCalculator(tournament)

        group_standings_map = {}
        for g in groups:
            group_standings_map[g.id] = calc.get_sorted_standings(g)

        ctx['group_standings_map'] = group_standings_map

        # Automatic Seed Deduction from Group Standings (A1, A2, B1, B2, C1, C2, D1, D2, 2ND.1, 2ND.2)
        seed_teams = {}
        second_place_teams = []

        for g in groups:
            g_letter = g.name.replace('Groupe', '').replace('المجموعة', '').strip()
            st = group_standings_map.get(g.id, [])
            for rank_idx, standing in enumerate(st):
                code = f"{g_letter}{rank_idx + 1}"
                seed_teams[code] = standing.team
                if rank_idx == 1:
                    second_place_teams.append(standing)

        second_place_teams.sort(key=lambda x: (x.points, x.goal_difference, x.goals_for), reverse=True)
        if len(second_place_teams) >= 1:
            seed_teams['2ND1'] = second_place_teams[0].team
            seed_teams['2ND_1'] = second_place_teams[0].team
        if len(second_place_teams) >= 2:
            seed_teams['2ND2'] = second_place_teams[1].team
            seed_teams['2ND_2'] = second_place_teams[1].team
        if len(second_place_teams) >= 3:
            seed_teams['2ND3'] = second_place_teams[2].team
            seed_teams['2ND_3'] = second_place_teams[2].team

        ctx['seed_teams'] = seed_teams

        # Knockout Matches
        r16_matches = list(Match.objects.filter(tournament=tournament, stage=Match.Stage.ROUND_OF_16).select_related('team1', 'team2').order_by('match_date', 'id'))
        qf_matches = list(Match.objects.filter(tournament=tournament, stage=Match.Stage.QUARTER_FINAL).select_related('team1', 'team2').order_by('match_date', 'id'))
        sf_matches = list(Match.objects.filter(tournament=tournament, stage=Match.Stage.SEMI_FINAL).select_related('team1', 'team2').order_by('match_date', 'id'))
        final_match = Match.objects.filter(tournament=tournament, stage=Match.Stage.FINAL).select_related('team1', 'team2').first()
        tp_match = Match.objects.filter(tournament=tournament, stage=Match.Stage.THIRD_PLACE).select_related('team1', 'team2').first()

        ctx['r16_matches'] = r16_matches
        ctx['qf_matches'] = qf_matches
        ctx['sf_matches'] = sf_matches
        ctx['final_match'] = final_match
        ctx['tp_match'] = tp_match

        # Automatic Winner & Qualifier Propagation
        # 1. Semi-Finals Auto Teams:
        auto_sf1_t1 = None
        auto_sf1_t2 = None
        auto_sf2_t1 = None
        auto_sf2_t2 = None

        if sf_matches and len(sf_matches) >= 1:
            auto_sf1_t1 = sf_matches[0].team1
            auto_sf1_t2 = sf_matches[0].team2
        if not auto_sf1_t1 and len(qf_matches) >= 1 and qf_matches[0].winner:
            auto_sf1_t1 = qf_matches[0].winner
        if not auto_sf1_t2 and len(qf_matches) >= 2 and qf_matches[1].winner:
            auto_sf1_t2 = qf_matches[1].winner

        if sf_matches and len(sf_matches) >= 2:
            auto_sf2_t1 = sf_matches[1].team1
            auto_sf2_t2 = sf_matches[1].team2
        if not auto_sf2_t1 and len(qf_matches) >= 3 and qf_matches[2].winner:
            auto_sf2_t1 = qf_matches[2].winner
        if not auto_sf2_t2 and len(qf_matches) >= 4 and qf_matches[3].winner:
            auto_sf2_t2 = qf_matches[3].winner

        ctx['auto_sf1_team1'] = auto_sf1_t1
        ctx['auto_sf1_team2'] = auto_sf1_t2
        ctx['auto_sf2_team1'] = auto_sf2_t1
        ctx['auto_sf2_team2'] = auto_sf2_t2

        # 2. Final Auto Teams:
        auto_final_t1 = final_match.team1 if final_match and final_match.team1 else None
        auto_final_t2 = final_match.team2 if final_match and final_match.team2 else None

        if not auto_final_t1 and len(sf_matches) >= 1 and sf_matches[0].winner:
            auto_final_t1 = sf_matches[0].winner
        if not auto_final_t2 and len(sf_matches) >= 2 and sf_matches[1].winner:
            auto_final_t2 = sf_matches[1].winner

        ctx['auto_final_team1'] = auto_final_t1
        ctx['auto_final_team2'] = auto_final_t2

        # 3. Champion / Winner Auto Team:
        auto_champion = final_match.winner if final_match and final_match.winner else None
        ctx['auto_champion'] = auto_champion

        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()

        return ctx


class TournamentAdminView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Admin panel for tournament management actions."""
    template_name = 'tournaments/admin_panel.html'

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        # All tournaments for the dropdown selector
        all_tournaments = Tournament.objects.all().order_by('-year', '-edition')
        ctx['all_tournaments_selector'] = all_tournaments
        
        # Filter by selected tournament if any
        tournament_id_str = self.request.GET.get('tournament_id')
        selected_tournament_id = None
        tournaments = all_tournaments
        
        if tournament_id_str:
            try:
                selected_tournament_id = int(tournament_id_str)
                tournaments = tournaments.filter(id=selected_tournament_id)
            except ValueError:
                pass
        
        ctx['tournaments'] = tournaments
        ctx['selected_tournament_id'] = selected_tournament_id
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        # Pending participations
        from apps.tournaments.models import TournamentTeam
        pending = TournamentTeam.objects.filter(is_confirmed=False).select_related('tournament', 'team')
        if selected_tournament_id:
            pending = pending.filter(tournament_id=selected_tournament_id)
        ctx['pending_participations'] = pending
        
        # All teams for manual inclusion
        from apps.teams.models import Team
        ctx['all_teams'] = Team.objects.filter(is_active=True).order_by('name')
        
        import json
        tournament_teams_map = {
            t.id: list(t.teams.values_list('id', flat=True)) 
            for t in all_tournaments
        }
        ctx['tournament_teams_map_json'] = json.dumps(tournament_teams_map)
        
        return ctx

    def post(self, request, *args, **kwargs):
        action  = request.POST.get('action')
        
        # Global Settings Action
        if action == 'update_settings':
            from apps.core.models import SiteSettings
            settings = SiteSettings.load()
            settings.app_name = request.POST.get('app_name', settings.app_name)
            if request.FILES.get('app_logo'):
                settings.app_logo = request.FILES.get('app_logo')
            settings.save()
            messages.success(request, _('✅ Paramètres de l\'application mis à jour !'))
            return redirect('tournaments:admin_panel')

        elif action == 'create_tournament':
            name = request.POST.get('name')
            year_str = request.POST.get('year')
            edition_str = request.POST.get('edition')
            format_choice = request.POST.get('format')
            max_teams_str = request.POST.get('max_teams')
            num_groups_str = request.POST.get('num_groups', '4')
            subscription_price_str = request.POST.get('subscription_price', '0')
            location = request.POST.get('location', 'Stade Communal')
            
            from django.utils import timezone
            try:
                year = int(year_str) if year_str else timezone.now().year
                edition = int(edition_str) if edition_str else 1
                max_teams = int(max_teams_str) if max_teams_str else 16
                num_groups = int(num_groups_str) if num_groups_str else 4
                subscription_price = float(subscription_price_str) if subscription_price_str else 0.0
                
                if name:
                    Tournament.objects.create(
                        name=name,
                        year=year,
                        edition=edition,
                        format=format_choice or Tournament.Format.GROUP_KNOCKOUT,
                        status=Tournament.Status.DRAFT,
                        max_teams=max_teams,
                        num_groups=num_groups,
                        subscription_price=subscription_price,
                        location=location,
                        start_date=timezone.now().date()
                    )
                    messages.success(request, _('✅ Tournoi créé avec succès ! / تم إنشاء البطولة بنجاح.'))
                else:
                    messages.error(request, _('❌ Nom du tournoi manquant.'))
            except ValueError:
                messages.error(request, _('❌ Valeurs numériques invalides.'))
            return redirect('tournaments:admin_panel')

        t_id    = request.POST.get('tournament_id')
        tournament = get_object_or_404(Tournament, pk=t_id)

        if action == 'generate_groups':
            from apps.tournaments.services.scheduler import GroupSeeder, MatchScheduler
            try:
                GroupSeeder(tournament).seed_groups()
                MatchScheduler(tournament).generate_group_stage()
                tournament.status = Tournament.Status.GROUP_STAGE
                tournament.save(update_fields=['status'])
                messages.success(request, f'Groupes et calendrier générés pour {tournament}.')
            except ValueError as e:
                messages.error(request, str(e))

        elif action == 'generate_knockout':
            if tournament.format == Tournament.Format.ROUND_ROBIN:
                messages.error(request, 'Ce tournoi suit un format de Championnat aller-retour. Il n\'y a pas de phase finale élliminatoire.')
            else:
                from apps.tournaments.services.scheduler import (
                    MatchScheduler, StandingsCalculator
                )
                calc = StandingsCalculator(tournament)
                advancing = calc.get_all_advancing_teams()
                if len(advancing) < 2:
                    messages.error(request, 'Pas assez d\'équipes qualifiées.')
                else:
                    MatchScheduler(tournament).generate_knockout_bracket(advancing)
                    tournament.status = Tournament.Status.KNOCKOUT
                    tournament.save(update_fields=['status'])
                    messages.success(request, f'🔥 Phase finale générée avec succès pour {len(advancing)} équipes ! Voici la grille officielle.')
                    return redirect('tournaments:bracket_detail', pk=tournament.pk)

        elif action == 'set_status':
            new_status = request.POST.get('new_status')
            if new_status in Tournament.Status.values:
                tournament.status = new_status
                tournament.save(update_fields=['status'])
                messages.success(request, f'Statut mis à jour : {tournament.get_status_display()}.')

        elif action == 'add_group':
            import string
            next_idx = tournament.groups.count()
            letter = string.ascii_uppercase[next_idx] if next_idx < 26 else f"{next_idx+1}"
            Group.objects.create(tournament=tournament, name=f"Groupe {letter}")
            tournament.num_groups = tournament.groups.count()
            tournament.save(update_fields=['num_groups'])
            messages.success(request, _('✅ Nouveau groupe ajouté ! / تم إضافة مجموعة جديدة!'))

        elif action == 'delete_tournament':
            name = tournament.name
            tournament.delete()
            messages.success(request, f'🗑️ Tournoi "{name}" supprimé avec succès. / تم حذف البطولة بنجاح.')
            return redirect('tournaments:admin_panel')

        return redirect('tournaments:admin_panel')
class ManualGroupView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'tournaments/manual_groups.html'

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tournament = get_object_or_404(Tournament, pk=self.kwargs.get('pk'))
        ctx['tournament'] = tournament
        ctx['teams'] = tournament.tournament_teams.filter(is_confirmed=True).select_related('team')
        ctx['groups'] = tournament.groups.all().prefetch_related('teams')
        return ctx

    def post(self, request, *args, **kwargs):
        tournament = get_object_or_404(Tournament, pk=self.kwargs.get('pk'))
        action = request.POST.get('action')

        if action == 'save_groups':
            # Format expected: group_{group_id} = [team_id, team_id, ...]
            try:
                with transaction.atomic():
                    # Clean existing group teams and standings for this tournament
                    for group in tournament.groups.all():
                        group.teams.clear()
                        group.groupstanding_set.all().delete()

                    # Parse and save new assignments
                    from apps.teams.models import Team
                    for group in tournament.groups.all():
                        team_ids = request.POST.getlist(f'group_{group.pk}')
                        for t_id in team_ids:
                            team = get_object_or_404(Team, pk=t_id)
                            group.teams.add(team)
                            GroupStanding.objects.create(group=group, team=team)

                messages.success(request, _('✅ Groupes enregistrés avec succès !'))
                
                # Auto-generate group stage matches
                from apps.tournaments.services.scheduler import MatchScheduler
                MatchScheduler(tournament).generate_group_stage()
                tournament.status = Tournament.Status.GROUP_STAGE
                tournament.save(update_fields=['status'])
                messages.success(request, _('📅 Calendrier généré automatiquement.'))

            except Exception as e:
                messages.error(request, f'Erreur : {str(e)}')

        return redirect('tournaments:admin_panel')


class ManualKnockoutView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Allows organizers to manually set knockout quarter-final pairings."""
    template_name = 'tournaments/manual_knockout.html'

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tournament = get_object_or_404(Tournament, pk=self.kwargs.get('pk'))
        ctx['tournament'] = tournament

        groups = tournament.groups.prefetch_related('teams').order_by('name')
        ctx['groups'] = groups

        from apps.tournaments.services.scheduler import StandingsCalculator
        calc = StandingsCalculator(tournament)
        group_standings_map = {}
        seed_teams = {}
        for g in groups:
            st = calc.get_sorted_standings(g)
            group_standings_map[g.id] = st
            g_letter = g.name.replace('Groupe', '').replace('المجموعة', '').strip()
            for rank_idx, standing in enumerate(st):
                code = f"{g_letter}{rank_idx + 1}"
                seed_teams[code] = standing.team

        ctx['seed_teams'] = seed_teams

        from apps.teams.models import Team
        confirmed_teams = list(
            Team.objects.filter(tournament_teams__tournament=tournament, tournament_teams__is_confirmed=True)
            .order_by('name')
        )
        ctx['confirmed_teams'] = confirmed_teams

        qf_matches = list(
            Match.objects.filter(tournament=tournament, stage=Match.Stage.QUARTER_FINAL)
            .select_related('team1', 'team2')
            .order_by('match_day', 'id')
        )
        ctx['qf_matches'] = qf_matches

        return ctx

    def post(self, request, *args, **kwargs):
        tournament = get_object_or_404(Tournament, pk=self.kwargs.get('pk'))
        from apps.teams.models import Team
        from apps.tournaments.services.scheduler import MatchScheduler

        try:
            with transaction.atomic():
                pairs = []
                for i in range(1, 5):
                    t1_id = request.POST.get(f'match_{i}_team1')
                    t2_id = request.POST.get(f'match_{i}_team2')

                    t1 = Team.objects.filter(pk=t1_id).first() if t1_id else None
                    t2 = Team.objects.filter(pk=t2_id).first() if t2_id else None

                    pairs.append((t1, t2))

                MatchScheduler(tournament).generate_manual_knockout_bracket(pairs)
                messages.success(request, _('✅ تم حفظ وإنشاء القرعة اليدوية للأدوار النهائية بنجاح!'))
                return redirect('tournaments:bracket_detail', pk=tournament.pk)

        except Exception as e:
            messages.error(request, f'❌ حدث خطأ أثناء الحفظ: {str(e)}')
            return redirect('tournaments:manual_knockout', pk=tournament.pk)

import json
class SaveGroupOrderAPIView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, *args, **kwargs):
        tournament = get_object_or_404(Tournament, pk=self.kwargs.get('pk'))
        try:
            data = json.loads(request.body)
            with transaction.atomic():
                from apps.teams.models import Team
                for group_id_str, team_ids in data.items():
                    # Check if group belongs to this tournament
                    group = get_object_or_404(Group, pk=int(group_id_str), tournament=tournament)
                    
                    # Clear current assignments for this group
                    group.teams.clear()
                    group.groupstanding_set.all().delete()
                    
                    for t_id in team_ids:
                        if not t_id: continue
                        team = get_object_or_404(Team, pk=int(t_id))
                        group.teams.add(team)
                        GroupStanding.objects.create(group=group, team=team)
                
                # Auto-generate group stage matches based on new arrangement
                from apps.tournaments.services.scheduler import MatchScheduler
                MatchScheduler(tournament).generate_group_stage()
                if tournament.status == Tournament.Status.DRAFT:
                    tournament.status = Tournament.Status.GROUP_STAGE
                    tournament.save(update_fields=['status'])
                        
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

class ParticipationActionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Approve or Reject a team's participation in a tournament."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        from apps.tournaments.models import TournamentTeam
        from apps.notifications.models import Notification
        
        tt = get_object_or_404(TournamentTeam, pk=pk)
        action = request.POST.get('action')

        if action == 'approve':
            tt.is_confirmed = True
            tt.save(update_fields=['is_confirmed'])
            messages.success(request, _('✅ Participation de « %s » confirmée !') % tt.team.name)
            
            # Notify manager
            if tt.team.manager:
                Notification.objects.create(
                    recipient=tt.team.manager,
                    notif_type=Notification.Type.TOURNAMENT,
                    title=_('Participation validée !'),
                    message=_('Votre équipe « %s » a été acceptée pour %s.') % (tt.team.name, tt.tournament.name)
                )
        elif action == 'reject':
            name = tt.team.name
            tt.delete()
            messages.warning(request, _('🗑️ Demande de participation de « %s » rejetée.') % name)

        return redirect('tournaments:admin_panel')


class ManualTeamInclusionView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Manually add an existing team to a tournament."""
    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def post(self, request, pk):
        from apps.teams.models import Team
        from apps.tournaments.models import Tournament, TournamentTeam
        
        tournament = get_object_or_404(Tournament, pk=pk)
        team_ids = request.POST.getlist('team_ids')
        
        added_count = 0
        for t_id in team_ids:
            team = get_object_or_404(Team, pk=t_id)
            tt, created = TournamentTeam.objects.get_or_create(
                tournament=tournament,
                team=team,
                defaults={'is_confirmed': True}
            )
            if not created and not tt.is_confirmed:
                tt.is_confirmed = True
                tt.save(update_fields=['is_confirmed'])
                added_count += 1
            elif created:
                added_count += 1
        
        if added_count > 0:
            messages.success(request, _('✅ %d équipe(s) ajoutée(s) au tournoi.') % added_count)
        else:
            messages.info(request, _('ℹ️ Aucune nouvelle équipe n\'a été ajoutée.'))
        return redirect('tournaments:admin_panel')


class CreateVeteransTournamentView(LoginRequiredMixin, UserPassesTestMixin, View):
    """POST-only view to quickly create the Veterans tournament."""
    
    def test_func(self):
        return self.request.user.role == 'admin'

    def post(self, request):
        from django.utils import timezone
        
        # Check if it already exists to prevent duplicates
        exists = Tournament.objects.filter(name="الماضي يلهم الحاضر", year=timezone.now().year).exists()
        if exists:
            messages.error(request, '❌ هذه الدورة موجودة مسبقاً لهذا العام!')
        else:
            Tournament.objects.create(
                name="الماضي يلهم الحاضر",
                year=timezone.now().year,
                edition=1,
                status=Tournament.Status.DRAFT,
                max_teams=16,
                start_date=timezone.datetime(2026, 5, 22).date()
            )
            messages.success(request, '✅ تم إنشاء دورة الكهول بنجاح!')
            
        return redirect('tournaments:admin_panel')


class BestXIView(DetailView):
    """Calculates and displays the 'Dream Team' of the tournament."""
    model = Tournament
    template_name = 'tournaments/best_xi.html'
    context_object_name = 'tournament'

    def get_context_data(self, **kwargs):
        from apps.teams.models import Player
        from apps.matches.models import Goal, Card, PlayerMatchPerformance
        from django.db.models import Count, Avg, F, Q, FloatField, ExpressionWrapper
        from django.db.models.functions import Coalesce

        ctx = super().get_context_data(**kwargs)
        tournament = self.object

        # FORMATION LOGIC
        # Standard: 4-3-3. Options: 4-4-2, 3-5-2, 5-3-2
        formation_slug = self.request.GET.get('formation', '4-3-3')
        formation_map = {
            '4-3-3': {'DEF': 4, 'MID': 3, 'FWD': 3},
            '4-4-2': {'DEF': 4, 'MID': 4, 'FWD': 2},
            '3-5-2': {'DEF': 3, 'MID': 5, 'FWD': 2},
            '5-3-2': {'DEF': 5, 'MID': 3, 'FWD': 2},
        }
        config = formation_map.get(formation_slug, formation_map['4-3-3'])
        ctx['current_formation'] = formation_slug
        ctx['available_formations'] = formation_map.keys()

        # Scoring weights
        GOAL_WEIGHT = 5
        ASSIST_WEIGHT = 3
        YELLOW_WEIGHT = -2
        RED_WEIGHT = -5

        # All players in this tournament — select_related for team color access in template
        players = Player.objects.filter(
            team__tournament_teams__tournament=tournament,
            team__tournament_teams__is_confirmed=True
        ).select_related('team').distinct()

        # Calculate "Dream Score"
        annotated_players = players.annotate(
            total_goals=Coalesce(Count('goals', filter=Q(goals__match__tournament=tournament, goals__goal_type__in=['normal', 'penalty', 'header', 'free_kick'])), 0),
            total_assists=Coalesce(Count('assists', filter=Q(assists__match__tournament=tournament)), 0),
            total_yellows=Coalesce(Count('cards', filter=Q(cards__match__tournament=tournament, cards__card_type='yellow')), 0),
            total_reds=Coalesce(Count('cards', filter=Q(cards__match__tournament=tournament, cards__card_type__in=['red', 'yellow_red'])), 0),
            avg_rating=Coalesce(Avg('performances__rating', filter=Q(performances__match__tournament=tournament)), 6.0, output_field=FloatField()),
        ).annotate(
            dream_score=ExpressionWrapper(
                F('total_goals') * GOAL_WEIGHT +
                F('total_assists') * ASSIST_WEIGHT +
                F('total_yellows') * YELLOW_WEIGHT +
                F('total_reds') * RED_WEIGHT +
                F('avg_rating'),
                output_field=FloatField()
            )
        ).order_by('-dream_score')

        # Pick players based on configuration
        best_xi = {
            'GK':  annotated_players.filter(position='GK')[:1],
            'DEF': annotated_players.filter(position='DEF')[:config['DEF']],
            'MID': annotated_players.filter(position='MID')[:config['MID']],
            'FWD': annotated_players.filter(position='FWD')[:config['FWD']],
        }

        ctx['best_xi'] = best_xi
        ctx['best_xi_list'] = list(best_xi['GK']) + list(best_xi['DEF']) + list(best_xi['MID']) + list(best_xi['FWD'])
        
        return ctx

class TournamentBookView(DetailView):
    """Generates a comprehensive printable view of the tournament (Standings, Matches, Stats)."""
    model = Tournament
    template_name = 'tournaments/book.html'
    context_object_name = 'tournament'

    def get_context_data(self, **kwargs):
        from apps.tournaments.models import GroupStanding
        from apps.matches.models import Match, Goal, Card
        from apps.teams.models import Player, Team
        from django.db.models import Count, Sum, Q, F
        from django.utils import timezone
        import django.db.models.functions as db_funcs
        
        ctx = super().get_context_data(**kwargs)
        tournament = self.object

        # 1. Groups & Standings
        ctx['groups'] = tournament.groups.prefetch_related('teams')

        # 2. Knockout Matches
        knockout_matches = (
            Match.objects.filter(tournament=tournament, stage__in=[
                Match.Stage.ROUND_OF_16, Match.Stage.QUARTER_FINAL, 
                Match.Stage.SEMI_FINAL, Match.Stage.THIRD_PLACE, Match.Stage.FINAL
            ]).select_related('team1', 'team2')
            .prefetch_related('goals', 'goals__player', 'goals__team', 'cards', 'cards__player', 'cards__team')
            .order_by('match_date')
        )
        ctx['knockout_matches'] = knockout_matches

        # 3. Top Scorers
        top_scorers = (
            Goal.objects.filter(match__tournament=tournament, goal_type__in=['normal', 'penalty', 'header', 'free_kick'])
            .values('player__first_name', 'player__last_name', 'team__name')
            .annotate(goals_count=Count('id'))
            .order_by('-goals_count')[:10]
        )
        ctx['top_scorers'] = top_scorers

        # 4. Top Assists (Playmakers)
        top_assists = (
            Goal.objects.filter(match__tournament=tournament, assist_player__isnull=False)
            .values('assist_player__first_name', 'assist_player__last_name', 'assist_player__team__name')
            .annotate(assists_count=Count('id'))
            .order_by('-assists_count')[:10]
        )
        ctx['top_assists'] = top_assists

        # 5. Tournament Statistics
        total_matches = Match.objects.filter(tournament=tournament, team1__isnull=False, team2__isnull=False).count()
        played_matches = Match.objects.filter(tournament=tournament, status=Match.Status.FINISHED).count()
        total_goals = Goal.objects.filter(match__tournament=tournament).count()
        
        # Calculate goal average per played match
        goal_average = round(total_goals / played_matches, 2) if played_matches > 0 else 0.0
        
        # Cards
        yellow_cards = Card.objects.filter(match__tournament=tournament, card_type=Card.CardType.YELLOW).count()
        red_cards = Card.objects.filter(match__tournament=tournament, card_type__in=[Card.CardType.RED, Card.CardType.YELLOW_RED]).count()
        
        # Teams & Players
        total_teams = tournament.tournament_teams.filter(is_confirmed=True).count()
        total_players = Player.objects.filter(
            team__tournament_teams__tournament=tournament,
            team__tournament_teams__is_confirmed=True
        ).distinct().count()

        ctx['stats'] = {
            'total_matches': total_matches,
            'played_matches': played_matches,
            'total_goals': total_goals,
            'goal_average': goal_average,
            'yellow_cards': yellow_cards,
            'red_cards': red_cards,
            'total_teams': total_teams,
            'total_players': total_players,
        }

        # 6. Team-specific Aggregates & Comprehensive 13 Category Statistics
        teams_stats = []
        confirmed_teams = Team.objects.filter(tournament_teams__tournament=tournament, tournament_teams__is_confirmed=True).distinct()
        for team in confirmed_teams:
            fin_matches = Match.objects.filter(
                Q(team1=team) | Q(team2=team),
                tournament=tournament,
                status=Match.Status.FINISHED
            )
            played = fin_matches.count()
            wins = 0
            losses = 0
            draws = 0
            scored = Goal.objects.filter(match__tournament=tournament, team=team).count()
            
            conceded_home = Match.objects.filter(tournament=tournament, team1=team, status=Match.Status.FINISHED).aggregate(total=Sum('score_team2'))['total'] or 0
            conceded_away = Match.objects.filter(tournament=tournament, team2=team, status=Match.Status.FINISHED).aggregate(total=Sum('score_team1'))['total'] or 0
            conceded = conceded_home + conceded_away

            for m in fin_matches:
                if m.team1 == team:
                    s_for = m.score_team1 or 0
                    s_against = m.score_team2 or 0
                else:
                    s_for = m.score_team2 or 0
                    s_against = m.score_team1 or 0

                if s_for > s_against:
                    wins += 1
                elif s_for < s_against:
                    losses += 1
                else:
                    draws += 1
            
            cs_home = Match.objects.filter(tournament=tournament, team1=team, score_team2=0, status=Match.Status.FINISHED).count()
            cs_away = Match.objects.filter(tournament=tournament, team2=team, score_team1=0, status=Match.Status.FINISHED).count()
            clean_sheets = cs_home + cs_away
            
            teams_stats.append({
                'team': team,
                'played': played,
                'wins': wins,
                'losses': losses,
                'draws': draws,
                'scored': scored,
                'conceded': conceded,
                'gd': scored - conceded,
                'clean_sheets': clean_sheets
            })

        ctx['teams_stats'] = teams_stats

        # 1. 📊 نتائج دور المجموعات
        group_standings_qs = GroupStanding.objects.filter(group__tournament=tournament).select_related('team', 'group')
        ctx['group_standings_data'] = group_standings_qs

        # 2. 🏆 أفضل الفرق في دور المجموعات
        ctx['top_group_teams'] = list(group_standings_qs.order_by('-points', '-goal_difference', '-goals_for')[:5])

        # 3. ⚽ أقوى خط هجوم
        ctx['best_attacks'] = sorted(teams_stats, key=lambda x: (x['scored'], x['gd']), reverse=True)[:5]
        
        # 4. 🛡️ أقوى خط دفاع
        active_teams = [t for t in teams_stats if t['played'] > 0]
        ctx['best_defenses'] = sorted(active_teams if active_teams else teams_stats, key=lambda x: (x['conceded'], -x['scored']))[:5]
        
        # 5. 📉 أضعف خط دفاع
        ctx['worst_defenses'] = sorted(active_teams if active_teams else teams_stats, key=lambda x: (x['conceded'], x['scored']), reverse=True)[:5]
            
        ctx['top_clean_sheets'] = sorted(teams_stats, key=lambda x: x['clean_sheets'], reverse=True)[:5]

        # 6. 🟨🟥 حصيلة البطاقات
        ctx['cards_summary'] = {
            'yellow': yellow_cards,
            'red': red_cards,
            'total': yellow_cards + red_cards,
            'avg_per_match': round((yellow_cards + red_cards) / played_matches, 2) if played_matches > 0 else 0.0
        }

        # 7. 🔥 أكثر مباراة شهدت بطاقات
        most_carded_match = (
            Match.objects.filter(tournament=tournament, status=Match.Status.FINISHED)
            .annotate(cards_count=Count('cards'))
            .order_by('-cards_count')
            .first()
        )
        ctx['most_carded_match'] = most_carded_match

        # 8. 🚨 أكثر الفرق حصولًا على البطاقات
        team_cards = []
        for t in confirmed_teams:
            y = Card.objects.filter(match__tournament=tournament, team=t, card_type=Card.CardType.YELLOW).count()
            r = Card.objects.filter(match__tournament=tournament, team=t, card_type__in=[Card.CardType.RED, Card.CardType.YELLOW_RED]).count()
            team_cards.append({'team': t, 'yellow': y, 'red': r, 'total': y + r})
        team_cards.sort(key=lambda x: (x['total'], x['red'], x['yellow']), reverse=True)
        ctx['most_carded_teams'] = team_cards[:5]

        # 9. 📉 أضعف حصيلة في دور المجموعات
        ctx['weakest_group_teams'] = list(group_standings_qs.order_by('points', 'goal_difference', 'goals_for')[:5])

        # 10. ⭐ الأكثر فوزًا بجائزة رجل المباراة (محسوبة رسمياً من المباريات المسجلة)
        from apps.matches.models import MatchVote
        top_mom_players = list(
            Match.objects.filter(tournament=tournament, man_of_the_match__isnull=False)
            .values('man_of_the_match__id', 'man_of_the_match__first_name', 'man_of_the_match__last_name', 'man_of_the_match__team__name')
            .annotate(
                player__id=F('man_of_the_match__id'),
                player__first_name=F('man_of_the_match__first_name'),
                player__last_name=F('man_of_the_match__last_name'),
                player__team__name=F('man_of_the_match__team__name'),
                mom_count=Count('id')
            )
            .order_by('-mom_count')[:5]
        )
        if not top_mom_players:
            top_mom_players = list(
                MatchVote.objects.filter(match__tournament=tournament)
                .values('player__id', 'player__first_name', 'player__last_name', 'player__team__name')
                .annotate(mom_count=Count('id'))
                .order_by('-mom_count')[:5]
            )
        if not top_mom_players:
            top_mom_players = list(
                PlayerMatchPerformance.objects.filter(match__tournament=tournament, rating__gte=7.5)
                .values('player__id', 'player__first_name', 'player__last_name', 'player__team__name')
                .annotate(mom_count=Count('id'))
                .order_by('-mom_count')[:5]
            )
        ctx['top_mom_players'] = top_mom_players

        # 11. ⚽ حصيلة الأهداف
        highest_scoring_match = (
            Match.objects.filter(tournament=tournament, status=Match.Status.FINISHED)
            .annotate(total_match_goals=F('score_team1') + F('score_team2'))
            .order_by('-total_match_goals')
            .first()
        )
        ctx['goals_summary'] = {
            'total_goals': total_goals,
            'goal_average': goal_average,
            'played_matches': played_matches,
            'highest_scoring_match': highest_scoring_match
        }

        # 12. ✅ الفرق التي لم تتذوق طعم الهزيمة
        ctx['unbeaten_teams'] = [t for t in teams_stats if t['played'] > 0 and t['losses'] == 0]

        # 13. ❌ الفرق التي لم تحقق أي انتصار
        ctx['winless_teams'] = [t for t in teams_stats if t['played'] > 0 and t['wins'] == 0]

        # 7. Competition Records
        highest_scoring_match = (
            Match.objects.filter(tournament=tournament, status=Match.Status.FINISHED)
            .annotate(total_match_goals=F('score_team1') + F('score_team2'))
            .order_by('-total_match_goals')
            .first()
        )
        ctx['highest_scoring_match'] = highest_scoring_match

        biggest_win = (
            Match.objects.filter(tournament=tournament, status=Match.Status.FINISHED)
            .annotate(goal_diff=db_funcs.Abs(F('score_team1') - F('score_team2')))
            .order_by('-goal_diff')
            .first()
        )
        ctx['biggest_win'] = biggest_win

        # Average age
        players_with_dob = Player.objects.filter(
            team__tournament_teams__tournament=tournament,
            team__tournament_teams__is_confirmed=True,
            date_of_birth__isnull=False
        )
        if players_with_dob.exists():
            current_year = timezone.now().year
            ages = [current_year - p.date_of_birth.year for p in players_with_dob]
            ctx['average_player_age'] = round(sum(ages) / len(ages), 1)
        else:
            ctx['average_player_age'] = None

        # 8. Awards from Match Media
        import re
        def clean_title(title_text):
            if not title_text:
                return ""
            # Remove URLs with optional trailing parenthesis/comma
            title_text = re.sub(r'https?://\S+(\s*\)\s*،?)?', '', title_text)
            # Remove redundant characters like •
            title_text = re.sub(r'•+', '', title_text)
            # Clean up hashtags
            title_text = title_text.replace('#', '')
            # Clean up leading/trailing symbols, double spaces
            title_text = re.sub(r'\s+', ' ', title_text).strip()
            # Clean up leading/trailing colons, dots, spaces, commas
            title_text = title_text.strip(':').strip('.').strip('،').strip('-').strip()
            return title_text

        from apps.matches.models import MatchMedia, Referee
        best_goalkeeper_media = None
        best_goal_media = None
        best_scorer_media = None
        other_awards_media = []

        match_medias = MatchMedia.objects.filter(match__tournament=tournament, media_type='image')
        for mm in match_medias:
            title = mm.title or ""
            if "حارس" in title or "القفاز" in title or "goalkeeper" in title.lower():
                best_goalkeeper_media = mm
            elif "هداف" in title or "golden boot" in title.lower():
                best_scorer_media = mm
            elif "هدف" in title or "goal" in title.lower():
                best_goal_media = mm
            else:
                other_awards_media.append(mm)

        if best_goalkeeper_media:
            best_goalkeeper_media.cleaned_title = clean_title(best_goalkeeper_media.title)
        if best_goal_media:
            best_goal_media.cleaned_title = clean_title(best_goal_media.title)
        if best_scorer_media:
            best_scorer_media.cleaned_title = clean_title(best_scorer_media.title)
        for mm in other_awards_media:
            mm.cleaned_title = clean_title(mm.title) if mm.title else ""

        ctx['best_goalkeeper_media'] = best_goalkeeper_media
        ctx['best_goal_media'] = best_goal_media
        ctx['best_scorer_media'] = best_scorer_media
        ctx['other_awards_media'] = other_awards_media

        # Fallback Best Goalkeeper from stats if no media found
        fallback_gk = None
        gks = Player.objects.filter(position='GK', team__tournament_teams__tournament=tournament).distinct()
        gk_sheets = []
        for gk in gks:
            sheets = Match.objects.filter(
                tournament=tournament,
                status=Match.Status.FINISHED
            ).filter(
                Q(team1=gk.team, score_team2=0) |
                Q(team2=gk.team, score_team1=0)
            ).count()
            if sheets > 0:
                gk_sheets.append((gk, sheets))
        if gk_sheets:
            gk_sheets.sort(key=lambda x: x[1], reverse=True)
            fallback_gk = gk_sheets[0][0]
        ctx['fallback_gk'] = fallback_gk

        # 9. List of all goals (Timeline of goals)
        goals_list = list(
            Goal.objects.filter(match__tournament=tournament)
            .select_related('player', 'team', 'match', 'match__team1', 'match__team2', 'assist_player')
            .order_by('match__match_day', 'match__match_date', 'minute')
        )
        ctx['goals_list'] = goals_list

        # Chunk goals into pages of 15 goals for crisp A4 PDF printing with zero page spilling
        CHUNK_SIZE = 15
        goals_pages = [goals_list[i:i + CHUNK_SIZE] for i in range(0, len(goals_list), CHUNK_SIZE)] if goals_list else []
        ctx['goals_pages'] = goals_pages

        # 10. Tournament Referees
        referees_list = []
        tournament_referees = Referee.objects.filter(matches__tournament=tournament).distinct()
        for ref in tournament_referees:
            match_count = ref.matches.filter(tournament=tournament).count()
            referees_list.append({
                'referee': ref,
                'match_count': match_count,
                'photo_url': ref.photo_url
            })
        ctx['tournament_referees'] = referees_list

        # Chunk multi-item sections for strict A4 pagination
        groups_list = list(ctx.get('groups', []))
        ctx['groups_pages'] = [groups_list[i:i + 2] for i in range(0, len(groups_list), 2)] if groups_list else []

        ko_list = list(ctx.get('knockout_matches', []))
        ctx['knockout_pages'] = [ko_list[i:i + 3] for i in range(0, len(ko_list), 3)] if ko_list else []

        ref_list = referees_list
        ctx['referee_pages'] = [ref_list[i:i + 4] for i in range(0, len(ref_list), 4)] if ref_list else []

        # 11. Best XI (التشكيلة المثالية)
        best_gk = fallback_gk
        if not best_gk:
            best_gk = Player.objects.filter(
                position='GK',
                team__tournament_teams__tournament=tournament
            ).first()
            if not best_gk:
                best_gk = Player.objects.filter(
                    team__tournament_teams__tournament=tournament
                ).first()
        
        # Defenders
        defenders = Player.objects.filter(
            position='DEF',
            team__tournament_teams__tournament=tournament
        ).distinct()
        defenders_list = list(defenders[:4])
        if len(defenders_list) < 4:
            other_players = Player.objects.filter(
                team__tournament_teams__tournament=tournament
            ).exclude(id__in=[p.id for p in defenders_list]).exclude(position='GK').distinct()
            defenders_list.extend(list(other_players[:4 - len(defenders_list)]))
            
        # Midfielders
        mids = Player.objects.filter(
            position='MID',
            team__tournament_teams__tournament=tournament
        ).annotate(
            assists_count=Count('assists', filter=Q(assists__match__tournament=tournament))
        ).order_by('-assists_count', 'last_name').distinct()
        mids_list = list(mids[:3])
        if len(mids_list) < 3:
            other_players = Player.objects.filter(
                team__tournament_teams__tournament=tournament
            ).exclude(id__in=[p.id for p in defenders_list] + [p.id for p in mids_list]).exclude(position='GK').distinct()
            mids_list.extend(list(other_players[:3 - len(mids_list)]))
            
        # Forwards
        fwds = Player.objects.filter(
            position='FWD',
            team__tournament_teams__tournament=tournament
        ).annotate(
            goals_count=Count('goals', filter=Q(goals__match__tournament=tournament))
        ).order_by('-goals_count', 'last_name').distinct()
        fwds_list = list(fwds[:3])
        if len(fwds_list) < 3:
            other_players = Player.objects.filter(
                team__tournament_teams__tournament=tournament
            ).exclude(id__in=[p.id for p in defenders_list] + [p.id for p in mids_list] + [p.id for p in fwds_list]).exclude(position='GK').distinct()
            fwds_list.extend(list(other_players[:3 - len(fwds_list)]))
            
        ctx['best_xi'] = {
            'gk': best_gk,
            'defenders': defenders_list,
            'midfielders': mids_list,
            'forwards': fwds_list
        }
        
        # 12. Fair-Play Standings (سجل اللعب النظيف)
        from apps.matches.models import Card
        fair_play_data = {}
        for t in tournament.teams.all():
            fair_play_data[t.id] = {
                'team': t,
                'yellow': 0,
                'red': 0,
                'points': 0
            }
        
        cards = Card.objects.filter(match__tournament=tournament).select_related('team')
        for card in cards:
            tid = card.team.id
            if tid in fair_play_data:
                if card.card_type == 'yellow':
                    fair_play_data[tid]['yellow'] += 1
                    fair_play_data[tid]['points'] += 1
                elif card.card_type in ('red', 'yellow_red'):
                    fair_play_data[tid]['red'] += 1
                    fair_play_data[tid]['points'] += 3
                    
        fair_play_standings = sorted(
            fair_play_data.values(),
            key=lambda x: (x['points'], x['red'], x['yellow'], x['team'].name)
        )
        ctx['fair_play_standings'] = fair_play_standings
        ctx['fair_play_winner'] = fair_play_standings[0] if fair_play_standings else None

        # Chunk fair play standings into pages of 10 teams per A4 page
        fp_list = list(fair_play_standings)
        ctx['fair_play_pages'] = [fp_list[i:i + 10] for i in range(0, len(fp_list), 10)] if fp_list else []

        # 13. Historical Tournaments (السجل التاريخي)
        historical_tournaments = Tournament.objects.filter(winner__isnull=False).select_related('winner', 'runner_up').order_by('-year', '-edition')
        ctx['historical_tournaments'] = historical_tournaments

        # Bracket matches (for interactive visual bracket page)
        ctx['bracket_qf'] = knockout_matches.filter(stage=Match.Stage.QUARTER_FINAL)
        ctx['bracket_sf'] = knockout_matches.filter(stage=Match.Stage.SEMI_FINAL)
        ctx['bracket_final'] = knockout_matches.filter(stage=Match.Stage.FINAL).first()
        ctx['bracket_third'] = knockout_matches.filter(stage=Match.Stage.THIRD_PLACE).first()

        return ctx

class AwardsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Dashboard to manage and view all tournament awards and certificates."""
    template_name = 'tournaments/awards_dashboard.html'

    def test_func(self):
        return self.request.user.role == 'admin'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)
        ctx['tournament'] = tournament

        # Stats for awards
        ctx['top_scorers'] = (
            Goal.objects.filter(match__tournament=tournament)
            .values('player__id', 'player__first_name', 'player__last_name', 'team__name')
            .annotate(goals_count=Count('id'))
            .order_by('-goals_count')[:5]
        )
        
        ctx['best_players'] = (
            PlayerMatchPerformance.objects.filter(match__tournament=tournament)
            .values('player__id', 'player__first_name', 'player__last_name', 'player__team__name')
            .annotate(avg_rating=Count('rating')) # Simplified for now
        )

        return ctx

class FinalCertificateView(DetailView):
    """View to generate the special high-end Final Certificate."""
    model = Tournament
    template_name = 'tournaments/final_certificate.html'
    context_object_name = 'tournament'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tournament = self.object
        
        # Get final match
        final_match = Match.objects.filter(tournament=tournament, stage=Match.Stage.FINAL).first()
        ctx['final_match'] = final_match
        
        if final_match:
            ctx['winner'] = final_match.winner
            ctx['runner_up'] = final_match.loser
            
        return ctx


class TournamentFinanceView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'tournaments/finance.html'

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)
        ctx['tournament'] = tournament
        
        tournament_teams = list(tournament.tournament_teams.filter(is_confirmed=True).select_related('team'))
        ctx['tournament_teams'] = tournament_teams
        
        expenses = tournament.expenses.all().order_by('-date')
        ctx['expenses'] = expenses
        
        # Other revenues (sponsors, donations, ads)
        revenues = tournament.revenues.all().order_by('-date')
        ctx['revenues'] = revenues
        
        # Financial Calculations
        from django.db.models import Sum
        total_paid = tournament.tournament_teams.filter(is_confirmed=True).aggregate(total=Sum('amount_paid'))['total'] or 0
        total_revenues = revenues.aggregate(total=Sum('amount'))['total'] or 0
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
        
        num_teams = len(tournament_teams)
        expected_revenue = (tournament.subscription_price * num_teams) + total_revenues
        remaining_revenue = (tournament.subscription_price * num_teams) - total_paid
        net_balance = (total_paid + total_revenues) - total_expenses
        
        num_paid_teams = sum(1 for tt in tournament_teams if tt.payment_confirmed)

        ctx['finance_summary'] = {
            'total_paid': total_paid,
            'total_revenues': total_revenues,
            'total_perceived': total_paid + total_revenues,
            'total_expenses': total_expenses,
            'expected_revenue': expected_revenue,
            'remaining_revenue': remaining_revenue,
            'net_balance': net_balance,
            'num_teams': num_teams,
            'num_paid_teams': num_paid_teams,
        }
        
        # Generate WhatsApp share links, calculate remaining balance, and prefetch transactions history
        import urllib.parse
        from django.urls import reverse
        for tt in tournament_teams:
            tt.remaining = max(0, tournament.subscription_price - tt.amount_paid)
            
            # Build receipt link
            receipt_url = self.request.build_absolute_uri(reverse('tournaments:payment_receipt', args=[tt.pk]))
            
            # Construct a polished Arabic message
            msg = (
                f"السلام عليكم ورحمة الله وبركاته 📣\n\n"
                f"إثبات دفع اشتراك - بطولة: {tournament.name}\n"
                f"الفريق: {tt.team.name}\n"
                f"المبلغ الإجمالي المدفوع: {tt.amount_paid} DZD\n"
                f"المبلغ المتبقي: {tt.remaining} DZD\n"
                f"حالة الدفع: {'مؤكد بالكامل ✅' if tt.payment_confirmed else 'غير مكتمل ⏳'}\n\n"
                f"رابط الوصل الرسمي لمعاينة وتحميل الإيصال:\n{receipt_url}"
            )
            tt.whatsapp_link = f"https://api.whatsapp.com/send?text={urllib.parse.quote(msg)}"
            
            # Prefetch transactions for history display
            tt.payment_history = tt.transactions.all().order_by('-date')
        
        return ctx

    def post(self, request, *args, **kwargs):
        pk = self.kwargs.get('pk')
        tournament = get_object_or_404(Tournament, pk=pk)
        action = request.POST.get('action')
        
        if action == 'update_price':
            price = request.POST.get('subscription_price')
            try:
                tournament.subscription_price = float(price) if price else 0.00
                tournament.save(update_fields=['subscription_price'])
                messages.success(request, _('✅ Tarif de participation mis à jour ! / تم تحديث سعر الاشتراك.'))
            except ValueError:
                messages.error(request, _('❌ Prix invalide.'))
                
        elif action == 'update_payments':
            tournament_teams = tournament.tournament_teams.filter(is_confirmed=True)
            updated_count = 0
            for tt in tournament_teams:
                amount_paid_key = f'amount_paid_{tt.team.pk}'
                confirmed_key = f'payment_confirmed_{tt.team.pk}'
                
                paid_str = request.POST.get(amount_paid_key)
                confirmed_val = request.POST.get(confirmed_key) == 'on'
                
                try:
                    new_amount = float(paid_str) if paid_str else 0.00
                    old_amount = float(tt.amount_paid)
                    
                    # Create transaction if amount has changed
                    if new_amount != old_amount:
                        from apps.tournaments.models import TeamPaymentTransaction
                        diff = new_amount - old_amount
                        note_text = "تحديث المبلغ" if diff > 0 else "تعديل المبلغ بالخصم"
                        TeamPaymentTransaction.objects.create(
                            tournament_team=tt,
                            amount=diff,
                            notes=f"{note_text} / Modification"
                        )
                    
                    tt.amount_paid = new_amount
                    tt.payment_confirmed = confirmed_val
                    tt.save(update_fields=['amount_paid', 'payment_confirmed'])
                    updated_count += 1
                except ValueError:
                    pass
            messages.success(request, _('✅ Paiements mis à jour (%d équipes) ! / تم تحديث مستحقات الفرق.') % updated_count)
            
        elif action == 'add_expense':
            title = request.POST.get('title')
            amount = request.POST.get('amount')
            notes = request.POST.get('notes', '')
            
            if title and amount:
                try:
                    from apps.tournaments.models import TournamentExpense
                    TournamentExpense.objects.create(
                        tournament=tournament,
                        title=title,
                        amount=float(amount),
                        notes=notes
                    )
                    messages.success(request, _('✅ Dépense enregistrée ! / تم إضافة المصاريف بنجاح.'))
                except ValueError:
                    messages.error(request, _('❌ Montant invalide.'))
            else:
                messages.error(request, _('❌ Informations incomplètes.'))
                
        elif action == 'delete_expense':
            expense_id = request.POST.get('expense_id')
            from apps.tournaments.models import TournamentExpense
            expense = get_object_or_404(TournamentExpense, pk=expense_id, tournament=tournament)
            title = expense.title
            expense.delete()
            messages.warning(request, _('🗑️ Dépense « %s » supprimée.') % title)

        elif action == 'edit_expense':
            expense_id = request.POST.get('expense_id')
            title = request.POST.get('title')
            amount = request.POST.get('amount')
            notes = request.POST.get('notes', '')
            from apps.tournaments.models import TournamentExpense
            expense = get_object_or_404(TournamentExpense, pk=expense_id, tournament=tournament)
            if title and amount:
                try:
                    expense.title = title
                    expense.amount = float(amount)
                    expense.notes = notes
                    expense.save()
                    messages.success(request, _('📝 Dépense modifiée ! / تم تعديل المصاريف بنجاح.'))
                except ValueError:
                    messages.error(request, _('❌ Montant invalide.'))

        elif action == 'add_revenue':
            title = request.POST.get('title')
            amount = request.POST.get('amount')
            notes = request.POST.get('notes', '')
            
            if title and amount:
                try:
                    from apps.tournaments.models import TournamentRevenue
                    TournamentRevenue.objects.create(
                        tournament=tournament,
                        title=title,
                        amount=float(amount),
                        notes=notes
                    )
                    messages.success(request, _('✅ Recette enregistrée ! / تم إضافة الإيراد بنجاح.'))
                except ValueError:
                    messages.error(request, _('❌ Montant invalide.'))
            else:
                messages.error(request, _('❌ Informations incomplètes.'))
                
        elif action == 'delete_revenue':
            revenue_id = request.POST.get('revenue_id')
            from apps.tournaments.models import TournamentRevenue
            revenue = get_object_or_404(TournamentRevenue, pk=revenue_id, tournament=tournament)
            title = revenue.title
            revenue.delete()
            messages.warning(request, _('🗑️ Recette « %s » supprimée.') % title)

        elif action == 'edit_revenue':
            revenue_id = request.POST.get('revenue_id')
            title = request.POST.get('title')
            amount = request.POST.get('amount')
            notes = request.POST.get('notes', '')
            from apps.tournaments.models import TournamentRevenue
            revenue = get_object_or_404(TournamentRevenue, pk=revenue_id, tournament=tournament)
            if title and amount:
                try:
                    revenue.title = title
                    revenue.amount = float(amount)
                    revenue.notes = notes
                    revenue.save()
                    messages.success(request, _('📝 Recette modifiée ! / تم تعديل الإيراد بنجاح.'))
                except ValueError:
                    messages.error(request, _('❌ Montant invalide.'))

        elif action == 'delete_transaction':
            tx_id = request.POST.get('transaction_id')
            from apps.tournaments.models import TeamPaymentTransaction
            tx = get_object_or_404(TeamPaymentTransaction, pk=tx_id, tournament_team__tournament=tournament)
            tt = tx.tournament_team
            tt.amount_paid -= tx.amount
            if tt.amount_paid < 0:
                tt.amount_paid = 0
            tt.payment_confirmed = (tt.amount_paid >= tournament.subscription_price)
            tt.save(update_fields=['amount_paid', 'payment_confirmed'])
            tx.delete()
            messages.warning(request, _('🗑️ Transaction supprimée et solde mis à jour ! / تم حذف المعاملة وتحديث رصيد الفريق.'))

        elif action == 'add_team_installment':
            tt_id = request.POST.get('tournament_team_id')
            amount_str = request.POST.get('amount')
            notes = request.POST.get('notes', '')
            from apps.tournaments.models import TournamentTeam, TeamPaymentTransaction
            tt = get_object_or_404(TournamentTeam, pk=tt_id, tournament=tournament)
            if amount_str:
                try:
                    amount = float(amount_str)
                    if amount != 0:
                        tt.amount_paid += amount
                        if tt.amount_paid < 0:
                            tt.amount_paid = 0
                        tt.payment_confirmed = (tt.amount_paid >= tournament.subscription_price)
                        tt.save(update_fields=['amount_paid', 'payment_confirmed'])
                        
                        TeamPaymentTransaction.objects.create(
                            tournament_team=tt,
                            amount=amount,
                            notes=notes or _("Installment payment / دفعة اشتراك")
                        )
                        messages.success(request, _('✅ Versement enregistré avec succès ! / تم تسجيل الدفعة بنجاح.'))
                except ValueError:
                    messages.error(request, _('❌ Montant invalide.'))
            
        return redirect('tournaments:finance', pk=pk)


class PaymentReceiptView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    template_name = 'tournaments/payment_receipt.html'
    context_object_name = 'tt'

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def get_queryset(self):
        from apps.tournaments.models import TournamentTeam
        return TournamentTeam.objects.all().select_related('tournament', 'team')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        ctx['now'] = timezone.now()
        
        # Calculate remaining
        tt = self.object
        remaining = max(0, tt.tournament.subscription_price - tt.amount_paid)
        ctx['remaining'] = remaining
        
        # Construct QR content (text)
        qr_lines = [
            f"RECU DE PAIEMENT - N° REC-{tt.tournament.year}-{tt.id:04d}",
            f"Tournoi: {tt.tournament.name}",
            f"Equipe: {tt.team.name}",
            f"Frais d'inscription: {tt.tournament.subscription_price} DZD",
            f"Montant paye: {tt.amount_paid} DZD",
            f"Reste a payer: {remaining} DZD",
            f"Statut: {'CONFIRME' if tt.payment_confirmed else 'PARTIEL / NON VALIDE'}",
            f"Date: {ctx['now'].strftime('%d/%m/%Y %H:%M')}"
        ]
        ctx['qr_content'] = "\n".join(qr_lines)
        
        return ctx


class TournamentFinanceReportView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Tournament
    template_name = 'tournaments/finance_report.html'
    context_object_name = 'tournament'

    def test_func(self):
        return self.request.user.role in ('admin', 'organizer')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tournament = self.object
        
        tournament_teams = tournament.tournament_teams.filter(is_confirmed=True).select_related('team')
        ctx['tournament_teams'] = tournament_teams
        
        expenses = tournament.expenses.all().order_by('-date')
        ctx['expenses'] = expenses
        
        # Other revenues (sponsors, donations, ads)
        revenues = tournament.revenues.all().order_by('-date')
        ctx['revenues'] = revenues
        
        # Financial Calculations
        from django.db.models import Sum
        total_paid = tournament_teams.aggregate(total=Sum('amount_paid'))['total'] or 0
        total_revenues = revenues.aggregate(total=Sum('amount'))['total'] or 0
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0
        
        num_teams = tournament_teams.count()
        num_paid_teams = tournament_teams.filter(payment_confirmed=True).count()
        num_unpaid_teams = num_teams - num_paid_teams
        
        expected_revenue = (tournament.subscription_price * num_teams) + total_revenues
        remaining_revenue = (tournament.subscription_price * num_teams) - total_paid
        net_balance = (total_paid + total_revenues) - total_expenses
        
        ctx['finance_summary'] = {
            'total_paid': total_paid,
            'total_revenues': total_revenues,
            'total_perceived': total_paid + total_revenues,
            'total_expenses': total_expenses,
            'expected_revenue': expected_revenue,
            'remaining_revenue': remaining_revenue,
            'net_balance': net_balance,
            'num_teams': num_teams,
            'num_paid_teams': num_paid_teams,
            'num_unpaid_teams': num_unpaid_teams,
        }
        
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        
        from django.utils import timezone
        now = timezone.now()
        ctx['now'] = now
        
        import json
        ctx['qr_content'] = json.dumps({
            'doc': 'BILAN FINANCIER',
            'net_balance': f"{net_balance} DZD",
            'date': now.strftime('%Y-%m-%d %H:%M')
        })
        
        return ctx


class CommitteeMemberListView(DetailView):
    """Public list of organizing committee members for a given tournament."""
    model = Tournament
    template_name = 'tournaments/committee_list.html'
    context_object_name = 'tournament'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['members'] = self.object.committee_members.order_by('order', 'full_name')
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        return ctx


class CommitteeMemberCardView(DetailView):
    """Printable ID card for a single committee member."""
    model = CommitteeMember
    template_name = 'tournaments/committee_card.html'
    context_object_name = 'member'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        member = self.object
        tournament = member.tournament
        ctx['tournament'] = tournament

        # Build ordered queryset to find prev/next
        qs = list(tournament.committee_members.order_by('order', 'full_name'))
        current_idx = next((i for i, m in enumerate(qs) if m.pk == member.pk), None)
        ctx['prev_member'] = qs[current_idx - 1] if current_idx and current_idx > 0 else None
        ctx['next_member'] = qs[current_idx + 1] if current_idx is not None and current_idx < len(qs) - 1 else None
        ctx['member_index'] = (current_idx or 0) + 1
        ctx['member_total'] = len(qs)

        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        return ctx


class CommitteeMemberCardsAllView(DetailView):
    """Printable ID cards for ALL members of a tournament at once."""
    model = Tournament
    template_name = 'tournaments/committee_cards_all.html'
    context_object_name = 'tournament'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['members'] = self.object.committee_members.order_by('order', 'full_name')
        from apps.core.models import SiteSettings
        ctx['site_settings'] = SiteSettings.load()
        return ctx
