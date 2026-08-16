import hashlib
import hmac
import tempfile

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.templatetags.static import static

from ..models import Collection, PlayerItem, PlayerGear, HockeyJersey, GeneralItem, League, GameType, UsageType, GearType, SeasonSet, UserProfile, PlayerItemImage, PlayerGearImage, GeneralItemImage, PhotoMatch, AuthSource, WantListProfile, WantList, WantListItem, WantListItemImage, OwnerInquiry, InquiryMessage, GeneralItemAuthentication
from ..relay import ingest_inbound, extract_token, strip_quoted_reply, relay_message, relay_address
from ..templatetags.memorabilia_extras import get_user_avatar_url, getmediaurl, collage_rows

from .base import BaseTestCase

class AuthSourceModelTests(BaseTestCase):
    """Tests for the AuthSource lookup model."""

    def test_authsource_str(self):
        from memorabilia.models import AuthSource
        src = AuthSource.objects.create(key='PSA', name='PSA Authentication')
        self.assertEqual(str(src), 'PSA Authentication')

    def test_authsource_ordering_is_alphabetical(self):
        from memorabilia.models import AuthSource
        AuthSource.objects.create(key='JSA', name='JSA Authentication')
        AuthSource.objects.create(key='BAS', name='Beckett Authentication')
        AuthSource.objects.create(key='PSA2', name='PSA Authentication')
        sources = list(AuthSource.objects.values_list('name', flat=True))
        self.assertEqual(sources, sorted(sources))

    def test_authsource_creation_with_key_pk(self):
        from memorabilia.models import AuthSource
        src = AuthSource.objects.create(key='TRISTAR', name='Tristar')
        self.assertEqual(src.pk, 'TRISTAR')

class AuthFormTests(BaseTestCase):
    """Tests that auth formsets are wired correctly and old flat fields are gone."""

    def test_hockeyjersey_form_excludes_old_auth_fields(self):
        from memorabilia.forms import HockeyJerseyForm
        form = HockeyJerseyForm(current_user=self.owner)
        self.assertNotIn('team_inventory_number', form.fields)
        self.assertNotIn('auth_tag_number', form.fields)
        self.assertNotIn('auth_source', form.fields)
        self.assertNotIn('coa', form.fields)

    def test_playergear_form_excludes_old_auth_fields(self):
        from memorabilia.forms import PlayerGearForm
        form = PlayerGearForm(current_user=self.owner)
        self.assertNotIn('team_inventory_number', form.fields)
        self.assertNotIn('auth_tag_number', form.fields)
        self.assertNotIn('auth_source', form.fields)
        self.assertNotIn('coa', form.fields)

    def test_player_gear_authentication_formset_instantiates(self):
        from memorabilia.forms import PlayerGearAuthenticationFormSet
        fs = PlayerGearAuthenticationFormSet(prefix='authentications')
        self.assertIsNotNone(fs)

    def test_player_item_authentication_formset_instantiates(self):
        from memorabilia.forms import PlayerItemAuthenticationFormSet
        fs = PlayerItemAuthenticationFormSet(prefix='authentications')
        self.assertIsNotNone(fs)

    def test_general_item_authentication_formset_instantiates(self):
        from memorabilia.forms import GeneralItemAuthenticationFormSet
        fs = GeneralItemAuthenticationFormSet(prefix='authentications')
        self.assertIsNotNone(fs)

