from django import template

from accounts.auth import is_organizer, is_student

register = template.Library()


@register.filter
def user_is_student(user) -> bool:
    return is_student(user)


@register.filter
def user_is_organizer(user) -> bool:
    return is_organizer(user)


@register.filter
def dict_get(d: dict, key):
    try:
        return d.get(key)
    except Exception:
        return None

