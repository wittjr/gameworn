"""
Export and import helpers for Heavy Use collectible data.

Export format (ZIP):
  manifest.json         — version + type + exported_at
  collectible.csv       — single-collectible export
  collection.csv        — collection metadata (collection export)
  items.csv             — all collectibles (collection export)
  images/               — collectible image files
    <filename>          — (single-collectible export)
    <export_id>/        — (collection export, one dir per collectible)
      <filename>
  photomatches/         — photo match image files (same layout as images/)
    <filename>
    <export_id>/
      <filename>

images_json CSV column holds a JSON array describing every collectible image:
  [{"filename": "img.jpg", "primary": true, "source": "upload"}, ...]
  [{"link": "https://...", "primary": false, "source": "external"}, ...]

photomatches_json CSV column holds a JSON array describing every photo match:
  [{"filename": "pm.jpg", "link": "...", "description": "...", "game_date": "2023-01-15", "source": "upload"}, ...]
"""

import csv
import io
import json
import os
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone

VERSION = 1

COLLECTIBLE_FIELDNAMES = [
    'export_id', 'collectible_type', 'title', 'description',
    'for_sale', 'for_trade', 'asking_price',
    'coa', 'how_obtained', 'flickr_url',
    'player', 'team', 'number', 'league',
    'brand', 'size', 'season',
    'game_type', 'usage_type', 'gear_type',
    'season_set', 'home_away',
    'allow_featured',
    'images_json',
    'photomatches_json',
]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _get_images(collectible):
    if hasattr(collectible, 'gear_images'):
        return list(collectible.gear_images.all())
    return list(collectible.images.all())


def _build_image_manifest(collectible, images_dir, zf, include_external):
    """Write uploaded images into zf, return list of image meta dicts."""
    images_meta = []
    used_names = set()
    for idx, img in enumerate(_get_images(collectible)):
        meta = {'primary': bool(img.primary)}
        if img.image and img.image.name:
            try:
                base_name = os.path.basename(img.image.name)
                name, counter = base_name, 1
                while name in used_names:
                    stem, ext = os.path.splitext(base_name)
                    name = f"{stem}_{counter}{ext}"
                    counter += 1
                used_names.add(name)
                with img.image.open('rb') as f:
                    zf.writestr(f"{images_dir}/{name}", f.read())
                meta.update(filename=name, source='upload')
            except Exception:
                if img.link:
                    meta.update(link=img.link, source='external')
        elif img.link:
            meta.update(source='external', link=img.link)
            if include_external:
                try:
                    import requests as _req
                    resp = _req.get(img.link, timeout=10)
                    resp.raise_for_status()
                    ct = resp.headers.get('content-type', '')
                    ext = ('.png' if 'png' in ct else '.gif' if 'gif' in ct
                           else '.webp' if 'webp' in ct else '.jpg')
                    name = f"external_{idx}{ext}"
                    while name in used_names:
                        name = f"external_{idx}_{uuid.uuid4().hex[:6]}{ext}"
                    used_names.add(name)
                    zf.writestr(f"{images_dir}/{name}", resp.content)
                    meta['filename'] = name
                except Exception:
                    pass
        if img.flickrObject:
            meta['flickrObject'] = img.flickrObject
        images_meta.append(meta)
    return images_meta


