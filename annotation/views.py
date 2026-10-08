from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, F
from django.shortcuts import render
from django.utils import timezone

from django.contrib.auth import login
from django.shortcuts import redirect

from annotation.forms import SimpleSignupForm

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from annotation.models import Image, ImageAssignment, Annotation
from annotation.services.s3_storage import get_presigned_image_url

from annotation.forms import AnnotationForm
from annotation.models import (
    AnnotationSelection,
    TaxonomyItem,
)
from annotation.services.s3_storage import (
    get_presigned_image_url,
)

import csv

from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse

def superuser_check(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(superuser_check)
def admin_export(request):

    completed_count = (
        Annotation.objects
        .filter(completed=True)
        .count()
    )

    return render(
        request,
        "annotation/admin_export.html",
        {
            "completed_count": completed_count,
        },
    )


@user_passes_test(superuser_check)
def download_annotations_csv(request):

    response = HttpResponse(
        content_type="text/csv"
    )

    response[
        "Content-Disposition"
    ] = (
        'attachment; '
        'filename="human_annotations.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        "annotation_id",
        "audit_id",
        "image_id",
        "filename",
        "annotator",
        "worker_count",
        "ppe_compliance",
        "equipment",
        "materials_components",
        "hazards",
        "activities",
        "quality_observations",
        "stage",
        "notes",
        "taxonomy_version",
        "completed_at",
    ])

    category_map = {
        "Equipment":
            "equipment",

        "Materials / Components":
            "materials_components",

        "Hazards":
            "hazards",

        "Activities":
            "activities",

        "Quality Observations":
            "quality_observations",

        "Stage":
            "stage",
    }

    annotations = (
        Annotation.objects
        .filter(completed=True)
        .select_related(
            "image",
            "annotator",
        )
        .prefetch_related(
            "selections__taxonomy_item__category"
        )
        .order_by("id")
    )

    for annotation in annotations:

        selections = {
            "equipment": [],
            "materials_components": [],
            "hazards": [],
            "activities": [],
            "quality_observations": [],
            "stage": [],
        }

        for selection in annotation.selections.all():

            item = selection.taxonomy_item

            category_name = (
                item.category.name
            )

            column_name = (
                category_map.get(
                    category_name
                )
            )

            if not column_name:
                continue

            selections[
                column_name
            ].append(
                item.canonical_name
            )

        writer.writerow([
            annotation.id,
            annotation.image.audit_id,
            annotation.image.image_id,
            annotation.image.filename,
            annotation.annotator.username,
            annotation.worker_count,
            annotation.ppe_compliance,

            " | ".join(
                selections["equipment"]
            ),

            " | ".join(
                selections[
                    "materials_components"
                ]
            ),

            " | ".join(
                selections["hazards"]
            ),

            " | ".join(
                selections["activities"]
            ),

            " | ".join(
                selections[
                    "quality_observations"
                ]
            ),

            " | ".join(
                selections["stage"]
            ),

            annotation.notes,
            annotation.taxonomy_version,

            (
                annotation.completed_at.isoformat()
                if annotation.completed_at
                else ""
            ),
        ])

    return response

def home(request):

    if request.user.is_authenticated:
        return redirect("annotate")

    return render(
        request,
        "annotation/home.html",
    )


def signup(request):

    if request.user.is_authenticated:
        return redirect(
            "annotate"
        )

    if request.method == "POST":

        form = SimpleSignupForm(
            request.POST
        )

        if form.is_valid():

            user = form.save()

            login(
                request,
                user
            )

            return redirect(
                "annotate"
            )

    else:

        form = SimpleSignupForm()

    return render(
        request,
        "registration/signup.html",
        {
            "form": form
        }
    )


