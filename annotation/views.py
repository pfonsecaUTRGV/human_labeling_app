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
    Image,
    ImageAssignment,
    Annotation,
    AnnotationSelection,
    TaxonomyItem,
)
from annotation.services.s3_storage import (
    get_presigned_image_url,
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
                    completed_count=Count(
                        "assignments",
                        filter=Q(
                            assignments__status="completed"
                        ),
                    )
                )
                .filter(
                    completed_count__lt=F(
                        "target_annotations"
                    )
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

                # Save taxonomy selections
                for field_info in (
                    form.taxonomy_fields
                ):

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

                    # ModelChoiceField:
                    # one TaxonomyItem
                    if isinstance(
                        selected,
                        TaxonomyItem
                    ):

                        AnnotationSelection.objects.create(
                            annotation=annotation,
                            taxonomy_item=selected,
                        )

                    # ModelMultipleChoiceField:
                    # queryset of TaxonomyItems
                    else:

                        for item in selected:

                            AnnotationSelection.objects.create(
                                annotation=annotation,
                                taxonomy_item=item,
                            )

                # Complete assignment
                assignment.status = "completed"
                assignment.completed_at = timezone.now()

                assignment.save(
                    update_fields=[
                        "status",
                        "completed_at",
                    ]
                )

            # Reload /annotate/ and receive next image
            return redirect(
                "annotate"
            )

    else:

        form = AnnotationForm()

    # -----------------------------------------
    # S3 temporary URL
    # -----------------------------------------

    image_url = (
        get_presigned_image_url(
            image
        )
    )

    return render(
        request,
        "annotation/annotate.html",
        {
            "image": image,
            "image_url": image_url,
            "form": form,
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

    if item.example_image:
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
