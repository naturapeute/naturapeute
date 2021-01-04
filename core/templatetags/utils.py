from django import template
from django.utils import safestring
from markdown import markdown as md

register = template.Library()


@register.filter
def markdown(text):
    return safestring.mark_safe(md(text))
