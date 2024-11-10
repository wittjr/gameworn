from django import template
from django_gravatar.helpers import get_gravatar_url, has_gravatar, get_gravatar_profile_url, calculate_gravatar_hash
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def get_user_avatar_url(email):

    user = User.objects.filter(email=email)[0]

    # social_info = SocialAccount.objects.filter(user_id=uid, provider='discord')
    # if len(social_info) > 0:
    #     return f'https://cdn.discordapp.com/avatars/{social_info[0].extra_data['id']}/{social_info[0].extra_data['avatar']}'
    
    #  Use gravatar\
    url = get_gravatar_url(user.email, size=32)
    # gravatar_exists = has_gravatar(user.email)
    # profile_url = get_gravatar_profile_url(user.email)
    # email_hash = calculate_gravatar_hash(user.email)
    return url

# @register.simple_tag(takes_context=True)
# def buildfullurl(context, url):
#     return context.request.build_absolute_uri(url)

@register.simple_tag(takes_context=True)
def getmediaurl(context, image):
    # print(context)
    print(image)
    if image:
        return image.url
        return context.request.build_absolute_uri(image.url)
    # return context.request.build_absolute_uri(static('memorabilia/placeholder.svg'))
    return static('memorabilia/placeholder.svg')
    # return 'https://placehold.co/600x400/svg?text=Game+Used&font=Roboto'
