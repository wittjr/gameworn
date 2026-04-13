from itertools import chain

from django.http import HttpResponseRedirect, JsonResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import generic
from .models import Collection, PhotoMatch, League, GameType, GearType, UsageType, CoaType, HowObtainedOption, PlayerItem, PlayerItemImage, ExternalResource, Team, GeneralItem, GeneralItemImage, PlayerGear, PlayerGearImage, SeasonSet, HockeyJersey, UserProfile
from .forms import CollectibleForm, CollectibleImageFormSet, CollectionForm, PhotoMatchForm, CollectibleSearchForm, BulkCollectibleForm, BulkPlayerGearForm, BulkGeneralItemForm, BulkHockeyJerseyForm, get_collectible_form_class, GeneralItemForm, GeneralItemImageForm, PlayerGearForm, PlayerGearImageFormSet, HockeyJerseyForm, UserProfileForm
from django.forms import inlineformset_factory, modelformset_factory
from django.contrib.auth.decorators import login_required
from rules.contrib.views import permission_required, objectgetter
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery, Q
from django.conf import settings
import requests
import threading
import json as _json
from django.db import connection as _db_connection
import logging

logger = logging.getLogger(__name__)


def _get_collectible(request, **view_kwargs):
    collectible_id = view_kwargs['collectible_id']
    collectible_type = view_kwargs.get('collectible_type', 'playeritem')
    if collectible_type == 'generalitem':
        return get_object_or_404(GeneralItem, pk=collectible_id)
    elif collectible_type == 'playergear':
        return get_object_or_404(PlayerGear, pk=collectible_id)
    elif collectible_type == 'hockeyjersey':
        return get_object_or_404(HockeyJersey, pk=collectible_id)
    return get_object_or_404(PlayerItem, pk=collectible_id)


# Create your views here.

_FEATURED_Q = Q(allow_featured=True) | Q(allow_featured__isnull=True, collection__allow_featured=True)


def home(request):
    recent = PlayerItem.objects.filter(_FEATURED_Q).select_related('collection').prefetch_related('images').order_by('-last_updated')[:6]
    recent_gear = PlayerGear.objects.filter(_FEATURED_Q).exclude(gear_type_id='JRS').select_related('collection').prefetch_related('gear_images').order_by('-last_updated')[:6]
    recent_jersey = HockeyJersey.objects.filter(_FEATURED_Q).select_related('collection').prefetch_related('gear_images').order_by('-last_updated')[:6]
    recent_other = GeneralItem.objects.filter(_FEATURED_Q).select_related('collection').prefetch_related('images').order_by('-last_updated')[:6]
    data = sorted(chain(recent, recent_gear, recent_jersey, recent_other), key=lambda x: x.last_updated, reverse=True)[:6]
    return render(request, 'memorabilia/index.html', {'collectibles': data})


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


def _model_has_field(qs, field_name):
    return any(f.name == field_name for f in qs.model._meta.get_fields())


def _apply_collectible_filters(qs, data):
    query = data.get('query')
    if query:
        q = Q(title__icontains=query) | Q(description__icontains=query)
        if _model_has_field(qs, 'player'):
            q |= Q(player__icontains=query)
        if _model_has_field(qs, 'team'):
            q |= Q(team__icontains=query)
        if _model_has_field(qs, 'brand'):
            q |= Q(brand__icontains=query)
        qs = qs.filter(q)
    player = data.get('player')
    if player:
        qs = qs.filter(player__icontains=player)
    team = data.get('team')
    if team:
        qs = qs.filter(team__icontains=team)
    brand = data.get('brand')
    if brand:
        qs = qs.filter(brand__icontains=brand)
    number = data.get('number')
    if number not in (None, ''):
        qs = qs.filter(number=number)
    season = data.get('season')
    if season:
        qs = qs.filter(season__icontains=season)
    league = data.get('league')
    if league:
        qs = qs.filter(league__icontains=league)
    game_type = data.get('game_type')
    if game_type:
        qs = qs.filter(game_type=game_type)
    usage_type = data.get('usage_type')
    if usage_type:
        qs = qs.filter(usage_type=usage_type)
    collection = data.get('collection')
    if collection:
        qs = qs.filter(collection_id=collection)
    for_sale = data.get('for_sale')
    if for_sale == 'true':
        qs = qs.filter(for_sale=True)
    elif for_sale == 'false':
        qs = qs.filter(for_sale=False)
    for_trade = data.get('for_trade')
    if for_trade == 'true':
        qs = qs.filter(for_trade=True)
    elif for_trade == 'false':
        qs = qs.filter(for_trade=False)
    season_set = data.get('season_set')
    if season_set and _model_has_field(qs, 'season_set'):
        qs = qs.filter(season_set=season_set)
    gear_type = data.get('gear_type')
    if gear_type and _model_has_field(qs, 'gear_type'):
        qs = qs.filter(gear_type=gear_type)
    home_away = data.get('home_away')
    if home_away and _model_has_field(qs, 'home_away'):
        qs = qs.filter(home_away=home_away)
    return qs


def search_collectibles(request):
    # Fields that only exist on PlayerGear/HockeyJersey
    _GEAR_ONLY = ('brand', 'season', 'game_type', 'usage_type', 'gear_type')
    # Fields that exist on PlayerItem + PlayerGear but NOT GeneralItem
    _PLAYER_FIELDS = ('league', 'player', 'team', 'number')
    # Fields that only exist on HockeyJersey
    _JERSEY_ONLY = ('season_set', 'home_away')

    form = CollectibleSearchForm(request.GET or None)
    gear_qs = PlayerGear.objects.exclude(gear_type_id='JRS')
    hockey_qs = HockeyJersey.objects.all()
    player_qs = PlayerItem.objects.all()
    other_qs = GeneralItem.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        has_gear_filter = any(data.get(f) not in (None, '') for f in _GEAR_ONLY)
        has_player_filter = any(data.get(f) not in (None, '') for f in _PLAYER_FIELDS)
        has_jersey_filter = any(data.get(f) not in (None, '') for f in _JERSEY_ONLY)

        # Filter by item type first
        item_type = data.get('item_type')
        if item_type == 'playergear':
            gear_qs = PlayerGear.objects.all()
            hockey_qs = HockeyJersey.objects.none()
            player_qs = PlayerItem.objects.none()
            other_qs = GeneralItem.objects.none()
        elif item_type == 'hockeyjersey':
            gear_qs = PlayerGear.objects.none()
            hockey_qs = HockeyJersey.objects.all()
            player_qs = PlayerItem.objects.none()
            other_qs = GeneralItem.objects.none()
        elif item_type == 'playeritem':
            gear_qs = PlayerGear.objects.none()
            hockey_qs = HockeyJersey.objects.none()
            other_qs = GeneralItem.objects.none()
        elif item_type == 'generalitem':
            gear_qs = PlayerGear.objects.none()
            hockey_qs = HockeyJersey.objects.none()
            player_qs = PlayerItem.objects.none()

        gear_qs = _apply_collectible_filters(gear_qs, data)
        hockey_qs = _apply_collectible_filters(hockey_qs, data)

        player_data = {k: v for k, v in data.items() if k not in _GEAR_ONLY + _JERSEY_ONLY}
        player_qs = _apply_collectible_filters(player_qs, player_data)

        other_data = {k: v for k, v in data.items() if k not in _GEAR_ONLY + _PLAYER_FIELDS + _JERSEY_ONLY}
        other_qs = _apply_collectible_filters(other_qs, other_data)

        # Exclude types that don't have the filtered fields
        if has_jersey_filter:
            gear_qs = PlayerGear.objects.none()
            player_qs = PlayerItem.objects.none()
            other_qs = GeneralItem.objects.none()
        elif has_gear_filter:
            player_qs = PlayerItem.objects.none()
            other_qs = GeneralItem.objects.none()
        elif has_player_filter:
            other_qs = GeneralItem.objects.none()

    results = sorted(
        list(gear_qs.prefetch_related('gear_images')) +
        list(hockey_qs.prefetch_related('gear_images')) +
        list(player_qs.prefetch_related('images')) +
        list(other_qs.prefetch_related('images')),
        key=lambda x: x.last_updated,
        reverse=True,
    )
    # Build custom league options from existing collectibles (free-text values)
    league_keys = set(League.objects.values_list('key', flat=True))
    distinct_values = PlayerItem.objects.values_list('league', flat=True).distinct()
    custom_leagues = [v for v in distinct_values if v and v not in league_keys]
    context = {
        'title': 'Search Collectibles',
        'form': form,
        'results': results,
        'leagues': League.objects.all(),
        'custom_leagues': custom_leagues,
    }
    return render(request, 'memorabilia/search.html', context)

