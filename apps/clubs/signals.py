
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.clubs.models import LeagueMatch, LeagueStanding, LeagueTeam

@receiver([post_save, post_delete], sender=LeagueMatch)
def update_league_standings(sender, instance, **kwargs):
    cat = instance.category
    # Reset all standings for this category
    LeagueStanding.objects.filter(category=cat).update(
        played=0, won=0, drawn=0, lost=0, goals_for=0, goals_against=0, points=0
    )
    
    # Recalculate
    matches = LeagueMatch.objects.filter(category=cat, is_played=True)
    for m in matches:
        if m.home_score is None or m.away_score is None:
            continue
            
        home_st, _ = LeagueStanding.objects.get_or_create(team=m.home_team, category=cat)
        away_st, _ = LeagueStanding.objects.get_or_create(team=m.away_team, category=cat)
        
        home_st.played += 1
        away_st.played += 1
        
        home_st.goals_for += m.home_score
        home_st.goals_against += m.away_score
        
        away_st.goals_for += m.away_score
        away_st.goals_against += m.home_score
        
        if m.home_score > m.away_score:
            home_st.won += 1
            home_st.points += 3
            away_st.lost += 1
        elif m.home_score < m.away_score:
            away_st.won += 1
            away_st.points += 3
            home_st.lost += 1
        else:
            home_st.drawn += 1
            home_st.points += 1
            away_st.drawn += 1
            away_st.points += 1
            
        home_st.save()
        away_st.save()
