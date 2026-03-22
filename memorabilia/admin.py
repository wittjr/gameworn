from django.contrib import admin
from .models import GeneralItem, PlayerItem, PlayerGear, Collection, PhotoMatch, WantedItem, ExternalResource, Team, League, GameType, GearType, UsageType, CoaType, HowObtainedOption, SeasonSet, HockeyJersey

# Register your models here.
admin.site.register(Collection)
admin.site.register(PlayerItem)
admin.site.register(PlayerGear)
admin.site.register(HockeyJersey)
admin.site.register(GeneralItem)
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