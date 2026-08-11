import logging
import os
import tempfile

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Collection, MeiGrayPopulationReport
from .core import _get_collectible

logger = logging.getLogger(__name__)

def _safe_filename(name):
    """Turn a title into a safe ASCII filename (no path separators)."""
    import re
    safe = re.sub(r'[^\w\-]', '_', name)
    return safe[:80] or 'export'


@login_required
def export_collectible(request, collection_id, collectible_type, collectible_id):
    collectible = _get_collectible(
        request, collection_id=collection_id,
        collectible_type=collectible_type, collectible_id=collectible_id,
    )
    if collectible.collection.owner_uid != request.user.id and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    from .export_import import build_collectible_zip
    include_external = request.GET.get('include_external') == '1'
    zip_bytes = build_collectible_zip(collectible, include_external=include_external)

    response = HttpResponse(zip_bytes, content_type='application/zip')
    fname = _safe_filename(collectible.title)
    response['Content-Disposition'] = f'attachment; filename="{fname}.zip"'
    return response


@login_required
def export_collection(request, collection_id):
    collection = get_object_or_404(Collection, pk=collection_id)
    if collection.owner_uid != request.user.id and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    from .export_import import build_collection_zip
    include_external = request.GET.get('include_external') == '1'
    zip_bytes = build_collection_zip(collection, include_external=include_external)

    response = HttpResponse(zip_bytes, content_type='application/zip')
    fname = _safe_filename(collection.title)
    response['Content-Disposition'] = f'attachment; filename="{fname}.zip"'
    return response


@login_required
def download_population_report(request, league, season):
    report = get_object_or_404(MeiGrayPopulationReport, league=league, season=season)
    filename = os.path.basename(report.file.name)
    response = FileResponse(report.file.open('rb'), as_attachment=True, filename=filename)
    return response


@login_required
def import_upload(request, collection_id=None):
    # When collection_id is provided the import is scoped to that collection (merge mode).
    preset_collection = None
    if collection_id:
        preset_collection = get_object_or_404(Collection, pk=collection_id, owner_uid=request.user.id)

    if request.method == 'POST':
        if 'zip_file' not in request.FILES:
            return render(request, 'memorabilia/import_upload.html',
                          {'error': 'Please select a ZIP file to upload.',
                           'preset_collection': preset_collection})
        zip_file = request.FILES['zip_file']
        zip_bytes = zip_file.read()

        from .export_import import parse_zip
        from .export_import import ImportError as ZipImportError
        try:
            parsed = parse_zip(zip_bytes)
        except ZipImportError as e:
            return render(request, 'memorabilia/import_upload.html',
                          {'error': str(e), 'preset_collection': preset_collection})

        # Save bytes to a temp file; store path in session
        fd, tmp_path = tempfile.mkstemp(suffix='.zip', prefix='heavyuse_import_')
        try:
            os.write(fd, zip_bytes)
        finally:
            os.close(fd)

        request.session['import_tmp_path'] = tmp_path
        request.session['import_preview'] = {
            'type': parsed['type'],
            'collection': parsed.get('collection'),
            'item_count': len(parsed['items']),
            'items_preview': parsed['items'][:10],
            'preset_collection_id': preset_collection.id if preset_collection else None,
            'preset_collection_title': preset_collection.title if preset_collection else None,
        }
        return redirect('memorabilia:import_preview')

    return render(request, 'memorabilia/import_upload.html',
                  {'preset_collection': preset_collection})


@login_required
def import_preview(request):
    tmp_path = request.session.get('import_tmp_path')
    preview = request.session.get('import_preview')

    if not tmp_path or not preview:
        return redirect('memorabilia:import_upload')

    # Security: path must be inside the system temp dir
    if not tmp_path.startswith(tempfile.gettempdir()):
        return redirect('memorabilia:import_upload')

    if not os.path.exists(tmp_path):
        return redirect('memorabilia:import_upload')

    preset_collection_id = preview.get('preset_collection_id')
    preset_collection_title = preview.get('preset_collection_title')
    user_collections = (Collection.objects.filter(owner_uid=request.user.id).order_by('title')
                        if not preset_collection_id else None)

    if request.method == 'POST':
        if preset_collection_id:
            mode = 'merge'
            target_collection_id = preset_collection_id
        else:
            mode = request.POST.get('mode', 'new')
            target_collection_id = request.POST.get('target_collection') or None

        try:
            with open(tmp_path, 'rb') as f:
                zip_bytes = f.read()
        except OSError:
            return redirect('memorabilia:import_upload')

        from .export_import import parse_zip, commit_import
        from .export_import import ImportError as ZipImportError
        try:
            parsed = parse_zip(zip_bytes)
            collection = commit_import(zip_bytes, parsed, request.user.id, mode,
                                       target_collection_id)
        except ZipImportError as e:
            return render(request, 'memorabilia/import_preview.html', {
                'preview': preview,
                'user_collections': user_collections,
                'error': str(e),
            })
        except Exception as e:
            logger.exception("Import failed")
            return render(request, 'memorabilia/import_preview.html', {
                'preview': preview,
                'user_collections': user_collections,
                'error': f"Import failed: {e}",
            })
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            request.session.pop('import_tmp_path', None)
            request.session.pop('import_preview', None)

        return redirect('memorabilia:collection', pk=collection.id)

    return render(request, 'memorabilia/import_preview.html', {
        'preview': preview,
        'user_collections': user_collections,
        'preset_collection_title': preset_collection_title,
    })

