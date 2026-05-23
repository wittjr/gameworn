from django.contrib import admin
from django.utils.html import format_html
from .models import (
    GeneralItem, GeneralItemImage,
    PlayerItem, PlayerItemImage,
    PlayerGear, PlayerGearImage,
    HockeyJersey,
    Collection, PhotoMatch, WantedItem, ExternalResource,
    Team, League, GameType, GearType, UsageType, CoaType, AuthSource, HowObtainedOption, SeasonSet,
    PopulationReport, MeiGrayEntry,
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
admin.site.register(AuthSource)
admin.site.register(HowObtainedOption)


@admin.register(PopulationReport)
class PopulationReportAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'season', 'league', 'imported_at')
    fields = ('season', 'league', 'file')
    actions = ['import_entries_action']

    @admin.action(description='Import entries from file')
    def import_entries_action(self, request, queryset):
        from memorabilia.meigray import import_entries
        total_deleted = total_created = total_with = total_without = 0
        errors = []
        for report in queryset:
            try:
                (deleted, created, _, duplicates, with_dates, without_dates,
                 _) = import_entries(report)
                total_deleted += deleted
                total_created += created
                total_with += with_dates
                total_without += without_dates
                if duplicates:
                    self.message_user(
                        request,
                        f'{report}: duplicate tags kept last occurrence — {", ".join(duplicates)}',
                        level='warning',
                    )
            except Exception as e:
                errors.append(f'{report}: {e}')
        if errors:
            self.message_user(request, f'Errors: {"; ".join(errors)}', level='error')
        if total_created:
            self.message_user(
                request,
                f'Imported: {total_deleted} removed, {total_created} created. '
                f'Dates: {total_with} with, {total_without} without.',
            )


@admin.register(MeiGrayEntry)
class MeiGrayEntryAdmin(admin.ModelAdmin):
    list_display = ('tag_number', 'player', 'team', 'league', 'color', 'set_number', 'report')
    list_filter = ('league', 'report')
    search_fields = ('tag_number', 'player', 'team')
    readonly_fields = ('tag_number', 'league', 'player', 'team', 'jersey_number', 'color',
                       'set_number', 'size', 'notes', 'games_worn', 'report', 'imported_at')
