"""
TurniQ — Tournament Scheduler Service
Handles:
  1. Automatic group seeding
  2. Round-robin group stage match generation
  3. Standings recalculation (atomic)
  4. Knockout bracket generation from advancing teams
  5. Winner propagation through bracket
"""
import itertools
import random
from datetime import timedelta, time as dtime
from django.db import transaction
from django.utils import timezone

from apps.tournaments.models import Tournament, Group, GroupStanding, TournamentTeam
from apps.matches.models import Match


class GroupSeeder:
    """
    Divides confirmed tournament teams into balanced groups.
    Uses snake-draft seeding to distribute strength evenly.
    """

    def __init__(self, tournament: Tournament):
        self.tournament = tournament

    @transaction.atomic
    def seed_groups(self) -> list[Group]:
        """
        1. Delete existing groups (and their matches).
        2. Fetch confirmed teams (sorted by seed if set, else random).
        3. Create num_groups Group objects.
        4. Distribute teams using snake draft.
        5. Create GroupStanding rows.
        """
        t = self.tournament

        # Validate
        confirmed = list(
            TournamentTeam.objects
            .filter(tournament=t, is_confirmed=True)
            .select_related('team')
            .order_by('seed', 'team__name')
        )
        if len(confirmed) < 2:
            raise ValueError("Au moins 2 équipes confirmées sont nécessaires.")
        if t.num_groups < 1:
            raise ValueError("Le nombre de groupes doit être >= 1.")

        # Clean previous groups
        t.groups.all().delete()

        # Shuffle unseeded teams, keep seeded ones first
        seeded = [tt for tt in confirmed if tt.seed]
        unseeded = [tt for tt in confirmed if not tt.seed]
        random.shuffle(unseeded)
        ordered = seeded + unseeded

        # Create group objects (Groupe A, Groupe B, …)
        import string
        groups = []
        for i in range(t.num_groups):
            letter = string.ascii_uppercase[i] if i < 26 else f"G{i+1}"
            group = Group.objects.create(tournament=t, name=f"Groupe {letter}")
            groups.append(group)

        # Snake draft: row i -> groups[i % num_groups] (alternating direction)
        for idx, tt in enumerate(ordered):
            row = idx // t.num_groups
            col = idx % t.num_groups
            # Reverse direction on odd rows
            actual_col = col if row % 2 == 0 else (t.num_groups - 1 - col)
            actual_col = min(actual_col, len(groups) - 1)
            target_group = groups[actual_col]
            target_group.teams.add(tt.team)
            # Create standing row
            GroupStanding.objects.create(group=target_group, team=tt.team)

        return groups


