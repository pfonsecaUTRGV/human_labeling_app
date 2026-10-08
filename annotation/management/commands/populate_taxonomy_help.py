import csv
import time
from pathlib import Path

import requests

from django.core.management.base import BaseCommand

from annotation.models import TaxonomyItem


COMMONS_API = "https://commons.wikimedia.org/w/api.php"


# ============================================================
# Categories that should receive example images
# ============================================================

VISUAL_CATEGORIES = {
    "Equipment",
    "Materials / Components",
}


# ============================================================
# Special fallback options should not receive example images
# ============================================================

SPECIAL_OPTIONS = {
    "None visible",
    "Uncertain / cannot determine",
    "Other / not listed",
}


# ============================================================
# Wikimedia search terms
#
# More specific phrases improve the quality of the images
# returned by Wikimedia Commons.
# ============================================================

SEARCH_TERMS = {

    # --------------------------------------------------------
    # EQUIPMENT
    # --------------------------------------------------------

    "Backhoe loader":
        "backhoe loader construction",

    "Barrels":
        "construction site barrels drums",

    "Benches":
        "construction work bench",

    "Boom lift":
        "boom lift construction",

    "Bucket":
        "construction bucket",

    "Concrete pump truck":
        "concrete pump truck construction",

    "Concrete truck":
        "concrete mixer truck construction",

    "Construction barrier":
        "construction safety barrier",

    "Construction vehicles":
        "construction vehicles site",

    "Crane":
        "construction crane",

    "Crane truck":
        "truck mounted crane construction",

    "Dump truck":
        "dump truck construction",

    "Excavator":
        "excavator construction",

    "Fire extinguisher":
        "fire extinguisher",

    "Flatbed truck":
        "flatbed truck construction",

    "Gas cylinders":
        "welding gas cylinders",

    "Generator":
        "portable generator construction",

    "Hand tools":
        "construction hand tools",

    "Hoses":
        "construction hose",

    "Ladder":
        "construction ladder",

    "Light tower":
        "construction light tower",

    "Measuring tape":
        "measuring tape construction",

    "Motor grader":
        "motor grader construction",

    "Other MEWP / aerial lift":
        "mobile elevating work platform",

    "Pickup truck":
        "pickup truck construction",

    "Pipe fusion machine":
        "HDPE pipe fusion machine",

    "Portable toilet":
        "portable toilet construction",

    "Road roller":
        "road roller construction",

    "Scaffolding":
        "construction scaffolding",

    "Scissor lift":
        "scissor lift construction",

    "Shovel":
        "construction shovel",

    "Soil compactor":
        "soil compactor construction",

    "Tables":
        "construction work table",

    "Temporary fencing / construction fencing":
        "temporary construction fencing",

    "Temporary shelter":
        "temporary construction shelter",

    "Tent":
        "construction site tent",

    "Traffic barrels":
        "traffic construction barrels",

    "Traffic cone":
        "traffic cone construction",

    "Truck":
        "construction truck",

    "Van":
        "construction work van",

    "Water coolers":
        "construction water cooler",

    "Water truck":
        "water truck construction",

    "Welding machine":
        "welding machine construction",

    "Wheelbarrow":
        "wheelbarrow construction",


    # --------------------------------------------------------
    # MATERIALS / COMPONENTS
    # --------------------------------------------------------

    "Bricks":
        "construction bricks",

    "Cables":
        "construction cables",

    "Caution tape":
        "construction caution tape",

    "Concrete":
        "concrete construction material",

    "Concrete barriers":
        "concrete traffic barrier",

    "Concrete blocks":
        "concrete masonry blocks",

    "Concrete columns":
        "reinforced concrete columns construction",

    "Concrete debris":
        "concrete construction debris",

    "Concrete foundation element":
        "concrete foundation footing construction",

    "Construction debris":
        "construction debris site",

    "Electrical cables":
        "electrical cable construction",

    "Formwork":
        "concrete formwork construction",

    "Formwork panel":
        "formwork panels construction",

    "Gravel":
        "construction gravel aggregate",

    "Metal rods":
        "metal rods construction",

    "Orange safety fencing":
        "orange construction safety fence",

    "Pipe":
        "construction pipe",

    "Plastic sheeting":
        "plastic sheeting construction",

    "Rebar":
        "reinforcing steel rebar construction",

    "Rebar cages":
        "reinforcement rebar cage construction",

    "Sand":
        "construction sand aggregate",

    "Sandbags":
        "construction sandbags",

    "Scaffolding components":
        "scaffolding components construction",

    "Soil":
        "construction soil earthwork",

    "Steel beam":
        "structural steel beam construction",

    "Steel columns":
        "structural steel columns construction",

    "Steel pipe":
        "steel pipe construction",

    "Structural steel":
        "structural steel construction",

    "Tarps":
        "construction tarp",

    "Welding rods":
        "welding electrodes rods",

    "Wood":
        "construction lumber wood",

    "Wooden blocks":
        "wood blocking construction",

    "Wooden pallets":
        "wooden pallets construction",

    "Wooden planks":
        "wood planks construction",

    "Wooden supports":
        "timber supports construction",
}