class ExternalResourceListView(generic.ListView):
    model = ExternalResource

    # def get_context_data(self, **kwargs):
    #     context = super(ExternalResourceListView, self).get_context_data(**kwargs)
    #     user_subquery = User.objects.filter(id=OuterRef('owner_uid'))
    #     context['resource_list'] = context['resource_list'].annotate(owner_email=Subquery(user_subquery.values('email')), owner_username=Subquery(user_subquery.values('username')))
    #     return context

def _get_all_collage_images(collection):
    """Return (picker_items, default_collage_images).

    picker_items — list of dicts with type/id/url/title for every collectible with a primary image.
    default_collage_images — first 9 primary image objects, for the collage card preview when no
        custom collage_collectible_ids are set.  Both are built in a single DB round-trip.
    """
    picker_items = []
    default_collage_images = []
    for collectible in chain(
        PlayerGear.objects.filter(collection=collection).exclude(gear_type_id='JRS').prefetch_related('gear_images').all(),
        HockeyJersey.objects.filter(collection=collection).prefetch_related('gear_images').all(),
        collection.playeritem_set.prefetch_related('images').all(),
        collection.generalitem_set.prefetch_related('images').all(),
    ):
        img = collectible.get_primary_image()
        if img is None:
            continue
        url = collectible.get_primary_image_url()
        if not url:
            continue
        picker_items.append({
            'type': collectible.collectible_type,
            'id': collectible.id,
            'url': url,
            'title': collectible.title,
        })
        if len(default_collage_images) < 9:
            default_collage_images.append(img)
    return picker_items, default_collage_images


@login_required
@permission_required('memorabilia.create_collection')
def create_collection(request):
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = CollectionForm(request.POST, request.FILES)
        # check whether it's valid:
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner_uid = request.user.id
            print(vars(obj))
            obj = form.save()
            return HttpResponseRedirect(f'/collection/{obj.id}')

    else:
        form = CollectionForm()

    return render(request, 'memorabilia/collection_form.html', {'form': form, 'title': 'New Collection'})



