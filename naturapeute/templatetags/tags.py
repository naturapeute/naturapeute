from django.template import Library

register = Library()


@register.inclusion_tag("partials/avatar.html")
def avatar(therapist):
    return {"therapist": therapist}


@register.inclusion_tag("partials/therapist-card.html")
def therapist_card(therapist):
    return {"therapist": therapist}


@register.inclusion_tag("partials/map.html")
def map(**kwargs):
    return kwargs
