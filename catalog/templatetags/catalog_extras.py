import hashlib

from django import template
from django.utils.safestring import mark_safe

from catalog.icons import icon_for_product

register = template.Library()

# A small curated set of hues so category tile colors stay in the same
# tasteful palette as the rest of the UI, rather than any random hue.
_PALETTE_HUES = [242, 262, 199, 172, 25, 340, 158, 291]


@register.filter
def category_hue(category_name):
    """Deterministic hue for a category name -- same category always gets
    the same tile color, without hardcoding a category list.
    """
    digest = hashlib.md5((category_name or '').encode()).hexdigest()
    index = int(digest, 16) % len(_PALETTE_HUES)
    return _PALETTE_HUES[index]


@register.simple_tag
def product_icon(product):
    """A guaranteed-accurate <svg> for this product's type -- see
    catalog/icons.py for why this replaced a photo-lookup approach.
    """
    inner = icon_for_product(product.name, product.category.name)
    svg = f'<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    return mark_safe(svg)