@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def edit_collection(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == "POST":
        form = CollectionForm(request.POST, request.FILES, instance=collection)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collection', pk=collection_id)
    else:
        form = CollectionForm(instance=collection)

    all_collage_images, default_collage_images = _get_all_collage_images(collection)
    collage_images = collection.get_collage_images() if collection.collage_collectible_ids else default_collage_images
    return render(request, 'memorabilia/collection_form.html', {
        'form': form,
        'title': 'Edit Collection',
        'collection': collection,
        'all_collage_images': all_collage_images,
        'collage_images': collage_images,
    })


@login_required
@permission_required('memorabilia.delete_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def delete_collection(request, collection_id):
    Collection.objects.filter(pk=collection_id).delete()
    return HttpResponseRedirect('/collection/')


class CollectionView(generic.DetailView):
    model = Collection
    
    def get_context_data(self, **kwargs):
        context = super(CollectionView, self).get_context_data(**kwargs)
        collection = context['object']
        
        player_gear_items = list(PlayerGear.objects.filter(collection=collection).exclude(gear_type_id='JRS').prefetch_related('gear_images').all())
        hockey_jerseys = list(HockeyJersey.objects.filter(collection=collection).prefetch_related('gear_images').all())
        player_items = list(collection.playeritem_set.prefetch_related('images').all())
        other_items = list(collection.generalitem_set.prefetch_related('images').all())

        # Merge and sort by title
        collectibles = player_items + player_gear_items + hockey_jerseys + other_items
        collectibles.sort(key=lambda x: x.title, reverse=False)
        
        context['collectibles'] = collectibles
        return context


class PhotoMatchView(generic.DetailView):
    model = PhotoMatch


class CollectibleView(generic.DetailView):
    model = PlayerItem  # Default model for URL resolution
    
    def get_object(self, queryset=None):
        """Try to get PlayerItem first, then OtherItem"""
        pk = self.kwargs.get('pk')
        collection_id = self.kwargs.get('collection_id')
        collectible_type = self.kwargs.get('collectible_type')

        if collectible_type == 'playeritem':
            return get_object_or_404(PlayerItem.objects.prefetch_related('images'), pk=pk, collection_id=collection_id)
        elif collectible_type == 'generalitem':
            return get_object_or_404(GeneralItem.objects.prefetch_related('images'), pk=pk, collection_id=collection_id)
        elif collectible_type == 'playergear':
            return get_object_or_404(
                PlayerGear.objects.select_related('game_type', 'usage_type', 'gear_type').prefetch_related('gear_images'),
                pk=pk, collection_id=collection_id,
            )
        elif collectible_type == 'hockeyjersey':
            return get_object_or_404(
                HockeyJersey.objects.select_related('game_type', 'usage_type', 'gear_type', 'season_set').prefetch_related('gear_images'),
                pk=pk, collection_id=collection_id,
            )

        raise Http404("Collectible not found")

    _COLLECTIBLE_TEMPLATES = {
        'playergear': 'memorabilia/playergear_detail.html',
        'playeritem': 'memorabilia/playeritem_detail.html',
        'generalitem': 'memorabilia/generalitem_detail.html',
        'hockeyjersey': 'memorabilia/hockeyjersey_detail.html',
    }

    def get_template_names(self):
        collectible_type = self.kwargs.get('collectible_type')
        return [self._COLLECTIBLE_TEMPLATES.get(collectible_type, 'memorabilia/playeritem_detail.html')]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        collectible = context['object']
        context['title'] = collectible.title

        if isinstance(collectible, (PlayerGear, HockeyJersey, PlayerItem)):
            try:
                context['league'] = League.objects.get(pk=collectible.league)
            except League.DoesNotExist:
                context['league'] = None

        images = list(collectible.gear_images.all() if isinstance(collectible, (PlayerGear, HockeyJersey)) else collectible.images.all())
        primary = next((img for img in images if img.primary), None)
        if primary:
            context['primary_image'] = primary.image if primary.image else primary.link
        else:
            context['primary_image'] = images[0].image if images else None

        return context


@login_required
def collectible_pdf(request, collection_id, collectible_type, pk):
    from weasyprint import HTML
    from django.template.loader import render_to_string

    # Fetch the object (same logic as CollectibleView.get_object)
    if collectible_type == 'playeritem':
        collectible = get_object_or_404(PlayerItem.objects.prefetch_related('images'), pk=pk, collection_id=collection_id)
        images = list(collectible.images.all())
        photomatches = []
    elif collectible_type == 'generalitem':
        collectible = get_object_or_404(GeneralItem.objects.prefetch_related('images'), pk=pk, collection_id=collection_id)
        images = list(collectible.images.all())
        photomatches = []
    elif collectible_type == 'playergear':
        collectible = get_object_or_404(
            PlayerGear.objects.select_related('game_type', 'usage_type', 'gear_type').prefetch_related('gear_images', 'photomatches'),
            pk=pk, collection_id=collection_id,
        )
        images = list(collectible.gear_images.all())
        photomatches = list(collectible.photomatches.all())
    elif collectible_type == 'hockeyjersey':
        collectible = get_object_or_404(
            HockeyJersey.objects.select_related('game_type', 'usage_type', 'gear_type', 'season_set').prefetch_related('gear_images', 'photomatches'),
            pk=pk, collection_id=collection_id,
        )
        images = list(collectible.gear_images.all())
        photomatches = list(collectible.photomatches.all())
    else:
        raise Http404("Collectible not found")

    # Only the owner (or superuser) may download
    if not request.user.is_superuser and request.user.id != collectible.collection.owner_uid:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    # Resolve image URLs for WeasyPrint.
    # Local files use file:// paths to avoid HTTP round-trips; external links are used as-is.
    def resolve_url(img_obj):
        if img_obj is None:
            return None
        if img_obj.link:
            return img_obj.link
        if img_obj.image:
            try:
                return f"file://{img_obj.image.path}"
            except NotImplementedError:
                return request.build_absolute_uri(img_obj.image.url)
        return None

    primary = next((img for img in images if img.primary), images[0] if images else None)
    primary_url = resolve_url(primary)
    secondary_images = [{'url': resolve_url(img)} for img in images if img is not primary]
    photomatch_data = [{'url': resolve_url(pm), 'date': pm.game_date, 'description': pm.description} for pm in photomatches]

    league = None
    if hasattr(collectible, 'league') and collectible.league:
        try:
            league = League.objects.get(pk=collectible.league)
        except League.DoesNotExist:
            pass

    context = {
        'collectible': collectible,
        'collectible_type': collectible_type,
        'primary_url': primary_url,
        'secondary_images': secondary_images,
        'photomatch_data': photomatch_data,
        'league': league,
    }

    html_string = render_to_string('memorabilia/collectible_pdf.html', context, request=request)
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    filename = f"{collectible.title.replace(' ', '_')}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    token = request.GET.get('dl', '')
    if token:
        response.set_cookie('downloadReady', token, max_age=60, samesite='Lax')
    return response


@login_required
@permission_required('memorabilia.create_collectible', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def create_collectible(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == "POST":
        # Get the selected collectible type
        collectible_type = request.POST.get('collectible_type', 'PlayerItem')
        
        # Get the appropriate form class
        FormClass = get_collectible_form_class(collectible_type)
        
        # Select appropriate formset based on type
        if collectible_type == 'GeneralItem':
            ImageFormSet = inlineformset_factory(
                GeneralItem,
                GeneralItemImage,
                form=GeneralItemImageForm,
                extra=0,
                can_delete=True,
            )
        elif collectible_type == 'PlayerGear':
            ImageFormSet = PlayerGearImageFormSet
        elif collectible_type == 'HockeyJersey':
            ImageFormSet = PlayerGearImageFormSet
        else:
            ImageFormSet = CollectibleImageFormSet
        
        form = FormClass(request.POST, request.FILES, current_user=request.user)
        # Ensure collection is set even if not posted as a field
        form.instance.collection = collection
        image_formset = ImageFormSet(request.POST, request.FILES, prefix='images')
        if form.is_valid() and image_formset.is_valid():
            collectible = form.save()
            flickr_url = request.POST.get('flickrAlbum', '').strip()
            if flickr_url:
                collectible.flickr_url = flickr_url
                collectible.save(update_fields=['flickr_url'])
            image_formset.instance = collectible
            image_formset.save()
            # return redirect('memorabilia:collection', pk=collection_id)
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type=collectible.collectible_type, pk=collectible.id)
        # On failure, always render with HockeyJerseyForm so all field rows
        # exist in the DOM and the type toggle JS works correctly.
        if not isinstance(form, HockeyJerseyForm):
            display_form = HockeyJerseyForm(request.POST, request.FILES, current_user=request.user)
            # Copy validation errors from the actual form to the display form
            display_form._errors = form.errors
            form = display_form
    else:
        collectible_type = 'HockeyJersey'
        form = HockeyJerseyForm(initial={'collection': collection}, current_user=request.user)
        image_formset = PlayerGearImageFormSet(prefix='images')

    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'title': 'New Collectible',
        'collection': collection,
        'leagues': League.objects.all(),
        'how_obtained_options': HowObtainedOption.objects.all(),
        'users': User.objects.filter(is_superuser=False),
        'selected_collectible_type': collectible_type,
        'is_post_error': request.method == 'POST',
        'flickr_id': profile_obj.flickr_id,
    })

def _get_image_formset_class(ctype):
    if ctype == 'generalitem':
        return inlineformset_factory(GeneralItem, GeneralItemImage, form=GeneralItemImageForm, extra=0, can_delete=True)
    elif ctype == 'playergear':
        return PlayerGearImageFormSet
    elif ctype == 'hockeyjersey':
        return PlayerGearImageFormSet
    return CollectibleImageFormSet


def _update_collage_after_conversion(old_instance, new_instance):
    """If the collection's collage references the old item, update it to point to the new one."""
    collection = old_instance.collection
    if not collection.collage_collectible_ids:
        return
    old_type = old_instance.collectible_type
    old_pk = old_instance.pk
    new_type = new_instance.collectible_type
    updated = [
        {'type': new_type, 'id': new_instance.pk}
        if entry.get('type') == old_type and entry.get('id') == old_pk
        else entry
        for entry in collection.collage_collectible_ids
    ]
    if updated != collection.collage_collectible_ids:
        collection.collage_collectible_ids = updated
        collection.save(update_fields=['collage_collectible_ids'])


def _convert_bulk_item(old_instance, new_type, form, collection, post_data=None):
    """Convert a bulk-edit collectible to a new type, copying shared fields from form data."""
    data = form.cleaned_data
    prefix = form.prefix
    post_data = post_data or {}

    def get_field(name):
        """Read from cleaned_data first, then extra POST inputs, then old instance."""
        if name in data:
            return data[name]
        key = f'{prefix}-{name}'
        if key in post_data:
            val = post_data[key]
            return val if val != '' else None
        return getattr(old_instance, name, None)

    base = {
        'title': get_field('title') or old_instance.title,
        'description': get_field('description') or '',
        'collection': collection,
        'how_obtained': get_field('how_obtained') or '',
    }
    player_base = dict(base)
    for field in ['league', 'player', 'team', 'number']:
        player_base[field] = get_field(field)

    def get_fk_id(name):
        """Return the raw PK string for a FK field (works with instances or raw POST strings)."""
        val = get_field(name)
        if hasattr(val, 'pk'):
            return val.pk
        return val or getattr(old_instance, f'{name}_id', None)

    coa_id = get_fk_id('coa')
    base['coa_id'] = coa_id
    player_base['coa_id'] = coa_id

    if new_type == 'playeritem':
        new_instance = PlayerItem(**player_base)
    elif new_type == 'playergear':
        gear_extra = {field: get_field(field) for field in ['brand', 'size', 'season']}
        gear_extra['game_type_id'] = get_fk_id('game_type')
        gear_extra['usage_type_id'] = get_fk_id('usage_type')
        gear_extra['gear_type_id'] = get_fk_id('gear_type')
        new_instance = PlayerGear(**player_base, **gear_extra)
    elif new_type == 'hockeyjersey':
        gear_extra = {field: get_field(field) for field in ['brand', 'size', 'season']}
        gear_extra['game_type_id'] = get_fk_id('game_type')
        gear_extra['usage_type_id'] = get_fk_id('usage_type')
        gear_extra['season_set_id'] = get_fk_id('season_set')
        new_instance = HockeyJersey(**player_base, **gear_extra)
    else:  # generalitem
        new_instance = GeneralItem(**base)

    new_instance.save()
    _copy_images(old_instance, new_instance)
    _update_collage_after_conversion(old_instance, new_instance)
    old_instance.delete()


def _copy_images(old_collectible, new_collectible):
    """Copy all images from old collectible to new collectible."""
    if isinstance(old_collectible, (PlayerGear, HockeyJersey)):
        old_images = list(old_collectible.gear_images.all())
    else:
        old_images = list(old_collectible.images.all())

    if isinstance(new_collectible, PlayerGear):
        NewImage = PlayerGearImage
    elif isinstance(new_collectible, PlayerItem):
        NewImage = PlayerItemImage
    else:
        NewImage = GeneralItemImage

    for img in old_images:
        NewImage.objects.create(
            collectible=new_collectible,
            primary=img.primary,
            image=img.image,
            link=img.link,
            flickrObject=img.flickrObject,
        )


_TYPE_NORMALIZE = {
    'PlayerGear': 'playergear',
    'PlayerItem': 'playeritem',
    'GeneralItem': 'generalitem',
    'HockeyJersey': 'hockeyjersey',
}
_TYPE_DISPLAY = {v: k for k, v in _TYPE_NORMALIZE.items()}


@login_required
@permission_required('memorabilia.update_collectible', fn=_get_collectible, raise_exception=True)
def edit_collectible(request, collection_id, collectible_type, collectible_id):
    if collectible_type == 'generalitem':
        collectible = get_object_or_404(GeneralItem, pk=collectible_id)
    elif collectible_type == 'playergear':
        collectible = get_object_or_404(PlayerGear, pk=collectible_id)
    elif collectible_type == 'hockeyjersey':
        collectible = get_object_or_404(HockeyJersey, pk=collectible_id)
    else:
        collectible = get_object_or_404(PlayerItem, pk=collectible_id)

    if request.method == "POST":
        submitted_type_raw = request.POST.get('collectible_type', '')
        new_type = _TYPE_NORMALIZE.get(submitted_type_raw, submitted_type_raw.lower())

        if new_type == collectible_type:
            # Same type — standard edit
            FormClass = get_collectible_form_class(submitted_type_raw)
            ImageFormSet = _get_image_formset_class(collectible_type)
            form = FormClass(request.POST, request.FILES, instance=collectible, current_user=request.user)
            image_formset = ImageFormSet(request.POST, request.FILES, instance=collectible, prefix='images')
            if form.is_valid() and image_formset.is_valid():
                collectible = form.save()
                flickr_url = request.POST.get('flickrAlbum', '').strip()
                if flickr_url:
                    collectible.flickr_url = flickr_url
                    collectible.save(update_fields=['flickr_url'])
                image_formset.instance = collectible
                image_formset.save()
                return redirect('memorabilia:collectible', collection_id=collectible.collection_id, collectible_type=collectible_type, pk=collectible.pk)
            else:
                print(form.errors)
                if not isinstance(form, HockeyJerseyForm):
                    display_form = HockeyJerseyForm(request.POST, request.FILES, current_user=request.user)
                    display_form._errors = form.errors
                    form = display_form
        else:
            # Type changed — convert collectible
            NewFormClass = get_collectible_form_class(submitted_type_raw)
            form = NewFormClass(request.POST, request.FILES, current_user=request.user)
            if form.is_valid():
                new_instance = form.save(commit=False)
                flickr_url = request.POST.get('flickrAlbum', '').strip()
                if flickr_url:
                    new_instance.flickr_url = flickr_url
                new_instance.save()
                _copy_images(collectible, new_instance)
                # Update the collection's collage if this item was referenced there.
                _update_collage_after_conversion(collectible, new_instance)
                collectible.delete()
                return redirect('memorabilia:collectible',
                                collection_id=new_instance.collection_id,
                                collectible_type=new_instance.collectible_type,
                                pk=new_instance.pk)
            else:
                print(form.errors)
                if not isinstance(form, HockeyJerseyForm):
                    display_form = HockeyJerseyForm(request.POST, request.FILES, current_user=request.user)
                    display_form._errors = form.errors
                    form = display_form
            # Show existing images on type-change failure
            ImageFormSet = _get_image_formset_class(collectible_type)
            image_formset = ImageFormSet(instance=collectible, prefix='images')

        selected_collectible_type = submitted_type_raw
    else:
        # GET — pre-populate PlayerGearForm with existing instance data so all
        # field rows exist in the DOM and the type-toggle JS works correctly.
        initial = {
            'title': collectible.title,
            'description': collectible.description,
            'collection': collectible.collection_id,
            'for_sale': collectible.for_sale,
            'for_trade': collectible.for_trade,
            'asking_price': collectible.asking_price,
        }
        for field in ['league', 'player', 'team', 'number', 'brand', 'size', 'season', 'game_type', 'usage_type', 'gear_type', 'season_set', 'home_away', 'how_obtained', 'coa', 'allow_featured']:
            if hasattr(collectible, field):
                initial[field] = getattr(collectible, field)
        form = HockeyJerseyForm(initial=initial, current_user=request.user)
        ImageFormSet = _get_image_formset_class(collectible_type)
        image_formset = ImageFormSet(instance=collectible, prefix='images')
        selected_collectible_type = _TYPE_DISPLAY.get(collectible_type, 'HockeyJersey')

    _type_labels = {
        'HockeyJersey': 'Hockey Jersey',
        'PlayerGear': 'Player Gear',
        'PlayerItem': 'Player Item',
        'GeneralItem': 'General Item',
    }
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'title': 'Edit Collectible',
        'collectible': collectible,
        'collection': collectible.collection,
        'leagues': League.objects.all(),
        'how_obtained_options': HowObtainedOption.objects.all(),
        'users': User.objects.filter(is_superuser=False),
        'selected_collectible_type': selected_collectible_type,
        'type_display_label': _type_labels.get(selected_collectible_type, selected_collectible_type),
        'convertible_types': [(k, v) for k, v in _type_labels.items() if k != selected_collectible_type],
        'flickr_id': profile_obj.flickr_id,
    })



