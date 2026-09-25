from django.urls import path

from . import views


urlpatterns = [
    path(
        "annotate/",
        views.annotate,
        name="annotate"
    ),
    path(
    "signup/",
    views.signup,
    name="signup"
    ),

    path(
    "taxonomy-help/<int:item_id>/",
    views.taxonomy_help,
    name="taxonomy_help",
    ),
]