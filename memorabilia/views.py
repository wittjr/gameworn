from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, HttpResponseRedirect
from django.views import generic
from .models import Collectible, Collection, PhotoMatch, League, GameType, UsageType, CollectibleImage
from .forms import CollectibleForm, CollectionForm, PhotoMatchForm
from django.forms import inlineformset_factory
from django.contrib.auth.decorators import user_passes_test, login_required
from rules.contrib.views import permission_required, objectgetter
from django.contrib.auth.models import User
from django.db.models import OuterRef, Subquery
from django.conf import settings
from django.urls import reverse


# Create your views here.

def home(request):
    return render(request, 'memorabilia/index.html')


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
            # process the data in form.cleaned_data as required
            # if form.cleaned_data['image']:
            #     form.cleaned_data['image_link'] = settings.MEDIA_URL + form.cleaned_data['image']
            obj = form.save(commit=False)
            obj.owner_uid = request.user.id
            obj.save()
            return HttpResponseRedirect(f'/collection/{obj.id}')

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CollectionForm()

    return render(request, 'memorabilia/collection_form.html', {'form': form, 'title': 'New Collection'})


@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def edit_collection(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if request.method == "POST":
        form = CollectionForm(request.POST, request.FILES, instance = collection)
        # print(form.is_valid())
        # print(vars(form.cleaned_data['image']))
        if form.is_valid():
            # collection.owner_uid = form.cleaned_data['owner_uid']
            # collection.title = form.cleaned_data['title']
            # collection.image = form.cleaned_data['image']
            # collection.save()
            # print(vars(form))
            # print(form.cleaned_data)
            # print(form.instance)

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
        primary_image_filter = context['object'].images.filter(primary=True)
        if len(primary_image_filter) >= 1:
            primary_image = primary_image_filter[0].image
            context['object'].primary_image = primary_image
        else:
            images = context['object'].images.all()
            if len(images) >= 1:
                primary_image = images[0].image
                context['object'].primary_image = primary_image
        return context


@login_required
@permission_required('memorabilia.create_collectible', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
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
        form = CollectibleForm(request.POST, request.FILES, current_user=request.user)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:collection', pk=collection_id)
        else:
            collection = get_object_or_404(Collection, pk=collection_id)
    else:
        collection = get_object_or_404(Collection, pk=collection_id)
        form = CollectibleForm(initial={'collection':collection}, current_user=request.user)

    return render(request, 'memorabilia/collectible_form.html', {'form': form, 'title': 'New Collectible', 'collection': collection})


@login_required
@permission_required('memorabilia.update_collectible', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
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
            return redirect('memorabilia:collectible', collection_id=collection_id, pk=collectible_id)
        else:
            print('ERROR')
    else:
        form = CollectibleForm(instance = collectible)

    return render(request, 'memorabilia/collectible_form.html', {'form': form, 'title': 'Edit Collectible', 'collectible': collectible})



@login_required
@permission_required('memorabilia.delete_collectible', fn=objectgetter(Collectible, 'collectible_id'), raise_exception=True)
def delete_collectible(request, collection_id, collectible_id):
    Collectible.objects.filter(pk=collectible_id).delete()
    return redirect('memorabilia:collection', pk=collection_id)


@login_required
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


@login_required
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


@login_required
def delete_photo_match(request, collection_id, collectible_id, photo_match_id):
    PhotoMatch.objects.filter(pk=photo_match_id).delete()
    return HttpResponseRedirect(f'/memorabilia/collection/{collection_id}/collectible/{collectible_id}')
