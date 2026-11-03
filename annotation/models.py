from django.db import models

from django.conf import settings
from django.db import models



# ---------------------------------------------------------
# IMAGE
# ---------------------------------------------------------

class Image(models.Model):

    image_id = models.CharField(
        max_length=100
    )

    audit_id = models.CharField(
        max_length=100,
        blank=True
    )

    filename = models.CharField(
        max_length=255
    )

    image_path = models.CharField(
        max_length=500
    )

    target_annotations = models.PositiveIntegerField(
        default=1
    )

    active = models.BooleanField(
        default=True
    )

    storage_backend = models.CharField(
    max_length=20,
    default="s3"
    )

    storage_bucket = models.CharField(
        max_length=255,
        default="bohrim-app"
    )

    storage_key = models.CharField(
        max_length=1000,
        blank=True
    )
    

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "audit_id",
                    "image_id"
                ],
                name="unique_audit_image"
            )
        ]

    def __str__(self):
        return self.filename


class ImageAssignment(models.Model):

    STATUS_CHOICES = [
        ("assigned", "Assigned"),
        ("completed", "Completed"),
        ("expired", "Expired"),
    ]

    image = models.ForeignKey(
        Image,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="image_assignments"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="assigned"
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "image",
                    "annotator"
                ],
                name="unique_image_annotator_assignment"
            )
        ]

    def __str__(self):
        return (
            f"{self.annotator} - "
            f"{self.image} - "
            f"{self.status}"
        ) 


# ---------------------------------------------------------
# TAXONOMY CATEGORY
# ---------------------------------------------------------

class TaxonomyCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.name


# ---------------------------------------------------------
# TAXONOMY ITEM
# ---------------------------------------------------------

class TaxonomyItem(models.Model):

    category = models.ForeignKey(
        TaxonomyCategory,
        on_delete=models.CASCADE,
        related_name="items"
    )

    canonical_name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True
    )

    example_image = models.ImageField(
        upload_to="taxonomy_examples/",
        blank=True,
        null=True
    )

    taxonomy_version = models.CharField(
        max_length=20,
        default="1.0"
    )

    active = models.BooleanField(
        default=True
    )

    example_source_image = models.ForeignKey(
    Image,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="taxonomy_examples"
    )

    example_image_url = models.URLField(
    blank=True,
    max_length=1000,
    )  

    def __str__(self):
        return (
            f"{self.category.name}: "
            f"{self.canonical_name}"
        )


# ---------------------------------------------------------
# ANNOTATION
# ---------------------------------------------------------

class Annotation(models.Model):

    image = models.ForeignKey(
        Image,
        on_delete=models.CASCADE,
        related_name="annotations"
    )

    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="annotations"
    )

    worker_count = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    PPE_CHOICES = [
        ("compliant", "Compliant"),
        ("partial", "Partially compliant"),
        ("non_compliant", "Non-compliant"),
        ("not_visible", "Not visible"),
        ("uncertain", "Uncertain"),
    ]

    ppe_compliance = models.CharField(
        max_length=30,
        choices=PPE_CHOICES,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    taxonomy_version = models.CharField(
        max_length=20,
        default="1.0"
    )

    completed = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "image",
                    "annotator"
                ],
                name="unique_image_per_annotator"
            )

        ]

    def __str__(self):

        return (
            f"{self.annotator} - "
            f"{self.image.filename}"
        )


# ---------------------------------------------------------
# ANNOTATION SELECTION
# ---------------------------------------------------------

class AnnotationSelection(models.Model):

    annotation = models.ForeignKey(
        Annotation,
        on_delete=models.CASCADE,
        related_name="selections"
    )

    taxonomy_item = models.ForeignKey(
        TaxonomyItem,
        on_delete=models.CASCADE
    )

    def __str__(self):

        return (
            f"{self.annotation} -> "
            f"{self.taxonomy_item}"
        )






