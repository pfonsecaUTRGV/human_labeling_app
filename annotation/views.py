from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, F
from django.shortcuts import render
from django.utils import timezone
import random
import hashlib

import tempfile
import zipfile
from pathlib import Path

from django.core.management import call_command
from django.http import FileResponse, HttpResponseForbidden


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



from django.utils import timezone

from .models import (
    VLMExtraction,
    VLMHumanReview,
    VLMClaimJudgment,
    VLMMissingClaim,
    TaxonomyItem,
)



def superuser_check(user):
    return user.is_authenticated and user.is_superuser

@user_passes_test(superuser_check)
def admin_export(request):

    completed_count = (
        Annotation.objects
        .filter(completed=True)
        .count()
    )
    completed_vlm_reviews = (
        VLMHumanReview.objects
        .filter(completed=True)
        .count()
    )

    return render(
        request,
        "annotation/admin_export.html",
        {
            "completed_count":
                completed_count,

            "completed_vlm_reviews":
                completed_vlm_reviews,
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

            # Images already completed by this user
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

            # Images this user has ever been assigned
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

            # ---------------------------------
            # STEP 1:
            # Find eligible image IDs.
            #
            # IMPORTANT:
            # Do NOT use select_for_update()
            # on this query because Count()
            # produces GROUP BY in PostgreSQL.
            # ---------------------------------

            candidate_ids = (
                Image.objects
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
                .values_list(
                    "id",
                    flat=True,
                )
            )

            # ---------------------------------
            # STEP 2:
            # Lock one actual Image row.
            #
            # This query has no GROUP BY,
            # so PostgreSQL allows FOR UPDATE.
            # skip_locked=True prevents two
            # annotators from receiving the
            # same image concurrently.
            # ---------------------------------

            candidate_id_list = list(candidate_ids)

            image = None

            if candidate_id_list:
                random.shuffle(candidate_id_list)

                for candidate_id in candidate_id_list:
                    image = (
                        Image.objects
                        .select_for_update(
                            skip_locked=True
                        )
                        .filter(
                            id=candidate_id
                        )
                        .first()
                    )

                    if image:
                        break

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

            # ---------------------------------
            # Redirect to next image
            # ---------------------------------

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


def get_image_url(image):
    """
    Try common image/file field names without depending on
    one specific Image model implementation.
    """

    possible_fields = [
        "image",
        "file",
        "image_file",
        "photo",
        "uploaded_file",
    ]

    for field_name in possible_fields:

        value = getattr(
            image,
            field_name,
            None,
        )

        if value:

            try:
                return value.url
            except Exception:
                pass

    # If your Image model already stores a URL/path string
    for field_name in [
        "url",
        "image_url",
        "absolute_path",
        "relative_path",
    ]:

        value = getattr(
            image,
            field_name,
            None,
        )

        if value:
            return str(value)

    return ""


@login_required
def vlm_review(request, extraction_id=None):

    # ============================================================
    # SELECT REVIEW
    # ============================================================

    if extraction_id:

        extraction = get_object_or_404(
            VLMExtraction.objects.select_related("image"),
            id=extraction_id,
        )

    else:

        # Exclude all VLM analyses this reviewer has already completed.
        completed_reviews = (
            VLMHumanReview.objects
            .filter(
                reviewer=request.user,
                completed=True,
            )
            .select_related(
                "extraction",
                "extraction__image",
            )
        )

        completed_ids = {
            review.extraction_id
            for review in completed_reviews
        }

        available = list(
            VLMExtraction.objects
            .select_related("image")
            .exclude(
                id__in=completed_ids
            )
        )


        def review_sort_key(extraction):
            """
            Stable blinded pseudo-random ordering per reviewer.
            """

            seed = (
                f"{request.user.id}:"
                f"{extraction.id}:"
                "mcif-vlm-review-v1"
            )

            return hashlib.sha256(
                seed.encode("utf-8")
            ).hexdigest()


        available.sort(
            key=review_sort_key
        )


        # ------------------------------------------------------------
        # Avoid showing the same image twice consecutively
        # ------------------------------------------------------------

        last_review = (
            completed_reviews
            .order_by("-completed_at")
            .first()
        )

        last_image_id = None

        if last_review:

            last_image_id = (
                last_review
                .extraction
                .image_id
            )


        extraction = None

        for candidate in available:

            if (
                last_image_id is None
                or candidate.image_id != last_image_id
            ):

                extraction = candidate
                break


        # Fallback:
        # if only the paired extraction remains, allow it.
        if extraction is None and available:

            extraction = available[0]


        if extraction is None:

            return render(
                request,
                "annotation/vlm_review_complete.html",
            )

    review, _ = (
        VLMHumanReview.objects
        .get_or_create(
            extraction=extraction,
            reviewer=request.user,
        )
    )

    claims = (
        extraction.claims
        .all()
        .order_by(
            "field",
            "claim_order",
            "id",
        )
    )

    # ============================================================
    # POST REVIEW
    # ============================================================

    if request.method == "POST":

        with transaction.atomic():

            # ----------------------------------------
            # Save each individual GPT claim judgment
            # ----------------------------------------

            for claim in claims:

                verdict = request.POST.get(
                    f"claim_{claim.id}"
                )

                if verdict not in {
                    "supported",
                    "partially_supported",
                    "unsupported",
                    "cannot_determine",
                }:
                    continue

                notes = request.POST.get(
                    f"notes_{claim.id}",
                    "",
                ).strip()

                VLMClaimJudgment.objects.update_or_create(
                    review=review,
                    claim=claim,
                    defaults={
                        "verdict": verdict,
                        "notes": notes,
                    },
                )

            # ----------------------------------------
            # Missing visible claims
            # ----------------------------------------

            missing_answer = request.POST.get(
                "has_missing_claim"
            )

            # Prevent duplicate rows if the review is resubmitted.
            review.missing_claims.all().delete()


            if missing_answer == "yes":

                missing_fields = request.POST.getlist(
                    "missing_field[]"
                )

                taxonomy_item_ids = request.POST.getlist(
                    "missing_taxonomy_item[]"
                )

                missing_texts = request.POST.getlist(
                    "missing_text[]"
                )

                missing_notes_list = request.POST.getlist(
                    "missing_notes[]"
                )


                max_items = max(
                    len(missing_fields),
                    len(taxonomy_item_ids),
                    len(missing_texts),
                    len(missing_notes_list),
                    0,
                )


                for i in range(max_items):

                    missing_field = (
                        missing_fields[i].strip()
                        if i < len(missing_fields)
                        else ""
                    )

                    taxonomy_item_id = (
                        taxonomy_item_ids[i].strip()
                        if i < len(taxonomy_item_ids)
                        else ""
                    )

                    missing_text = (
                        missing_texts[i].strip()
                        if i < len(missing_texts)
                        else ""
                    )

                    missing_notes = (
                        missing_notes_list[i].strip()
                        if i < len(missing_notes_list)
                        else ""
                    )


                    taxonomy_item = None

                    if taxonomy_item_id:

                        taxonomy_item = (
                            TaxonomyItem.objects
                            .filter(
                                id=taxonomy_item_id
                            )
                            .first()
                        )


                    if (
                        missing_field
                        and (
                            taxonomy_item
                            or missing_text
                        )
                    ):

                        VLMMissingClaim.objects.create(
                            review=review,
                            field=missing_field,
                            taxonomy_item=taxonomy_item,
                            free_text=missing_text,
                            notes=missing_notes,
                        )

            # ----------------------------------------
            # Overall notes
            # ----------------------------------------

            review.overall_notes = (
                request.POST.get(
                    "overall_notes",
                    "",
                ).strip()
            )

            # Only mark complete when every GPT claim
            # received a judgment.
            total_claims = claims.count()

            judged_claims = (
                review.claim_judgments
                .filter(
                    claim__in=claims
                )
                .count()
            )

            if judged_claims == total_claims:

                review.completed = True
                review.completed_at = timezone.now()

            review.save()

        if review.completed:

            return redirect(
                "vlm_review"
            )

    # ============================================================
    # EXISTING JUDGMENTS
    # ============================================================

    judgments = {
        judgment.claim_id: judgment
        for judgment
        in review.claim_judgments.all()
    }

    claim_rows = []

    for claim in claims:

        claim_rows.append({
            "claim": claim,
            "judgment": judgments.get(
                claim.id
            ),
        })

    # ============================================================
    # PROGRESS
    # ============================================================

    total_extractions = (
        VLMExtraction.objects.count()
    )

    completed_reviews = (
        VLMHumanReview.objects
        .filter(
            reviewer=request.user,
            completed=True,
        )
        .count()
    )

    taxonomy_items = (
        TaxonomyItem.objects
        .filter(active=True)
        .order_by(
            "category",
            "canonical_name",
        )
    )

    taxonomy_by_category = {}

    for item in taxonomy_items:

        category = str(
            item.category
        ).strip()

        taxonomy_by_category.setdefault(
            category,
            []
        )

        taxonomy_by_category[category].append({
            "id": item.id,
            "name": item.canonical_name,
        })
    context = {
        "extraction": extraction,
        "review": review,
        "claim_rows": claim_rows,
        "taxonomy_by_category": taxonomy_by_category,
        # Do NOT expose extraction.model_version.
        "image_url": get_presigned_image_url(
            extraction.image
        ),

        "total_extractions": total_extractions,
        "completed_reviews": completed_reviews,
        "current_number": completed_reviews + 1,

        "field_choices": [
            ("worker_count", "Worker Count"),
            ("ppe_compliance", "PPE Compliance"),
            ("equipment", "Equipment"),
            (
                "materials_components",
                "Materials / Components",
            ),
            ("hazards", "Hazards"),
            ("activities", "Activities"),
            (
                "quality_observations",
                "Quality Observations",
            ),
            ("stage", "Construction Stage"),
        ],
    }

    return render(
        request,
        "annotation/vlm_review.html",
        context,
    )

@login_required
def export_vlm_reviews(request):

    if not request.user.is_superuser:
        return HttpResponseForbidden(
            "Superuser access required."
        )

    temp_dir = tempfile.TemporaryDirectory()

    export_dir = Path(
        temp_dir.name
    ) / "vlm_reviews"

    export_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    call_command(
        "export_human_judge",
        output_dir=str(export_dir),
    )

    zip_path = (
        Path(temp_dir.name)
        / "vlm_human_reviews.zip"
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zip_file:

        for file_path in export_dir.glob("*"):

            if file_path.is_file():

                zip_file.write(
                    file_path,
                    arcname=file_path.name,
                )

    response = FileResponse(
        open(zip_path, "rb"),
        as_attachment=True,
        filename="vlm_human_reviews.zip",
        content_type="application/zip",
    )

    # Keep temporary directory alive until
    # Django finishes returning the response.
    response._temp_dir = temp_dir

    return response
