from itertools import chain

from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import generic
from .models import Collection, PhotoMatch, League, GameType, PlayerItem, UsageType, ExternalResource, Team, OtherItem, OtherItemImage, PlayerGearItem, PlayerGearItemImage
from .forms import CollectibleForm, CollectibleImageFormSet, CollectionForm, PhotoMatchForm, CollectibleSearchForm, BulkCollectibleForm, BulkPlayerGearItemForm, BulkOtherItemForm, get_collectible_form_class, OtherItemForm, OtherItemImageForm, PlayerGearItemForm, PlayerGearItemImageFormSet
from django.forms import inlineformset_factory, modelformset_factory
from django.contrib.auth.decorators import login_required
from rules.contrib.views import permission_required, objectgetter
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery, Q
from django.conf import settings
import requests
import datetime


def _get_collectible(request, **view_kwargs):
    collectible_id = view_kwargs['collectible_id']
    collectible_type = view_kwargs.get('collectible_type', 'playeritem')
    if collectible_type == 'otheritem':
        return get_object_or_404(OtherItem, pk=collectible_id)
    elif collectible_type == 'playergearitem':
        return get_object_or_404(PlayerGearItem, pk=collectible_id)
    return get_object_or_404(PlayerItem, pk=collectible_id)


# Create your views here.

def home(request):
    print(request)
    data = sorted(
        chain(PlayerItem.objects.all(), PlayerGearItem.objects.all()),
        key=lambda x: x.last_updated,
        reverse=True,
    )[:6]
    return render(request, 'memorabilia/index.html', {'collectibles': data})


class IndexView(generic.ListView):
    model = Collection

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        user_subquery = User.objects.filter(id=OuterRef('owner_uid'))
        context['collection_list'] = context['collection_list'].annotate(owner_email=Subquery(user_subquery.values('email')), owner_username=Subquery(user_subquery.values('username')))
        return context


def _model_has_field(qs, field_name):
    return any(f.name == field_name for f in qs.model._meta.get_fields())


def _apply_collectible_filters(qs, data):
    query = data.get('query')
    if query:
        q = (
            Q(title__icontains=query) |
            Q(player__icontains=query) |
            Q(team__icontains=query) |
            Q(description__icontains=query)
        )
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
    return qs