class AuthenticationModelTests(BaseTestCase):
    """Tests for the new per-type authentication tables."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import CoaType, AuthSource
        cls.coa_paper = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper Document'})[0]
        cls.coa_printed = CoaType.objects.get_or_create(key='printed', defaults={'name': 'Printed on Jersey'})[0]
        cls.meigray = AuthSource.objects.get_or_create(key='MEIGRAY', defaults={'name': 'MeiGray'})[0]
        cls.team_src = AuthSource.objects.get_or_create(key='TEAM', defaults={'name': 'Team Authenticated'})[0]

    def test_playergear_authentication_creates_and_relates(self):
        from memorabilia.models import PlayerGearAuthentication
        auth = PlayerGearAuthentication.objects.create(
            collectible=self.player_gear,
            auth_type=self.coa_paper,
            number='M12345',
            issuer=self.meigray,
        )
        self.assertEqual(self.player_gear.authentications.count(), 1)
        self.assertEqual(auth.number, 'M12345')

    def test_playeritem_authentication_creates_and_relates(self):
        from memorabilia.models import PlayerItemAuthentication
        auth = PlayerItemAuthentication.objects.create(
            collectible=self.player_item,
            auth_type=self.coa_paper,
            number='',
            issuer=None,
        )
        self.assertEqual(self.player_item.authentications.count(), 1)
        self.assertIsNone(auth.issuer)

    def test_generalitem_authentication_creates_and_relates(self):
        from memorabilia.models import GeneralItemAuthentication
        auth = GeneralItemAuthentication.objects.create(
            collectible=self.general_item,
            auth_type=self.coa_paper,
            number='',
            issuer=None,
        )
        self.assertEqual(self.general_item.authentications.count(), 1)

    def test_authentication_str_with_all_fields(self):
        from memorabilia.models import PlayerGearAuthentication
        auth = PlayerGearAuthentication(
            collectible=self.player_gear,
            auth_type=self.coa_paper,
            number='M12345',
            issuer=self.meigray,
        )
        s = str(auth)
        self.assertIn('M12345', s)

    def test_authentication_str_empty(self):
        from memorabilia.models import PlayerGearAuthentication
        auth = PlayerGearAuthentication(collectible=self.player_gear)
        self.assertEqual(str(auth), '—')

    def test_authentication_deleted_with_collectible(self):
        from memorabilia.models import PlayerGearAuthentication
        jersey = HockeyJersey.objects.create(
            title='Delete Auth Test Jersey', description='', collection=self.collection,
            league='NHL', player='Test', brand='CCM', size='54', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=jersey, auth_type=self.coa_printed, number='TI-99', issuer=self.team_src,
        )
        pk = jersey.pk
        jersey.delete()
        self.assertEqual(PlayerGearAuthentication.objects.filter(collectible_id=pk).count(), 0)

    def test_two_auth_records_per_jersey(self):
        from memorabilia.models import PlayerGearAuthentication
        jersey = HockeyJersey.objects.create(
            title='Two Auth Jersey', description='', collection=self.collection,
            league='NHL', player='Two Auth', brand='CCM', size='54', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=jersey, auth_type=self.coa_paper, number='M99', issuer=self.meigray,
        )
        PlayerGearAuthentication.objects.create(
            collectible=jersey, auth_type=self.coa_printed, number='TI-001', issuer=self.team_src,
        )
        self.assertEqual(jersey.authentications.count(), 2)

class HockeyJerseyAuthDetailTests(BaseTestCase):
    """Tests that the detail view correctly exposes authentications on a jersey."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import CoaType, AuthSource, PlayerGearAuthentication
        cls.coa = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper Document'})[0]
        cls.source = AuthSource.objects.get_or_create(key='BAS2', defaults={'name': 'Beckett'})[0]
        cls.auth_jersey = HockeyJersey.objects.create(
            title='Auth Detail Jersey',
            description='Jersey with authentications',
            collection=cls.collection,
            league='NHL',
            player='Wayne Gretzky',
            brand='CCM',
            size='54',
            season='1988',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )
        cls.auth = PlayerGearAuthentication.objects.create(
            collectible=cls.auth_jersey,
            auth_type=cls.coa,
            number='TAG-DETAIL-99',
            issuer=cls.source,
        )

    def _detail_url(self):
        return reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'hockeyjersey', 'pk': self.auth_jersey.id},
        )

    def test_detail_returns_200(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)

    def test_detail_context_collectible_has_authentication(self):
        response = self.client.get(self._detail_url())
        collectible = response.context['object']
        self.assertEqual(collectible.authentications.count(), 1)
        auth = collectible.authentications.first()
        self.assertEqual(auth.number, 'TAG-DETAIL-99')

    def test_detail_uses_hockeyjersey_template(self):
        response = self.client.get(self._detail_url())
        self.assertTemplateUsed(response, 'memorabilia/hockeyjersey_detail.html')

