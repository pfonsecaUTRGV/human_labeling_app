from django.urls import path

from . import views


urlpatterns = [

    path(
        "",
        views.home,
        name="home"
    ),

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
        name="taxonomy_help"
    ),
    path(
    "admin-export/",
    views.admin_export,
    name="admin_export"
    ),

    path(
        "admin-export/download/",
        views.download_annotations_csv,
        name="download_annotations_csv"
    ),

]