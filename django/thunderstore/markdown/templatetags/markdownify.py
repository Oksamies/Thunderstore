import nh3
from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from markdown_it import MarkdownIt

from thunderstore.markdown.allowed_tags import (
    ALLOWED_ATTRIBUTES,
    ALLOWED_PROTOCOLS,
    ALLOWED_TAGS,
)

register = template.Library()
md = MarkdownIt("gfm-like")


def render_markdown(value: str):
    if value.startswith("\ufeff"):
        value = value[1:]
    # nh3 replaces bleach (unmaintained). Note behavior deltas: nh3 strips
    # disallowed tags (bleach escaped them) and adds rel="noopener noreferrer"
    # to links by default. Its allowlists are sets rather than lists.
    return mark_safe(
        nh3.clean(
            md.render(value.strip()),
            tags=set(ALLOWED_TAGS),
            attributes={tag: set(attrs) for tag, attrs in ALLOWED_ATTRIBUTES.items()},
            url_schemes=set(ALLOWED_PROTOCOLS),
        ),
    )


@register.filter
@stringfilter
def markdownify(value):
    return render_markdown(value)
