"""
Signals fired after a Match is saved.
- Recalculates group standings for GROUP stage matches.
- Propagates winner to next bracket match for KNOCKOUT matches.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Match


@receiver(post_save, sender=Match)
def on_match_save(sender, instance: Match, **kwargs):
    """
    Triggered every time a Match is saved.
    Only acts when status == FINISHED and scores are set.
    """
    if instance.status != Match.Status.FINISHED:
        return
    if instance.score_team1 is None or instance.score_team2 is None:
        return

    from apps.tournaments.services.scheduler import (
        StandingsCalculator,
        WinnerPropagator,
    )

    # 1. Group stage → recalculate standings
    if instance.stage == Match.Stage.GROUP:
        calc = StandingsCalculator(instance.tournament)
        if instance.group:
            calc.recalculate_group(instance.group)
        else:
            # Cross-group match: recalculate groups of both teams
            groups_to_recalc = set()
            for team in [instance.team1, instance.team2]:
                if team:
                    g = instance.tournament.groups.filter(teams=team).first()
                    if g:
                        groups_to_recalc.add(g)
            for g in groups_to_recalc:
                calc.recalculate_group(g)
        
        # AUTOMATIC TRANSITION: Check if all group matches are done
        t = instance.tournament
        if not t.matches.filter(stage=Match.Stage.GROUP).exclude(status=Match.Status.FINISHED).exists():
            from apps.tournaments.models import Tournament
            if t.format == Tournament.Format.ROUND_ROBIN:
                # Direct transition to FINISHED, determining winner and runner_up
                first_group = t.groups.first()
                if first_group:
                    sorted_standings = calc.get_sorted_standings(first_group)
                    if len(sorted_standings) >= 1:
                        t.winner = sorted_standings[0].team
                    if len(sorted_standings) >= 2:
                        t.runner_up = sorted_standings[1].team
                t.status = Tournament.Status.FINISHED
                t.save(update_fields=['status', 'winner', 'runner_up'])
            else:
                # Check if knockout stage has NOT started yet (no finished KO matches)
                ko_qs = t.matches.exclude(stage=Match.Stage.GROUP)
                if not ko_qs.filter(status=Match.Status.FINISHED).exists():
                    from apps.tournaments.services.scheduler import MatchScheduler
                    sched = MatchScheduler(t)
                    advancing = calc.get_all_advancing_teams()
                    if advancing:
                        # Automatically generate the bracket
                        sched.generate_knockout_bracket(advancing)
                        # Update tournament status
                        t.status = Tournament.Status.KNOCKOUT
                        t.save(update_fields=['status'])

    # 2. Knockout stage → propagate winner + update tournament winner
    else:
        prop = WinnerPropagator(instance.tournament)
        prop.propagate(instance)


@receiver(post_save, sender=Match)
def auto_suspend_carded_players(sender, instance: Match, **kwargs):
    """
    Check accumulated cards and auto-set player is_suspended flag.
    3 yellow cards in a tournament → suspended 1 match.
    """
    if instance.status != Match.Status.FINISHED:
        return

    from .models import Card
    from apps.teams.models import Player, Team

    # 1. Handle Red Cards (Immediate suspension)
    red_cards = Card.objects.filter(
        match=instance,
        card_type__in=[Card.CardType.RED, Card.CardType.YELLOW_RED]
    ).select_related('player')

    for card in red_cards:
        # Auto-set results_in_suspension if not set
        if not card.results_in_suspension:
            card.results_in_suspension = True
            card.save(update_fields=['results_in_suspension'])

    # 2. Handle Yellow Cards Accumulation
    yellow_cards_in_match = Card.objects.filter(
        match=instance,
        card_type=Card.CardType.YELLOW
    ).select_related('player')

    for card in yellow_cards_in_match:
        # Count yellow cards for this player in this tournament
        total_yellows = Card.objects.filter(
            match__tournament=instance.tournament,
            player=card.player,
            card_type=Card.CardType.YELLOW
        ).count()
        
        if total_yellows % 2 == 0:
            card.results_in_suspension = True
            card.save(update_fields=['results_in_suspension'])
