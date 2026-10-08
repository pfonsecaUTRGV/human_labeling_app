import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from annotation.models import TaxonomyItem


VISUAL_CATEGORIES = {
    "Equipment",
    "Materials / Components",
}


SPECIAL_OPTIONS = {
    "None visible",
    "Uncertain / cannot determine",
    "Other / not listed",
}


class Command(BaseCommand):

    help = (
        "Export the finalized taxonomy help content "
        "including descriptions and example image URLs."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "output_file",
            type=str,
            help="Output CSV path.",
        )

    def handle(self, *args, **options):

        output_file = Path(
            options["output_file"]
        )

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        items = (
            TaxonomyItem.objects
            .select_related("category")
            .filter(active=True)
            .order_by(
                "category__name",
                "canonical_name",
            )
        )

        fieldnames = [
            "category",
            "canonical_name",
            "description",
            "use_example_image",
            "example_image_url",
            "taxonomy_version",
        ]

        exported = 0
        with_image = 0
        missing_description = 0
        missing_expected_image = 0

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

            for item in items:

                category = (
                    item.category.name
                )

                name = (
                    item.canonical_name
                )

                should_use_image = (
                    category in VISUAL_CATEGORIES
                    and
                    name not in SPECIAL_OPTIONS
                )

                description = (
                    item.description or ""
                )

                image_url = (
                    item.example_image_url or ""
                )

                if not description.strip():
                    missing_description += 1

                if (
                    should_use_image
                    and
                    not image_url.strip()
                ):
                    missing_expected_image += 1

                if image_url.strip():
                    with_image += 1

                writer.writerow({
                    "category":
                        category,

                    "canonical_name":
                        name,

                    "description":
                        description,

                    "use_example_image":
                        "yes"
                        if should_use_image
                        else "no",

                    "example_image_url":
                        image_url,

                    "taxonomy_version":
                        item.taxonomy_version,
                })

                exported += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Final taxonomy help export complete."
            )
        )

        self.stdout.write(
            f"Items exported: {exported}"
        )

        self.stdout.write(
            f"Items with example image: {with_image}"
        )

        self.stdout.write(
            f"Missing descriptions: {missing_description}"
        )

        self.stdout.write(
            f"Missing expected Equipment/Material images: "
            f"{missing_expected_image}"
        )

        self.stdout.write(
            f"Output: {output_file}"
        )