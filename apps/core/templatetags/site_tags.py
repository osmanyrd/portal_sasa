from django import template
from wagtail.models import Site

register = template.Library()


@register.simple_tag(takes_context=True)
def main_menu(context):
    request = context.get("request")
    if request is None:
        return []
    site = Site.find_for_request(request)
    if site is None or site.root_page is None:
        return []
    return (
        site.root_page.get_children()
        .live()
        .public()
        .in_menu()
        .order_by("path")
    )
