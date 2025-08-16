from django.utils.timezone import now
from django.db import models
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from rules.contrib.models import RulesModel
import rules

from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneModelField


# Create your models here.
@rules.predicate(bind=True)
def is_collection_owner(self, user, collection):
    if self.context.args:
        return user.id == collection.owner_uid
    return False


@rules.predicate(bind=True)
def is_collectible_owner(self, user, collectible):
    if self.context.args:
        # print(user.id)
        # print(collectible.collection.owner_uid)
        return user.id == collectible.collection.owner_uid
    return False


class Collection(RulesModel):
    owner_uid = models.IntegerField()
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='images', blank=True, null=True)
    image_link = models.CharField(max_length=255, blank=True, null=True)
    last_updated = models.DateTimeField(default=now, editable=False)

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
    league = models.CharField(max_length=5)
    brand = models.CharField(max_length=25)
    size = models.CharField(max_length=5)
    player = models.CharField(max_length=100)
    team = models.CharField(max_length=150, blank=True, null=True)
    number = models.IntegerField(blank=True, null=True)
    season = models.CharField(max_length=10)
    game_type = models.CharField(max_length=5)
    description = models.CharField(max_length=500)
    usage_type = models.CharField(max_length=5)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    for_sale = models.BooleanField(blank=True, null=True)
    for_trade = models.BooleanField(blank=True, null=True)
    asking_price = models.FloatField(blank=True, null=True)
    looking_for = models.ForeignKey(WantedItem, on_delete=models.CASCADE, blank=True, null=True)
    last_updated = models.DateTimeField(default=now, editable=False)


    class Meta:
        rules_permissions = {
            'create': rules.is_authenticated & is_collection_owner,
            'update': rules.is_authenticated & is_collectible_owner,
            'delete': rules.is_authenticated & is_collectible_owner
        }


    def get_primary_image(self):
        primary_image_filter = self.images.filter(primary=True)
        # print(primary_image_filter)
        if len(primary_image_filter) >= 1:
            # print(primary_image_filter[0])
            if primary_image_filter[0].image:
                return primary_image_filter[0].image
            elif primary_image_filter[0].link:
                return primary_image_filter[0].link
        else:
            images = self.images.all()
            if len(images) >= 1:
                primary_image = images[0].image
                return primary_image
        return None

    def __str__(self):
        return self.title


class CollectibleImage(RulesModel):
    collectible = models.ForeignKey(Collectible, on_delete=models.CASCADE, related_name='images')
    primary = models.BooleanField(blank=True, null=True)
    image = models.ImageField(upload_to='images', blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    flickrObject = models.TextField(blank=True, null=True)


class PhotoMatch(RulesModel):
    image = models.ImageField(upload_to='images', blank=True, null=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    description = models.CharField(max_length=500, blank=True, null=True)
    game_date = models.DateField()
    collectible = models.ForeignKey(Collectible, on_delete=models.CASCADE, related_name='photomatches')

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
