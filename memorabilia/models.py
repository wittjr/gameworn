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
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        rules_permissions = {
            'create': rules.is_authenticated,
            'update': rules.is_authenticated & is_collection_owner,
            'delete': rules.is_authenticated & is_collection_owner
        }

    def __str__(self):
        return self.title

    # @admin.display(
    #         boolean = True,
    #         ordering="pub_date",
    #         description="Published recently?"
    # )


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

class Collectible(RulesModel):
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=500)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    for_sale = models.BooleanField(blank=True, null=True)
    for_trade = models.BooleanField(blank=True, null=True)
    asking_price = models.FloatField(blank=True, null=True)
    looking_for = models.ForeignKey(WantedItem, on_delete=models.CASCADE, blank=True, null=True)
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

    def __str__(self):
        return self.title

class PlayerGearItem(BasePlayerItem):
    brand = models.CharField(max_length=25)
    size = models.CharField(max_length=5)
    season = models.CharField(max_length=10)
    game_type = models.ForeignKey('GameType', to_field='key', on_delete=models.PROTECT, db_column='game_type')
    usage_type = models.ForeignKey('UsageType', to_field='key', on_delete=models.PROTECT, db_column='usage_type')
    collectible_type = 'playergearitem'

    def __str__(self):
        return self.title

    def get_primary_image(self):
        images = list(self.gear_images.all())
        primary = next((img for img in images if img.primary), None)
        if primary:
            return primary.image if primary.image else primary.link
        return images[0].image if images else None

class OtherItem(Collectible):
    collectible_type = 'otheritem'
    ...
    
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

class PlayerGearItemImage(CollectibleImage):
    collectible = models.ForeignKey(PlayerGearItem, on_delete=models.CASCADE, related_name='gear_images')

class OtherItemImage(CollectibleImage):
    collectible = models.ForeignKey(OtherItem, on_delete=models.CASCADE, related_name='images')

class PhotoMatch(RulesModel):
    image = models.ImageField(upload_to='images', blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=500, blank=True, null=True)
    game_date = models.DateField()
    collectible = models.ForeignKey(PlayerGearItem, on_delete=models.CASCADE, related_name='photomatches')

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


class Team(models.Model):
    name = models.CharField(max_length=150)
    league = models.ForeignKey(League, to_field='key', on_delete=models.CASCADE)

    class Meta:
        unique_together = ("name", "league")

    def __str__(self):
        return f"{self.name} ({self.league_id})"
