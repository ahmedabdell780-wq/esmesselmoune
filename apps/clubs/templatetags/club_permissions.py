from django import template

register = template.Library()

@register.filter
def can_manage_category(user, category_id):
    if not user.is_authenticated:
        return False
    # If admin or organizer, they can manage anything
    if user.role in ('admin', 'organizer'):
        return True
    if user.role == 'coach':
        if not user.coach_category_id:
            return True # Head coach (no specific category restriction)
        # Check if the object's category matches the coach's category
        if category_id:
            return user.coach_category_id == category_id
    return False

@register.filter
def can_manage_object(user, obj):
    if not user.is_authenticated:
        return False
    if user.role in ('admin', 'organizer'):
        return True
    if user.role == 'coach':
        if not user.coach_category_id:
            return True
        # Find category_id on the object
        category_id = None
        if hasattr(obj, 'category_id'):
            category_id = obj.category_id
        elif hasattr(obj, 'player') and hasattr(obj.player, 'category_id'):
            category_id = obj.player.category_id
        elif hasattr(obj, 'session') and hasattr(obj.session, 'category_id'):
            category_id = obj.session.category_id
        # For Category objects
        elif obj.__class__.__name__ == 'Category':
            category_id = obj.id
            
        if category_id:
            return user.coach_category_id == category_id
    return False
