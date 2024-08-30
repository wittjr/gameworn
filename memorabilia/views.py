from django.shortcuts import render
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, HttpResponseRedirect
from django.views import generic
from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage
from .forms import CollectibleForm, CollectionForm, PhotoMatchForm
from django.forms import inlineformset_factory


# Create your views here.
class IndexView(generic.ListView):
    model = Collection

def create_collection(request):
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = CollectionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            form.save()
            # redirect to a new URL:
            return HttpResponseRedirect("/memorabilia/")

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CollectionForm()

    return render(request, 'memorabilia/collection_form.html', {'form': form, 'title': 'New Collection'})


def edit_collection(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == "POST":
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection.title = form.cleaned_data['owner_uid']
            collection.title = form.cleaned_data['title']
            collection.save()
            return HttpResponseRedirect('/memorabilia/')
    else:
        form = CollectionForm(instance = collection)

    return render(request, 'memorabilia/collection_form.html', {'form': form, 'title': 'Edit Collection'})

def delete_collection(request, collection_id):
    Collection.objects.filter(pk=collection_id).delete()
    return HttpResponseRedirect('/memorabilia/')

class CollectionView(generic.DetailView):
    model = Collection


class PhotoMatchView(generic.DetailView):
    model = PhotoMatch


class CollectibleView(generic.DetailView):
    model = Collectible

    # question = get_object_or_404(Collection, pk=collection)
    # try:
    #     selected_choice = question.choice_set.get(pk=request.POST["choice"])
    # except (KeyError, Choice.DoesNotExist):
    #     # Redisplay the question voting form.
    #     return render(
    #         request,
    #         "polls/detail.html",
    #         {
    #             "question": question,
    #             "error_message": "You didn't select a choice.",
    #         },
    #     )
    # else:
    #     selected_choice.votes = F("votes") + 1
    #     selected_choice.save()
    #     # Always return an HttpResponseRedirect after successfully dealing
    #     # with POST data. This prevents data from being posted twice if a
    #     # user hits the Back button.
    #     return HttpResponseRedirect(reverse("polls:results", args=(question.id,)))


    def get_context_data(self, **kwargs):
        context = super(CollectibleView, self).get_context_data(**kwargs)
        context['title'] = context['object'].title
        context['object'].league = League.objects.get(pk=context['object'].league)
        context['object'].game_type = GameType.objects.get(pk=context['object'].game_type)
        context['object'].usage_type = UsageType.objects.get(pk=context['object'].usage_type)
        return context

# TODO
def create_collectible(request, collection_id):
    # CollectibleImageFormSet = inlineformset_factory(Collectible, CollectibleImage, exclude=[], can_delete=False, extra=2)
    # collectible = Collectible()
    # form = CollectibleForm(instance=collectible)
    # form2 = CollectibleImageFormSet(instance=collectible)
    # if request.method == "POST":
    #     # form = CollectibleForm(request.POST, request.FILES)
    #     if form.is_valid():
    #         form.save()
    #         return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}')
    #     else:
    #         print(form.errors)
    # else:
    #     collection = get_object_or_404(Collection, pk=collection_id)
    #     # form = CollectibleForm(initial={'collection':collection})

    # return render(request, 'memorabilia/collectible_form.html', {'form': form, 'image_form': form2, 'title': 'New Collectible'})

    if request.method == "POST":
        form = CollectibleForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}')
        else:
            print(form.errors)
    else:
        collection = get_object_or_404(Collection, pk=collection_id)
        form = CollectibleForm(initial={'collection':collection})

    return render(request, 'memorabilia/collectible_form.html', {'form': form, 'title': 'New Collectible'})


def edit_collectible(request, collection_id, collectible_id):
    collectible = get_object_or_404(Collectible, pk=collectible_id)
    if request.method == "POST":
        form = CollectibleForm(request.POST, request.FILES, instance = collectible)
        # uploaded_images = request.FILES.getlist('images')
        # print(uploaded_images)
        if form.is_valid():
            # collectible.title = form.cleaned_data['title']
            # # collectible.image = form.cleaned_data['image']
            # collectible.league = form.cleaned_data['league']
            # collectible.brand = form.cleaned_data['brand']
            # collectible.size = form.cleaned_data['size']
            # collectible.player = form.cleaned_data['player']
            # collectible.season = form.cleaned_data['season']
            # collectible.description = form.cleaned_data['description']
            # collectible.usage_type = form.cleaned_data['usage_type']
            # collectible.game_type = form.cleaned_data['game_type']
            # collectible.collection = form.cleaned_data['collection']
            # collectible.for_sale = form.cleaned_data['for_sale']
            # collectible.for_trade = form.cleaned_data['for_trade']
            # collectible.asking_price = form.cleaned_data['asking_price']
            # collectible.looking_for = form.cleaned_data['looking_for']
            # collectible.save()
            form.save()
            return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}')
        else:
            print('ERROR')
    else:
        form = CollectibleForm(instance = collectible)

    return render(request, 'memorabilia/collectible_form.html', {'form': form, 'title': 'Edit Collectible'})

def delete_collectible(request, collection_id, collectible_id):
    Collectible.objects.filter(pk=collectible_id).delete()
    return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}')


def create_photo_match(request, collection_id, collectible_id):
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}/collectible/{collectible_id}')
    else:
        collectible = get_object_or_404(Collectible, pk=collectible_id)
        form = PhotoMatchForm(initial={'collectible':collectible})

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'New Photo Match'})


def edit_photo_match(request, collection_id, collectible_id, photo_match_id):
    photomatch = get_object_or_404(PhotoMatch, pk=photo_match_id)
    if request.method == "POST":
        form = PhotoMatchForm(request.POST, request.FILES)
        if form.is_valid():
            photomatch.collectible = form.cleaned_data['collectible']
            photomatch.image = form.cleaned_data['image']
            photomatch.game_date = form.cleaned_data['game_date']
            photomatch.save()
            return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}/collectible/{collectible_id}')
    else:
        form = PhotoMatchForm(instance = photomatch)

    return render(request, 'memorabilia/photomatch_form.html', {'form': form, 'title': 'Edit Photo Match'})


def delete_photo_match(request, collection_id, collectible_id, photo_match_id):
    PhotoMatch.objects.filter(pk=photo_match_id).delete()
    return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}/collectible/{collectible_id}')