class Command(BaseCommand):

    help = (
        "Populate taxonomy descriptions and provisional "
        "Wikimedia Commons example images."
    )


    # ========================================================
    # COMMAND ARGUMENTS
    # ========================================================

    def add_arguments(self, parser):

        parser.add_argument(
            "csv_file",
            type=str,
            help="Path to the populated taxonomy help CSV.",
        )

        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Only import descriptions and do not search images.",
        )


    # ========================================================
    # WIKIMEDIA COMMONS SEARCH
    # ========================================================

    def search_commons_image(
        self,
        search_term,
        max_retries=5,
    ):

        params = {
            "action": "query",
            "format": "json",

            "generator": "search",

            "gsrsearch":
                search_term,

            "gsrnamespace":
                6,

            "gsrlimit":
                10,

            "prop":
                "imageinfo",

            "iiprop":
                "url|mime|extmetadata",

            "iiurlwidth":
                800,
        }


        headers = {
            "User-Agent":
                "MCIF-Human-Annotation/1.0 "
                "(academic research project)"
        }


        data = None


        # ----------------------------------------------------
        # Retry logic
        # ----------------------------------------------------

        for attempt in range(
            1,
            max_retries + 1,
        ):

            try:

                response = requests.get(
                    COMMONS_API,
                    params=params,
                    headers=headers,
                    timeout=20,
                )


                # --------------------------------------------
                # Wikimedia rate limiting
                # --------------------------------------------

                if response.status_code == 429:

                    wait_time = (
                        10 * attempt
                    )

                    self.stdout.write(
                        self.style.WARNING(
                            f"Rate limited. "
                            f"Waiting {wait_time}s..."
                        )
                    )

                    time.sleep(
                        wait_time
                    )

                    continue


                response.raise_for_status()

                data = (
                    response.json()
                )

                break


            except requests.RequestException as exc:

                if attempt == max_retries:

                    self.stdout.write(
                        self.style.WARNING(
                            f"Commons request failed: "
                            f"{exc}"
                        )
                    )

                    return None


                wait_time = (
                    5 * attempt
                )

                self.stdout.write(
                    self.style.WARNING(
                        f"Request failed. "
                        f"Retrying in "
                        f"{wait_time}s..."
                    )
                )

                time.sleep(
                    wait_time
                )


        # ----------------------------------------------------
        # No successful response
        # ----------------------------------------------------

        if data is None:
            return None


        pages = (
            data
            .get(
                "query",
                {}
            )
            .get(
                "pages",
                {}
            )
        )


        # ----------------------------------------------------
        # Review candidate results
        # ----------------------------------------------------

        for page in pages.values():

            imageinfo_list = (
                page.get(
                    "imageinfo",
                    []
                )
            )


            if not imageinfo_list:
                continue


            info = (
                imageinfo_list[0]
            )


            mime = (
                info.get(
                    "mime",
                    ""
                )
            )


            # --------------------------------------------
            # Use only standard image formats
            # --------------------------------------------

            if mime not in {
                "image/jpeg",
                "image/png",
                "image/webp",
            }:

                continue


            image_url = (
                info.get(
                    "thumburl"
                )
                or
                info.get(
                    "url"
                )
            )


            if not image_url:
                continue


            title = (
                page.get(
                    "title",
                    ""
                )
            )


            metadata = (
                info.get(
                    "extmetadata",
                    {}
                )
            )


            license_name = (
                metadata
                .get(
                    "LicenseShortName",
                    {}
                )
                .get(
                    "value",
                    ""
                )
            )


            artist = (
                metadata
                .get(
                    "Artist",
                    {}
                )
                .get(
                    "value",
                    ""
                )
            )


            source_url = (
                info.get(
                    "descriptionurl",
                    ""
                )
            )


            return {
                "title":
                    title,

                "image_url":
                    image_url,

                "source_url":
                    source_url,

                "license":
                    license_name,

                "artist":
                    artist,
            }


        return None


    # ========================================================
    # MAIN COMMAND
    # ========================================================

    def handle(
        self,
        *args,
        **options,
    ):

        csv_file = Path(
            options[
                "csv_file"
            ]
        )


        skip_images = (
            options[
                "skip_images"
            ]
        )


        # ----------------------------------------------------
        # Validate CSV
        # ----------------------------------------------------

        if not csv_file.exists():

            self.stderr.write(
                self.style.ERROR(
                    f"File not found: "
                    f"{csv_file}"
                )
            )

            return


        # ----------------------------------------------------
        # Read CSV
        # ----------------------------------------------------

        with csv_file.open(
            "r",
            newline="",
            encoding="utf-8",
        ) as f:

            rows = list(
                csv.DictReader(
                    f
                )
            )


        # ----------------------------------------------------
        # Counters
        # ----------------------------------------------------

        description_updates = 0
        image_updates = 0
        image_skipped = 0
        image_not_found = 0
        taxonomy_not_found = 0


        # ----------------------------------------------------
        # Process every taxonomy item
        # ----------------------------------------------------

        for row in rows:

            category = (
                row
                .get(
                    "category",
                    ""
                )
                .strip()
            )


            name = (
                row
                .get(
                    "canonical_name",
                    ""
                )
                .strip()
            )


            description = (
                row
                .get(
                    "description",
                    ""
                )
                .strip()
            )


            if not category or not name:
                continue


            # ------------------------------------------------
            # Find taxonomy item
            # ------------------------------------------------

            try:

                item = (
                    TaxonomyItem.objects
                    .select_related(
                        "category"
                    )
                    .get(
                        category__name=
                            category,

                        canonical_name=
                            name,

                        active=True,
                    )
                )


            except TaxonomyItem.DoesNotExist:

                self.stdout.write(
                    self.style.WARNING(
                        f"Taxonomy item not found: "
                        f"{category} / {name}"
                    )
                )

                taxonomy_not_found += 1

                continue


            # =================================================
            # DESCRIPTION
            # =================================================

            if description:

                if (
                    item.description
                    != description
                ):

                    item.description = (
                        description
                    )

                    item.save(
                        update_fields=[
                            "description"
                        ]
                    )


                description_updates += 1


            # =================================================
            # IMAGE
            # =================================================

            if skip_images:
                continue


            # ------------------------------------------------
            # Only Equipment and Materials receive images
            # ------------------------------------------------

            if (
                category
                not in VISUAL_CATEGORIES
            ):

                continue


            # ------------------------------------------------
            # Special options do not receive images
            # ------------------------------------------------

            if name in SPECIAL_OPTIONS:
                continue


            # ------------------------------------------------
            # Skip items that already have an example image
            # ------------------------------------------------

            if item.example_image_url:

                self.stdout.write(
                    f"Skipping existing image: "
                    f"{category} / {name}"
                )

                image_skipped += 1

                continue


            # ------------------------------------------------
            # Determine Commons search term
            # ------------------------------------------------

            search_term = (
                SEARCH_TERMS.get(
                    name,
                    f"{name} construction"
                )
            )


            self.stdout.write(
                f"Searching: "
                f"{category} / {name}"
            )


            # ------------------------------------------------
            # Search Commons
            # ------------------------------------------------

            result = (
                self.search_commons_image(
                    search_term
                )
            )


            if not result:

                self.stdout.write(
                    self.style.WARNING(
                        f"  No suitable image "
                        f"found for {name}"
                    )
                )

                image_not_found += 1

                continue


            # ------------------------------------------------
            # Save image URL
            # ------------------------------------------------

            item.example_image_url = (
                result[
                    "image_url"
                ]
            )


            item.save(
                update_fields=[
                    "example_image_url"
                ]
            )


            image_updates += 1


            # ------------------------------------------------
            # Display result
            # ------------------------------------------------

            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ "
                    f"{result['title']}"
                )
            )


            if result[
                "license"
            ]:

                self.stdout.write(
                    f"    License: "
                    f"{result['license']}"
                )


            # ------------------------------------------------
            # Delay to avoid Wikimedia rate limiting
            # ------------------------------------------------

            time.sleep(
                2.5
            )


        # ====================================================
        # SUMMARY
        # ====================================================

        self.stdout.write(
            ""
        )

        self.stdout.write(
            "-----------------------------------"
        )


        self.stdout.write(
            self.style.SUCCESS(
                "Taxonomy help import complete."
            )
        )


        self.stdout.write(
            f"Descriptions processed: "
            f"{description_updates}"
        )


        self.stdout.write(
            f"Existing images skipped: "
            f"{image_skipped}"
        )


        self.stdout.write(
            f"Example images updated: "
            f"{image_updates}"
        )


        self.stdout.write(
            f"Images not found: "
            f"{image_not_found}"
        )


        self.stdout.write(
            f"Taxonomy items not found: "
            f"{taxonomy_not_found}"
        )