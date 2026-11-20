import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from annotation.models import (
    Image,
    VLMExtraction,
    VLMClaim,
)


LIST_FIELDS = [
    "equipment",
    "materials_components",
    "hazards",
    "activities",
    "quality_observations",
]

SCALAR_FIELDS = [
    "worker_count",
    "ppe_compliance",
    "stage",
]


def parse_list(value):
    """
    Our V2/V3 CSV files store multilabel predictions using:

        Crane | Truck | Scaffolding

    Convert that string into individual claims.
    """

    if value is None:
        return []

    value = str(value).strip()

    if not value:
        return []

    return [
        item.strip()
        for item in value.split("|")
        if item.strip()
    ]


class Command(BaseCommand):

    help = (
        "Import VLM extraction CSV files into "
        "VLMExtraction and VLMClaim."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to VLM results CSV.",
        )

        parser.add_argument(
            "--model-version",
            required=True,
            type=str,
            help=(
                "Internal model identifier, for example "
                "V2_taxonomy or V3_finetuned."
            ),
        )

        parser.add_argument(
            "--replace",
            action="store_true",
            help=(
                "Delete existing extraction for this image/model "
                "before importing again."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):

        csv_path = Path(
            options["csv_file"]
        ).expanduser().resolve()

        model_version = (
            options["model_version"]
            .strip()
        )

        replace = options["replace"]

        if not csv_path.exists():
            raise CommandError(
                f"CSV does not exist: {csv_path}"
            )

        self.stdout.write("")
        self.stdout.write(
            "=" * 70
        )
        self.stdout.write(
            f"IMPORTING {model_version}"
        )
        self.stdout.write(
            "=" * 70
        )

        created_extractions = 0
        created_claims = 0
        skipped = 0
        missing_images = []

        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(f)

            for row_number, row in enumerate(
                reader,
                start=2,
            ):

                human_image_id = (
                    row.get("human_image_id", "")
                    .strip()
                )

                if not human_image_id:

                    self.stdout.write(
                        self.style.WARNING(
                            f"Row {row_number}: "
                            "missing human_image_id"
                        )
                    )

                    skipped += 1
                    continue

                # -------------------------------------------------
                # Find image already stored by the MCIF app
                # -------------------------------------------------

                # -------------------------------------------------
                # Find image already stored by the MCIF app
                # -------------------------------------------------

                image = None

                # First try legacy behavior:
                # match directly using image_id.
                try:
                    image = Image.objects.get(
                        image_id=human_image_id
                    )

                except Image.DoesNotExist:
                    pass


                # If not found, try V4-style matching
                # using audit_id + filename.
                if image is None:

                    audit_id = str(
                        row.get("audit_id", "")
                    ).strip()

                    filename = (
                        row.get("filename", "")
                        .strip()
                    )

                    if audit_id and filename:

                        image = (
                            Image.objects
                            .filter(
                                audit_id=audit_id,
                                filename=filename,
                            )
                            .first()
                        )


                # Still not found
                if image is None:

                    missing_images.append(
                        human_image_id
                    )

                    self.stdout.write(
                        self.style.WARNING(
                            f"Image not found: "
                            f"{human_image_id}"
                        )
                    )

                    continue

                # -------------------------------------------------
                # Existing extraction
                # -------------------------------------------------

                existing = (
                    VLMExtraction.objects
                    .filter(
                        image=image,
                        model_version=model_version,
                    )
                    .first()
                )

                if existing:

                    if replace:

                        existing.delete()

                    else:

                        self.stdout.write(
                            f"Skipping existing: "
                            f"{human_image_id} "
                            f"{model_version}"
                        )

                        skipped += 1
                        continue

                # -------------------------------------------------
                # Save original structured model output
                # -------------------------------------------------

                raw_output = {}

                for field in (
                    SCALAR_FIELDS
                    + LIST_FIELDS
                ):

                    value = row.get(
                        field,
                        ""
                    )

                    if field in LIST_FIELDS:
                        raw_output[field] = (
                            parse_list(value)
                        )

                    elif field == "worker_count":

                        try:
                            raw_output[field] = int(
                                float(value)
                            )
                        except Exception:
                            raw_output[field] = value

                    else:
                        raw_output[field] = value

                extraction = (
                    VLMExtraction.objects.create(
                        image=image,
                        model_version=model_version,
                        source_file=csv_path.name,
                        raw_output=raw_output,
                    )
                )

                created_extractions += 1

                # -------------------------------------------------
                # Scalar claims
                # -------------------------------------------------

                order = 0

                for field in SCALAR_FIELDS:

                    value = row.get(
                        field,
                        ""
                    )

                    if value is None:
                        continue

                    value = str(value).strip()

                    if not value:
                        continue

                    VLMClaim.objects.create(
                        extraction=extraction,
                        field=field,
                        claim_value=value,
                        claim_order=order,
                    )

                    created_claims += 1
                    order += 1

                # -------------------------------------------------
                # Multilabel claims
                # -------------------------------------------------

                for field in LIST_FIELDS:

                    values = parse_list(
                        row.get(field, "")
                    )

                    for value in values:

                        VLMClaim.objects.create(
                            extraction=extraction,
                            field=field,
                            claim_value=value,
                            claim_order=order,
                        )

                        created_claims += 1
                        order += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Imported "
                        f"{human_image_id} "
                        f"({model_version}) "
                        f"with {order} claims"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            "=" * 70
        )
        self.stdout.write(
            "IMPORT SUMMARY"
        )
        self.stdout.write(
            "=" * 70
        )

        self.stdout.write(
            f"Extractions created: "
            f"{created_extractions}"
        )

        self.stdout.write(
            f"Claims created: "
            f"{created_claims}"
        )

        self.stdout.write(
            f"Skipped: "
            f"{skipped}"
        )

        self.stdout.write(
            f"Images not found: "
            f"{len(missing_images)}"
        )

        if missing_images:

            self.stdout.write("")
            self.stdout.write(
                "Missing image IDs:"
            )

            for image_id in missing_images:

                self.stdout.write(
                    f"  {image_id}"
                )
