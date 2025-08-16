from django.shortcuts import redirect, render
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, HttpResponseRedirect
from django.views import generic

from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage, ExternalResource, Team
from .forms import CollectibleForm, CollectibleImageForm, CollectibleImageFormSet, CollectionForm, PhotoMatchForm, CollectibleSearchForm
from django.forms import ModelForm, inlineformset_factory, modelformset_factory
from django.contrib.auth.decorators import user_passes_test, login_required
from rules.contrib.views import permission_required, objectgetter
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery, Q
from django.conf import settings
from django.urls import reverse
import requests
import datetime


# Create your views here.

def home(request):
    data = Collectible.objects.order_by('-last_updated')[:6]
    return render(request, 'memorabilia/index.html', {'collectibles': data})


class IndexView(generic.ListView):
    model = Collection

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        user_subquery = User.objects.filter(id=OuterRef('owner_uid'))
        context['collection_list'] = context['collection_list'].annotate(owner_email=Subquery(user_subquery.values('email')), owner_username=Subquery(user_subquery.values('username')))
        return context


def _apply_collectible_filters(qs, data):
    query = data.get('query')
    if query:
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(player__icontains=query) |
            Q(team__icontains=query) |
            Q(brand__icontains=query) |
            Q(description__icontains=query)
        )
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
    results = Collectible.objects.all().order_by('-last_updated')
    if form.is_valid():
        results = _apply_collectible_filters(results, form.cleaned_data)
    # Build custom league options from existing collectibles (free-text values)
    league_keys = set(League.objects.values_list('key', flat=True))
    distinct_values = Collectible.objects.values_list('league', flat=True).distinct()
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


class PhotoMatchView(generic.DetailView):
    model = PhotoMatch


class CollectibleView(generic.DetailView):
    model = Collectible
    def get_context_data(self, **kwargs):
        context = super(CollectibleView, self).get_context_data(**kwargs)
        context['title'] = context['object'].title
        # league may be a custom string; resolve if possible, else leave as-is
        try:
            context['object'].league = League.objects.get(pk=context['object'].league)
        except League.DoesNotExist:
            pass
        context['object'].game_type = GameType.objects.get(pk=context['object'].game_type)
        context['object'].usage_type = UsageType.objects.get(pk=context['object'].usage_type)
        primary_image_filter = context['object'].images.filter(primary=True)
        # print(photomatch.collectible.collection.owner_uid == request.user.id)
        # print(request.user.is_staff)
        # is_owner = (photomatch.collectible.collection.owner_uid == request.user.id) or (request.user.is_staff)
        # print(is_owner)

        if len(primary_image_filter) >= 1:
            if primary_image_filter[0].image:
                context['object'].primary_image = f'settings.MEDIA_URL{primary_image_filter[0].image}'
            elif primary_image_filter[0].link:
                context['object'].primary_image = primary_image_filter[0].link
        else:
            images = context['object'].images.all()
            if len(images) >= 1:
                primary_image = images[0].image
                context['object'].primary_image = primary_image
        return context


@login_required
@permission_required('memorabilia.create_collectible', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def create_collectible(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == "POST":
        form = CollectibleForm(request.POST, request.FILES, current_user=request.user)
        # Ensure collection is set even if not posted as a field
        form.instance.collection = collection
        image_formset = CollectibleImageFormSet(request.POST, request.FILES, prefix='images')
        if form.is_valid() and image_formset.is_valid():
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            # return redirect('memorabilia:collection', pk=collection_id)
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible.id)
    else:
        form = CollectibleForm(initial={'collection':collection}, current_user=request.user)
        image_formset = CollectibleImageFormSet(prefix='images')

    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'title': 'New Collectible',
        'collection': collection,
        'leagues': League.objects.all(),
    })

@login_required
@permission_required('memorabilia.update_collectible', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def edit_collectible(request, collection_id, collectible_id):
    collectible = get_object_or_404(Collectible, pk=collectible_id)
    if request.method == "POST":
        form = CollectibleForm(request.POST, request.FILES, instance = collectible, current_user=request.user)
        # Ensure collection is set even if not posted as a field
        form.instance.collection = collectible.collection
        image_formset = CollectibleImageFormSet(request.POST, request.FILES, instance=collectible, prefix='images')
        if form.is_valid() and image_formset.is_valid():
            print('IS VALID')
            form.instance.last_updated = datetime.datetime.now()
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible_id)
        else:
            print(form.errors)
    else:
        form = CollectibleForm(instance = collectible, current_user=request.user)
        print(collectible.collection.id)
        image_formset = CollectibleImageFormSet(instance=collectible, prefix='images')

    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'title': 'Edit Collectible',
        'collectible': collectible,
        'leagues': League.objects.all(),
    })



@login_required
@permission_required('memorabilia.delete_collectible', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def delete_collectible(request, collection_id, collectible_id):
    Collectible.objects.filter(pk=collectible_id).delete()
    return redirect('memorabilia:collection', pk=collection_id)


@login_required
@permission_required('memorabilia.create_photomatch', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def create_photo_match(request, collection_id, collectible_id):
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES, current_user=request.user)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible_id)
        else:
            collectible = get_object_or_404(Collectible, pk=collectible_id)
    else:
        collectible = get_object_or_404(Collectible, pk=collectible_id)
        form = PhotoMatchForm(initial={'collectible':collectible}, current_user=request.user)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'New Photo Match', 'collectible': collectible})


@login_required
@permission_required('memorabilia.update_photomatch', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def edit_photo_match(request, collection_id, collectible_id, photo_match_id):
    photomatch = get_object_or_404(PhotoMatch, pk=photo_match_id)
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible_id)
    else:
        form = PhotoMatchForm(instance = photomatch)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'Edit Photo Match', 'photomatch': photomatch})


@login_required
@permission_required('memorabilia.delete_photomatch', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def delete_photo_match(request, collection_id, collectible_id, photo_match_id):
    PhotoMatch.objects.filter(pk=photo_match_id).delete()
    return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible_id)

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
        username = request.GET['username']
        album = request.GET['album']
        url = f'https://www.flickr.com/services/rest/?method=flickr.photosets.getPhotos&api_key={settings.FLICKR_KEY}&photoset_id={album}&user_id={username}&format=json&nojsoncallback=1'
        r = requests.get(url)
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