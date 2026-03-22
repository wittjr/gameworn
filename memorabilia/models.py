from django.db import models
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from rules.contrib.models import RulesModel
import rules

from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneModelField


# Create your models here.
@rules.predicate
def is_collection_owner(user, collection):
    if collection is None:
        return False
    return user.id == collection.owner_uid


@rules.predicate
def is_collectible_owner(user, collectible):
    if collectible is None:
        return False
    return user.id == collectible.collection.owner_uid


class Collection(RulesModel):
    owner_uid = models.IntegerField()
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='images', blank=True, null=True)
    image_link = models.CharField(max_length=255, blank=True, null=True)
    collage_collectible_ids = models.JSONField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner_uid'], name='mem_collection_owner_idx'),
        ]
        rules_permissions = {
            'create': rules.is_authenticated,
            'update': rules.is_authenticated & is_collection_owner,
            'delete': rules.is_authenticated & is_collection_owner
        }

    def __str__(self):
        return self.title

    def get_header_image_url(self):
        """Return the collection's own header image URL, or None if not set."""
        if self.image and self.image.name:
            return self.image.url
        if self.image_link:
            return self.image_link
        return None

    def get_collage_images(self, max_count=9):
        """Return up to max_count primary image objects for the collage.

        If collage_collectible_ids is set, use those specific collectibles (in order).
        Otherwise fall back to the first max_count collectibles that have a primary image.
        """
        if self.collage_collectible_ids:
            return self._get_collage_images_by_ids(self.collage_collectible_ids)

        from itertools import chain
        images = []
        for collectible in chain(
            self.playergear_set.prefetch_related('gear_images').all(),
            self.hockeyjersey_set.prefetch_related('gear_images').all(),
            self.playeritem_set.prefetch_related('images').all(),
            self.generalitem_set.prefetch_related('images').all(),
        ):
            img = collectible.get_primary_image()
            if img:
                images.append(img)
            if len(images) >= max_count:
                break
        return images

    def _get_collage_images_by_ids(self, id_list):
        # Ownership is enforced implicitly: <type>_set managers are FK-scoped to this
        # collection — never replace these with global lookups (e.g. PlayerItem.objects.get).
        from collections import defaultdict

        by_type = defaultdict(list)
        for entry in id_list:
            ctype = entry.get('type')
            cid = entry.get('id')
            if ctype in ('playergear', 'playeritem', 'generalitem', 'hockeyjersey') and isinstance(cid, int):
                by_type[ctype].append(cid)

        # Fetch each type in two queries (SELECT + prefetch) rather than one per item.
        fetched = {}  # (type, pk) -> collectible
        if by_type['playergear']:
            for c in self.playergear_set.filter(pk__in=by_type['playergear']).prefetch_related('gear_images'):
                fetched[('playergear', c.pk)] = c
        if by_type['hockeyjersey']:
            for c in self.hockeyjersey_set.filter(pk__in=by_type['hockeyjersey']).prefetch_related('gear_images'):
                fetched[('hockeyjersey', c.pk)] = c
        if by_type['playeritem']:
            for c in self.playeritem_set.filter(pk__in=by_type['playeritem']).prefetch_related('images'):
                fetched[('playeritem', c.pk)] = c
        if by_type['generalitem']:
            for c in self.generalitem_set.filter(pk__in=by_type['generalitem']).prefetch_related('images'):
                fetched[('generalitem', c.pk)] = c

        # Reconstruct in the original requested order; missing IDs are silently skipped.
        images = []
        for entry in id_list:
            collectible = fetched.get((entry.get('type'), entry.get('id')))
            if collectible is None:
                continue
            img = collectible.get_primary_image()
            if img:
                images.append(img)
        return images


class ExternalResource(RulesModel):
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.title


class WantedItem(RulesModel):
    title = models.CharField(max_length=100)
    league = models.CharField(max_length=5)
    player = models.CharField(max_length=100)
    season = models.CharField(max_length=10, blank=True, null=True)
    game_type = models.CharField(max_length=25)
    description = models.CharField(max_length=500)
    usage_type = models.CharField(max_length=5)

    def __str__(self):
        return self.title

