from django.contrib import admin
from .models import OtherItem, PlayerItem, Collection, PhotoMatch, WantedItem, ExternalResource, Team

# Register your models here.
admin.site.register(Collection)
admin.site.register(PlayerItem)
admin.site.register(OtherItem)
admin.site.register(PhotoMatch)
admin.site.register(WantedItem)
admin.site.register(ExternalResource)
admin.site.register(Team)