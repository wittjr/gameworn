from django import template
from django_gravatar.helpers import get_gravatar_url, has_gravatar, get_gravatar_profile_url, calculate_gravatar_hash
from allauth.socialaccount.models import SocialAccount
from django.templatetags.static import static
from django.db.models.fields.files import ImageFieldFile
from memorabilia.models import PhotoMatch, CollectibleImage, PlayerItemImage, GeneralItemImage, PlayerGearImage

register = template.Library()

@register.simple_tag
def get_user_avatar_url(email):
    return get_gravatar_url(email, size=32)

# @register.simple_tag(takes_context=True)
# def buildfullurl(context, url):
#     return context.request.build_absolute_uri(url)

@register.simple_tag(takes_context=True)
def getmediaurl(context, image):
    if image:
        if type(image) == str:
            return image
        elif type(image) is ImageFieldFile:
            return image.url
        elif type(image) is CollectibleImage or type(image) is PlayerItemImage or type(image) is GeneralItemImage or type(image) is PlayerGearImage:
            if image.link:
                return image.link
            else:
                return image.image.url
        elif type(image) is PhotoMatch:
            if image.link:
                return image.link
            elif image.image and image.image.url:
                return image.image.url
            elif image.getty_thumbnail_url:
                return image.getty_thumbnail_url
    return static('memorabilia/placeholder.svg')

@register.simple_tag(takes_context=True)
def test(context, input):
    print(vars(input))


_COLLAGE_LAYOUT = {
    1: [1],
    2: [2],
    3: [3],
    4: [2, 2],
    5: [2, 3],
    6: [3, 3],
    7: [2, 2, 3],
    8: [2, 3, 3],
    9: [3, 3, 3],
}


@register.simple_tag
def collage_rows(images):
    """Group images into rows for a collage layout with no empty cells."""
    images = list(images) if images else []
    count = len(images)
    row_sizes = _COLLAGE_LAYOUT.get(count, [3] * (count // 3) + ([count % 3] if count % 3 else []))
    rows = []
    idx = 0
    for size in row_sizes:
        rows.append(images[idx:idx + size])
        idx += size
    return rows
