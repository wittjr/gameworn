from django.contrib import admin
from django.utils.html import format_html
from .models import (
    GeneralItem, GeneralItemImage,
    PlayerItem, PlayerItemImage,
    PlayerGear, PlayerGearImage,
    HockeyJersey,
    Collection, PhotoMatch, WantedItem, ExternalResource,
    Team, League, GameType, GearType, UsageType, CoaType, HowObtainedOption, SeasonSet,
)


class ImageInlineMixin:
    extra = 0
    readonly_fields = ('preview',)
    fields = ('preview', 'image', 'link', 'primary', 'flickrObject')

    def preview(self, obj):
        url = obj.link or (obj.image.url if obj.image else None)
        if url:
            return format_html('<img src="{}" style="max-height:80px;max-width:120px;object-fit:contain;">', url)
        return '—'
    preview.short_description = 'Preview'


class PlayerItemImageInline(ImageInlineMixin, admin.TabularInline):
    model = PlayerItemImage


class PlayerGearImageInline(ImageInlineMixin, admin.TabularInline):
    model = PlayerGearImage


class GeneralItemImageInline(ImageInlineMixin, admin.TabularInline):
    model = GeneralItemImage


@admin.register(PlayerItem)
class PlayerItemAdmin(admin.ModelAdmin):
    inlines = [PlayerItemImageInline]


@admin.register(PlayerGear)
class PlayerGearAdmin(admin.ModelAdmin):
    inlines = [PlayerGearImageInline]


@admin.register(HockeyJersey)
class HockeyJerseyAdmin(admin.ModelAdmin):
    inlines = [PlayerGearImageInline]


@admin.register(GeneralItem)
class GeneralItemAdmin(admin.ModelAdmin):
    inlines = [GeneralItemImageInline]


admin.site.register(Collection)
admin.site.register(SeasonSet)
admin.site.register(PhotoMatch)
admin.site.register(WantedItem)
admin.site.register(ExternalResource)
admin.site.register(Team)
admin.site.register(League)
admin.site.register(GameType)
admin.site.register(GearType)
admin.site.register(UsageType)
admin.site.register(CoaType)
admin.site.register(HowObtainedOption)
