import arrow
from django import template
from django.utils import timezone

register = template.Library()


@register.simple_tag
def humanize_timestamp(timestamp):
    # arrow 1.x raises TypeError on None (0.x tolerated it); templates may pass
    # a null timestamp (e.g. an unsaved/dummy instance), so guard it.
    if timestamp is None:
        return ""
    timestamp = arrow.get(timestamp)
    now = arrow.get(timezone.now())
    return timestamp.humanize(now)
