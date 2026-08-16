import io
import json
import os
import zipfile

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import (
    HockeyJerseyForm, WantListForm, WantListItemForm, WantListItemImageFormSet,
    WantListProfileForm, get_collectible_form_class,
)
from ..models import (
    GameType, GearType, HowObtainedOption, League, SeasonSet, UsageType, UserProfile,
    WantList, WantListItem, WantListItemImage, WantListProfile, _generate_want_list_slug,
)
from .collectibles import _get_auth_formset_class, _get_image_formset_class

def _check_want_list_visibility(request, profile):
    """Return a redirect response if the visitor lacks access, else None."""
    if profile.visibility == 'private':
        if not request.user.is_authenticated or request.user != profile.user:
            raise Http404
    elif profile.visibility == 'logged_in':
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
    return None


def want_list_public(request, slug, list_slug=None):
    profile = get_object_or_404(WantListProfile, slug=slug)
    redirect_response = _check_want_list_visibility(request, profile)
    if redirect_response:
        return redirect_response

    # When a list_slug is given we show only that one list.
    single_list = None
    if list_slug is not None:
        single_list = get_object_or_404(WantList, profile=profile, slug=list_slug)

    filter_type = request.GET.get('type', '').strip()
    filter_league = request.GET.get('league', '').strip()
    filter_player = request.GET.get('player', '').strip()
    filter_team = request.GET.get('team', '').strip()

    base_qs = WantListItem.objects.filter(want_list__profile=profile)
    if single_list is not None:
        base_qs = base_qs.filter(want_list=single_list)

    used_type_keys = set(base_qs.values_list('collectible_type', flat=True).distinct())
    available_types = [
        (key, label)
        for key, label in WantListItem._meta.get_field('collectible_type').choices
        if key in used_type_keys
    ]
    available_leagues = League.objects.filter(
        key__in=base_qs.exclude(league__isnull=True).values_list('league_id', flat=True).distinct()
    ).order_by('name')
    available_players = sorted(
        base_qs.exclude(player__isnull=True).exclude(player='').order_by().values_list('player', flat=True).distinct()
    )
    available_teams = sorted(
        base_qs.exclude(team__isnull=True).exclude(team='').order_by().values_list('team', flat=True).distinct()
    )

    items_qs = base_qs.select_related(
        'league', 'game_type', 'usage_type', 'gear_type', 'season_set', 'want_list'
    ).prefetch_related('images')

    if filter_type:
        items_qs = items_qs.filter(collectible_type=filter_type)
    if filter_league:
        items_qs = items_qs.filter(league_id=filter_league)
    if filter_player:
        items_qs = items_qs.filter(player=filter_player)
    if filter_team:
        items_qs = items_qs.filter(team=filter_team)

    want_lists = WantList.objects.filter(profile=profile).order_by('order', 'id')
    if single_list is not None:
        want_lists = want_lists.filter(pk=single_list.pk)
    items_by_list = {}
    for item in items_qs:
        items_by_list.setdefault(item.want_list_id, []).append(item)

    is_filtered = any([filter_type, filter_league, filter_player, filter_team])
    lists_with_items = [
        (wl, items_by_list.get(wl.id, []))
        for wl in want_lists
        if not is_filtered or items_by_list.get(wl.id)
    ]

    return render(request, 'memorabilia/want_list_public.html', {
        'profile': profile,
        'lists_with_items': lists_with_items,
        'filter_type': filter_type,
        'filter_league': filter_league,
        'filter_player': filter_player,
        'filter_team': filter_team,
        'available_types': available_types,
        'available_leagues': available_leagues,
        'available_players': available_players,
        'available_teams': available_teams,
        'is_owner': request.user.is_authenticated and request.user == profile.user,
        'single_list': single_list,
    })


def _get_or_create_want_list_profile(user):
    profile, created = WantListProfile.objects.get_or_create(
        user=user,
        defaults={'slug': _generate_want_list_slug(user), 'visibility': 'public'},
    )
    return profile, created


@login_required
def want_list_manage(request):
    profile, created = _get_or_create_want_list_profile(request.user)
    if created:
        return redirect('memorabilia:want_list_profile_edit')
    want_lists = WantList.objects.filter(profile=profile).prefetch_related('items__images')
    return render(request, 'memorabilia/want_list_manage.html', {
        'profile': profile,
        'want_lists': want_lists,
    })