def _build_photomatch_manifest(collectible, pm_dir, zf, include_external):
    """Write photo match images into zf, return list of photomatch meta dicts.
    Only PlayerGear (and its proxy HockeyJersey) has photomatches.
    """
    if not hasattr(collectible, 'photomatches'):
        return []
    pm_meta = []
    used_names = set()
    for idx, pm in enumerate(collectible.photomatches.all()):
        meta = {
            'description': pm.description or '',
            'game_date': str(pm.game_date),
        }
        if pm.image and pm.image.name:
            try:
                base_name = os.path.basename(pm.image.name)
                name, counter = base_name, 1
                while name in used_names:
                    stem, ext = os.path.splitext(base_name)
                    name = f"{stem}_{counter}{ext}"
                    counter += 1
                used_names.add(name)
                with pm.image.open('rb') as f:
                    zf.writestr(f"{pm_dir}/{name}", f.read())
                meta.update(filename=name, source='upload')
            except Exception:
                if pm.link:
                    meta.update(link=pm.link, source='external')
        elif pm.link:
            meta.update(source='external', link=pm.link)
            if include_external:
                try:
                    import requests as _req
                    resp = _req.get(pm.link, timeout=10)
                    resp.raise_for_status()
                    ct = resp.headers.get('content-type', '')
                    ext = ('.png' if 'png' in ct else '.gif' if 'gif' in ct
                           else '.webp' if 'webp' in ct else '.jpg')
                    name = f"pm_external_{idx}{ext}"
                    while name in used_names:
                        name = f"pm_external_{idx}_{uuid.uuid4().hex[:6]}{ext}"
                    used_names.add(name)
                    zf.writestr(f"{pm_dir}/{name}", resp.content)
                    meta['filename'] = name
                except Exception:
                    pass
        pm_meta.append(meta)
    return pm_meta


def _collectible_to_row(collectible, images_meta, photomatches_meta):
    return {
        'export_id': str(collectible.export_id),
        'collectible_type': collectible.collectible_type,
        'title': collectible.title,
        'description': collectible.description,
        'for_sale': '' if collectible.for_sale is None else str(collectible.for_sale),
        'for_trade': '' if collectible.for_trade is None else str(collectible.for_trade),
        'asking_price': '' if collectible.asking_price is None else collectible.asking_price,
        'coa': collectible.coa_id or '',
        'how_obtained': collectible.how_obtained or '',
        'flickr_url': collectible.flickr_url or '',
        'player': getattr(collectible, 'player', ''),
        'team': getattr(collectible, 'team', None) or '',
        'number': ('' if getattr(collectible, 'number', None) is None
                   else getattr(collectible, 'number')),
        'league': getattr(collectible, 'league', None) or '',
        'brand': getattr(collectible, 'brand', ''),
        'size': getattr(collectible, 'size', ''),
        'season': getattr(collectible, 'season', ''),
        'game_type': getattr(collectible, 'game_type_id', ''),
        'usage_type': getattr(collectible, 'usage_type_id', ''),
        'gear_type': getattr(collectible, 'gear_type_id', None) or '',
        'season_set': getattr(collectible, 'season_set_id', None) or '',
        'home_away': getattr(collectible, 'home_away', None) or '',
        'allow_featured': ('' if collectible.allow_featured is None
                           else str(collectible.allow_featured)),
        'images_json': json.dumps(images_meta),
        'photomatches_json': json.dumps(photomatches_meta),
    }


