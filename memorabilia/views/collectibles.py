import json
from itertools import chain

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.forms import inlineformset_factory, modelformset_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import generic
from csp.constants import NONCE
from csp.decorators import csp_replace
from rules.contrib.views import objectgetter, permission_required

from ..forms import (
    BulkCollectibleForm, BulkGeneralItemForm, BulkHockeyJerseyForm, BulkPlayerGearForm,
    CollectibleImageFormSet, GeneralItemAuthenticationFormSet, GeneralItemImageForm,
    HockeyJerseyForm, PhotoMatchForm, PlayerGearAuthenticationFormSet,
    PlayerGearImageFormSet, PlayerItemAuthenticationFormSet, get_collectible_form_class,
)
from ..models import (
    COLLECTIBLE_MODELS, Collection, GameType, GearType, GeneralItem, GeneralItemImage,
    HockeyJersey, HowObtainedOption, League, MeiGrayTagEntry, PhotoMatch, PlayerGear,
    PlayerGearImage, PlayerItem, PlayerItemImage, SeasonSet, UsageType, UserProfile,
)
from .core import _collectible_trade_url, _get_collectible, _user_want_list_url

class PhotoMatchView(generic.DetailView):
    model = PhotoMatch


def _collectible_script_src():
    csp = getattr(settings, 'CONTENT_SECURITY_POLICY', {})
    base = csp.get('DIRECTIVES', {}).get('script-src', ["'self'"])
    return [s for s in base if s is not NONCE] + ["'unsafe-inline'", "https://embed-cdn.gettyimages.com"]


@method_decorator(
    csp_replace({"script-src": _collectible_script_src()}),
    name='dispatch'
)
class CollectibleView(generic.DetailView):
    model = PlayerItem  # Default model for URL resolution
    
    def get_object(self, queryset=None):
        """Try to get PlayerItem first, then OtherItem"""
        pk = self.kwargs.get('pk')
        collection_id = self.kwargs.get('collection_id')
        collectible_type = self.kwargs.get('collectible_type')

        Model = COLLECTIBLE_MODELS.get(collectible_type)
        if Model is None:
            raise Http404("Collectible not found")
        return get_object_or_404(Model.detail_queryset(), pk=pk, collection_id=collection_id)

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

        context['primary_image'] = collectible.get_primary_image()

        if isinstance(collectible, HockeyJersey):
            tag_numbers = [
                a.number for a in collectible.authentications.all()
                if a.issuer_id == 'MEIGRAY' and a.number
            ]
            if tag_numbers:
                context['meigray_entries'] = list(
                    MeiGrayTagEntry.objects
                    .select_related('schedule', 'report')
                    .prefetch_related('schedule__games', 'schedule__set_ranges')
                    .filter(pk__in=tag_numbers)
                )

        collection = collectible.collection
        all_siblings = sorted(
            chain(
                PlayerGear.objects.filter(collection=collection).exclude(gear_type_id='JRS').only('id', 'title', 'collection_id').prefetch_related('gear_images'),
                HockeyJersey.objects.filter(collection=collection).only('id', 'title', 'collection_id').prefetch_related('gear_images'),
                PlayerItem.objects.filter(collection=collection).only('id', 'title', 'collection_id').prefetch_related('images'),
                GeneralItem.objects.filter(collection=collection).only('id', 'title', 'collection_id').prefetch_related('images'),
            ),
            key=lambda x: x.title,
        )
        current_index = next(
            (i for i, s in enumerate(all_siblings)
             if s.collectible_type == collectible.collectible_type and s.id == collectible.id),
            None,
        )
        if current_index is not None:
            context['prev_item'] = all_siblings[current_index - 1] if current_index > 0 else None
            context['next_item'] = all_siblings[current_index + 1] if current_index < len(all_siblings) - 1 else None
            context['item_position'] = current_index + 1
            context['item_total'] = len(all_siblings)

        # Link to the collection owner's want list, surfaced next to the
        # "For Trade" indicator so prospective traders can see what they want.
        owner = User.objects.filter(id=collection.owner_uid).first()
        context['owner_want_list_url'] = _collectible_trade_url(collectible, owner)
        # The owner can be contacted only if we have an address to relay to.
        context['owner_can_contact'] = bool(owner and owner.email)

        return context


