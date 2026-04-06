from django.urls import path, include
from . import views

app_name = "memorabilia"
urlpatterns = [
    path("", views.home, name="home"),
    path("search", views.search_collectibles, name="search_collectibles"),
    path('accounts/', include('allauth.urls')),
    path("collection/create", views.create_collection, name="create_collection"),
    path("collection/", views.IndexView.as_view(), name="list_collections"),
    path("collection/mine/", views.MyCollectionsView.as_view(), name="my_collections"),
    path("collection/<int:pk>/", views.CollectionView.as_view(), name="collection"),
    path("collection/<int:collection_id>/edit", views.edit_collection, name="edit_collection"),
    path("collection/<int:collection_id>/delete", views.delete_collection, name="delete_collection"),
    path("collection/<int:collection_id>/collectible/create", views.create_collectible, name="create_collectible"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:pk>", views.CollectibleView.as_view(), name="collectible"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:collectible_id>/edit", views.edit_collectible, name="edit_collectible"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:collectible_id>/delete", views.delete_collectible, name="delete_collectible"),
    path("collection/<int:collection_id>/bulk-edit", views.bulk_edit_collectibles, name="bulk_edit_collectibles"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:collectible_id>/photoMatch/create", views.create_photo_match, name="create_photo_match"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:collectible_id>/photoMatch/<int:pk>", views.PhotoMatchView.as_view(), name="photo_match"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:collectible_id>/photoMatch/<int:photo_match_id>/edit", views.edit_photo_match, name="edit_photo_match"),
    path("collection/<int:collection_id>/collectible/<str:collectible_type>/<int:collectible_id>/photoMatch/<int:photo_match_id>/delete", views.delete_photo_match, name="delete_photo_match"),
    path("external/flickr/album", views.get_flickr_album, name="get_flickr_album"),
    path("external/flickr/albums/<str:username>/<str:album>", views.get_flickr_albums, name="get_flickr_albums"),
    path("external/flickr/user-albums", views.get_flickr_user_albums, name="get_flickr_user_albums"),
    path("external/flickr/album-photo-ids", views.get_flickr_album_photo_ids, name="get_flickr_album_photo_ids"),
    path("collection/<int:collection_id>/bulk-add-flickr", views.bulk_add_from_flickr, name="bulk_add_from_flickr"),
    path("collection/<int:collection_id>/bulk-add-flickr/album", views.bulk_add_flickr_album, name="bulk_add_flickr_album"),
    path("collection/<int:collection_id>/bulk-add-flickr/batch", views.bulk_add_flickr_batch, name="bulk_add_flickr_batch"),
    path("profile/", views.profile, name="profile"),
    path("resources", views.ExternalResourceListView.as_view(), name="list_externalresources"),
    path("api/teams", views.get_teams, name="get_teams"),
]