def search_collectibles(request):
    form = CollectibleSearchForm(request.GET or None)
    gear_qs = PlayerGearItem.objects.all()
    player_qs = PlayerItem.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        gear_qs = _apply_collectible_filters(gear_qs, data)
        # PlayerItem has no gear-specific fields; strip them before filtering
        player_data = {
            k: v for k, v in data.items()
            if k not in ('brand', 'season', 'game_type', 'usage_type')
        }
        player_qs = _apply_collectible_filters(player_qs, player_data)
    results = sorted(
        list(gear_qs) + list(player_qs),
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
        form = CollectionForm(request.POST, request.FILES, instance = collection)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collection', pk=collection_id)
    else:
        form = CollectionForm(instance = collection)

    return render(request, 'memorabilia/collection_form.html', {'form': form, 'title': 'Edit Collection'})


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
        
        player_gear_items = list(collection.playergearitem_set.all())
        player_items = list(collection.playeritem_set.all())
        other_items = list(collection.otheritem_set.all())

        # Merge and sort by title
        collectibles = player_items + player_gear_items + other_items
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
            return PlayerItem.objects.get(pk=pk, collection_id=collection_id)
        elif collectible_type == 'otheritem':
            return OtherItem.objects.get(pk=pk, collection_id=collection_id)
        elif collectible_type == 'playergearitem':
            return PlayerGearItem.objects.get(pk=pk, collection_id=collection_id)

        raise Http404("Collectible not found")
    
    def get_template_names(self):
        """Return appropriate template based on object type"""
        obj = self.get_object()
        
        if isinstance(obj, PlayerGearItem):
            return ['memorabilia/playergearitem_detail.html']
        elif isinstance(obj, PlayerItem):
            return ['memorabilia/playeritem_detail.html']
        elif isinstance(obj, OtherItem):
            return ['memorabilia/otheritem_detail.html']

        return ['memorabilia/playeritem_detail.html']
    
    def get_context_data(self, **kwargs):
        context = super(CollectibleView, self).get_context_data(**kwargs)
        collectible = context['object']
        context['title'] = collectible.title
        
        if isinstance(collectible, PlayerGearItem):
            try:
                collectible.league = League.objects.get(pk=collectible.league)
            except League.DoesNotExist:
                pass
            collectible.game_type = GameType.objects.get(pk=collectible.game_type)
            collectible.usage_type = UsageType.objects.get(pk=collectible.usage_type)
        elif isinstance(collectible, PlayerItem):
            try:
                collectible.league = League.objects.get(pk=collectible.league)
            except League.DoesNotExist:
                pass
        
        # Handle primary image
        image_qs = collectible.gear_images if isinstance(collectible, PlayerGearItem) else collectible.images
        primary_image_filter = image_qs.filter(primary=True)
        if len(primary_image_filter) >= 1:
            if primary_image_filter[0].image:
                collectible.primary_image = f'settings.MEDIA_URL{primary_image_filter[0].image}'
            elif primary_image_filter[0].link:
                collectible.primary_image = primary_image_filter[0].link
        else:
            images = image_qs.all()
            if len(images) >= 1:
                collectible.primary_image = images[0].image
        
        print(context['object'].collectible_type)
        print(context['object'].id)
        return context


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
        if collectible_type == 'OtherItem':
            ImageFormSet = inlineformset_factory(
                OtherItem,
                OtherItemImage,
                form=OtherItemImageForm,
                extra=0,
                can_delete=True,
            )
        elif collectible_type == 'PlayerGearItem':
            ImageFormSet = PlayerGearItemImageFormSet
        else:
            ImageFormSet = CollectibleImageFormSet
        
        form = FormClass(request.POST, request.FILES, current_user=request.user)
        # Ensure collection is set even if not posted as a field
        form.instance.collection = collection
        image_formset = ImageFormSet(request.POST, request.FILES, prefix='images')
        if form.is_valid() and image_formset.is_valid():
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            # return redirect('memorabilia:collection', pk=collection_id)
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type=collectible.collectible_type, pk=collectible.id)
        # On failure, always render with PlayerGearItemForm so all field rows
        # exist in the DOM and the type toggle JS works correctly.
        if not isinstance(form, PlayerGearItemForm):
            display_form = PlayerGearItemForm(request.POST, request.FILES, current_user=request.user)
            # Copy validation errors from the actual form to the display form
            display_form._errors = form.errors
            form = display_form
    else:
        collectible_type = 'PlayerGearItem'
        form = PlayerGearItemForm(initial={'collection': collection}, current_user=request.user)
        image_formset = PlayerGearItemImageFormSet(prefix='images')

    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'title': 'New Collectible',
        'collection': collection,
        'leagues': League.objects.all(),
        'selected_collectible_type': collectible_type,
    })

@login_required
@permission_required('memorabilia.update_collectible', fn=_get_collectible, raise_exception=True)
def edit_collectible(request, collection_id, collectible_type, collectible_id):
    if collectible_type == 'otheritem':
        collectible = get_object_or_404(OtherItem, pk=collectible_id)
        FormClass = OtherItemForm
        ImageFormSet = inlineformset_factory(
            OtherItem, OtherItemImage, form=OtherItemImageForm, extra=0, can_delete=True,
        )
    elif collectible_type == 'playergearitem':
        collectible = get_object_or_404(PlayerGearItem, pk=collectible_id)
        FormClass = PlayerGearItemForm
        ImageFormSet = PlayerGearItemImageFormSet
    else:
        collectible = get_object_or_404(PlayerItem, pk=collectible_id)
        FormClass = CollectibleForm
        ImageFormSet = CollectibleImageFormSet
    
    if request.method == "POST":
        form = FormClass(request.POST, request.FILES, instance = collectible, current_user=request.user)
        # Ensure collection is set even if not posted as a field
        form.instance.collection = collectible.collection
        image_formset = ImageFormSet(request.POST, request.FILES, instance=collectible, prefix='images')
        if form.is_valid() and image_formset.is_valid():
            print('IS VALID')
            form.instance.last_updated = datetime.datetime.now()
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type=collectible_type, pk=collectible_id)
        else:
            print(form.errors)
    else:
        form = FormClass(instance = collectible, current_user=request.user)
        print(collectible.collection.id)
        image_formset = ImageFormSet(instance=collectible, prefix='images')

    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'title': 'Edit Collectible',
        'collectible': collectible,
        'leagues': League.objects.all(),
    })