@login_required
@permission_required('memorabilia.delete_collectible', fn=_get_collectible, raise_exception=True)
def delete_collectible(request, collection_id, collectible_type, collectible_id):
    if collectible_type == 'generalitem':
        get_object_or_404(GeneralItem, pk=collectible_id).delete()
    elif collectible_type == 'playergear':
        get_object_or_404(PlayerGear, pk=collectible_id).delete()
    elif collectible_type == 'hockeyjersey':
        get_object_or_404(HockeyJersey, pk=collectible_id).delete()
    else:
        get_object_or_404(PlayerItem, pk=collectible_id).delete()
    
    return redirect('memorabilia:collection', pk=collection_id)


@login_required
@permission_required('memorabilia.create_photomatch', fn=_get_collectible, raise_exception=True)
def create_photo_match(request, collection_id, collectible_type, collectible_id):
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES, current_user=request.user)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type=collectible_type, pk=collectible_id)
        else:
            collectible = _get_collectible(request, collection_id=collection_id, collectible_type=collectible_type, collectible_id=collectible_id)
    else:
        collectible = _get_collectible(request, collection_id=collection_id, collectible_type=collectible_type, collectible_id=collectible_id)
        form = PhotoMatchForm(initial={'collectible': collectible}, current_user=request.user)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'New Photo Match', 'collectible': collectible, 'collectible_type': collectible_type})