@login_required
def annotate(request):

    user = request.user

    # -----------------------------------------
    # Find current assignment
    # -----------------------------------------

    assignment = (
        ImageAssignment.objects
        .filter(
            annotator=user,
            status="assigned",
        )
        .select_related("image")
        .first()
    )

    # -----------------------------------------
    # If no assignment exists, create one
    # -----------------------------------------

    if assignment is None:

        with transaction.atomic():

            annotated_image_ids = (
                Annotation.objects
                .filter(
                    annotator=user,
                    completed=True,
                )
                .values_list(
                    "image_id",
                    flat=True,
                )
            )

            assigned_image_ids = (
                ImageAssignment.objects
                .filter(
                    annotator=user,
                )
                .values_list(
                    "image_id",
                    flat=True,
                )
            )

            candidates = (
                Image.objects
                .select_for_update(
                    skip_locked=True
                )
                .filter(
                    active=True
                )
                .exclude(
                    id__in=annotated_image_ids
                )
                .exclude(
                    id__in=assigned_image_ids
                )
                .annotate(
                    occupied_count=Count(
                        "assignments",
                        filter=Q(
                            assignments__status__in=[
                                "assigned",
                                "completed",
                            ]
                        ),
                    )
                )
                .filter(
                    occupied_count=0
                )
                .order_by("id")
            )

            image = candidates.first()

            if image:

                assignment = (
                    ImageAssignment.objects.create(
                        image=image,
                        annotator=user,
                        status="assigned",
                    )
                )

    # -----------------------------------------
    # No more images
    # -----------------------------------------

    if assignment is None:

        return render(
            request,
            "annotation/no_images.html",
        )

    image = assignment.image

    # -----------------------------------------
    # S3 temporary URL
    # -----------------------------------------

    image_url = get_presigned_image_url(
        image
    )

    # -----------------------------------------
    # Handle submitted annotation
    # -----------------------------------------

    if request.method == "POST":

        form = AnnotationForm(
            request.POST
        )

        if form.is_valid():

            with transaction.atomic():

                annotation = (
                    Annotation.objects.create(
                        image=image,
                        annotator=user,
                        worker_count=(
                            form.cleaned_data[
                                "worker_count"
                            ]
                        ),
                        ppe_compliance=(
                            form.cleaned_data[
                                "ppe_compliance"
                            ]
                        ),
                        notes=(
                            form.cleaned_data[
                                "notes"
                            ]
                        ),
                        taxonomy_version="1.0",
                        completed=True,
                        completed_at=timezone.now(),
                    )
                )

                # ---------------------------------
                # Save taxonomy selections
                # ---------------------------------

                for field_info in form.taxonomy_fields:

                    field_name = (
                        field_info["name"]
                    )

                    selected = (
                        form.cleaned_data.get(
                            field_name
                        )
                    )

                    if selected is None:
                        continue

                    # Single TaxonomyItem
                    if isinstance(
                        selected,
                        TaxonomyItem
                    ):

                        AnnotationSelection.objects.create(
                            annotation=annotation,
                            taxonomy_item=selected,
                        )

                    # Multiple TaxonomyItems
                    else:

                        for item in selected:

                            AnnotationSelection.objects.create(
                                annotation=annotation,
                                taxonomy_item=item,
                            )

                # ---------------------------------
                # Complete assignment
                # ---------------------------------

                assignment.status = "completed"

                assignment.completed_at = (
                    timezone.now()
                )

                assignment.save(
                    update_fields=[
                        "status",
                        "completed_at",
                    ]
                )

            return redirect(
                "annotate"
            )

    else:

        form = AnnotationForm()

    # -----------------------------------------
    # Completed annotations by current user
    # -----------------------------------------

    completed_count = (
        Annotation.objects
        .filter(
            annotator=user,
            completed=True,
        )
        .count()
    )

    # -----------------------------------------
    # Render page
    # -----------------------------------------

    return render(
        request,
        "annotation/annotate.html",
        {
            "image": image,
            "image_url": image_url,
            "form": form,
            "completed_count": completed_count,
        },
    )




@login_required
def taxonomy_help(request, item_id):

    item = get_object_or_404(
        TaxonomyItem,
        id=item_id,
        active=True,
    )

    example_image_url = None

    if item.example_image_url:

        example_image_url = (
            item.example_image_url
        )

    elif item.example_image:

        try:

            example_image_url = (
                item.example_image.url
            )

        except Exception:

            example_image_url = None


    return JsonResponse({
        "name": item.canonical_name,
        "description": item.description,
        "example_image": example_image_url,
    })



