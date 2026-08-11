from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from ..forms import CollectibleSearchForm, ContactOwnerForm, MarketplaceFilterForm
from ..models import GeneralItem, HockeyJersey, InquiryMessage, League, PlayerGear, PlayerItem, Team
from ..relay import relay_message
from .core import _get_collectible

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
    auth_issuer = data.get('auth_issuer')
    if auth_issuer:
        qs = qs.filter(authentications__issuer_id=auth_issuer).distinct()
    auth_number = data.get('auth_number')
    if auth_number:
        qs = qs.filter(authentications__number__icontains=auth_number).distinct()
    return qs


def search_collectibles(request):
    # Fields that only exist on PlayerGear/HockeyJersey
    _GEAR_ONLY = ('brand', 'season', 'game_type', 'usage_type', 'gear_type')
    # Fields that exist on PlayerItem + PlayerGear but NOT GeneralItem
    _PLAYER_FIELDS = ('league', 'player', 'team', 'number')
    # Fields that only exist on HockeyJersey
    _JERSEY_ONLY = ('season_set', 'home_away')

    form = CollectibleSearchForm(request.GET if request.GET else {'item_type': 'hockeyjersey'})
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

        # Exclude types that don't have the filtered fields.
        # Jersey-only fields (season_set, home_away) are DB columns on PlayerGear
        # but are only exposed via HockeyJerseyForm. Zeroing gear_qs here is an
        # intentional product decision: these filters are semantically jersey-only.
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


def marketplace(request):
    """Public listing of collectibles for sale/trade, with Search-style filters."""
    form = MarketplaceFilterForm(request.GET or None)

    show = request.GET.get('show', '')  # 'sale', 'trade', or '' for either
    if show == 'sale':
        availability = Q(for_sale=True)
    elif show == 'trade':
        availability = Q(for_trade=True)
    else:
        show = ''
        availability = Q(for_sale=True) | Q(for_trade=True)

    gear_qs = PlayerGear.objects.exclude(gear_type_id='JRS').filter(availability)
    hockey_qs = HockeyJersey.objects.filter(availability)
    player_qs = PlayerItem.objects.filter(availability)
    other_qs = GeneralItem.objects.filter(availability)

    if form.is_valid():
        data = form.cleaned_data

        # Narrow to the chosen item type (keeping the availability filter).
        item_type = data.get('item_type')
        if item_type == 'playergear':
            hockey_qs = HockeyJersey.objects.none(); player_qs = PlayerItem.objects.none(); other_qs = GeneralItem.objects.none()
        elif item_type == 'hockeyjersey':
            gear_qs = PlayerGear.objects.none(); player_qs = PlayerItem.objects.none(); other_qs = GeneralItem.objects.none()
        elif item_type == 'playeritem':
            gear_qs = PlayerGear.objects.none(); hockey_qs = HockeyJersey.objects.none(); other_qs = GeneralItem.objects.none()
        elif item_type == 'generalitem':
            gear_qs = PlayerGear.objects.none(); hockey_qs = HockeyJersey.objects.none(); player_qs = PlayerItem.objects.none()

        gear_qs = _apply_collectible_filters(gear_qs, data)
        hockey_qs = _apply_collectible_filters(hockey_qs, data)
        # PlayerItem/GeneralItem lack gear-only fields; GeneralItem also lacks
        # player fields — drop those keys so the filter helper doesn't touch them.
        player_data = {k: v for k, v in data.items() if k not in ('game_type', 'usage_type')}
        player_qs = _apply_collectible_filters(player_qs, player_data)
        other_data = {k: v for k, v in data.items() if k not in ('game_type', 'usage_type', 'league', 'team')}
        other_qs = _apply_collectible_filters(other_qs, other_data)

        # Exclude types that can't carry the filtered fields.
        if data.get('home_away'):
            gear_qs = PlayerGear.objects.none(); player_qs = PlayerItem.objects.none(); other_qs = GeneralItem.objects.none()
        elif data.get('game_type') or data.get('usage_type'):
            player_qs = PlayerItem.objects.none(); other_qs = GeneralItem.objects.none()
        elif data.get('league') or data.get('team'):
            other_qs = GeneralItem.objects.none()

    results = sorted(
        list(gear_qs.select_related('collection').prefetch_related('gear_images')) +
        list(hockey_qs.select_related('collection').prefetch_related('gear_images')) +
        list(player_qs.select_related('collection').prefetch_related('images')) +
        list(other_qs.select_related('collection').prefetch_related('images')),
        key=lambda x: x.last_updated,
        reverse=True,
    )

    # Free-text league suggestions (datalist), matching the search page.
    league_keys = set(League.objects.values_list('key', flat=True))
    distinct_values = PlayerItem.objects.values_list('league', flat=True).distinct()
    custom_leagues = [v for v in distinct_values if v and v not in league_keys]

    context = {
        'title': 'Marketplace',
        'form': form,
        'results': results,
        'show': show,
        'leagues': League.objects.all(),
        'custom_leagues': custom_leagues,
    }
    return render(request, 'memorabilia/marketplace.html', context)


