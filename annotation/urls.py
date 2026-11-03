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
    path(
    "vlm-review/",
    views.vlm_review,
    name="vlm_review",
    ),

    path(
        "vlm-review/<int:extraction_id>/",
        views.vlm_review,
        name="vlm_review_specific",
    ),
    path(
        "admin-export/vlm-reviews/",
        views.export_vlm_reviews,
        name="export_vlm_reviews",
    ),

]