class MatchScheduler:
    """
    Generates the full calendar of matches for group stage and knockout.
    """

    def __init__(self, tournament: Tournament):
        self.tournament = tournament

    def _make_round_robin_rounds(self, teams, double_leg=False):
        """
        Generates a list of rounds, where each round is a list of pairs (team1, team2).
        Uses a modified Circle Method to ensure Round 1 pairs adjacent teams: 1v2, 3v4...
        """
        n = len(teams)
        if n < 2:
            return []

        # If odd number of teams, add None for bye
        temp_teams = list(teams)
        if n % 2 != 0:
            temp_teams.append(None)
        
        # Rearrange so that Circle Method pairs 1v2, 3v4, 5v6 in Round 1
        # By taking even indices, then odd indices reversed
        temp_teams = temp_teams[0::2] + temp_teams[1::2][::-1]
        
        num_teams = len(temp_teams)
        rounds = []
        
        # Generate single leg rounds
        for r in range(num_teams - 1):
            round_pairs = []
            for i in range(num_teams // 2):
                home = temp_teams[i]
                away = temp_teams[num_teams - 1 - i]
                
                if home is not None and away is not None:
                    # Alternate home/away for the first team to balance home/away matches
                    if r % 2 == 0:
                        round_pairs.append((home, away))
                    else:
                        round_pairs.append((away, home))
                elif home is not None:
                    round_pairs.append((home, None))
                elif away is not None:
                    round_pairs.append((away, None))
            
            # Ensure the bye match is always at the end of the list for visual clarity
            round_pairs.sort(key=lambda pair: 1 if pair[0] is None or pair[1] is None else 0)
            
            rounds.append(round_pairs)
            
            # Rotate teams (keep first team fixed, rotate others)
            temp_teams = [temp_teams[0]] + [temp_teams[-1]] + temp_teams[1:-1]
            
        if double_leg:
            # Generate second leg rounds (swap home/away)
            second_leg_rounds = []
            for rd in rounds:
                second_leg_round = []
                for home, away in rd:
                    second_leg_round.append((away, home))
                second_leg_rounds.append(second_leg_round)
            rounds.extend(second_leg_rounds)
            
        return rounds

    @transaction.atomic
    def generate_group_stage(
        self,
        start_date=None,
        match_time="17:00",
        gap_days: int = 2,
    ) -> list[Match]:
        """
        For each group: generate all unique pairings (round-robin) using Circle Method.
        Matches are distributed across days with gap_days between matchdays.
        No team plays more than once on the same day.
        """
        t = self.tournament
        
        # SPECIAL LOGIC: "الماضي يلهم الحاضر" or keyword "كهول" (Veterans Tournament)
        # We check for the specific name or the word "كهول" to be sure it applies.
        is_veterans = "الماضي يلهم الحاضر" in t.name or "كهول" in t.name
        is_wafa = "الوفاء" in t.name or "الإخاء" in t.name
        
        if is_veterans:
            start_date = timezone.datetime(2026, 5, 22).date()
            match_time = "17:30"
            matches_per_day = 1
        elif is_wafa:
            start_date = timezone.datetime(2026, 7, 16).date()
            matches_per_day = 2
        else:
            matches_per_day = 2

        if start_date is None:
            start_date = t.start_date or timezone.now().date()

        # Delete existing group-stage matches
        t.matches.filter(stage=Match.Stage.GROUP).delete()

        h, m = (int(x) for x in match_time.split(':'))
        current_date = start_date

        # 1. Generate all rounds for all groups using Circle Method
        all_group_rounds = []
        group_team_counts = {g.id: g.groupstanding_set.count() for g in t.groups.all()}
        for group in t.groups.all():
            teams = [s.team for s in group.groupstanding_set.select_related('team').order_by('id')]
            if len(teams) < 2:
                continue
            
            double_leg = (t.format == Tournament.Format.ROUND_ROBIN)
            rounds = self._make_round_robin_rounds(teams, double_leg=double_leg)
            all_group_rounds.append({
                'group': group,
                'rounds': rounds
            })

        if not all_group_rounds:
            return []

        # 2. Interlace round by round
        max_rounds = max(len(g['rounds']) for g in all_group_rounds)
        
        created_matches = []
        match_count_in_day = 0

        for r_idx in range(max_rounds):
            # Gather all matches for round r_idx across all groups
            round_matches = []
            for g_data in all_group_rounds:
                if r_idx < len(g_data['rounds']):
                    for team1, team2 in g_data['rounds'][r_idx]:
                        round_matches.append((g_data['group'], team1, team2))
            
            previous_group = None
            def advance_date(dt, vets, wafa, gap):
                if vets:
                    if dt.weekday() == 4:
                        dt += timedelta(days=1)
                    else:
                        days_to_friday = (4 - dt.weekday() + 7) % 7
                        if days_to_friday == 0: days_to_friday = 7
                        dt += timedelta(days=days_to_friday)
                elif wafa:
                    dt += timedelta(days=1)
                    if dt.weekday() == 4:
                        dt += timedelta(days=1)
                else:
                    dt += timedelta(days=gap)
                return dt

            previous_group = None
            for idx, (group, team1, team2) in enumerate(round_matches):
                group_changed = (previous_group is not None and group != previous_group)
                
                # Advance day if group changed OR if daily limit reached (and it's a real match)
                if (group_changed and match_count_in_day > 0) or (match_count_in_day >= matches_per_day and team2 is not None):
                    current_date = advance_date(current_date, is_veterans, is_wafa, 1)
                    match_count_in_day = 0

                previous_group = group

                current_h, current_m = h, m
                if is_wafa:
                    # Alternate the 17:00 and 18:45 timeslots per round to balance play times as much as possible
                    if r_idx % 2 == 0:
                        if match_count_in_day == 0:
                            current_h, current_m = 17, 0
                        elif match_count_in_day == 1:
                            current_h, current_m = 18, 45
                    else:
                        if match_count_in_day == 0:
                            current_h, current_m = 18, 45
                        elif match_count_in_day == 1:
                            current_h, current_m = 17, 0

                dt = timezone.make_aware(
                    timezone.datetime.combine(current_date, dtime(current_h, current_m))
                )
                
                match = Match.objects.create(
                    tournament=t,
                    group=group,
                    stage=Match.Stage.GROUP,
                    match_day=r_idx + 1,
                    team1=team1,
                    team2=team2,
                    match_date=dt,
                    venue=t.location,
                    status=Match.Status.SCHEDULED,
                )
                created_matches.append(match)
                
                # Only count actual matches towards the daily limit (bye matches take no time)
                if team2 is not None:
                    match_count_in_day += 1
            
            # Always advance day at the end of the round for the next round
            current_date = advance_date(current_date, is_veterans, is_wafa, gap_days)
            match_count_in_day = 0

        return created_matches

    @transaction.atomic
    def generate_knockout_bracket(
        self,
        advancing_teams: list,
        start_date=None,
        gap_days: int = 3,
        match_time: str = "17:00",
    ) -> list[Match]:
        """
        Generate all knockout rounds from the list of advancing teams.
        Teams are paired: [0 vs last, 1 vs last-1, …] for balanced bracket.
        Returns all created matches.
        """
        t = self.tournament
        n = len(advancing_teams)

        # SPECIAL LOGIC: "الماضي يلهم الحاضر" or keyword "كهول" (Veterans Tournament)
        is_veterans = "الماضي يلهم الحاضر" in t.name or "كهول" in t.name
        is_wafa = "الوفاء" in t.name or "الإخاء" in t.name
        
        if is_veterans:
            match_time = "17:30"
            gap_days = 0 # Handled by weekday logic below
        elif is_wafa:
            gap_days = 1

        if n < 2:
            raise ValueError("Need at least 2 teams for knockout.")

        stage_map = {
            16: Match.Stage.ROUND_OF_16,
            8:  Match.Stage.QUARTER_FINAL,
            4:  Match.Stage.SEMI_FINAL,
            2:  Match.Stage.FINAL,
        }
        # Find nearest stage
        def get_stage(count):
            if count == 16: return Match.Stage.ROUND_OF_16
            if count == 8: return Match.Stage.QUARTER_FINAL
            if count == 4: return Match.Stage.SEMI_FINAL
            if count == 2: return Match.Stage.FINAL
            
            for threshold, stage in stage_map.items():
                if count <= threshold:
                    return stage
            return Match.Stage.ROUND_OF_16

        # Delete existing knockout matches
        t.matches.exclude(stage=Match.Stage.GROUP).delete()

        if start_date is None:
            # Start 3 days after last group match
            last_group_match = (
                t.matches.filter(stage=Match.Stage.GROUP)
                .order_by('-match_date').first()
            )
            if last_group_match:
                start_date = last_group_match.match_date.date() + timedelta(days=3)
            else:
                start_date = timezone.now().date() + timedelta(days=3)

        h, m_val = (int(x) for x in match_time.split(':'))
        current_date = start_date
        all_created: list[Match] = []

        # Build rounds recursively
        current_teams = advancing_teams[:]
        round_num = 1
        previous_round_matches = []
        match_count_in_day = 0

        while len(current_teams) >= 2:
            stage = get_stage(len(current_teams))
            current_round_matches = []

            # Pair teams for this round
            paired = []
            tc = current_teams[:]
            if round_num == 1 and len(tc) == 8 and len(self.tournament.groups.all()) >= 4:
                # Standard 4-group quarter-final cross pairing (as shown in official tournament tree):
                # tc: [A1, B1, C1, D1, A2, B2, C2, D2]
                # QF1 (Match 1 - Top Right):    A1 vs B2 (tc[0], tc[5])
                # QF2 (Match 2 - Bottom Right): C1 vs D2 (tc[2], tc[7])
                # QF3 (Match 3 - Top Left):     B1 vs A2 (tc[1], tc[4])
                # QF4 (Match 4 - Bottom Left):  D1 vs C2 (tc[3], tc[6])
                paired = [
                    (tc[0], tc[5]),  # QF1: A1 vs B2
                    (tc[2], tc[7]),  # QF2: C1 vs D2
                    (tc[1], tc[4]),  # QF3: B1 vs A2
                    (tc[3], tc[6]),  # QF4: D1 vs C2
                ]
            else:
                while len(tc) >= 2:
                    paired.append((tc.pop(0), tc.pop()))
                if tc:
                    paired.append((tc[0], None))

            for pair_idx, (t1, t2) in enumerate(paired):
                if t2 is None and stage != Match.Stage.FINAL:
                    continue  # bye
                
                current_h, current_m = h, m_val
                if is_wafa:
                    if match_count_in_day == 0:
                        current_h, current_m = 17, 0
                    elif match_count_in_day == 1:
                        current_h, current_m = 18, 45

                dt = timezone.make_aware(
                    timezone.datetime.combine(current_date, dtime(current_h, current_m))
                )
                match = Match.objects.create(
                    tournament=t,
                    stage=stage,
                    team1=t1,
                    team2=t2,
                    match_date=dt,
                    match_day=pair_idx + 1,
                    round_number=round_num,
                    venue=t.location,
                    status=Match.Status.SCHEDULED,
                )
                current_round_matches.append(match)
                all_created.append(match)
                
                match_count_in_day += 1
                matches_per_day = 2 if is_wafa else 1
                if match_count_in_day >= matches_per_day or pair_idx == len(paired) - 1:
                    # Increment date
                    if is_veterans:
                        # One match per day on Fri/Sat
                        if current_date.weekday() == 4: # Friday -> Saturday
                            current_date += timedelta(days=1)
                        else: # Saturday -> next Friday
                            days_to_friday = (4 - current_date.weekday() + 7) % 7
                            if days_to_friday == 0: days_to_friday = 7
                            current_date += timedelta(days=days_to_friday)
                    elif is_wafa:
                        current_date += timedelta(days=1) # 1 day gap
                        if current_date.weekday() == 4: # Skip Friday
                            current_date += timedelta(days=1)
                    else:
                        current_date += timedelta(days=gap_days)
                    match_count_in_day = 0

            # Link previous round matches to current round matches
            if previous_round_matches:
                for i, prev_match in enumerate(previous_round_matches):
                    # Every two matches in previous round link to one match in current round
                    next_match_idx = i // 2
                    if next_match_idx < len(current_round_matches):
                        prev_match.next_match = current_round_matches[next_match_idx]
                        prev_match.save(update_fields=['next_match'])

            if stage == Match.Stage.FINAL:
                # Also create 3rd place match if we had semi-finals
                if previous_round_matches and len(previous_round_matches) >= 2:
                    dt3 = timezone.make_aware(
                        timezone.datetime.combine(current_date, dtime(h, m_val))
                    )
                    tp = Match.objects.create(
                        tournament=t,
                        stage=Match.Stage.THIRD_PLACE,
                        team1=None,  # Will be filled by losers of semis
                        team2=None,
                        match_date=dt3,
                        match_day=1,
                        round_number=round_num,
                        venue=t.location,
                        status=Match.Status.SCHEDULED,
                    )
                    all_created.append(tp)
                break  # Final round done

            # Next round: winners TBD (placeholders)
            previous_round_matches = current_round_matches
            current_teams = [None] * len(current_round_matches)
            round_num += 1
            if match_count_in_day != 0:
                # Force round change to start on a new day
                if is_veterans:
                    pass
                elif is_wafa:
                    current_date += timedelta(days=1)
                    if current_date.weekday() == 4: # Skip Friday
                        current_date += timedelta(days=1)
                else:
                    current_date += timedelta(days=gap_days)
                match_count_in_day = 0
            else:
                # If match_count_in_day is 0, we already incremented date at the end of the round loop.
                # Just optionally add gap days between rounds if not wafa.
                if not is_wafa and not is_veterans:
                    current_date += timedelta(days=gap_days)

        return all_created

    @transaction.atomic
    def generate_manual_knockout_bracket(
        self,
        pairs: list,
        start_date=None,
        gap_days: int = 3,
        match_time: str = "17:00",
    ) -> list[Match]:
        """
        Generate all knockout rounds starting from a manually defined list of pairs for the first round.
        Pairs format: [(team1, team2), (team3, team4), ...]
        """
        t = self.tournament
        num_matches = len(pairs)
        if num_matches < 1:
            raise ValueError("Au moins une rencontre est nécessaire pour la phase finale.")

        # Determine stage for first round
        if num_matches >= 8:
            first_stage = Match.Stage.ROUND_OF_16
        elif num_matches >= 4:
            first_stage = Match.Stage.QUARTER_FINAL
        elif num_matches >= 2:
            first_stage = Match.Stage.SEMI_FINAL
        else:
            first_stage = Match.Stage.FINAL

        # Delete existing knockout matches
        t.matches.exclude(stage=Match.Stage.GROUP).delete()

        if start_date is None:
            last_group_match = t.matches.filter(stage=Match.Stage.GROUP).order_by('-match_date').first()
            if last_group_match:
                start_date = last_group_match.match_date.date() + timedelta(days=3)
            else:
                start_date = timezone.now().date() + timedelta(days=3)

        h, m_val = (int(x) for x in match_time.split(':'))
        current_date = start_date
        all_created: list[Match] = []

        is_veterans = "الماضي يلهم الحاضر" in t.name or "كهول" in t.name
        is_wafa = "الوفاء" in t.name or "الإخاء" in t.name

        if is_veterans:
            match_time = "17:30"
            gap_days = 0
        elif is_wafa:
            gap_days = 1

        # Create First Round matches from specified pairs
        previous_round_matches = []
        for pair_idx, (t1, t2) in enumerate(pairs):
            current_h, current_m = h, m_val
            dt = timezone.make_aware(
                timezone.datetime.combine(current_date, dtime(current_h, current_m))
            )
            match = Match.objects.create(
                tournament=t,
                stage=first_stage,
                team1=t1,
                team2=t2,
                match_date=dt,
                match_day=pair_idx + 1,
                round_number=1,
                venue=t.location,
                status=Match.Status.SCHEDULED,
            )
            previous_round_matches.append(match)
            all_created.append(match)
            current_date += timedelta(days=gap_days if not is_wafa else 1)

        # Build subsequent rounds recursively up to FINAL
        stage_sequence = [
            Match.Stage.ROUND_OF_16,
            Match.Stage.QUARTER_FINAL,
            Match.Stage.SEMI_FINAL,
            Match.Stage.FINAL
        ]
        
        current_stage_idx = stage_sequence.index(first_stage)
        round_num = 2

        while current_stage_idx < len(stage_sequence) - 1:
            current_stage_idx += 1
            next_stage = stage_sequence[current_stage_idx]
            num_next_matches = len(previous_round_matches) // 2
            if num_next_matches == 0:
                break

            current_round_matches = []
            for pair_idx in range(num_next_matches):
                dt = timezone.make_aware(
                    timezone.datetime.combine(current_date, dtime(h, m_val))
                )
                match = Match.objects.create(
                    tournament=t,
                    stage=next_stage,
                    team1=None,
                    team2=None,
                    match_date=dt,
                    match_day=pair_idx + 1,
                    round_number=round_num,
                    venue=t.location,
                    status=Match.Status.SCHEDULED,
                )
                current_round_matches.append(match)
                all_created.append(match)
                current_date += timedelta(days=gap_days if not is_wafa else 1)

            # Link previous round matches to current round matches
            for i, prev_match in enumerate(previous_round_matches):
                next_match_idx = i // 2
                if next_match_idx < len(current_round_matches):
                    prev_match.next_match = current_round_matches[next_match_idx]
                    prev_match.save(update_fields=['next_match'])

            if next_stage == Match.Stage.FINAL:
                # Also create 3rd place match if coming from SEMI_FINAL
                dt3 = timezone.make_aware(
                    timezone.datetime.combine(current_date, dtime(h, m_val))
                )
                tp = Match.objects.create(
                    tournament=t,
                    stage=Match.Stage.THIRD_PLACE,
                    team1=None,
                    team2=None,
                    match_date=dt3,
                    match_day=1,
                    round_number=round_num,
                    venue=t.location,
                    status=Match.Status.SCHEDULED,
                )
                all_created.append(tp)
                break

            previous_round_matches = current_round_matches
            round_num += 1

        t.status = Tournament.Status.KNOCKOUT
        t.save(update_fields=['status'])
        return all_created


class StandingsCalculator:
    """
    Atomically recalculates GroupStanding for a group
    by replaying all FINISHED group matches from scratch.
    """

    def __init__(self, tournament: Tournament):
        self.tournament = tournament

    @transaction.atomic
    def recalculate_group(self, group: Group):
        """Full recalculation: reset → replay all finished matches."""
        # Reset all standings in the group
        GroupStanding.objects.filter(group=group).update(
            played=0, won=0, drawn=0, lost=0,
            goals_for=0, goals_against=0, goal_difference=0, points=0
        )

        # Get all team IDs in this group
        group_team_ids = set(group.teams.values_list('id', flat=True))

        from django.db.models import Q
        finished = Match.objects.filter(
            tournament=self.tournament,
            status=Match.Status.FINISHED,
        ).filter(
            Q(group=group) |
            Q(group__isnull=True, team1_id__in=group_team_ids) |
            Q(group__isnull=True, team2_id__in=group_team_ids)
        ).select_related('team1', 'team2')

        for match in finished:
            self._apply_match(match, group, group_team_ids)

    def _apply_match(self, match: Match, group: Group, group_team_ids: set):
        t = self.tournament
        
        has_team1 = match.team1_id in group_team_ids
        has_team2 = match.team2_id in group_team_ids
        
        if not has_team1 and not has_team2:
            return

        # Forfeit handling
        if match.is_forfeit:
            if match.forfeit_type == Match.ForfeitType.TEAM1:
                score1, score2 = 0, 3
            elif match.forfeit_type == Match.ForfeitType.TEAM2:
                score1, score2 = 3, 0
            else: # BOTH
                score1, score2 = 0, 0
        else:
            score1 = match.score_team1 or 0
            score2 = match.score_team2 or 0
        
        if has_team1:
            s1, _ = GroupStanding.objects.get_or_create(group=group, team=match.team1)
            s1.played += 1
            s1.goals_for += score1
            s1.goals_against += score2
            s1.goal_difference = s1.goals_for - s1.goals_against
            
            if match.result == 'team1_win':
                s1.won += 1;  s1.points += t.points_win
            elif match.result == 'team2_win':
                s1.lost += 1; s1.points += t.points_loss
            elif match.result == 'double_forfeit':
                s1.lost += 1; s1.points += 0 # Double forfeit: 0 points for both
            else:  # draw
                s1.drawn += 1; s1.points += t.points_draw
            s1.save()
            
        if has_team2:
            s2, _ = GroupStanding.objects.get_or_create(group=group, team=match.team2)
            s2.played += 1
            s2.goals_for += score2
            s2.goals_against += score1
            s2.goal_difference = s2.goals_for - s2.goals_against
            
            if match.result == 'team2_win':
                s2.won += 1;  s2.points += t.points_win
            elif match.result == 'team1_win':
                s2.lost += 1; s2.points += t.points_loss
            elif match.result == 'double_forfeit':
                s2.lost += 1; s2.points += 0 # Double forfeit: 0 points for both
            else:  # draw
                s2.drawn += 1; s2.points += t.points_draw
            s2.save()

    def get_sorted_standings(self, group: Group):
        """
        Implementation of official tie-breaking rules:
        1. Points
        2. Head-to-Head points (among tied teams)
        3. Head-to-Head goal difference
        4. Overall goal difference
        5. Overall goals scored
        6. Alphabetical
        """
        standings = list(
            GroupStanding.objects.filter(group=group)
            .select_related('team')
        )
        
        if not standings:
            return []

        # Group teams by points to handle ties
        from collections import defaultdict
        tied_groups = defaultdict(list)
        for s in standings:
            tied_groups[s.points].append(s)
            
        final_sorted = []
        # Sort points in descending order
        for points in sorted(tied_groups.keys(), reverse=True):
            tied_teams = tied_groups[points]
            
            if len(tied_teams) > 1:
                # Handle tie using H2H if possible
                team_ids = [s.team.id for s in tied_teams]
                h2h_matches = Match.objects.filter(
                    group=group,
                    status=Match.Status.FINISHED,
                    team1_id__in=team_ids,
                    team2_id__in=team_ids
                )
                
                h2h_stats = {tid: {'pts': 0, 'gd': 0, 'gs': 0} for tid in team_ids}
                for m in h2h_matches:
                    h2h_stats[m.team1_id]['gs'] += (m.score_team1 or 0)
                    h2h_stats[m.team1_id]['gd'] += ((m.score_team1 or 0) - (m.score_team2 or 0))
                    h2h_stats[m.team2_id]['gs'] += (m.score_team2 or 0)
                    h2h_stats[m.team2_id]['gd'] += ((m.score_team2 or 0) - (m.score_team1 or 0))
                    
                    res = m.result
                    if res == 'team1_win':
                        h2h_stats[m.team1_id]['pts'] += self.tournament.points_win
                        h2h_stats[m.team2_id]['pts'] += self.tournament.points_loss
                    elif res == 'team2_win':
                        h2h_stats[m.team2_id]['pts'] += self.tournament.points_win
                        h2h_stats[m.team1_id]['pts'] += self.tournament.points_loss
                    elif res == 'draw':
                        h2h_stats[m.team1_id]['pts'] += self.tournament.points_draw
                        h2h_stats[m.team2_id]['pts'] += self.tournament.points_draw
                
                # Custom sort key: (H2H Pts, H2H GD, H2H GS, Overall GD, Overall GS)
                tied_teams.sort(
                    key=lambda s: (
                        h2h_stats.get(s.team_id, {}).get('pts', 0),
                        h2h_stats.get(s.team_id, {}).get('gd', 0),
                        h2h_stats.get(s.team_id, {}).get('gs', 0),
                        s.goal_difference,
                        s.goals_for,
                    ),
                    reverse=True
                )
            else:
                # No tie, just sort by overall stats anyway to be safe
                tied_teams.sort(
                    key=lambda s: (s.goal_difference, s.goals_for),
                    reverse=True
                )
            
            final_sorted.extend(tied_teams)
                
        return final_sorted

    def get_advancing_teams(self, group: Group) -> list:
        """
        Returns the top N teams from a group sorted by official football criteria.
        """
        n = self.tournament.teams_advancing_per_group
        sorted_standings = self.get_sorted_standings(group)
        return [s.team for s in sorted_standings[:n]]

    def get_all_advancing_teams(self) -> list:
        """
        Intelligently select advancing teams to form a perfect knockout bracket (4, 8, 16).
        It pulls top teams from groups, and if there's a gap to the next power of 2, 
        it picks the "best" teams from the next rank across all groups (e.g., best 2nds).
        """
        groups = list(self.tournament.groups.all().order_by('name'))
        if not groups:
            return []

        # Get all sorted standings for all groups
        all_group_standings = [self.get_sorted_standings(g) for g in groups]
        total_teams = sum(len(st) for st in all_group_standings)

        # Determine target knockout size (4, 8, 16)
        if total_teams >= 16:
            target_bracket_size = 16
        elif total_teams >= 8:
            target_bracket_size = 8
        elif total_teams >= 4:
            target_bracket_size = 4
        else:
            target_bracket_size = 2

        advancing = []
        rank_idx = 0
        
        while len(advancing) < target_bracket_size:
            # Collect all teams at the current rank across all groups
            teams_at_rank = []
            for st in all_group_standings:
                if rank_idx < len(st):
                    teams_at_rank.append(st[rank_idx])
            
            if not teams_at_rank:
                break # Ran out of teams entirely
                
            needed = target_bracket_size - len(advancing)
            
            if len(teams_at_rank) > needed:
                # We have more teams at this rank than we need (e.g. 6 runners-up, need 2).
                # Compare them across groups!
                # Sort by FIFA rules: Points, then Goal Difference, then Goals Scored
                teams_at_rank.sort(key=lambda x: (x.points, x.goal_difference, x.goals_for), reverse=True)
                teams_to_add = teams_at_rank[:needed]
            else:
                # Add all teams at this rank (e.g. all 1st places)
                teams_to_add = teams_at_rank
                
            advancing.extend([s.team for s in teams_to_add])
            rank_idx += 1
            
        return advancing


class WinnerPropagator:
    """
    After a knockout match is finished, push winner to the next match.
    Updates tournament.winner when the Final is decided.
    """

    def __init__(self, tournament: Tournament):
        self.tournament = tournament

    @transaction.atomic
    def propagate(self, match: Match):
        """Call this after any knockout match is saved with FINISHED status."""
        if match.stage == Match.Stage.GROUP:
            return
        if not match.is_finished or match.winner is None:
            return

        winner = match.winner
        loser  = match.loser

        if match.stage == Match.Stage.FINAL:
            t = self.tournament
            t.winner = winner
            t.runner_up = loser
            t.status = Tournament.Status.FINISHED
            t.save(update_fields=['winner', 'runner_up', 'status'])

        elif match.next_match:
            nm = match.next_match
            # Place winner in first available slot
            if nm.team1 is None or nm.team1 == match.team1 or nm.team1 == match.team2:
                nm.team1 = winner
            else:
                nm.team2 = winner
            nm.save(update_fields=['team1', 'team2'])

            # If semi-final, propagate loser to 3rd place match
            if match.stage == Match.Stage.SEMI_FINAL:
                tp_match = Match.objects.filter(
                    tournament=self.tournament, 
                    stage=Match.Stage.THIRD_PLACE
                ).first()
                if tp_match:
                    if tp_match.team1 is None or tp_match.team1 == match.team1 or tp_match.team1 == match.team2:
                        tp_match.team1 = loser
                    else:
                        tp_match.team2 = loser
                    tp_match.save(update_fields=['team1', 'team2'])
