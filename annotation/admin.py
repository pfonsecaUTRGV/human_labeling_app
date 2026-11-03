from django.contrib import admin
from .models import ImageAssignment


from .models import (
    Image,
    TaxonomyCategory,
    TaxonomyItem,
    Annotation,
    AnnotationSelection,
)

from .models import (
    VLMExtraction,
    VLMClaim,
    VLMHumanReview,
    VLMClaimJudgment,
    VLMMissingClaim,
)


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = (
        "image_id",
        "audit_id",
        "filename",
        "target_annotations",
        "active",
    )

    search_fields = (
        "image_id",
        "audit_id",
        "filename",
    )


@admin.register(TaxonomyCategory)
class TaxonomyCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
    )

    search_fields = (
        "name",
    )


@admin.register(TaxonomyItem)
class TaxonomyItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "canonical_name",
        "category",
        "taxonomy_version",
        "active",
    )

    list_filter = (
        "category",
        "taxonomy_version",
        "active",
    )

    search_fields = (
        "canonical_name",
        "description",
    )


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "image",
        "annotator",
        "completed",
        "taxonomy_version",
    )

    list_filter = (
        "completed",
        "taxonomy_version",
    )


@admin.register(AnnotationSelection)
class AnnotationSelectionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "annotation",
        "taxonomy_item",
    )



@admin.register(ImageAssignment)
class ImageAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "image",
        "annotator",
        "status",
        "assigned_at",
        "expires_at",
        "completed_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "image__filename",
        "annotator__username",
    )


@admin.register(VLMExtraction)
class VLMExtractionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "image",
        "model_version",
        "created_at",
    )

    list_filter = (
        "model_version",
    )

    search_fields = (
        "image__image_id",
    )


@admin.register(VLMClaim)
class VLMClaimAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "extraction",
        "field",
        "claim_value",
    )

    list_filter = (
        "field",
        "extraction__model_version",
    )


@admin.register(VLMHumanReview)
class VLMHumanReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reviewer",
        "extraction",
        "completed",
        "started_at",
        "completed_at",
    )

    list_filter = (
        "completed",
        "extraction__model_version",
    )


@admin.register(VLMClaimJudgment)
class VLMClaimJudgmentAdmin(admin.ModelAdmin):
    list_display = (
        "review",
        "claim",
        "verdict",
    )

    list_filter = (
        "verdict",
        "claim__field",
    )


@admin.register(VLMMissingClaim)
class VLMMissingClaimAdmin(admin.ModelAdmin):
    list_display = (
        "review",
        "field",
        "taxonomy_item",
        "free_text",
    )

    list_filter = (
        "field",
    )