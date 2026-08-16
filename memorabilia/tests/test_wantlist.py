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

from .base import BaseTestCase, WantListBaseTestCase

class WantListProfileTests(WantListBaseTestCase):
    def test_first_visit_creates_profile_and_redirects_to_settings(self):
        new_user = User.objects.create_user(username='newuser', password='pass')
        self.client.force_login(new_user)
        response = self.client.get(reverse('memorabilia:want_list_manage'))
        self.assertRedirects(response, reverse('memorabilia:want_list_profile_edit'))
        self.assertTrue(WantListProfile.objects.filter(user=new_user).exists())

    def test_slug_collision_resolves(self):
        from memorabilia.models import _generate_want_list_slug
        conflict_user = User.objects.create_user(username='owner-wants', password='pass')
        slug = _generate_want_list_slug(conflict_user)
        self.assertFalse(WantListProfile.objects.filter(slug=slug).exists())

    def test_reserved_slug_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_profile_edit'),
            {'slug': 'manage', 'visibility': 'public'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'slug', 'That handle is reserved. Please choose another.')

    def test_profile_edit_saves(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_profile_edit'),
            {'slug': 'owner-wants', 'visibility': 'logged_in'},
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.visibility, 'logged_in')

class WantListCRUDTests(WantListBaseTestCase):
    def test_manage_page_shows_lists(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('memorabilia:want_list_manage'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Priority Wants')

    def test_create_list(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_create'),
            {'title': 'Long Shots'},
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertTrue(WantList.objects.filter(profile=self.profile, title='Long Shots').exists())

    def test_edit_list(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_edit', kwargs={'pk': self.want_list.pk}),
            {'title': 'Renamed List'},
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.want_list.refresh_from_db()
        self.assertEqual(self.want_list.title, 'Renamed List')

    def test_delete_list(self):
        extra = WantList.objects.create(profile=self.profile, title='Temp', order=1)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_delete', kwargs={'pk': extra.pk}),
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertFalse(WantList.objects.filter(pk=extra.pk).exists())

    def test_reorder_lists(self):
        import json
        second = WantList.objects.create(profile=self.profile, title='Second', order=1)
        self.client.force_login(self.owner)
        payload = json.dumps([
            {'id': self.want_list.pk, 'order': 1},
            {'id': second.pk, 'order': 0},
        ])
        response = self.client.post(
            reverse('memorabilia:want_list_reorder'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.want_list.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.want_list.order, 1)
        self.assertEqual(second.order, 0)

    def test_other_user_cannot_edit_list(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:want_list_edit', kwargs={'pk': self.want_list.pk}),
            {'title': 'Hacked'},
        )
        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_delete_list(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:want_list_delete', kwargs={'pk': self.want_list.pk}),
        )
        self.assertEqual(response.status_code, 404)

class WantListItemCRUDTests(WantListBaseTestCase):
    def test_create_item(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            self._item_post_data(player='Bobby Orr', team='Boston Bruins'),
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertTrue(WantListItem.objects.filter(want_list=self.want_list, player='Bobby Orr').exists())

    def test_edit_item(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(player='Updated Player')
        data['images-INITIAL_FORMS'] = '0'
        response = self.client.post(
            reverse('memorabilia:want_list_item_edit', kwargs={'pk': self.want_item.pk}),
            data,
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.want_item.refresh_from_db()
        self.assertEqual(self.want_item.player, 'Updated Player')

    def test_delete_item(self):
        extra = WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='Temp Player',
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_item_delete', kwargs={'pk': extra.pk}),
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertFalse(WantListItem.objects.filter(pk=extra.pk).exists())

    def test_image_limit_enforced(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(player='Test')
        data['images-TOTAL_FORMS'] = '4'
        data['images-INITIAL_FORMS'] = '0'
        data['images-MAX_NUM_FORMS'] = '3'
        for i in range(4):
            data[f'images-{i}-link'] = f'http://example.com/{i}.jpg'
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            data,
        )
        self.assertEqual(response.status_code, 200)

    def test_at_least_one_field_required(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(
            collectible_type='playeritem',
            player='', team='', notes='', league='',
            game_type='', usage_type='',
        )
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WantListItem.objects.filter(want_list=self.want_list, player='').exists())

    def test_item_valid_with_team_only(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(
            collectible_type='playeritem',
            player='', team='Boston Bruins', notes='', league='',
            game_type='', usage_type='',
        )
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            data,
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertTrue(WantListItem.objects.filter(want_list=self.want_list, team='Boston Bruins').exists())

    def test_other_user_cannot_edit_item(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:want_list_item_edit', kwargs={'pk': self.want_item.pk}),
            self._item_post_data(),
        )
        self.assertEqual(response.status_code, 404)

class WantListPermissionTests(WantListBaseTestCase):
    def test_public_page_visible_to_anonymous(self):
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_private_page_returns_404_for_anonymous(self):
        self.profile.visibility = 'private'
        self.profile.save()
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 404)
        self.profile.visibility = 'public'
        self.profile.save()

    def test_private_page_returns_404_for_other_user(self):
        self.profile.visibility = 'private'
        self.profile.save()
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 404)
        self.profile.visibility = 'public'
        self.profile.save()

    def test_private_page_visible_to_owner(self):
        self.profile.visibility = 'private'
        self.profile.save()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.profile.visibility = 'public'
        self.profile.save()

    def test_logged_in_page_redirects_anonymous(self):
        self.profile.visibility = 'logged_in'
        self.profile.save()
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.profile.visibility = 'public'
        self.profile.save()

    def test_manage_requires_login(self):
        response = self.client.get(reverse('memorabilia:want_list_manage'))
        self.assertEqual(response.status_code, 302)

    def test_anonymous_cannot_create_item(self):
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            self._item_post_data(),
        )
        self.assertEqual(response.status_code, 302)

class WantListConvertTests(WantListBaseTestCase):
    def test_convert_creates_collectible_and_deletes_item(self):
        item = WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='Bobby Hull',
            team='Chicago Blackhawks',
            league=self.league,
        )
        self.client.force_login(self.owner)
        post_data = self._player_item_post_data(
            player='Bobby Hull',
            title='Bobby Hull Player Item',
        )
        response = self.client.post(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': item.pk}),
            post_data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WantListItem.objects.filter(pk=item.pk).exists())
        self.assertTrue(PlayerItem.objects.filter(player='Bobby Hull', title='Bobby Hull Player Item').exists())

    def test_convert_get_shows_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': self.want_item.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_convert_invalid_form_does_not_delete_item(self):
        self.client.force_login(self.owner)
        post_data = self._hockey_jersey_post_data(player='', title='')
        response = self.client.post(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': self.want_item.pk}),
            post_data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(WantListItem.objects.filter(pk=self.want_item.pk).exists())

    def test_other_user_cannot_convert_item(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': self.want_item.pk})
        )
        self.assertEqual(response.status_code, 404)

class WantListPublicFilterTests(WantListBaseTestCase):
    def test_filter_by_type(self):
        WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='Filter Player',
        )
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug}),
            {'type': 'playeritem'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Filter Player')
        # Wayne Gretzky appears in the player dropdown options even when filtered out of results
        self.assertContains(response, 'Wayne Gretzky')

    def test_filter_by_player(self):
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug}),
            {'player': 'Wayne Gretzky'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wayne Gretzky')

    def test_filter_by_league(self):
        other_league = League.objects.create(key='AHL', name='American Hockey League')
        WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='AHL Player',
            league=other_league,
        )
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug}),
            {'league': 'AHL'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AHL Player')
        # Wayne Gretzky appears in the player dropdown options even when filtered out of results
        self.assertContains(response, 'Wayne Gretzky')

    def test_no_filter_shows_all_items(self):
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wayne Gretzky')


# ── Django 6.0 compatibility tests ───────────────────────────────────────────

class WantListShortcutTests(BaseTestCase):
    """The collectible form surfaces a link to the owner's want list (for the
    'for trade' shortcut) only when they actually have one."""

    def setUp(self):
        self.client.force_login(self.owner)

    def _create_get(self):
        return self.client.get(
            reverse('memorabilia:create_collectible', args=[self.collection.id])
        )

    def test_no_want_list_url_without_profile(self):
        response = self._create_get()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['want_list_url'])

    def test_no_want_list_url_with_empty_profile(self):
        WantListProfile.objects.create(user=self.owner, slug='owner-wants', visibility='public')
        response = self._create_get()
        self.assertIsNone(response.context['want_list_url'])

    def test_want_list_url_present_with_a_list(self):
        profile = WantListProfile.objects.create(user=self.owner, slug='owner-wants', visibility='public')
        WantList.objects.create(profile=profile, title='My Wants')
        response = self._create_get()
        self.assertEqual(
            response.context['want_list_url'],
            reverse('memorabilia:want_list_public', kwargs={'slug': 'owner-wants'}),
        )

