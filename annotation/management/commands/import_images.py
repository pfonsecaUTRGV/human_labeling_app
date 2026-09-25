import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from annotation.models import Image


class Command(BaseCommand):

    help = (
        "Import MCIF validation images from gpt_outputs_clean.csv"
    )

    def add_arguments(
        self,
        parser
    ):

        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to gpt_outputs_clean.csv"
        )

        parser.add_argument(
            "--target-annotations",
            type=int,
            default=1,
            help=(
                "Default number of human annotations "
                "requested per image."
            )
        )

    @transaction.atomic
    def handle(
        self,
        *args,
        **options
    ):

        csv_file = options[
            "csv_file"
        ]

        target_annotations = options[
            "target_annotations"
        ]

        created_count = 0
        updated_count = 0
        skipped_count = 0

        self.stdout.write(
            f"Importing images from:\n{csv_file}"
        )

        with open(
            csv_file,
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(
                file
            )

            required_columns = {
                "image_id",
                "audit_id",
                "image_filename",
                "relative_path",
            }

            missing = (
                required_columns
                -
                set(
                    reader.fieldnames or []
                )
            )

            if missing:

                raise ValueError(
                    "Missing required CSV columns: "
                    +
                    ", ".join(
                        sorted(
                            missing
                        )
                    )
                )

            for row in reader:

                image_id = (
                    row[
                        "image_id"
                    ]
                    .strip()
                )

                audit_id = (
                    row[
                        "audit_id"
                    ]
                    .strip()
                )

                filename = (
                    row[
                        "image_filename"
                    ]
                    .strip()
                )

                relative_path = (
                    row[
                        "relative_path"
                    ]
                    .strip()
                )

                if (
                    not image_id
                    or
                    not audit_id
                    or
                    not filename
                ):

                    skipped_count += 1
                    continue

                image, created = (
                    Image.objects.update_or_create(

                        audit_id=
                            audit_id,

                        image_id=
                            image_id,

                        defaults={

                            "filename":
                                filename,

                            "image_path":
                                relative_path,

                            "target_annotations":
                                target_annotations,

                            "active":
                                True,
                        }
                    )
                )

                if created:

                    created_count += 1

                else:

                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                "\nImage import complete."
            )
        )

        self.stdout.write(
            f"Created: {created_count}"
        )

        self.stdout.write(
            f"Updated: {updated_count}"
        )

        self.stdout.write(
            f"Skipped: {skipped_count}"
        )

        self.stdout.write(
            f"Default target annotations: "
            f"{target_annotations}"
        )