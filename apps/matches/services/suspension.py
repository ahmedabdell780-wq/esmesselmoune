from django.db import models
from apps.matches.models import Match, Card

def get_player_suspension_status(player, match):
    """
    Evaluates whether a player is suspended for a specific match, with support for
    multi-match suspensions (1 match, 2 matches, 3 matches, etc.).
    
    Rules & Logic:
    1. Administrative Suspension:
       - If player.is_suspended is True with player.suspension_matches_count == N:
         Player is suspended for N matches since activation.
       - If N == 0: Player is indefinitely suspended.

    2. Card Suspensions (Red Cards & 2 Consecutive Yellow Cards):
       - Red Card / Yellow-Red Card carries card.suspension_matches (default 1, configurable up to N matches).
       - 2 Consecutive Yellow Cards in two previous finished matches triggers a 1-match suspension (or custom N).
       - Tracks elapsed finished matches for the team to calculate remaining matches.
    """
    if not player or not match:
        return {'is_suspended': False, 'reason': None, 'remaining_matches': 0}

    # Fetch previous finished matches in the same tournament before this match
    qs = Match.objects.filter(
        tournament=match.tournament,
        status=Match.Status.FINISHED,
    ).filter(
        models.Q(team1=player.team) | models.Q(team2=player.team)
    )

    if match.match_date:
        qs = qs.filter(match_date__lt=match.match_date)
    else:
        qs = qs.filter(id__lt=match.id)

    previous_matches = list(qs.order_by('match_date', 'id'))

    # 1. Check Administrative Manual Suspension
    if player.is_suspended:
        total_suspension = player.suspension_matches_count
        if total_suspension == 0:
            custom_reason = player.suspension_reason or 'قرار إداري'
            return {
                'is_suspended': True,
                'reason': f'معاقب ({custom_reason}) / Suspendu (Décision administrative)',
                'short_reason': f'إداري ({custom_reason})',
                'remaining_matches': 999,
                'code': 'ADMIN_INDEFINITE'
            }
        else:
            elapsed_matches = len(previous_matches)
            remaining = total_suspension - elapsed_matches
            if remaining > 0:
                custom_reason = player.suspension_reason or f'قرار إداري ({total_suspension} مباراة)'
                return {
                    'is_suspended': True,
                    'reason': f'معاقب ({custom_reason} - متبقي {remaining} مباراة) / Suspendu (Reste {remaining} m)',
                    'short_reason': f'إداري (متبقي {remaining} مباراة)',
                    'remaining_matches': remaining,
                    'code': 'ADMIN_COUNT'
                }

    if not previous_matches:
        return {'is_suspended': False, 'reason': None, 'remaining_matches': 0}

    # 2. Check Match Cards History (Sequential Evaluation)
    # Each suspension event sets active_suspension_remaining = N
    active_suspension_remaining = 0
    suspension_reason = None
    short_reason = None
    suspension_code = None
    consecutive_yellows = 0

    for m in previous_matches:
        if active_suspension_remaining > 0:
            # Player served 1 match of their suspension during match 'm'
            active_suspension_remaining -= 1
            if active_suspension_remaining == 0:
                suspension_reason = None
                short_reason = None
                suspension_code = None
                consecutive_yellows = 0
            continue

        cards = m.cards.filter(player=player)
        red_card = cards.filter(card_type__in=['red', 'yellow_red']).first()
        has_yellow = cards.filter(card_type='yellow').exists()

        if red_card:
            dur = getattr(red_card, 'suspension_matches', 1) or 1
            active_suspension_remaining = dur
            suspension_code = 'RED'
            short_reason = f'بطاقة حمراء ({dur} مباراة)' if dur > 1 else 'بطاقة حمراء'
            suspension_reason = f'معاقب ({short_reason}) / Suspendu'
            consecutive_yellows = 0
        elif has_yellow:
            consecutive_yellows += 1
            if consecutive_yellows >= 2:
                dur = 1 # Default 1 match for 2 consecutive yellow cards
                active_suspension_remaining = dur
                suspension_code = 'DOUBLE_YELLOW'
                short_reason = 'إنذاران متتاليان'
                suspension_reason = 'معاقب (إنذاران متتاليان) / Suspendu (2 CJ)'
                consecutive_yellows = 0
        else:
            consecutive_yellows = 0

    if active_suspension_remaining > 0:
        rem = active_suspension_remaining
        reason_str = f"{short_reason} - متبقي {rem} مباراة" if rem > 1 else short_reason
        return {
            'is_suspended': True,
            'reason': f"معاقب ({reason_str}) / Suspendu ({rem} match remaining)",
            'short_reason': reason_str,
            'remaining_matches': rem,
            'code': suspension_code
        }

    return {
        'is_suspended': False,
        'reason': None,
        'short_reason': None,
        'remaining_matches': 0
    }


def get_suspended_players_for_match(match):
    """
    Returns list of suspended players for both team1 and team2 for a given match.
    """
    suspended = []
    if not match:
        return suspended

    teams = [t for t in [match.team1, match.team2] if t]
    for team in teams:
        for player in team.players.filter(is_active=True):
            status = get_player_suspension_status(player, match)
            if status['is_suspended']:
                suspended.append({
                    'player': player,
                    'team': team,
                    'reason': status['reason'],
                    'short_reason': status['short_reason'],
                    'remaining_matches': status['remaining_matches'],
                    'code': status['code']
                })

    return suspended