@login_required
def want_list_profile_edit(request):
    profile, _ = _get_or_create_want_list_profile(request.user)
    if request.method == 'POST':
        form = WantListProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:want_list_manage')
    else:
        form = WantListProfileForm(instance=profile)
    return render(request, 'memorabilia/want_list_profile_form.html', {
        'form': form,
        'profile': profile,
    })


@login_required
def want_list_create(request):
    profile, _ = _get_or_create_want_list_profile(request.user)
    if request.method == 'POST':
        form = WantListForm(request.POST)
        if form.is_valid():
            wl = form.save(commit=False)
            wl.profile = profile
            max_order = WantList.objects.filter(profile=profile).order_by('-order').values_list('order', flat=True).first()
            wl.order = (max_order + 1) if max_order is not None else 0
            wl.save()
            return redirect('memorabilia:want_list_manage')
    else:
        form = WantListForm()
    return render(request, 'memorabilia/want_list_form.html', {
        'form': form,
        'title': 'New List',
    })


@login_required
def want_list_edit(request, pk):
    profile = get_object_or_404(WantListProfile, user=request.user)
    want_list = get_object_or_404(WantList, pk=pk, profile=profile)
    if request.method == 'POST':
        form = WantListForm(request.POST, instance=want_list)
        if form.is_valid():
            form.save()
            return redirect('memorabilia:want_list_manage')
    else:
        form = WantListForm(instance=want_list)
    return render(request, 'memorabilia/want_list_form.html', {
        'form': form,
        'title': 'Edit List',
        'want_list': want_list,
    })


@login_required
def want_list_delete(request, pk):
    profile = get_object_or_404(WantListProfile, user=request.user)
    get_object_or_404(WantList, pk=pk, profile=profile).delete()
    return redirect('memorabilia:want_list_manage')


@login_required
def want_list_reorder(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    profile = get_object_or_404(WantListProfile, user=request.user)
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    for entry in data:
        WantList.objects.filter(pk=entry['id'], profile=profile).update(order=entry['order'])
    return JsonResponse({'status': 'ok'})


@login_required
def want_list_item_reorder(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    profile = get_object_or_404(WantListProfile, user=request.user)
    try:
        data = json.loads(request.body)
        list_pk = data['list_pk']
        item_ids = data['item_ids']
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    get_object_or_404(WantList, pk=list_pk, profile=profile)
    for order, item_id in enumerate(item_ids):
        WantListItem.objects.filter(pk=item_id, want_list_id=list_pk).update(order=order)
    return JsonResponse({'status': 'ok'})


@login_required
def want_list_item_create(request, list_pk):
    profile = get_object_or_404(WantListProfile, user=request.user)
    want_list = get_object_or_404(WantList, pk=list_pk, profile=profile)
    copy_from_pk = request.GET.get('copy_from')
    if request.method == 'POST':
        form = WantListItemForm(request.POST, current_user=request.user)
        formset = WantListItemImageFormSet(request.POST, request.FILES, prefix='images')
        if form.is_valid() and formset.is_valid():
            item = form.save()
            formset.instance = item
            formset.save()
            return redirect('memorabilia:want_list_manage')
    else:
        if copy_from_pk:
            source = get_object_or_404(WantListItem, pk=copy_from_pk, want_list__profile=profile)
            initial = _want_list_item_to_initial(source)
            initial['collectible_type'] = source.collectible_type
            initial['want_list'] = source.want_list_id
            if source.notes:
                initial['notes'] = source.notes
            form = WantListItemForm(initial=initial, current_user=request.user)
        else:
            form = WantListItemForm(initial={'want_list': want_list.pk}, current_user=request.user)
        formset = WantListItemImageFormSet(prefix='images')
    return render(request, 'memorabilia/want_list_item_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Copy Want List Item' if copy_from_pk else 'Add Want List Item',
        'want_list': want_list,
    })


@login_required
def want_list_item_edit(request, pk):
    profile = get_object_or_404(WantListProfile, user=request.user)
    item = get_object_or_404(WantListItem, pk=pk, want_list__profile=profile)
    if request.method == 'POST':
        form = WantListItemForm(request.POST, instance=item, current_user=request.user)
        formset = WantListItemImageFormSet(request.POST, request.FILES, instance=item, prefix='images')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('memorabilia:want_list_manage')
    else:
        form = WantListItemForm(instance=item, current_user=request.user)
        formset = WantListItemImageFormSet(instance=item, prefix='images')
    return render(request, 'memorabilia/want_list_item_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Edit Want List Item',
        'item': item,
        'want_list': item.want_list,
    })