def _rows_to_csv(rows, fieldnames):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def build_collectible_zip(collectible, include_external=False):
    """Return bytes of a ZIP for a single collectible."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps({
            'version': VERSION,
            'type': 'collectible',
            'exported_at': datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        images_meta = _build_image_manifest(collectible, 'images', zf, include_external)
        pm_meta = _build_photomatch_manifest(collectible, 'photomatches', zf, include_external)
        row = _collectible_to_row(collectible, images_meta, pm_meta)
        zf.writestr('collectible.csv', _rows_to_csv([row], COLLECTIBLE_FIELDNAMES))
    return buf.getvalue()


def build_collection_zip(collection, include_external=False):
    """Return bytes of a ZIP for an entire collection."""
    from itertools import chain
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('manifest.json', json.dumps({
            'version': VERSION,
            'type': 'collection',
            'exported_at': datetime.now(timezone.utc).isoformat(),
        }, indent=2))

        coll_row = {
            'export_id': str(collection.export_id),
            'title': collection.title,
            'image_link': collection.image_link or '',
        }
        zf.writestr('collection.csv', _rows_to_csv([coll_row], list(coll_row)))

        collectibles = list(chain(
            collection.playergear_set.prefetch_related('gear_images', 'photomatches').all(),
            collection.playeritem_set.prefetch_related('images').all(),
            collection.generalitem_set.prefetch_related('images').all(),
        ))
        rows = []
        for c in collectibles:
            images_dir = f"images/{c.export_id}"
            pm_dir = f"photomatches/{c.export_id}"
            images_meta = _build_image_manifest(c, images_dir, zf, include_external)
            pm_meta = _build_photomatch_manifest(c, pm_dir, zf, include_external)
            rows.append(_collectible_to_row(c, images_meta, pm_meta))
        if rows:
            zf.writestr('items.csv', _rows_to_csv(rows, COLLECTIBLE_FIELDNAMES))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportError(Exception):
    pass


def _check_zip_safety(zf):
    for name in zf.namelist():
        if name.startswith('/') or '..' in name.split('/'):
            raise ImportError(f"Unsafe path in ZIP: {name}")


def parse_zip(zip_bytes):
    """
    Parse export ZIP bytes. Returns:
    {'type': 'collection'|'collectible', 'collection': row_dict|None, 'items': [row_dict,...]}
    Raises ImportError on invalid data.
    """
    try:
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, 'r') as zf:
            _check_zip_safety(zf)
            names = set(zf.namelist())
            if 'manifest.json' not in names:
                raise ImportError("Not a valid Heavy Use export: manifest.json missing.")
            manifest = json.loads(zf.read('manifest.json'))
            if manifest.get('version') != VERSION:
                raise ImportError(f"Unsupported export version: {manifest.get('version')}")
            export_type = manifest.get('type')
            if export_type == 'collection':
                if 'collection.csv' not in names:
                    raise ImportError("collection.csv missing from ZIP.")
                coll_rows = list(csv.DictReader(
                    io.StringIO(zf.read('collection.csv').decode('utf-8'))))
                if not coll_rows:
                    raise ImportError("collection.csv is empty.")
                items = (list(csv.DictReader(
                    io.StringIO(zf.read('items.csv').decode('utf-8'))))
                    if 'items.csv' in names else [])
                return {'type': 'collection', 'collection': coll_rows[0], 'items': items}
            elif export_type == 'collectible':
                if 'collectible.csv' not in names:
                    raise ImportError("collectible.csv missing from ZIP.")
                items = list(csv.DictReader(
                    io.StringIO(zf.read('collectible.csv').decode('utf-8'))))
                if not items:
                    raise ImportError("collectible.csv is empty.")
                return {'type': 'collectible', 'collection': None, 'items': items}
            else:
                raise ImportError(f"Unknown export type: {export_type!r}")
    except (zipfile.BadZipFile, KeyError) as e:
        raise ImportError(f"Invalid ZIP file: {e}")


def commit_import(zip_bytes, parsed, owner_uid, mode, target_collection_id=None):
    """
    Atomically write the parsed import. Returns the Collection used/created.

    mode='new'   — always create a new Collection
    mode='merge' — add items to an existing collection (target_collection_id required)
    """
    from django.db import transaction
    from .models import Collection

    with transaction.atomic():
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, 'r') as zf:
            if mode == 'merge' and target_collection_id:
                collection = Collection.objects.get(pk=target_collection_id, owner_uid=owner_uid)
            else:
                # Create new collection
                if parsed['type'] == 'collection' and parsed.get('collection'):
                    title = parsed['collection'].get('title', 'Imported Collection')
                else:
                    title = 'Imported Collection'
                collection = Collection.objects.create(owner_uid=owner_uid, title=title)

            is_collection_export = (parsed['type'] == 'collection')
            for row in parsed['items']:
                _create_collectible(row, collection, zf, is_collection_export)

    return collection


def _create_collectible(row, collection, zf, is_collection_export):
    from .models import (PlayerItem, PlayerItemImage,
                         PlayerGear, PlayerGearImage, GeneralItem, GeneralItemImage,
                         GameType, UsageType, GearType, SeasonSet, CoaType)

    ctype = row.get('collectible_type', 'generalitem')
    common = {
        'collection': collection,
        'title': row.get('title', ''),
        'description': row.get('description', ''),
        'for_sale': _parse_bool(row.get('for_sale')),
        'for_trade': _parse_bool(row.get('for_trade')),
        'asking_price': _parse_float(row.get('asking_price')),
        'how_obtained': row.get('how_obtained') or None,
        'flickr_url': row.get('flickr_url', ''),
        'coa': _fk_or_none(CoaType, row.get('coa')),
        'allow_featured': _parse_bool(row.get('allow_featured')),
    }
    player = {
        'player': row.get('player', ''),
        'team': row.get('team') or None,
        'number': _parse_int(row.get('number')),
        'league': row.get('league') or None,
    }
    gear = {
        'brand': row.get('brand', ''),
        'size': row.get('size', ''),
        'season': row.get('season', ''),
        'game_type': _fk_or_none(GameType, row.get('game_type')),
        'usage_type': _fk_or_none(UsageType, row.get('usage_type')),
        'gear_type': _fk_or_none(GearType, row.get('gear_type')),
    }

    if ctype == 'playeritem':
        obj = PlayerItem.objects.create(**common, **player)
        ImageModel = PlayerItemImage
    elif ctype in ('playergear', 'hockeyjersey'):
        obj = PlayerGear.objects.create(
            **common, **player, **gear,
            home_away=row.get('home_away') or None,
            season_set=_fk_or_none(SeasonSet, row.get('season_set')),
        )
        if ctype == 'hockeyjersey':
            obj.gear_type_id = 'JRS'
            obj.save(update_fields=['gear_type_id'])
        ImageModel = PlayerGearImage
    else:
        obj = GeneralItem.objects.create(**common)
        ImageModel = GeneralItemImage

    # Directory layout: collection export uses <dir>/<export_id>/, single uses <dir>/
    orig_export_id = row.get('export_id', '')
    if is_collection_export and orig_export_id:
        images_dir = f"images/{orig_export_id}"
        pm_dir = f"photomatches/{orig_export_id}"
    else:
        images_dir = 'images'
        pm_dir = 'photomatches'

    _import_images(row, obj, ImageModel, images_dir, zf)
    if ctype in ('playergear', 'hockeyjersey'):
        _import_photomatches(row, obj, pm_dir, zf)
    return obj


def _import_images(row, obj, ImageModel, images_dir, zf):
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    zip_names = set(zf.namelist())
    try:
        images_meta = json.loads(row.get('images_json', '[]') or '[]')
    except (json.JSONDecodeError, TypeError):
        images_meta = []

    for meta in images_meta:
        primary = meta.get('primary', False)
        link = meta.get('link', '')
        filename = meta.get('filename', '')
        flickr_obj = meta.get('flickrObject')
        kwargs = {'collectible': obj, 'primary': primary}
        if filename:
            zip_path = f"{images_dir}/{filename}"
            if zip_path in zip_names:
                data = zf.read(zip_path)
                saved = default_storage.save(f"images/{filename}", ContentFile(data))
                kwargs['image'] = saved
            elif link:
                kwargs['link'] = link
        elif link:
            kwargs['link'] = link
        if flickr_obj:
            kwargs['flickrObject'] = flickr_obj
        ImageModel.objects.create(**kwargs)


def _import_photomatches(row, obj, pm_dir, zf):
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from .models import PhotoMatch

    zip_names = set(zf.namelist())
    try:
        pm_meta = json.loads(row.get('photomatches_json', '[]') or '[]')
    except (json.JSONDecodeError, TypeError):
        pm_meta = []

    for meta in pm_meta:
        game_date = meta.get('game_date')
        if not game_date:
            continue
        kwargs = {
            'collectible': obj,
            'game_date': game_date,
            'description': meta.get('description') or None,
        }
        filename = meta.get('filename', '')
        link = meta.get('link', '')
        if filename:
            zip_path = f"{pm_dir}/{filename}"
            if zip_path in zip_names:
                data = zf.read(zip_path)
                saved = default_storage.save(f"images/{filename}", ContentFile(data))
                kwargs['image'] = saved
            elif link:
                kwargs['link'] = link
        elif link:
            kwargs['link'] = link
        PhotoMatch.objects.create(**kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bool(val):
    if val in (None, ''):
        return None
    return val in ('True', 'true', '1', 'yes')


def _parse_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _fk_or_none(Model, key):
    if not key:
        return None
    try:
        return Model.objects.get(pk=key)
    except Model.DoesNotExist:
        return None