@login_required
def collectible_pdf(request, collection_id, collectible_type, pk):
    from weasyprint import HTML
    from django.template.loader import render_to_string

    # Fetch the object (same logic as CollectibleView.get_object)
    Model = COLLECTIBLE_MODELS.get(collectible_type)
    if Model is None:
        raise Http404("Collectible not found")
    collectible = get_object_or_404(Model.detail_queryset(), pk=pk, collection_id=collection_id)
    images = collectible.get_images()
    photomatches = list(collectible.photomatches.all()) if hasattr(collectible, 'photomatches') else []

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

    primary = collectible.get_primary_image_obj()
    primary_url = resolve_url(primary)
    secondary_images = [{'url': resolve_url(img)} for img in images if img is not primary]
    photomatch_data = [{'url': resolve_url(pm), 'getty_embed_code': pm.getty_embed_code or '', 'date': pm.game_date, 'description': pm.description} for pm in photomatches]

    league = None
    if hasattr(collectible, 'league') and collectible.league:
        try:
            league = League.objects.get(pk=collectible.league)
        except League.DoesNotExist:
            pass

    meigray_entries = []
    if collectible_type == 'hockeyjersey':
        tag_numbers = [
            a.number for a in collectible.authentications.all()
            if a.issuer_id == 'MEIGRAY' and a.number
        ]
        if tag_numbers:
            meigray_entries = list(
                MeiGrayTagEntry.objects
                .select_related('schedule', 'report')
                .prefetch_related('schedule__games', 'schedule__set_ranges')
                .filter(pk__in=tag_numbers)
            )

    context = {
        'collectible': collectible,
        'collectible_type': collectible_type,
        'primary_url': primary_url,
        'secondary_images': secondary_images,
        'photomatch_data': photomatch_data,
        'league': league,
        'meigray_entries': meigray_entries,
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
        
        AuthFormSet = _get_auth_formset_class(collectible_type)
        form = FormClass(request.POST, request.FILES, current_user=request.user)
        # Ensure collection is set even if not posted as a field
        form.instance.collection = collection
        image_formset = ImageFormSet(request.POST, request.FILES, prefix='images')
        auth_formset = AuthFormSet(request.POST, prefix='authentications')
        if form.is_valid() and image_formset.is_valid() and auth_formset.is_valid():
            collectible = form.save()
            flickr_url = request.POST.get('flickrAlbum', '').strip()
            if flickr_url:
                collectible.flickr_url = flickr_url
                collectible.save(update_fields=['flickr_url'])
            image_formset.instance = collectible
            image_formset.save()
            auth_formset.instance = collectible
            auth_formset.save()
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
        auth_formset = PlayerGearAuthenticationFormSet(prefix='authentications')

    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'memorabilia/collectible_form.html', {
        'form': form,
        'image_formset': image_formset,
        'auth_formset': auth_formset,
        'title': 'New Collectible',
        'collection': collection,
        'leagues': League.objects.all(),
        'how_obtained_options': HowObtainedOption.objects.all(),
        'users': User.objects.filter(is_superuser=False),
        'selected_collectible_type': collectible_type,
        'is_post_error': request.method == 'POST',
        'flickr_id': profile_obj.flickr_id,
        'want_list_url': _user_want_list_url(request.user),
    })


def _get_image_formset_class(ctype):
    if ctype == 'generalitem':
        return inlineformset_factory(GeneralItem, GeneralItemImage, form=GeneralItemImageForm, extra=0, can_delete=True)
    elif ctype == 'playergear':
        return PlayerGearImageFormSet
    elif ctype == 'hockeyjersey':
        return PlayerGearImageFormSet
    return CollectibleImageFormSet


def _get_auth_formset_class(ctype):
    if ctype in ('playergear', 'hockeyjersey', 'PlayerGear', 'HockeyJersey'):
        return PlayerGearAuthenticationFormSet
    if ctype in ('generalitem', 'GeneralItem'):
        return GeneralItemAuthenticationFormSet
    return PlayerItemAuthenticationFormSet


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
    Model = COLLECTIBLE_MODELS.get(collectible_type, PlayerItem)
    collectible = get_object_or_404(Model, pk=collectible_id)

    if request.method == "POST":
        submitted_type_raw = request.POST.get('collectible_type', '')
        new_type = _TYPE_NORMALIZE.get(submitted_type_raw, submitted_type_raw.lower())

        AuthFormSet = _get_auth_formset_class(collectible_type)
        if new_type == collectible_type:
            # Same type — standard edit
            FormClass = get_collectible_form_class(submitted_type_raw)
            ImageFormSet = _get_image_formset_class(collectible_type)
            form = FormClass(request.POST, request.FILES, instance=collectible, current_user=request.user)
            image_formset = ImageFormSet(request.POST, request.FILES, instance=collectible, prefix='images')
            auth_formset = AuthFormSet(request.POST, instance=collectible, prefix='authentications')
            if form.is_valid() and image_formset.is_valid() and auth_formset.is_valid():
                collectible = form.save()
                flickr_url = request.POST.get('flickrAlbum', '').strip()
                if flickr_url:
                    collectible.flickr_url = flickr_url
                    collectible.save(update_fields=['flickr_url'])
                image_formset.instance = collectible
                image_formset.save()
                auth_formset.instance = collectible
                auth_formset.save()
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
            ImageFormSet = _get_image_formset_class(collectible_type)
            image_formset = ImageFormSet(request.POST, request.FILES, instance=collectible, prefix='images')
            if form.is_valid() and image_formset.is_valid():
                # Apply image edits (new uploads, cover photo choice, deletions) to the
                # existing collectible first, so _copy_images carries the up-to-date set
                # of images over to the converted instance.
                image_formset.save()
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
            auth_formset = AuthFormSet(instance=collectible, prefix='authentications')

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
            'asking_price': f'{collectible.asking_price:.2f}' if collectible.asking_price is not None else None,
        }
        for field in ['league', 'player', 'team', 'number', 'brand', 'size', 'season', 'game_type', 'usage_type', 'gear_type', 'season_set', 'home_away', 'how_obtained', 'allow_featured', 'currency', 'trade_want_list']:
            if hasattr(collectible, field):
                initial[field] = getattr(collectible, field)
        form = HockeyJerseyForm(initial=initial, current_user=request.user)
        ImageFormSet = _get_image_formset_class(collectible_type)
        image_formset = ImageFormSet(instance=collectible, prefix='images')
        AuthFormSet = _get_auth_formset_class(collectible_type)
        auth_formset = AuthFormSet(instance=collectible, prefix='authentications')
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
        'auth_formset': auth_formset,
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
        'want_list_url': _user_want_list_url(request.user),
    })


@login_required
@permission_required('memorabilia.delete_collectible', fn=_get_collectible, raise_exception=True)
def delete_collectible(request, collection_id, collectible_type, collectible_id):
    Model = COLLECTIBLE_MODELS.get(collectible_type, PlayerItem)
    get_object_or_404(Model, pk=collectible_id).delete()

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
        'post_data_json': json.dumps(request.POST.dict()) if request.method == 'POST' else 'null',
    }
    return render(request, 'memorabilia/collectible_bulk_edit.html', context)

