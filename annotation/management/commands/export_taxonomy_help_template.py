import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from annotation.models import TaxonomyItem


VISUAL_CATEGORIES = {
    "Equipment",
    "Materials / Components",
}


class Command(BaseCommand):

    help = (
        "Export Taxonomy v1 into a CSV template "
        "for annotation help descriptions and example images."
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

        with open(
            output_file,
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "category",
                    "canonical_name",
                    "description",
                    "use_example_image",
                    "example_audit_id",
                    "example_filename",
                    "taxonomy_version",
                ],
            )

            writer.writeheader()

            count = 0

            for item in items:

                category_name = (
                    item.category.name
                )

                use_example_image = (
                    "yes"
                    if category_name
                    in VISUAL_CATEGORIES
                    else "no"
                )

                writer.writerow({
                    "category":
                        category_name,

                    "canonical_name":
                        item.canonical_name,

                    "description":
                        item.description or "",

                    "use_example_image":
                        use_example_image,

                    "example_audit_id":
                        "",

                    "example_filename":
                        "",

                    "taxonomy_version":
                        item.taxonomy_version,
                })

                count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {count} taxonomy items."
            )
        )

        self.stdout.write(
            f"Output: {output_file}"
        )