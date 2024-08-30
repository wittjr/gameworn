from django.db import models
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


# Create your models here.
class Collection(models.Model):
    owner_uid = models.IntegerField()
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title

    # @admin.display(
    #         boolean = True,
    #         ordering="pub_date",
    #         description="Published recently?"
    # )


class WantedItem(models.Model):
    title = models.CharField(max_length=100)
    league = models.CharField(max_length=5)
    player = models.CharField(max_length=100)
    season = models.CharField(max_length=10, blank=True, null=True)
    game_type = models.CharField(max_length=25)
    description = models.CharField(max_length=500)
    usage_type = models.CharField(max_length=5)

    def __str__(self):
        return self.title


class Collectible(models.Model):
    title = models.CharField(max_length=100)
    league = models.CharField(max_length=5)
    brand = models.CharField(max_length=25)
    size = models.CharField(max_length=5)
    player = models.CharField(max_length=100)
    season = models.CharField(max_length=10)
    game_type = models.CharField(max_length=5)
    description = models.CharField(max_length=500)
    usage_type = models.CharField(max_length=5)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    for_sale = models.BooleanField(blank=True, null=True)
    for_trade = models.BooleanField(blank=True, null=True)
    asking_price = models.FloatField(blank=True, null=True)
    looking_for = models.ForeignKey(WantedItem, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return self.title


class CollectibleImage(models.Model):
    image = models.ImageField(upload_to='images')
    collectible = models.ForeignKey(Collectible, on_delete=models.CASCADE, related_name='images')


class PhotoMatch(models.Model):
    image = models.ImageField(upload_to='images')
    game_date = models.DateField()
    collectible = models.ForeignKey(Collectible, on_delete=models.CASCADE)

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
