from django.contrib import admin
from django.utils.html import format_html
from .models import (
    GeneralItem, GeneralItemImage,
    PlayerItem, PlayerItemImage,
    PlayerGear, PlayerGearImage,
    HockeyJersey,
    Collection, PhotoMatch, WantedItem, ExternalResource,
    Team, League, GameType, GearType, UsageType, CoaType, AuthSource, HowObtainedOption, SeasonSet,
    MeiGrayPopulationReport, MeiGrayTagEntry, MeiGrayScheduleEntry,
    MeiGrayScheduleGameEntry, MeiGrayScheduleSetEntry,
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

@admin.register(MeiGrayPopulationReport)
class MeiGrayPopulationReportAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'season', 'league', 'imported_at')
    fields = ('season', 'league', 'file')
    actions = ['import_entries_action']

    @admin.action(description='Import entries from file')
    def import_entries_action(self, request, queryset):
        from memorabilia.meigray import import_report
        totals = {'tags': 0, 'schedules': 0, 'games': 0, 'set_ranges': 0}
        errors = []
        for report in queryset:
            try:
                counts = import_report(report)
                for k in totals:
                    totals[k] += counts[k]
            except Exception as e:
                errors.append(f'{report}: {e}')
        if errors:
            self.message_user(request, f'Errors: {"; ".join(errors)}', level='error')
        if totals['tags']:
            self.message_user(
                request,
                f"Imported: {totals['tags']} tag(s), {totals['schedules']} schedule(s), "
                f"{totals['games']} game(s), {totals['set_ranges']} set-range(s).",
            )


@admin.register(MeiGrayTagEntry)
class MeiGrayTagEntryAdmin(admin.ModelAdmin):
    list_display = ('tag_number', 'player', 'team', 'league', 'color', 'set_number', 'report')
    list_filter = ('league', 'season', 'team', 'set_number', 'report')
    search_fields = ('tag_number', 'season', 'league', 'team', 'player',
                     'jersey_number', 'color', 'set_number', 'size', 'notes')
    readonly_fields = ('imported_at',)


class MeiGrayScheduleGameInline(admin.TabularInline):
    model = MeiGrayScheduleGameEntry
    extra = 0
    fields = ('game_type', 'game_date', 'opponent', 'home_game', 'jersey', 'comment')
    readonly_fields = fields
    can_delete = False
    show_change_link = False
    ordering = ('game_date',)

    def has_add_permission(self, request, obj=None):
        return False


class MeiGrayScheduleSetInline(admin.TabularInline):
    model = MeiGrayScheduleSetEntry
    extra = 0
    fields = ('set_label', 'game_count', 'dates')
    readonly_fields = fields
    can_delete = False
    show_change_link = False
    ordering = ('set_label',)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(MeiGrayScheduleEntry)
class MeiGrayScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ('team', 'season', 'league', 'game_count', 'set_range_count', 'report')
    list_filter = ('league', 'season', 'report')
    search_fields = ('team',)
    readonly_fields = ('id', 'team', 'season', 'league', 'report')
    inlines = [MeiGrayScheduleGameInline, MeiGrayScheduleSetInline]

    def get_queryset(self, request):
        from django.db.models import Count
        return super().get_queryset(request).annotate(
            _game_count=Count('games', distinct=True),
            _set_range_count=Count('set_ranges', distinct=True),
        )

    @admin.display(description='Games', ordering='_game_count')
    def game_count(self, obj):
        return obj._game_count

    @admin.display(description='Set ranges', ordering='_set_range_count')
    def set_range_count(self, obj):
        return obj._set_range_count