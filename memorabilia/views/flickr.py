import json
import logging
import threading

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from rules.contrib.views import objectgetter, permission_required

from ..models import Collection, GeneralItem, GeneralItemImage, PlayerGear, PlayerItem, UserProfile

logger = logging.getLogger(__name__)

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
        'existing_albums_json': json.dumps(existing_albums),
    })


@login_required
@permission_required('memorabilia.update_collection', fn=objectgetter(Collection, 'collection_id'), raise_exception=True)
def bulk_add_flickr_album(request, collection_id):
    """Create a single GeneralItem from one Flickr album. Called via fetch for each selected album."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    collection = get_object_or_404(Collection, pk=collection_id)
    try:
        body = json.loads(request.body)
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
        body = json.loads(request.body)
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
        connection.close()


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

