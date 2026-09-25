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