class WantListSlugTests(WantListBaseTestCase):
    """WantList slugs are auto-generated from the title, unique per profile, and
    stable across later title edits."""

    def test_slug_generated_from_title(self):
        wl = WantList.objects.create(profile=self.profile, title='Favorite Players')
        self.assertEqual(wl.slug, 'favorite-players')

    def test_slug_unique_within_profile(self):
        a = WantList.objects.create(profile=self.profile, title='Goalie Masks')
        b = WantList.objects.create(profile=self.profile, title='Goalie Masks')
        self.assertEqual(a.slug, 'goalie-masks')
        self.assertEqual(b.slug, 'goalie-masks-1')

    def test_same_slug_allowed_across_profiles(self):
        other_profile = WantListProfile.objects.create(
            user=self.other_user, slug='other-wants', visibility='public')
        a = WantList.objects.create(profile=self.profile, title='Goalie Masks')
        b = WantList.objects.create(profile=other_profile, title='Goalie Masks')
        self.assertEqual(a.slug, b.slug)

    def test_slug_stable_after_title_edit(self):
        wl = WantList.objects.create(profile=self.profile, title='Favorite Players')
        wl.title = 'My Favorite Players'
        wl.save()
        wl.refresh_from_db()
        self.assertEqual(wl.slug, 'favorite-players')

