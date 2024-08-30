from django.urls import path
from . import views

app_name = "memorabilia"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("create", views.create_collection, name="create_collection"),
    path("collection/<int:pk>/", views.CollectionView.as_view(), name="collection"),
    path("collection/<int:collection_id>/edit", views.edit_collection, name="edit_collection"),
    path("collection/<int:collection_id>/delete", views.delete_collection, name="delete_collection"),
    path("collection/<int:collection_id>/collectible/create", views.create_collectible, name="create_collectible"),
    path("collection/<int:collection_id>/collectible/<int:pk>", views.CollectibleView.as_view(), name="collectible"),
    path("collection/<int:collection_id>/collectible/<int:collectible_id>/edit", views.edit_collectible, name="edit_collectible"),
    path("collection/<int:collection_id>/collectible/<int:collectible_id>/delete", views.delete_collectible, name="delete_collectible"),
    path("collection/<int:collection_id>/collectible/<int:collectible_id>/photoMatch/create", views.create_photo_match, name="create_photo_match"),
    path("collection/<int:collection_id>/collectible/<int:collectible_id>/photoMatch/<int:pk>", views.PhotoMatchView.as_view(), name="photo_match"),
    path("collection/<int:collection_id>/collectible/<int:collectible_id>/photoMatch/<int:photo_match_id>/edit", views.edit_photo_match, name="edit_photo_match"),
    path("collection/<int:collection_id>/collectible/<int:collectible_id>/photoMatch/<int:photo_match_id>/delete", views.delete_photo_match, name="delete_photo_match"),
]