class VLMExtraction(models.Model):
    """
    One VLM analysis of one construction image.

    Example model versions:
        V2_taxonomy
        V3_finetuned
    """

    image = models.ForeignKey(
        "Image",
        on_delete=models.CASCADE,
        related_name="vlm_extractions",
    )

    model_version = models.CharField(
        max_length=100,
    )

    source_file = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    raw_output = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "image",
                    "model_version",
                ],
                name="unique_vlm_extraction_per_image_model",
            )
        ]

    def __str__(self):
        return (
            f"{self.image} - "
            f"{self.model_version}"
        )


class VLMClaim(models.Model):
    """
    One individual visual claim produced by the VLM.

    Examples:
        worker_count -> 3
        equipment -> Crane
        materials_components -> Structural steel
        hazards -> Fall hazard
        stage -> Mid
    """

    FIELD_CHOICES = [
        ("worker_count", "Worker Count"),
        ("ppe_compliance", "PPE Compliance"),
        ("equipment", "Equipment"),
        ("materials_components", "Materials / Components"),
        ("hazards", "Hazards"),
        ("activities", "Activities"),
        ("quality_observations", "Quality Observations"),
        ("stage", "Construction Stage"),
    ]

    extraction = models.ForeignKey(
        VLMExtraction,
        on_delete=models.CASCADE,
        related_name="claims",
    )

    field = models.CharField(
        max_length=50,
        choices=FIELD_CHOICES,
    )

    claim_value = models.CharField(
        max_length=255,
    )

    claim_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "field",
            "claim_order",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.field}: "
            f"{self.claim_value}"
        )


class VLMHumanReview(models.Model):
    """
    One human judge reviewing one complete VLM extraction.

    IMPORTANT:
    The reviewer should not see the original human annotation.
    """

    extraction = models.ForeignKey(
        VLMExtraction,
        on_delete=models.CASCADE,
        related_name="human_reviews",
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vlm_claim_reviews",
    )

    completed = models.BooleanField(
        default=False,
    )

    overall_notes = models.TextField(
        blank=True,
        default="",
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "extraction",
                    "reviewer",
                ],
                name="unique_human_review_per_extraction_reviewer",
            )
        ]

    def __str__(self):
        return (
            f"{self.reviewer} - "
            f"{self.extraction}"
        )


class VLMClaimJudgment(models.Model):
    """
    Human judgment of one GPT/VLM claim.
    """

    VERDICT_CHOICES = [
        ("supported", "Supported"),
        ("partially_supported", "Partially Supported"),
        ("unsupported", "Unsupported"),
        ("cannot_determine", "Cannot Determine"),
    ]

    review = models.ForeignKey(
        VLMHumanReview,
        on_delete=models.CASCADE,
        related_name="claim_judgments",
    )

    claim = models.ForeignKey(
        VLMClaim,
        on_delete=models.CASCADE,
        related_name="human_judgments",
    )

    verdict = models.CharField(
        max_length=30,
        choices=VERDICT_CHOICES,
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "review",
                    "claim",
                ],
                name="unique_judgment_per_review_claim",
            )
        ]

    def __str__(self):
        return (
            f"{self.claim} → "
            f"{self.verdict}"
        )


class VLMMissingClaim(models.Model):
    """
    Important information visible in the image that GPT failed to report.
    """

    FIELD_CHOICES = VLMClaim.FIELD_CHOICES

    review = models.ForeignKey(
        VLMHumanReview,
        on_delete=models.CASCADE,
        related_name="missing_claims",
    )

    field = models.CharField(
        max_length=50,
        choices=FIELD_CHOICES,
    )

    taxonomy_item = models.ForeignKey(
        "TaxonomyItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vlm_missing_claims",
    )

    free_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    notes = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        if self.taxonomy_item:
            value = str(self.taxonomy_item)
        else:
            value = self.free_text

        return (
            f"{self.field}: {value}"
        )