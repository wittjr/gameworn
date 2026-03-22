from django.contrib import admin
from .models import OtherItem, PlayerItem, PlayerGearItem, Collection, PhotoMatch, WantedItem, ExternalResource, Team, League, GameType, UsageType, LoaType, HowObtainedOption

# Register your models here.
admin.site.register(Collection)
admin.site.register(PlayerItem)
admin.site.register(PlayerGearItem)
admin.site.register(OtherItem)
admin.site.register(PhotoMatch)
admin.site.register(WantedItem)
admin.site.register(ExternalResource)
admin.site.register(Team)
admin.site.register(League)
admin.site.register(GameType)
admin.site.register(UsageType)
admin.site.register(LoaType)
admin.site.register(HowObtainedOption)