class AuthSearchTests(BaseTestCase):
    """Tests that auth_issuer and auth_number search filters work across collectible types."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import CoaType, AuthSource, PlayerGearAuthentication, PlayerItemAuthentication
        cls.tristar = AuthSource.objects.get_or_create(key='TRISTAR', defaults={'name': 'Tristar'})[0]
        cls.coa = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper Document'})[0]
        cls.search_col = Collection.objects.create(owner_uid=cls.owner.id, title='Auth Search Collection')

        cls.auth_jersey = HockeyJersey.objects.create(
            title='Auth Search Jersey',
            description='Jersey with auth',
            collection=cls.search_col,
            league='NHL', player='Gordie Howe', brand='Koho', size='52', season='1970',
            game_type=cls.game_type, usage_type=cls.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=cls.auth_jersey, auth_type=cls.coa, number='STICKER-ALPHA', issuer=cls.tristar,
        )
        cls.auth_player = PlayerItem.objects.create(
            title='Auth Search Player', description='Player with auth',
            collection=cls.search_col, league='NHL', player='Phil Esposito',
        )
        PlayerItemAuthentication.objects.create(
            collectible=cls.auth_player, auth_type=cls.coa, number='PLAYER-AUTH-1', issuer=cls.tristar,
        )
        cls.plain_gear = PlayerGear.objects.create(
            title='Plain Gear No Auth', description='', collection=cls.search_col,
            league='NHL', player='Bobby Orr', brand='CCM', size='L', season='1972',
            game_type=cls.game_type, usage_type=cls.usage_type,
        )
        cls.plain_general = GeneralItem.objects.create(
            title='Plain General No Auth', description='', collection=cls.search_col,
        )

    def _search_url(self, **params):
        from urllib.parse import urlencode
        base = reverse('memorabilia:search_collectibles')
        return f'{base}?{urlencode(params)}' if params else base

    def test_auth_number_filter_returns_matching_jersey(self):
        response = self.client.get(self._search_url(auth_number='STICKER-ALPHA'))
        self.assertEqual(response.status_code, 200)
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Jersey', titles)

    def test_auth_number_filter_is_case_insensitive(self):
        response = self.client.get(self._search_url(auth_number='sticker'))
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Jersey', titles)

    def test_auth_number_excludes_items_without_matching_auth(self):
        response = self.client.get(self._search_url(auth_number='STICKER-ALPHA'))
        titles = [r.title for r in response.context['results']]
        self.assertNotIn('Plain Gear No Auth', titles)
        self.assertNotIn('Plain General No Auth', titles)

    def test_auth_number_matches_player_item(self):
        response = self.client.get(self._search_url(auth_number='PLAYER-AUTH-1'))
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Player', titles)

    def test_auth_issuer_filter_returns_matching_jersey(self):
        response = self.client.get(self._search_url(auth_issuer='TRISTAR'))
        self.assertEqual(response.status_code, 200)
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Jersey', titles)

    def test_auth_issuer_excludes_items_without_auth(self):
        response = self.client.get(self._search_url(auth_issuer='TRISTAR'))
        titles = [r.title for r in response.context['results']]
        self.assertNotIn('Plain Gear No Auth', titles)
        self.assertNotIn('Plain General No Auth', titles)

    def test_auth_issuer_no_match_returns_no_jersey(self):
        AuthSource.objects.get_or_create(key='JSA_NOONE', defaults={'name': 'JSA No Match'})
        response = self.client.get(self._search_url(auth_issuer='JSA_NOONE'))
        titles = [r.title for r in response.context['results']]
        self.assertNotIn('Auth Search Jersey', titles)

    def test_search_form_has_auth_issuer_field(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertIn('auth_issuer', form.fields)

    def test_search_form_has_auth_number_field(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertIn('auth_number', form.fields)

    def test_search_form_does_not_have_old_fields(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertNotIn('auth_source', form.fields)
        self.assertNotIn('auth_tag_number', form.fields)
        self.assertNotIn('team_inventory_number', form.fields)

class AuthExportImportTests(BaseTestCase):
    """Tests for export/import round-trip of authentication records."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import AuthSource, CoaType, PlayerGearAuthentication
        cls.coa_paper = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper COA'})[0]
        cls.coa_printed = CoaType.objects.get_or_create(key='printed', defaults={'name': 'Printed on Jersey'})[0]
        cls.auth_source = AuthSource.objects.create(key='BECKETT', name='Beckett')
        cls.team_source = AuthSource.objects.get_or_create(key='TEAM', defaults={'name': 'Team'})[0]
        cls.export_jersey = HockeyJersey.objects.create(
            title='Export Auth Jersey',
            description='Jersey for export testing',
            collection=cls.collection,
            league='NHL',
            player='Mario Lemieux',
            brand='CCM',
            size='56',
            season='1992',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=cls.export_jersey,
            auth_type=cls.coa_paper,
            number='TAG-EXPORT-007',
            issuer=cls.auth_source,
        )
        PlayerGearAuthentication.objects.create(
            collectible=cls.export_jersey,
            auth_type=cls.coa_printed,
            number='INV-EXPORT',
            issuer=cls.team_source,
        )

    def _round_trip(self, jersey):
        """Export a single jersey and import it into a fresh collection. Return the new jersey."""
        from memorabilia.export_import import build_collectible_zip, parse_zip, _create_collectible
        import zipfile, io

        zip_bytes = build_collectible_zip(jersey)
        parsed = parse_zip(zip_bytes)
        target_collection = Collection.objects.create(
            owner_uid=self.owner.id, title='Import Target'
        )
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        for row in parsed['items']:
            _create_collectible(row, target_collection, zf, is_collection_export=False)
        return HockeyJersey.objects.filter(collection=target_collection).prefetch_related('authentications').first()

    def _get_csv_row(self, jersey):
        import zipfile, io, csv
        from memorabilia.export_import import build_collectible_zip
        zip_bytes = build_collectible_zip(jersey)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_text = zf.read('collectible.csv').decode()
        reader = csv.DictReader(io.StringIO(csv_text))
        return next(reader)

    def test_export_contains_authentications_json_column(self):
        row = self._get_csv_row(self.export_jersey)
        self.assertIn('authentications_json', row)

    def test_export_does_not_contain_old_auth_columns(self):
        row = self._get_csv_row(self.export_jersey)
        self.assertNotIn('team_inventory_number', row)
        self.assertNotIn('auth_tag_number', row)
        self.assertNotIn('auth_source', row)

    def test_export_authentications_json_has_two_records(self):
        import json
        row = self._get_csv_row(self.export_jersey)
        auth_list = json.loads(row['authentications_json'])
        self.assertEqual(len(auth_list), 2)

    def test_export_preserves_auth_numbers(self):
        import json
        row = self._get_csv_row(self.export_jersey)
        auth_list = json.loads(row['authentications_json'])
        numbers = {a['number'] for a in auth_list}
        self.assertIn('TAG-EXPORT-007', numbers)
        self.assertIn('INV-EXPORT', numbers)

    def test_export_preserves_issuers(self):
        import json
        row = self._get_csv_row(self.export_jersey)
        auth_list = json.loads(row['authentications_json'])
        issuers = {a['issuer'] for a in auth_list}
        self.assertIn('BECKETT', issuers)
        self.assertIn('TEAM', issuers)

    def test_import_round_trip_preserves_auth_count(self):
        imported = self._round_trip(self.export_jersey)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.authentications.count(), 2)

    def test_import_round_trip_preserves_auth_numbers(self):
        imported = self._round_trip(self.export_jersey)
        numbers = set(imported.authentications.values_list('number', flat=True))
        self.assertIn('TAG-EXPORT-007', numbers)
        self.assertIn('INV-EXPORT', numbers)

    def test_import_round_trip_preserves_issuers(self):
        imported = self._round_trip(self.export_jersey)
        issuers = set(imported.authentications.values_list('issuer_id', flat=True))
        self.assertIn('BECKETT', issuers)
        self.assertIn('TEAM', issuers)

    def test_import_round_trip_keeps_collectible_type_hockeyjersey(self):
        imported = self._round_trip(self.export_jersey)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.collectible_type, 'hockeyjersey')
        self.assertEqual(imported.gear_type_id, 'JRS')

    def test_import_jersey_with_no_auths_imports_cleanly(self):
        jersey_no_auth = HockeyJersey.objects.create(
            title='No Auth Export Jersey',
            description='No auth',
            collection=self.collection,
            league='NHL',
            player='Brendan Shanahan',
            brand='Koho',
            size='52',
            season='1998',
            game_type=self.game_type,
            usage_type=self.usage_type,
        )
        imported = self._round_trip(jersey_no_auth)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.authentications.count(), 0)

    def test_import_with_unknown_issuer_gracefully_sets_null(self):
        from memorabilia.export_import import _create_collectible
        import zipfile, io, json
        from memorabilia.export_import import build_collectible_zip
        zip_bytes = build_collectible_zip(self.export_jersey)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        target = Collection.objects.create(owner_uid=self.owner.id, title='Unknown Auth Target')
        row = {
            'collectible_type': 'hockeyjersey',
            'title': 'Unknown Auth Jersey',
            'description': '',
            'player': 'Unknown Player',
            'league': 'NHL',
            'brand': 'CCM',
            'size': '54',
            'season': '2000',
            'game_type': 'REG',
            'usage_type': 'GU',
            'authentications_json': json.dumps([
                {'auth_type': 'paper', 'number': 'TAG-X', 'issuer': 'NONEXISTENT_KEY'}
            ]),
            'images_json': '[]',
            'photomatches_json': '[]',
        }
        obj = _create_collectible(row, target, zf, is_collection_export=False)
        auth = obj.authentications.first()
        self.assertIsNotNone(auth)
        self.assertIsNone(auth.issuer)

    def test_search_form_has_auth_issuer_and_auth_number_fields(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertIn('auth_issuer', form.fields)
        self.assertIn('auth_number', form.fields)