@login_required
@permission_required('memorabilia.update_photomatch', fn=_get_collectible, raise_exception=True)
def edit_photo_match(request, collection_id, collectible_type, collectible_id, photo_match_id):
    photomatch = get_object_or_404(PhotoMatch, pk=photo_match_id)
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type=collectible_type, pk=collectible_id)
    else:
        form = PhotoMatchForm(instance=photomatch)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'Edit Photo Match', 'photomatch': photomatch, 'collectible_type': collectible_type})


@login_required
@permission_required('memorabilia.delete_photomatch', fn=_get_collectible, raise_exception=True)
def delete_photo_match(request, collection_id, collectible_type, collectible_id, photo_match_id):
    PhotoMatch.objects.filter(pk=photo_match_id).delete()
    return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type=collectible_type, pk=collectible_id)

@login_required
def get_flickr_albums(request, username, album):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        r = requests.get(f'https://www.flickr.com/services/rest/?method=flickr.photosets.getPhotos&api_key={settings.FLICKR_KEY}&photoset_id={album}&user_id={username}&format=json&nojsoncallback=1')
        data = r.json()
        val = {}
        val['primary'] = data['photoset']['primary']
        val['photos'] = []
        for photo in data['photoset']['photo']:
            id = photo['id']
            p = requests.get(f'https://www.flickr.com/services/rest/?method=flickr.photos.getSizes&api_key={settings.FLICKR_KEY}&photo_id={id}&format=json&nojsoncallback=1', params=request.GET)
            sizes = p.json()['sizes']['size']
            image_sizes = {}
            for size in sizes:
                if size['label'] == 'Square':
                    image_sizes['square_75'] = size['source']
                elif size['label'] == 'Large Square':
                    image_sizes['square_150'] = size['source']
                elif size['label'] == 'Medium 640':
                    image_sizes['medium_640'] = size['source']
                elif size['label'] == 'Large':
                    image_sizes['large_1024'] = size['source']
            val['photos'].append({id: image_sizes})
        return JsonResponse(val)