class CoaType(models.Model):
    key = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class HowObtainedOption(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Collectible(RulesModel):
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    for_sale = models.BooleanField(blank=True, null=True)
    for_trade = models.BooleanField(blank=True, null=True)
    asking_price = models.FloatField(blank=True, null=True)
    looking_for = models.ForeignKey(WantedItem, on_delete=models.CASCADE, blank=True, null=True)
    how_obtained = models.CharField(max_length=255, blank=True, null=True)
    coa = models.ForeignKey('CoaType', to_field='key', on_delete=models.PROTECT, db_column='coa', blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        rules_permissions = {
            'create': rules.is_authenticated & is_collection_owner,
            'update': rules.is_authenticated & is_collectible_owner,
            'delete': rules.is_authenticated & is_collectible_owner
        }

    def get_primary_image(self):
        images = list(self.images.all())
        primary = next((img for img in images if img.primary), None)
        if primary:
            return primary.image if primary.image else primary.link
        return images[0].image if images else None

    def get_primary_image_url(self):
        img = self.get_primary_image()
        if img is None:
            return None
        if hasattr(img, 'url'):
            try:
                return img.url
            except ValueError:
                return None
        return str(img)

class BasePlayerItem(Collectible):
    league = models.CharField(max_length=5, blank=True, null=True)
    player = models.CharField(max_length=100)
    team = models.CharField(max_length=150, blank=True, null=True)
    number = models.IntegerField(blank=True, null=True)

    class Meta(Collectible.Meta):
        abstract = True


class PlayerItem(BasePlayerItem):
    collectible_type = 'playeritem'

    class Meta(BasePlayerItem.Meta):
        indexes = [
            models.Index(fields=['last_updated'], name='mem_playeritem_updated_idx'),
        ]

    def __str__(self):
        return self.title

class PlayerGearItem(BasePlayerItem):
    brand = models.CharField(max_length=25)
    size = models.CharField(max_length=5)
    season = models.CharField(max_length=10)
    game_type = models.ForeignKey('GameType', to_field='key', on_delete=models.PROTECT, db_column='game_type')
    usage_type = models.ForeignKey('UsageType', to_field='key', on_delete=models.PROTECT, db_column='usage_type')
    gear_type = models.ForeignKey('GearType', to_field='key', on_delete=models.PROTECT, db_column='gear_type', blank=True, null=True)

    class Meta(BasePlayerItem.Meta):
        abstract = True


class PlayerGear(PlayerGearItem):
    collectible_type = 'playergear'

    class Meta(PlayerGearItem.Meta):
        indexes = [
            models.Index(fields=['last_updated'], name='mem_playergear_updated_idx'),
        ]

    def __str__(self):
        return self.title

    def get_primary_image(self):
        images = list(self.gear_images.all())
        primary = next((img for img in images if img.primary), None)
        if primary:
            return primary.image if primary.image else primary.link
        return images[0].image if images else None


class HockeyJersey(PlayerGearItem):
    season_set = models.ForeignKey('SeasonSet', to_field='key', on_delete=models.PROTECT, db_column='season_set', blank=True, null=True)
    collectible_type = 'hockeyjersey'

    class Meta(PlayerGearItem.Meta):
        indexes = [
            models.Index(fields=['last_updated'], name='mem_hockeyjersey_updated_idx'),
        ]

    def save(self, *args, **kwargs):
        self.gear_type_id = 'JRS'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    def get_primary_image(self):
        images = list(self.gear_images.all())
        primary = next((img for img in images if img.primary), None)
        if primary:
            return primary.image if primary.image else primary.link
        return images[0].image if images else None

class GeneralItem(Collectible):
    collectible_type = 'generalitem'

    class Meta(Collectible.Meta):
        indexes = [
            models.Index(fields=['last_updated'], name='mem_generalitem_updated_idx'),
        ]

    def __str__(self):
        return self.title


class CollectibleImage(RulesModel):
    primary = models.BooleanField(blank=True, null=True)
    image = models.ImageField(upload_to='images', blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    flickrObject = models.JSONField(blank=True, null=True)

    class Meta:
        abstract = True

class PlayerItemImage(CollectibleImage):
    collectible = models.ForeignKey(PlayerItem, on_delete=models.CASCADE, related_name='images')

class PlayerGearImage(CollectibleImage):
    collectible = models.ForeignKey(PlayerGear, on_delete=models.CASCADE, related_name='gear_images')

class HockeyJerseyImage(CollectibleImage):
    collectible = models.ForeignKey(HockeyJersey, on_delete=models.CASCADE, related_name='gear_images')

class GeneralItemImage(CollectibleImage):
    collectible = models.ForeignKey(GeneralItem, on_delete=models.CASCADE, related_name='images')

class PhotoMatch(RulesModel):
    image = models.ImageField(upload_to='images', blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=500, blank=True, null=True)
    game_date = models.DateField()
    collectible = models.ForeignKey(PlayerGear, on_delete=models.CASCADE, related_name='photomatches')

    class Meta:
        rules_permissions = {
            'create': rules.is_authenticated & is_collectible_owner,
            'update': rules.is_authenticated & is_collectible_owner,
            'delete': rules.is_authenticated & is_collectible_owner
        }

    def __str__(self):
        return '%s %s' % (self.collectible.title, self.game_date)


class League(models.Model):
    key = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class UsageType(models.Model):
    key = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class GameType(models.Model):
    key = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class GearType(models.Model):
    key = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class SeasonSet(models.Model):
    key = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=150)
    league = models.ForeignKey(League, to_field='key', on_delete=models.CASCADE)

    class Meta:
        unique_together = ("name", "league")

    def __str__(self):
        return f"{self.name} ({self.league_id})"
