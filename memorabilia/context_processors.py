from django.contrib.auth.models import User
from django_gravatar.helpers import get_gravatar_url, has_gravatar, get_gravatar_profile_url, calculate_gravatar_hash
from allauth.socialaccount.models import SocialAccount
from django.conf import settings

def user_avatar(request):
    user = request.user

    if user.is_authenticated:
        social_info = SocialAccount.objects.filter(user=request.user, provider='discord')
        if len(social_info) > 0:
            return {'user_avatar_url':f"https://cdn.discordapp.com/avatars/{social_info[0].extra_data['id']}/{social_info[0].extra_data['avatar']}"}
        
        #  Use gravatar
        url = get_gravatar_url(user.email, size=32)
        # gravatar_exists = has_gravatar(user.email)
        # profile_url = get_gravatar_profile_url(user.email)
        # email_hash = calculate_gravatar_hash(user.email)
        return {'user_avatar_url':url}
    return {}

def site_name(request):
    return {'site_name': settings.SITE_NAME}

def google_tag(request):
    """Expose Google Tag ID to templates as `google_tag_id` if configured."""
    tag = getattr(settings, 'GOOGLE_TAG_ID', '')
    if tag:
        return {'google_tag_id': tag}
    return {}
