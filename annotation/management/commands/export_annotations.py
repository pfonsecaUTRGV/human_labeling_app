import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from annotation.models import Annotation


CATEGORY_COLUMN_MAP = {
    "Equipment": "equipment",
    "Materials / Components": "materials_components",
    "Hazards": "hazards",
    "Activities": "activities",
    "Quality Observations": "quality_observations",
    "Stage": "stage",
}


class Command(BaseCommand):

    help = (
        "Export completed human annotations "
        "to a CSV file."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "output_file",
            type=str,
            help="Output CSV path.",
        )

        parser.add_argument(
            "--anonymous",
            action="store_true",
            help=(
                "Export anonymous annotator IDs "
                "instead of usernames."
            ),
        )


    def handle(self, *args, **options):

        output_file = Path(
            options["output_file"]
        )

        anonymous = (
            options["anonymous"]
        )

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


        annotations = (
            Annotation.objects
            .filter(
                completed=True
            )
            .select_related(
                "image",
                "annotator",
            )
            .prefetch_related(
                "selections__taxonomy_item__category"
            )
            .order_by(
                "id"
            )
        )


        fieldnames = [
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
        ]


        count = 0


        with output_file.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )

            writer.writeheader()


            for annotation in annotations:

                selections = {
                    "equipment": [],
                    "materials_components": [],
                    "hazards": [],
                    "activities": [],
                    "quality_observations": [],
                    "stage": [],
                }


                for selection in (
                    annotation
                    .selections
                    .all()
                ):

                    item = (
                        selection.taxonomy_item
                    )

                    category_name = (
                        item.category.name
                    )

                    column_name = (
                        CATEGORY_COLUMN_MAP.get(
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


                # -----------------------------------------
                # Remove accidental duplicates
                # while preserving order
                # -----------------------------------------

                for key in selections:

                    selections[key] = list(
                        dict.fromkeys(
                            selections[key]
                        )
                    )


                # -----------------------------------------
                # Annotator identifier
                # -----------------------------------------

                if anonymous:

                    annotator_value = (
                        f"annotator_"
                        f"{annotation.annotator_id}"
                    )

                else:

                    annotator_value = (
                        annotation.annotator.username
                    )


                # -----------------------------------------
                # Write row
                # -----------------------------------------

                writer.writerow({

                    "annotation_id":
                        annotation.id,

                    "audit_id":
                        annotation.image.audit_id,

                    "image_id":
                        annotation.image.image_id,

                    "filename":
                        annotation.image.filename,

                    "annotator":
                        annotator_value,

                    "worker_count":
                        annotation.worker_count,

                    "ppe_compliance":
                        annotation.ppe_compliance,

                    "equipment":
                        " | ".join(
                            selections[
                                "equipment"
                            ]
                        ),

                    "materials_components":
                        " | ".join(
                            selections[
                                "materials_components"
                            ]
                        ),

                    "hazards":
                        " | ".join(
                            selections[
                                "hazards"
                            ]
                        ),

                    "activities":
                        " | ".join(
                            selections[
                                "activities"
                            ]
                        ),

                    "quality_observations":
                        " | ".join(
                            selections[
                                "quality_observations"
                            ]
                        ),

                    "stage":
                        " | ".join(
                            selections[
                                "stage"
                            ]
                        ),

                    "notes":
                        annotation.notes,

                    "taxonomy_version":
                        annotation.taxonomy_version,

                    "completed_at":
                        (
                            annotation.completed_at
                            .isoformat()
                            if annotation.completed_at
                            else ""
                        ),
                })

                count += 1


        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Annotation export complete."
            )
        )

        self.stdout.write(
            f"Completed annotations exported: "
            f"{count}"
        )

        self.stdout.write(
            f"Output: {output_file}"
        )