@login_required
def want_list_item_delete(request, pk):
    profile = get_object_or_404(WantListProfile, user=request.user)
    get_object_or_404(WantListItem, pk=pk, want_list__profile=profile).delete()
    return redirect('memorabilia:want_list_manage')


def _want_list_item_to_initial(item):
    initial = {'title': item.title or ''}
    if item.description:
        initial['description'] = item.description
    if item.player:
        initial['player'] = item.player
    if item.team:
        initial['team'] = item.team
    if item.league_id:
        initial['league'] = item.league_id
    if item.number:
        initial['number'] = item.number
    if item.season:
        initial['season'] = item.season
    if item.game_type_id:
        initial['game_type'] = item.game_type_id
    if item.usage_type_id:
        initial['usage_type'] = item.usage_type_id
    if item.gear_type_id:
        initial['gear_type'] = item.gear_type_id
    if item.season_set_id:
        initial['season_set'] = item.season_set_id
    return initial


@login_required
def want_list_item_convert(request, pk):
    profile = get_object_or_404(WantListProfile, user=request.user)
    item = get_object_or_404(WantListItem, pk=pk, want_list__profile=profile)

    ctype_map = {
        'playeritem': 'PlayerItem',
        'playergear': 'PlayerGear',
        'hockeyjersey': 'HockeyJersey',
        'generalitem': 'GeneralItem',
    }
    form_ctype = ctype_map.get(item.collectible_type, 'PlayerItem')
    FormClass = get_collectible_form_class(form_ctype)
    ImageFormSet = _get_image_formset_class(item.collectible_type)
    AuthFormSet = _get_auth_formset_class(item.collectible_type)

    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, current_user=request.user)
        image_formset = ImageFormSet(request.POST, request.FILES, prefix='images')
        auth_formset = AuthFormSet(request.POST, prefix='authentications')
        if form.is_valid() and image_formset.is_valid() and auth_formset.is_valid():
            collectible = form.save()
            image_formset.instance = collectible
            image_formset.save()
            auth_formset.instance = collectible
            auth_formset.save()
            item.delete()
            return redirect('memorabilia:collectible',
                            collection_id=collectible.collection.id,
                            collectible_type=collectible.collectible_type,
                            pk=collectible.id)
        if not isinstance(form, HockeyJerseyForm):
            display_form = HockeyJerseyForm(request.POST, request.FILES, current_user=request.user)
            display_form._errors = form.errors
            form = display_form
    else:
        initial = _want_list_item_to_initial(item)
        form = FormClass(initial=initial, current_user=request.user)
        image_formset = ImageFormSet(prefix='images')
        auth_formset = AuthFormSet(prefix='authentications')
        if not isinstance(form, HockeyJerseyForm):
            form = HockeyJerseyForm(initial=initial, current_user=request.user)

    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'memorabilia/want_list_item_convert.html', {
        'form': form,
        'image_formset': image_formset,
        'auth_formset': auth_formset,
        'item': item,
        'selected_collectible_type': form_ctype,
        'title': f'Convert to Collection Item',
        'leagues': League.objects.all(),
        'how_obtained_options': HowObtainedOption.objects.all(),
        'users': User.objects.filter(is_superuser=False),
        'is_post_error': request.method == 'POST',
        'flickr_id': profile_obj.flickr_id,
    })


@login_required
def want_list_export(request):
    profile, _ = _get_or_create_want_list_profile(request.user)
    want_lists = WantList.objects.filter(profile=profile).prefetch_related('items__images')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        manifest = {'version': 1, 'want_lists': []}

        for wl in want_lists:
            list_data = {'title': wl.title, 'items': []}
            for item in wl.items.all():
                item_data = {
                    'collectible_type': item.collectible_type,
                    'player':      item.player,
                    'league':      item.league_id,
                    'team':        item.team,
                    'number':      item.number,
                    'season':      item.season,
                    'game_type':   item.game_type_id,
                    'usage_type':  item.usage_type_id,
                    'gear_type':   item.gear_type_id,
                    'season_set':  item.season_set_id,
                    'title':       item.title,
                    'description': item.description,
                    'notes':       item.notes,
                    'order':       item.order,
                    'images':      [],
                }
                for i, img in enumerate(item.images.all()):
                    if img.image and img.image.name:
                        ext = os.path.splitext(img.image.name)[1]
                        filename = f'images/item_{item.pk}_{i}{ext}'
                        try:
                            with img.image.open('rb') as f:
                                zf.writestr(filename, f.read())
                            item_data['images'].append({'type': 'file', 'filename': filename})
                        except Exception:
                            pass
                    elif img.link:
                        item_data['images'].append({'type': 'link', 'url': img.link})
                list_data['items'].append(item_data)
            manifest['want_lists'].append(list_data)

        zf.writestr('manifest.json', json.dumps(manifest, indent=2))

    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="want_lists_export.zip"'
    return response


