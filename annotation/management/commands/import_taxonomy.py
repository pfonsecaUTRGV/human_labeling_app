import csv

from django.core.management.base import BaseCommand
from django.db import transaction

from annotation.models import (
    TaxonomyCategory,
    TaxonomyItem,
)


class Command(BaseCommand):

    help = (
        "Import MCIF taxonomy categories and items "
        "from a CSV file."
    )

    def add_arguments(
        self,
        parser
    ):

        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the taxonomy CSV file."
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

        self.stdout.write(
            f"Importing taxonomy from:\n{csv_file}"
        )

        categories_created = 0
        categories_updated = 0

        items_created = 0
        items_updated = 0

        with open(
            csv_file,
            newline="",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(
                file
            )

            for row in reader:

                category_name = (
                    row[
                        "category"
                    ]
                    .strip()
                )

                canonical_name = (
                    row[
                        "canonical_name"
                    ]
                    .strip()
                )

                # -----------------------------------------
                # CATEGORY
                # -----------------------------------------

                category, created = (
                    TaxonomyCategory.objects.get_or_create(
                        name=category_name
                    )
                )

                if created:

                    categories_created += 1

                else:

                    categories_updated += 1

                # -----------------------------------------
                # BOOLEAN VALUES
                # -----------------------------------------

                active = (
                    row[
                        "active"
                    ]
                    .strip()
                    .lower()
                    ==
                    "true"
                )

                special_option = (
                    row[
                        "special_option"
                    ]
                    .strip()
                    .lower()
                    ==
                    "true"
                )

                # -----------------------------------------
                # ITEM
                # -----------------------------------------

                item, created = (
                    TaxonomyItem.objects.update_or_create(

                        category=
                            category,

                        canonical_name=
                            canonical_name,

                        defaults={

                            "description":
                                row[
                                    "description"
                                ].strip(),

                            "example_image":
                                row[
                                    "example_image"
                                ].strip(),

                            "taxonomy_version":
                                row[
                                    "taxonomy_version"
                                ].strip(),

                            "active":
                                active,
                        }
                    )
                )

                if created:

                    items_created += 1

                else:

                    items_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "\nTaxonomy import complete."
            )
        )

        self.stdout.write(
            f"Categories created: "
            f"{categories_created}"
        )

        self.stdout.write(
            f"Categories reused: "
            f"{categories_updated}"
        )

        self.stdout.write(
            f"Items created: "
            f"{items_created}"
        )

        self.stdout.write(
            f"Items updated: "
            f"{items_updated}"
        )