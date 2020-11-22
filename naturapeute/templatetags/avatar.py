from django.template import Library

register = Library()


@register.inclusion_tag("partials/therapist-card.html")
def avatar(therapist):
    return {"therapist": therapist}