@login_required
@permission_required('memorabilia.delete_collectible', fn=_get_collectible, raise_exception=True)
def delete_collectible(request, collection_id, collectible_type, collectible_id):
    if collectible_type == 'otheritem':
        get_object_or_404(OtherItem, pk=collectible_id).delete()
    elif collectible_type == 'playergearitem':
        get_object_or_404(PlayerGearItem, pk=collectible_id).delete()
    else:
        get_object_or_404(PlayerItem, pk=collectible_id).delete()
    
    return redirect('memorabilia:collection', pk=collection_id)


@login_required
@permission_required('memorabilia.create_photomatch', fn=objectgetter(PlayerGearItem, 'collectible_id'), raise_exception=True)
def create_photo_match(request, collection_id, collectible_id):
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES, current_user=request.user)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type='playergearitem', pk=collectible_id)
        else:
            collectible = get_object_or_404(PlayerGearItem, pk=collectible_id)
    else:
        collectible = get_object_or_404(PlayerGearItem, pk=collectible_id)
        form = PhotoMatchForm(initial={'collectible':collectible}, current_user=request.user)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'New Photo Match', 'collectible': collectible})


@login_required
@permission_required('memorabilia.update_photomatch', fn=objectgetter(PlayerGearItem, 'collectible_id'), raise_exception=True)
def edit_photo_match(request, collection_id, collectible_id, photo_match_id):
    photomatch = get_object_or_404(PhotoMatch, pk=photo_match_id)
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type='playergearitem', pk=collectible_id)
    else:
        form = PhotoMatchForm(instance = photomatch)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'Edit Photo Match', 'photomatch': photomatch})


@login_required
@permission_required('memorabilia.delete_photomatch', fn=objectgetter(PlayerGearItem, 'collectible_id'), raise_exception=True)
def delete_photo_match(request, collection_id, collectible_id, photo_match_id):
    PhotoMatch.objects.filter(pk=photo_match_id).delete()
    return redirect('memorabilia:collectible', collection_id=collection_id, collectible_type='playergearitem', pk=collectible_id)

@login_required
def get_flickr_albums(request, username):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        r = requests.get(f'https://www.flickr.com/services/rest/?method=flickr.photosets.getPhotos&api_key=36f362344a45751e7c36d3de65ab9e4e&photoset_id=72177720322281002&user_id=201912407%40N04&format=json&nojsoncallback=1', params=request.GET)
        data = r.json()
        val = {}
        val['primary'] = data['photoset']['primary']
        val['photos'] = []
        for photo in data['photoset']['photo']:
            id = photo['id']
            p = requests.get(f'https://www.flickr.com/services/rest/?method=flickr.photos.getSizes&api_key=36f362344a45751e7c36d3de65ab9e4e&photo_id={id}&format=json&nojsoncallback=1', params=request.GET)
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
    GearFormSet = modelformset_factory(PlayerGearItem, form=BulkPlayerGearItemForm, extra=0, can_delete=False)
    PlayerFormSet = modelformset_factory(PlayerItem, form=BulkCollectibleForm, extra=0, can_delete=False)
    OtherFormSet = modelformset_factory(OtherItem, form=BulkOtherItemForm, extra=0, can_delete=False)
    gear_qs = PlayerGearItem.objects.filter(collection=collection).order_by('id')
    player_qs = PlayerItem.objects.filter(collection=collection).order_by('id')
    other_qs = OtherItem.objects.filter(collection=collection).order_by('id')
    if request.method == 'POST':
        gear_formset = GearFormSet(request.POST, queryset=gear_qs, prefix='gear')
        player_formset = PlayerFormSet(request.POST, queryset=player_qs, prefix='player')
        other_formset = OtherFormSet(request.POST, queryset=other_qs, prefix='other')
        if gear_formset.is_valid() and player_formset.is_valid() and other_formset.is_valid():
            now = datetime.datetime.now()
            for formset in [gear_formset, player_formset, other_formset]:
                instances = formset.save(commit=False)
                for obj in instances:
                    obj.collection = collection
                    obj.last_updated = now
                    obj.save()
            return redirect('memorabilia:collection', pk=collection_id)
    else:
        gear_formset = GearFormSet(queryset=gear_qs, prefix='gear')
        player_formset = PlayerFormSet(queryset=player_qs, prefix='player')
        other_formset = OtherFormSet(queryset=other_qs, prefix='other')

    context = {
        'title': 'Bulk Edit Collectibles',
        'collection': collection,
        'gear_formset': gear_formset,
        'player_formset': player_formset,
        'other_formset': other_formset,
        'leagues': League.objects.all(),
    }
    return render(request, 'memorabilia/collectible_bulk_edit.html', context)


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