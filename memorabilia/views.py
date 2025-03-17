from django.shortcuts import redirect, render
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, HttpResponseRedirect
from django.views import generic

from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage
from .forms import CollectibleForm, CollectibleImageForm, CollectibleImageFormSet, CollectionForm, PhotoMatchForm
from django.forms import ModelForm, inlineformset_factory, modelformset_factory
from django.contrib.auth.decorators import user_passes_test, login_required
from rules.contrib.views import permission_required, objectgetter
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery
from django.conf import settings
from django.urls import reverse
import requests


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
        context['object'].league = League.objects.get(pk=context['object'].league)
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
        image_formset = CollectibleImageFormSet(request.POST, request.FILES)
        if form.is_valid() and image_formset.is_valid():
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            # return redirect('memorabilia:collection', pk=collection_id)
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible.id)
    else:
        form = CollectibleForm(initial={'collection':collection}, current_user=request.user)
        image_formset = CollectibleImageFormSet()

    return render(request, 'memorabilia/collectible_form.html', {'form': form, 'image_formset': image_formset, 'title': 'New Collectible', 'collection': collection})

@login_required
@permission_required('memorabilia.update_collectible', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def edit_collectible(request, collection_id, collectible_id):
    collectible = get_object_or_404(Collectible, pk=collectible_id)
    if request.method == "POST":
        form = CollectibleForm(request.POST, request.FILES, instance = collectible, current_user=request.user)
        image_formset = CollectibleImageFormSet(request.POST, request.FILES, instance=collectible)
        if form.is_valid() and image_formset.is_valid():
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible_id)
    else:
        form = CollectibleForm(instance = collectible, current_user=request.user)
        image_formset = CollectibleImageFormSet(instance=collectible)

    return render(request, 'memorabilia/collectible_form.html', {'form': form, 'image_formset': image_formset, 'title': 'Edit Collectible', 'collectible': collectible})



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