@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def bulk_edit_collectibles(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    GearFormSet = modelformset_factory(PlayerGear, form=BulkPlayerGearForm, extra=0, can_delete=False)
    HockeyJerseyBulkFormSet = modelformset_factory(HockeyJersey, form=BulkHockeyJerseyForm, extra=0, can_delete=False)
    PlayerFormSet = modelformset_factory(PlayerItem, form=BulkCollectibleForm, extra=0, can_delete=False)
    OtherFormSet = modelformset_factory(GeneralItem, form=BulkGeneralItemForm, extra=0, can_delete=False)
    gear_qs = PlayerGear.objects.filter(collection=collection).exclude(gear_type_id='JRS').select_related('game_type', 'usage_type', 'gear_type').prefetch_related('gear_images').order_by('id')
    hockey_jersey_qs = HockeyJersey.objects.filter(collection=collection).select_related('game_type', 'usage_type', 'gear_type', 'season_set').prefetch_related('gear_images').order_by('id')
    player_qs = PlayerItem.objects.filter(collection=collection).prefetch_related('images').order_by('id')
    other_qs = GeneralItem.objects.filter(collection=collection).prefetch_related('images').order_by('id')
    if request.method == 'POST':
        if request.POST.get('action') == 'delete_selected':
            for entry in request.POST.getlist('delete_ids'):
                try:
                    kind, pk = entry.split(':', 1)
                    if kind == 'playergear':
                        PlayerGear.objects.filter(pk=pk, collection=collection).delete()
                    elif kind == 'hockeyjersey':
                        HockeyJersey.objects.filter(pk=pk, collection=collection).delete()
                    elif kind == 'playeritem':
                        PlayerItem.objects.filter(pk=pk, collection=collection).delete()
                    elif kind == 'generalitem':
                        GeneralItem.objects.filter(pk=pk, collection=collection).delete()
                except (ValueError, Exception):
                    pass
            return redirect('memorabilia:bulk_edit_collectibles', collection_id=collection_id)
        gear_formset = GearFormSet(request.POST, queryset=gear_qs, prefix='gear')
        hockey_jersey_formset = HockeyJerseyBulkFormSet(request.POST, queryset=hockey_jersey_qs, prefix='hockeyjersey')
        player_formset = PlayerFormSet(request.POST, queryset=player_qs, prefix='player')
        other_formset = OtherFormSet(request.POST, queryset=other_qs, prefix='other')
        if gear_formset.is_valid() and hockey_jersey_formset.is_valid() and player_formset.is_valid() and other_formset.is_valid():
            # Validate required FK fields for type conversions where the source form
            # doesn't include them (player/other forms lack game_type and usage_type).
            # Must be done before any saves so we can re-render with errors.
            conversion_errors = False

            def _require(form, post_key, label):
                nonlocal conversion_errors
                if not request.POST.get(post_key, '').strip():
                    form.add_error(None, f'{label} is required for this type.')
                    conversion_errors = True

            for form in player_formset.initial_forms:
                new_type = request.POST.get(f'item_type_{form.prefix}', 'playeritem')
                if new_type in ('playergear', 'hockeyjersey'):
                    prefix = form.prefix
                    _require(form, f'{prefix}-game_type', 'Game Type')
                    _require(form, f'{prefix}-usage_type', 'Usage Type')
                    _require(form, f'{prefix}-brand', 'Brand')
                    _require(form, f'{prefix}-size', 'Size')
                    _require(form, f'{prefix}-season', 'Season')

            for form in other_formset.initial_forms:
                new_type = request.POST.get(f'item_type_{form.prefix}', 'generalitem')
                if new_type in ('playeritem', 'playergear', 'hockeyjersey'):
                    prefix = form.prefix
                    _require(form, f'{prefix}-player', 'Player')
                if new_type in ('playergear', 'hockeyjersey'):
                    prefix = form.prefix
                    _require(form, f'{prefix}-game_type', 'Game Type')
                    _require(form, f'{prefix}-usage_type', 'Usage Type')
                    _require(form, f'{prefix}-brand', 'Brand')
                    _require(form, f'{prefix}-size', 'Size')
                    _require(form, f'{prefix}-season', 'Season')

            if conversion_errors:
                pass  # fall through to re-render with errors
            else:
                # Process type conversions first; track converted forms by object
                # reference (not pk) because Django sets pk=None after delete().
                gear_converted = set()
                hockey_jersey_converted = set()
                player_converted = set()
                other_converted = set()

                for form in gear_formset.initial_forms:
                    new_type = request.POST.get(f'item_type_{form.prefix}', 'playergear')
                    if new_type != 'playergear':
                        _convert_bulk_item(form.instance, new_type, form, collection, request.POST)
                        gear_converted.add(id(form))

                for form in hockey_jersey_formset.initial_forms:
                    new_type = request.POST.get(f'item_type_{form.prefix}', 'hockeyjersey')
                    if new_type != 'hockeyjersey':
                        _convert_bulk_item(form.instance, new_type, form, collection, request.POST)
                        hockey_jersey_converted.add(id(form))

                for form in player_formset.initial_forms:
                    new_type = request.POST.get(f'item_type_{form.prefix}', 'playeritem')
                    if new_type != 'playeritem':
                        _convert_bulk_item(form.instance, new_type, form, collection, request.POST)
                        player_converted.add(id(form))

                for form in other_formset.initial_forms:
                    new_type = request.POST.get(f'item_type_{form.prefix}', 'generalitem')
                    if new_type != 'generalitem':
                        _convert_bulk_item(form.instance, new_type, form, collection, request.POST)
                        other_converted.add(id(form))

                # Save non-converted items
                for form in gear_formset.initial_forms:
                    if id(form) not in gear_converted and form.has_changed():
                        obj = form.save(commit=False)
                        obj.collection = collection
                        obj.save()

                for form in hockey_jersey_formset.initial_forms:
                    if id(form) not in hockey_jersey_converted and form.has_changed():
                        obj = form.save(commit=False)
                        obj.collection = collection
                        obj.save()

                for form in player_formset.initial_forms:
                    if id(form) not in player_converted and form.has_changed():
                        obj = form.save(commit=False)
                        obj.collection = collection
                        obj.save()

                for form in other_formset.initial_forms:
                    if id(form) not in other_converted and form.has_changed():
                        obj = form.save(commit=False)
                        obj.collection = collection
                        obj.save()

                return redirect('memorabilia:collection', pk=collection_id)
    else:
        gear_formset = GearFormSet(queryset=gear_qs, prefix='gear')
        hockey_jersey_formset = HockeyJerseyBulkFormSet(queryset=hockey_jersey_qs, prefix='hockeyjersey')
        player_formset = PlayerFormSet(queryset=player_qs, prefix='player')
        other_formset = OtherFormSet(queryset=other_qs, prefix='other')

    context = {
        'title': 'Edit All Collectibles',
        'collection': collection,
        'gear_formset': gear_formset,
        'hockey_jersey_formset': hockey_jersey_formset,
        'player_formset': player_formset,
        'other_formset': other_formset,
        'leagues': League.objects.all(),
        'game_types': GameType.objects.all(),
        'usage_types': UsageType.objects.all(),
        'gear_types': GearType.objects.all(),
        'season_sets': SeasonSet.objects.all(),
        'how_obtained_options': HowObtainedOption.objects.all(),
        # On POST errors the extra fields (type selector, gear FK fields not in
        # formset) are plain HTML and won't be re-populated by Django automatically.
        # Pass the raw POST dict so JS can restore them.
        'post_data_json': _json.dumps(request.POST.dict()) if request.method == 'POST' else 'null',
    }
    return render(request, 'memorabilia/collectible_bulk_edit.html', context)


@login_required
def get_flickr_user_albums(request):
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Ajax required'}, status=400)
    username = request.GET.get('username', '').strip()
    if not username:
        return JsonResponse({'error': 'username required'}, status=400)
    try:
        r = requests.get(
            'https://www.flickr.com/services/rest/',
            params={
                'method': 'flickr.photosets.getList',
                'api_key': settings.FLICKR_KEY,
                'user_id': username,
                'format': 'json',
                'nojsoncallback': '1',
                'per_page': '500',
            },
            timeout=10,
        )
        data = r.json()
    except Exception:
        return JsonResponse({'error': 'Failed to reach Flickr. Please try again.'}, status=502)
    if data.get('stat') != 'ok':
        return JsonResponse({'error': data.get('message', 'Flickr error')}, status=502)
    albums = []
    for ps in data['photosets']['photoset']:
        server = ps.get('server', '')
        primary = ps.get('primary', '')
        secret = ps.get('secret', '')
        thumbnail = f'https://live.staticflickr.com/{server}/{primary}_{secret}_q.jpg' if server and primary and secret else ''
        albums.append({
            'id': ps['id'],
            'title': ps['title']['_content'],
            'description': ps['description']['_content'],
            'thumbnail': thumbnail,
            'count': ps.get('photos', 0),
        })
    return JsonResponse({'albums': albums})


@login_required
def get_flickr_album_photo_ids(request):
    """Return the list of Flickr photo IDs for a single album. Called async by the bulk-add page."""
    if request.headers.get('x-requested-with') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Ajax required'}, status=400)
    username = request.GET.get('username', '').strip()
    album_id = request.GET.get('album_id', '').strip()
    if not username or not album_id:
        return JsonResponse({'error': 'username and album_id required'}, status=400)
    try:
        r = requests.get(
            'https://www.flickr.com/services/rest/',
            params={
                'method': 'flickr.photosets.getPhotos',
                'api_key': settings.FLICKR_KEY,
                'photoset_id': album_id,
                'user_id': username,
                'format': 'json',
                'nojsoncallback': '1',
                'per_page': '500',
            },
            timeout=10,
        )
        data = r.json()
    except Exception:
        return JsonResponse({'error': 'Failed to reach Flickr. Please try again.'}, status=502)
    if data.get('stat') != 'ok':
        return JsonResponse({'error': data.get('message', 'Flickr error')}, status=502)
    photo_ids = [p['id'] for p in data.get('photoset', {}).get('photo', [])]
    return JsonResponse({'photo_ids': photo_ids})


@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def bulk_add_from_flickr(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    # Build a map of flickr album_id -> [imported_photo_ids] for this collection (DB only, no Flickr API calls).
    # The live Flickr photo ID list is fetched async by the browser after page load.
    # All collectible types are checked since flickr_url lives on the base Collectible model.
    existing_albums = {}
    collectible_querysets = [
        GeneralItem.objects.filter(collection=collection).exclude(flickr_url='').prefetch_related('images'),
        PlayerItem.objects.filter(collection=collection).exclude(flickr_url='').prefetch_related('images'),
        PlayerGear.objects.filter(collection=collection).exclude(flickr_url='').prefetch_related('gear_images'),
    ]
    for qs in collectible_querysets:
        for item in qs:
            parts = item.flickr_url.rstrip('/').split('/')
            try:
                album_idx = parts.index('albums')
                album_id = parts[album_idx + 1]
            except (ValueError, IndexError):
                continue
            image_rel = getattr(item, 'gear_images', None) or getattr(item, 'images', None)
            imported_ids = []
            if image_rel is not None:
                for img in image_rel.all():
                    pid = None
                    # Prefer flickrObject.id; fall back to parsing the photo ID from the link URL.
                    # Flickr link format: https://live.staticflickr.com/{server}/{photo_id}_{secret}_{size}.jpg
                    if img.flickrObject and isinstance(img.flickrObject, dict):
                        pid = img.flickrObject.get('id')
                    if not pid and img.link and 'staticflickr.com' in img.link:
                        filename = img.link.rstrip('/').rsplit('/', 1)[-1]
                        pid = filename.split('_')[0] or None
                    if pid:
                        imported_ids.append(str(pid))
            existing_albums[album_id] = imported_ids

    return render(request, 'memorabilia/flickr_bulk_add.html', {
        'title': 'Add from Flickr',
        'collection': collection,
        'flickr_id': profile_obj.flickr_id,
        'existing_albums_json': _json.dumps(existing_albums),
    })


@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def bulk_add_flickr_album(request, collection_id):
    """Create a single GeneralItem from one Flickr album. Called via fetch for each selected album."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    collection = get_object_or_404(Collection, pk=collection_id)
    import json as _json
    try:
        body = _json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    title = body.get('title', '').strip()
    description = body.get('description', '').strip() or title
    username = body.get('username', '').strip()
    album_id = body.get('album_id', '').strip()
    if not title:
        return JsonResponse({'error': 'title required'}, status=400)
    flickr_url = f'https://www.flickr.com/photos/{username}/albums/{album_id}' if username and album_id else ''
    item = GeneralItem.objects.create(
        title=title,
        description=description,
        collection=collection,
        flickr_url=flickr_url,
    )
    photo_count = 0
    if username and album_id:
        photo_count = _import_flickr_album_photos(item, username, album_id)
    return JsonResponse({'id': item.pk, 'title': item.title, 'photo_count': photo_count})


@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def bulk_add_flickr_batch(request, collection_id):
    """Accept all selected albums at once, process in a background thread, return immediately."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        body = _json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    username = body.get('username', '').strip()
    albums = body.get('albums', [])
    if not username:
        return JsonResponse({'error': 'username required'}, status=400)
    if not albums:
        return JsonResponse({'error': 'No albums provided'}, status=400)
    thread = threading.Thread(
        target=_process_albums_background,
        args=(collection_id, username, albums),
        daemon=True,
    )
    thread.start()
    return JsonResponse({'status': 'started', 'count': len(albums)})


def _process_albums_background(collection_id, username, albums):
    """Background thread: create GeneralItems and import Flickr photos for each album."""
    try:
        collection = Collection.objects.get(pk=collection_id)
        for album in albums:
            title = album.get('title', '').strip()
            description = album.get('description', '').strip() or title
            album_id = album.get('album_id', '').strip()
            if not title:
                continue
            flickr_url = f'https://www.flickr.com/photos/{username}/albums/{album_id}' if username and album_id else ''
            item = GeneralItem.objects.create(
                title=title,
                description=description,
                collection=collection,
                flickr_url=flickr_url,
            )
            if username and album_id:
                _import_flickr_album_photos(item, username, album_id)
    except Exception:
        logger.exception('Error in background Flickr album import for collection %s', collection_id)
    finally:
        _db_connection.close()


def _import_flickr_album_photos(item, username, album_id):
    """Fetch all photos from a Flickr album and create GeneralItemImage records. Returns photo count."""
    try:
        data = requests.get(
            'https://www.flickr.com/services/rest/',
            params={
                'method': 'flickr.photosets.getPhotos',
                'api_key': settings.FLICKR_KEY,
                'photoset_id': album_id,
                'user_id': username,
                'extras': 'url_l,url_m,url_s,url_sq',
                'format': 'json',
                'nojsoncallback': '1',
                'per_page': '500',
            },
            timeout=15,
        ).json()
    except Exception:
        return 0
    if data.get('stat') != 'ok':
        return 0
    photos = data.get('photoset', {}).get('photo', [])
    primary_id = data.get('photoset', {}).get('primary')
    count = 0
    first = True
    for photo in photos:
        link = photo.get('url_l') or photo.get('url_m') or photo.get('url_s') or ''
        if not link:
            continue
        is_primary = photo.get('id') == primary_id if primary_id else first
        GeneralItemImage.objects.create(
            collectible=item,
            link=link,
            primary=is_primary,
            flickrObject={'id': photo.get('id'), 'url_sq': photo.get('url_sq', '')},
        )
        first = False
        count += 1
    return count


def get_teams(request):
    """Return a JSON list of team names for a given league key.
    Query params: ?league=NHL
    """
    league = request.GET.get('league', '').strip()
    teams = []
    if league:
        teams = list(Team.objects.filter(league_id=league).values_list('name', flat=True).order_by('name'))
        # Small bootstrap defaults if DB has no entries yet
        if not teams and league.upper() == 'NHL':
            teams = ["Carolina Hurricanes", "Detroit Red Wings"]
        elif not teams and league.upper() == 'AHL':
            teams = ["Grand Rapids Griffins"]
    return JsonResponse({
        'league': league,
        'teams': teams,
    })

@login_required
def get_flickr_album(request):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        val = {}
        username = request.GET['username']
        album = request.GET['album']
        url = f'https://www.flickr.com/services/rest/?method=flickr.photosets.getInfo&api_key={settings.FLICKR_KEY}&photoset_id={album}&user_id={username}&format=json&nojsoncallback=1'
        r = requests.get(url)
        data = r.json()
        val['title'] = data['photoset']['title']['_content']
        val['description'] = data['photoset']['description']['_content']
        url = f'https://www.flickr.com/services/rest/?method=flickr.photosets.getPhotos&api_key={settings.FLICKR_KEY}&photoset_id={album}&user_id={username}&format=json&nojsoncallback=1'
        r = requests.get(url)
        data = r.json()
        val['primary'] = data['photoset']['primary']
        val['photos'] = []
        for photo in data['photoset']['photo']:
            id = photo['id']
            p = requests.get(f'https://www.flickr.com/services/rest/?method=flickr.photos.getSizes&api_key={settings.FLICKR_KEY}&photo_id={id}&format=json&nojsoncallback=1', params=request.GET)
            sizes = p.json()['sizes']['size']
            image_sizes = {}
            for size in sizes:
                if size['label'] == 'Square':
                    image_sizes['square_75'] = size['source']
                elif size['label'] == 'Large Square':
                    image_sizes['square_150'] = size['source']
                elif size['label'] == 'Medium 640':
                    image_sizes['medium_640'] = size['source']
                elif size['label'] == 'Large':
                    image_sizes['large_1024'] = size['source']
            val['photos'].append({id: image_sizes})
        return JsonResponse(val)

# ---------------------------------------------------------------------------
# Export views
# ---------------------------------------------------------------------------

def _safe_filename(name):
    """Turn a title into a safe ASCII filename (no path separators)."""
    import re
    safe = re.sub(r'[^\w\-]', '_', name)
    return safe[:80] or 'export'


@login_required
def export_collectible(request, collection_id, collectible_type, collectible_id):
    collectible = _get_collectible(
        request, collection_id=collection_id,
        collectible_type=collectible_type, collectible_id=collectible_id,
    )
    if collectible.collection.owner_uid != request.user.id and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    from .export_import import build_collectible_zip
    include_external = request.GET.get('include_external') == '1'
    zip_bytes = build_collectible_zip(collectible, include_external=include_external)

    response = HttpResponse(zip_bytes, content_type='application/zip')
    fname = _safe_filename(collectible.title)
    response['Content-Disposition'] = f'attachment; filename="{fname}.zip"'
    return response


@login_required
def export_collection(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if collection.owner_uid != request.user.id and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    from .export_import import build_collection_zip
    include_external = request.GET.get('include_external') == '1'
    zip_bytes = build_collection_zip(collection, include_external=include_external)

    response = HttpResponse(zip_bytes, content_type='application/zip')
    fname = _safe_filename(collection.title)
    response['Content-Disposition'] = f'attachment; filename="{fname}.zip"'
    return response


# ---------------------------------------------------------------------------
# Import views
# ---------------------------------------------------------------------------

import os as _os
import tempfile as _tempfile


@login_required
def import_upload(request, collection_id=None):
    # When collection_id is provided the import is scoped to that collection (merge mode).
    preset_collection = None
    if collection_id:
        preset_collection = get_object_or_404(Collection, pk=collection_id, owner_uid=request.user.id)

    if request.method == 'POST':
        if 'zip_file' not in request.FILES:
            return render(request, 'memorabilia/import_upload.html',
                          {'error': 'Please select a ZIP file to upload.',
                           'preset_collection': preset_collection})
        zip_file = request.FILES['zip_file']
        zip_bytes = zip_file.read()

        from .export_import import parse_zip
        from .export_import import ImportError as ZipImportError
        try:
            parsed = parse_zip(zip_bytes)
        except ZipImportError as e:
            return render(request, 'memorabilia/import_upload.html',
                          {'error': str(e), 'preset_collection': preset_collection})

        # Save bytes to a temp file; store path in session
        fd, tmp_path = _tempfile.mkstemp(suffix='.zip', prefix='heavyuse_import_')
        try:
            _os.write(fd, zip_bytes)
        finally:
            _os.close(fd)

        request.session['import_tmp_path'] = tmp_path
        request.session['import_preview'] = {
            'type': parsed['type'],
            'collection': parsed.get('collection'),
            'item_count': len(parsed['items']),
            'items_preview': parsed['items'][:10],
            'preset_collection_id': preset_collection.id if preset_collection else None,
            'preset_collection_title': preset_collection.title if preset_collection else None,
        }
        return redirect('memorabilia:import_preview')

    return render(request, 'memorabilia/import_upload.html',
                  {'preset_collection': preset_collection})


@login_required
def import_preview(request):
    tmp_path = request.session.get('import_tmp_path')
    preview = request.session.get('import_preview')

    if not tmp_path or not preview:
        return redirect('memorabilia:import_upload')

    # Security: path must be inside the system temp dir
    if not tmp_path.startswith(_tempfile.gettempdir()):
        return redirect('memorabilia:import_upload')

    if not _os.path.exists(tmp_path):
        return redirect('memorabilia:import_upload')

    preset_collection_id = preview.get('preset_collection_id')
    preset_collection_title = preview.get('preset_collection_title')
    user_collections = (Collection.objects.filter(owner_uid=request.user.id).order_by('title')
                        if not preset_collection_id else None)

    if request.method == 'POST':
        if preset_collection_id:
            mode = 'merge'
            target_collection_id = preset_collection_id
        else:
            mode = request.POST.get('mode', 'new')
            target_collection_id = request.POST.get('target_collection') or None

        try:
            with open(tmp_path, 'rb') as f:
                zip_bytes = f.read()
        except OSError:
            return redirect('memorabilia:import_upload')

        from .export_import import parse_zip, commit_import
        from .export_import import ImportError as ZipImportError
        try:
            parsed = parse_zip(zip_bytes)
            collection = commit_import(zip_bytes, parsed, request.user.id, mode,
                                       target_collection_id)
        except ZipImportError as e:
            return render(request, 'memorabilia/import_preview.html', {
                'preview': preview,
                'user_collections': user_collections,
                'error': str(e),
            })
        except Exception as e:
            logger.exception("Import failed")
            return render(request, 'memorabilia/import_preview.html', {
                'preview': preview,
                'user_collections': user_collections,
                'error': f"Import failed: {e}",
            })
        finally:
            try:
                _os.unlink(tmp_path)
            except OSError:
                pass
            request.session.pop('import_tmp_path', None)
            request.session.pop('import_preview', None)

        return redirect('memorabilia:collection', pk=collection.id)

    return render(request, 'memorabilia/import_preview.html', {
        'preview': preview,
        'user_collections': user_collections,
        'preset_collection_title': preset_collection_title,
    })
