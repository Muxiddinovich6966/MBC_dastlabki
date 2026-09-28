
from django import template

register = template.Library()

@register.filter
def spaced(value):
    """Raqamlarni prabel bilan ajratish"""

    try:
        n = int(float(value))
        return f"{n:,}".replace(',', ' ')
    except (ValueError, TypeError):
        return value