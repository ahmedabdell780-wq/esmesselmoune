from django import template
from django.db.models import Q

register = template.Library()

@register.filter(name='split')
def split_filter(value, delimiter=','):
    return [item.strip() for item in str(value).split(delimiter)]

@register.filter
def abs_val(value):
    try:    return abs(int(value))
    except: return value

@register.filter
def subtract(value, arg):
    try:    return int(value) - int(arg)
    except: return value

@register.filter
def get_item(d, key):
    return d.get(key) if isinstance(d, dict) else None

@register.simple_tag
def goal_diff_display(standing):
    gd = standing.goal_difference
    prefix = '+' if gd > 0 else ''
    return f"{prefix}{gd}"

@register.filter
def get_team_form(standing):
    from apps.matches.models import Match
    group = standing.group
    team = standing.team
    # Get finished group stage matches for this team
    matches = Match.objects.filter(
        tournament=group.tournament,
        group=group,
        status=Match.Status.FINISHED
    ).filter(Q(team1=team) | Q(team2=team)).order_by('match_date')
    
    # We want last 5 matches
    matches = list(matches)[-5:]
    
    form = []
    for m in matches:
        if m.winner == team:
            form.append('W')
        elif m.winner is None and m.score_team1 == m.score_team2:
            form.append('D')
        else:
            form.append('L')
    return form

@register.filter
def get_team_clean_sheets(standing):
    from apps.matches.models import Match
    group = standing.group
    team = standing.team
    cs_home = Match.objects.filter(
        tournament=group.tournament,
        group=group,
        team1=team,
        score_team2=0,
        status=Match.Status.FINISHED
    ).count()
    cs_away = Match.objects.filter(
        tournament=group.tournament,
        group=group,
        team2=team,
        score_team1=0,
        status=Match.Status.FINISHED
    ).count()
    return cs_home + cs_away

@register.filter
def get_team_goals_scored_avg(standing):
    if standing.played > 0:
        return round(standing.goals_for / standing.played, 2)
    return 0.0

@register.filter
def get_team_goals_conceded_avg(standing):
    if standing.played > 0:
        return round(standing.goals_against / standing.played, 2)
    return 0.0

@register.filter
def percentage_of(value, arg):
    try:
        val = float(value)
        total = float(arg)
        if total <= 0:
            return 0
        return round((val / total) * 100, 1)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0


@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def arabic_date(date_obj):
    if not date_obj:
        return ""
    months = {
        1: "جانفي", 2: "فيفري", 3: "مارس", 4: "أفريل",
        5: "ماي", 6: "جوان", 7: "جويلية", 8: "أوت",
        9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }
    return f"{date_obj.day} {months.get(date_obj.month, '')} {date_obj.year}"

@register.filter
def arabic_date_full(date_obj):
    if not date_obj:
        return ""
    months = {
        1: "جانفي", 2: "فيفري", 3: "مارس", 4: "أفريل",
        5: "ماي", 6: "جوان", 7: "جويلية", 8: "أوت",
        9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }
    days = {
        0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس",
        4: "الجمعة", 5: "السبت", 6: "الأحد"
    }
    return f"{days.get(date_obj.weekday(), '')} {date_obj.day} {months.get(date_obj.month, '')} {date_obj.year}"

from django.utils.safestring import mark_safe

@register.filter
def split_team_name(name):
    if not name:
        return ""
    words = name.split()
    if len(words) > 2:
        return mark_safe(f"{' '.join(words[:2])}<br>{' '.join(words[2:])}")
    return name