class WantListSingleListViewTests(WantListBaseTestCase):
    """The /wants/<handle>/<list-slug>/ page shows just one list."""

    def setUp(self):
        self.second_list = WantList.objects.create(profile=self.profile, title='Backups', order=1)
        WantListItem.objects.create(
            want_list=self.second_list, collectible_type='generalitem', title='A backup item')

    def _single_url(self, list_slug):
        return reverse('memorabilia:want_list_public_single',
                       kwargs={'slug': self.profile.slug, 'list_slug': list_slug})

    def test_single_list_shows_only_that_list(self):
        response = self.client.get(self._single_url(self.want_list.slug))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['single_list'], self.want_list)
        titles = [wl.title for wl, _ in response.context['lists_with_items']]
        self.assertEqual(titles, ['Priority Wants'])
        self.assertNotContains(response, 'A backup item')

    def test_unknown_list_slug_404(self):
        response = self.client.get(self._single_url('does-not-exist'))
        self.assertEqual(response.status_code, 404)

    def test_single_list_respects_private_visibility(self):
        self.profile.visibility = 'private'
        self.profile.save()
        response = self.client.get(self._single_url(self.want_list.slug))
        self.assertNotEqual(response.status_code, 200)

class TradeWantListFormTests(BaseTestCase):
    """The collectible form's trade_want_list choice is limited to the editing
    user's own lists."""

    def test_queryset_limited_to_current_user_lists(self):
        from ..forms import CollectibleForm
        mine = WantList.objects.create(
            profile=WantListProfile.objects.create(user=self.owner, slug='owner-wants'),
            title='Mine')
        theirs = WantList.objects.create(
            profile=WantListProfile.objects.create(user=self.other_user, slug='other-wants'),
            title='Theirs')
        form = CollectibleForm(current_user=self.owner)
        qs = form.fields['trade_want_list'].queryset
        self.assertIn(mine, qs)
        self.assertNotIn(theirs, qs)
        self.assertEqual(form.fields['trade_want_list'].empty_label, 'Entire want list')