def _resolve_interest(collectible, raw):
    """Normalize the requester's 'interest' (which listing they responded to) to
    'sale'/'trade', validated against what the item is actually listed as. Falls
    back to the only listing when there's just one."""
    raw = (raw or '').strip().lower()
    if raw == 'sale' and collectible.for_sale:
        return 'sale'
    if raw == 'trade' and collectible.for_trade:
        return 'trade'
    if collectible.for_sale and not collectible.for_trade:
        return 'sale'
    if collectible.for_trade and not collectible.for_sale:
        return 'trade'
    return ''


@login_required
def contact_owner(request, collection_id, collectible_type, collectible_id):
    """Form to message the owner of a for-sale/for-trade item. The message is
    relayed by email (reply-to the sender) so the owner's address is never
    exposed, and a record is kept. Requires login."""
    collectible = _get_collectible(request, collectible_id=collectible_id, collectible_type=collectible_type)
    if collectible.collection_id != collection_id:
        raise Http404("Collectible not found")
    # Only items the owner has actually listed can be contacted about.
    if not (collectible.for_sale or collectible.for_trade):
        raise Http404("Item is not listed for sale or trade")
    owner = User.objects.filter(id=collectible.collection.owner_uid).first()
    if not owner or not owner.email:
        raise Http404("Owner cannot be contacted")

    item_url = request.build_absolute_uri(reverse('memorabilia:collectible', kwargs={
        'collection_id': collection_id,
        'collectible_type': collectible_type,
        'pk': collectible_id,
    }))

    if request.method == 'POST':
        form = ContactOwnerForm(request.POST)
        if form.is_valid():
            # Honeypot tripped → act as if it succeeded, but do nothing.
            if form.is_spam():
                messages.success(request, 'Your message has been sent to the owner.')
                return redirect('memorabilia:collectible', collection_id=collection_id,
                                collectible_type=collectible_type, pk=collectible_id)

            inquiry = form.save(commit=False)
            inquiry.recipient = owner
            inquiry.sender_user = request.user
            inquiry.collection_id = collection_id
            inquiry.collectible_type = collectible_type
            inquiry.collectible_id = collectible_id
            inquiry.item_title = collectible.title
            inquiry.item_url = item_url
            interest = _resolve_interest(collectible, request.POST.get('interest'))
            inquiry.interest = interest
            if interest == 'sale':
                inquiry.item_price = collectible.asking_price
                inquiry.item_currency = collectible.currency
            inquiry.save()

            # The first message is from the requester; relay it to the owner.
            first_message = InquiryMessage.objects.create(
                inquiry=inquiry,
                sender_role=InquiryMessage.REQUESTER,
                body=form.cleaned_data['message'],
            )
            relay_message(first_message)

            if first_message.email_sent:
                messages.success(request, 'Your message has been sent to the owner.')
            else:
                messages.success(request, "Your message has been recorded and the owner will be notified.")
            return redirect('memorabilia:collectible', collection_id=collection_id,
                            collectible_type=collectible_type, pk=collectible_id)
    else:
        form = ContactOwnerForm(initial={
            'sender_name': request.user.get_full_name() or request.user.username,
            'sender_email': request.user.email,
        })

    return render(request, 'memorabilia/contact_owner.html', {
        'form': form,
        'collectible': collectible,
        'item_url': item_url,
        'interest': _resolve_interest(collectible, request.GET.get('interest')),
        'title': f'Contact owner about {collectible.title}',
    })


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