@login_required
def want_list_import(request):
    if request.method != 'POST':
        return render(request, 'memorabilia/want_list_import.html', {})

    uploaded = request.FILES.get('zip_file')
    if not uploaded:
        return render(request, 'memorabilia/want_list_import.html', {
            'error': 'Please select a file to import.',
        })

    try:
        with zipfile.ZipFile(uploaded, 'r') as zf:
            try:
                manifest = json.loads(zf.read('manifest.json'))
            except (KeyError, json.JSONDecodeError):
                return render(request, 'memorabilia/want_list_import.html', {
                    'error': 'Invalid export file — missing or unreadable manifest.',
                })

            profile, _ = _get_or_create_want_list_profile(request.user)
            lists_created = items_created = items_skipped = 0

            for list_data in manifest.get('want_lists', []):
                wl, created = WantList.objects.get_or_create(
                    profile=profile,
                    title=list_data['title'],
                )
                if created:
                    lists_created += 1

                for item_data in list_data.get('items', []):
                    league     = League.objects.filter(key=item_data['league']).first()     if item_data.get('league')     else None
                    game_type  = GameType.objects.filter(key=item_data['game_type']).first() if item_data.get('game_type')  else None
                    usage_type = UsageType.objects.filter(key=item_data['usage_type']).first() if item_data.get('usage_type') else None
                    gear_type  = GearType.objects.filter(key=item_data['gear_type']).first()  if item_data.get('gear_type')  else None
                    season_set = SeasonSet.objects.filter(key=item_data['season_set']).first() if item_data.get('season_set') else None

                    duplicate = WantListItem.objects.filter(
                        want_list=wl,
                        collectible_type=item_data.get('collectible_type', ''),
                        player=item_data.get('player'),
                        league=league,
                        team=item_data.get('team'),
                        number=item_data.get('number'),
                        season=item_data.get('season'),
                        game_type=game_type,
                        usage_type=usage_type,
                        gear_type=gear_type,
                        season_set=season_set,
                        title=item_data.get('title'),
                    ).exists()

                    if duplicate:
                        items_skipped += 1
                        continue

                    item = WantListItem.objects.create(
                        want_list=wl,
                        collectible_type=item_data.get('collectible_type', 'generalitem'),
                        player=item_data.get('player'),
                        league=league,
                        team=item_data.get('team'),
                        number=item_data.get('number'),
                        season=item_data.get('season'),
                        game_type=game_type,
                        usage_type=usage_type,
                        gear_type=gear_type,
                        season_set=season_set,
                        title=item_data.get('title'),
                        description=item_data.get('description'),
                        notes=item_data.get('notes', ''),
                        order=item_data.get('order', 0),
                    )
                    items_created += 1

                    for img_data in item_data.get('images', []):
                        if img_data.get('type') == 'link':
                            WantListItemImage.objects.create(item=item, link=img_data['url'])
                        elif img_data.get('type') == 'file':
                            try:
                                file_bytes = zf.read(img_data['filename'])
                                img_obj = WantListItemImage(item=item)
                                img_obj.image.save(
                                    os.path.basename(img_data['filename']),
                                    ContentFile(file_bytes),
                                    save=True,
                                )
                            except KeyError:
                                pass

    except zipfile.BadZipFile:
        return render(request, 'memorabilia/want_list_import.html', {
            'error': 'The uploaded file is not a valid ZIP archive.',
        })

    return render(request, 'memorabilia/want_list_import.html', {
        'success': True,
        'lists_created': lists_created,
        'items_created': items_created,
        'items_skipped': items_skipped,
    })

