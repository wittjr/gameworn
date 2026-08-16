from itertools import chain

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import generic

from ..forms import UserProfileForm
from ..models import (
    Collection, COLLECTIBLE_MODELS, GeneralItem, HockeyJersey, PlayerGear,
    PlayerItem, UserProfile, WantList, WantListProfile,
)

def _get_collectible(request, **view_kwargs):
    collectible_id = view_kwargs['collectible_id']
    collectible_type = view_kwargs.get('collectible_type', 'playeritem')
    Model = COLLECTIBLE_MODELS.get(collectible_type, PlayerItem)
    return get_object_or_404(Model, pk=collectible_id)


_FEATURED_Q = Q(allow_featured=True) | Q(allow_featured__isnull=True, collection__allow_featured=True)


def _has_image_q(rel):
    """Q matching collectibles with at least one image to show — either an
    uploaded file or an external link — via the given reverse relation name
    ('images' or 'gear_images'). Mirrors what get_primary_image() renders."""
    return Q(**{f'{rel}__image__gt': ''}) | Q(**{f'{rel}__link__gt': ''})


def _user_want_list_url(user):
    """Return the public want-list URL for a user who has a profile with at
    least one list, else None. Used to surface a 'for trade' shortcut."""
    if not user or not user.is_authenticated:
        return None
    profile = WantListProfile.objects.filter(user=user).first()
    if not profile or not WantList.objects.filter(profile=profile).exists():
        return None
    return reverse('memorabilia:want_list_public', kwargs={'slug': profile.slug})


def _collectible_trade_url(collectible, owner):
    """Want-list URL for a collectible's "For Trade" link: the specific list it
    points at if one is set (and still belongs to the owner), otherwise the
    owner's whole want-list profile."""
    wl = getattr(collectible, 'trade_want_list', None)
    if wl is not None and wl.profile.user_id == getattr(owner, 'id', None):
        return reverse('memorabilia:want_list_public_single',
                       kwargs={'slug': wl.profile.slug, 'list_slug': wl.slug})
    return _user_want_list_url(owner)


def home(request):
    # No DB access here so the page shell returns instantly even when the
    # Azure serverless DB is asleep. The recent-items grid is lazy-loaded
    # client-side from home_recent() once the DB has warmed up.
    return render(request, 'memorabilia/index.html')


def home_recent(request):
    recent = PlayerItem.objects.filter(_FEATURED_Q).filter(_has_image_q('images')).select_related('collection').prefetch_related('images').order_by('-last_updated').distinct()[:6]
    recent_gear = PlayerGear.objects.filter(_FEATURED_Q).exclude(gear_type_id='JRS').filter(_has_image_q('gear_images')).select_related('collection').prefetch_related('gear_images').order_by('-last_updated').distinct()[:6]
    recent_jersey = HockeyJersey.objects.filter(_FEATURED_Q).filter(_has_image_q('gear_images')).select_related('collection').prefetch_related('gear_images').order_by('-last_updated').distinct()[:6]
    recent_other = GeneralItem.objects.filter(_FEATURED_Q).filter(_has_image_q('images')).select_related('collection').prefetch_related('images').order_by('-last_updated').distinct()[:6]
    data = sorted(chain(recent, recent_gear, recent_jersey, recent_other), key=lambda x: x.last_updated, reverse=True)[:6]
    return render(request, 'memorabilia/_recent_items.html', {'collectibles': data})


def privacy_policy(request):
    return render(request, 'memorabilia/privacy_policy.html')


def data_deletion(request):
    return render(request, 'memorabilia/data_deletion.html')


@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:profile')
    else:
        form = UserProfileForm(instance=profile_obj)
    return render(request, 'memorabilia/profile.html', {'form': form})


class IndexView(generic.ListView):
    model = Collection

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        user_subquery = User.objects.filter(id=OuterRef('owner_uid'))
        context['collection_list'] = context['collection_list'].annotate(
            owner_email=Subquery(user_subquery.values('email')),
            owner_username=Subquery(user_subquery.values('username')),
        ).prefetch_related(
            'playergear_set__gear_images',
            'playeritem_set__images',
            'generalitem_set__images',
        )
        return context


class MyCollectionsView(IndexView):
    def get_queryset(self):
        return Collection.objects.filter(owner_uid=self.request.user.id)

    @classmethod
    def as_view(cls, **kwargs):
        view = super().as_view(**kwargs)
        return login_required(view)


class UserCollectionsView(IndexView):
    def get_queryset(self):
        self._profile_user = get_object_or_404(User, username=self.kwargs['username'])
        return Collection.objects.filter(owner_uid=self._profile_user.id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"{self._profile_user.username}'s Collections"
        return context

