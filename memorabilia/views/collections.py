from itertools import chain

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.views import generic
from rules.contrib.views import objectgetter, permission_required

from ..forms import CollectionForm
from ..models import Collection, ExternalResource, HockeyJersey, PlayerGear

class ExternalResourceListView(generic.ListView):
    model = ExternalResource
    ordering = ['title']


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

