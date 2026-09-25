import json
import re
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.db import transaction

from annotation.models import Image


FILE_ID_PATTERN = re.compile(
    r"_file_(\d+)"
)


def parse_file_id(filename):
    """
    Example:
        audit_731_file_72.jpg -> 72
    """

    match = FILE_ID_PATTERN.search(
        filename or ""
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


def extract_bucket_and_key(original_url):
    """
    Example:
        https://bohrim-app.s3.amazonaws.com/df4374048e

    Returns:
        ("bohrim-app", "df4374048e")
    """

    if not original_url:
        return None, None

    parsed = urlparse(
        original_url
    )

    hostname = (
        parsed.hostname
        or ""
    )

    key = (
        parsed.path
        .lstrip("/")
    )

    # Handles:
    # bohrim-app.s3.amazonaws.com
    # bohrim-app.s3.us-east-1.amazonaws.com

    bucket = None

    if ".s3" in hostname:

        bucket = hostname.split(
            ".s3",
            1
        )[0]

    return bucket, key


class Command(BaseCommand):

    help = (
        "Map existing Django Image records to their "
        "original AWS S3 objects using metadata.json "
        "files stored inside each audit folder."
    )

    def add_arguments(
        self,
        parser
    ):

        parser.add_argument(
            "dataset_root",
            type=str,
            help=(
                "Path to the photos_dataset directory "
                "containing audit_*/metadata.json folders."
            )
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Validate and report mappings without "
                "modifying the database."
            )
        )

        parser.add_argument(
            "--default-bucket",
            type=str,
            default="bohrim-app",
            help=(
                "Fallback S3 bucket if metadata does not "
                "contain a usable original_url."
            )
        )

    def handle(
        self,
        *args,
        **options
    ):

        dataset_root = Path(
            options[
                "dataset_root"
            ]
        )

        dry_run = options[
            "dry_run"
        ]

        default_bucket = options[
            "default_bucket"
        ]

        if not dataset_root.exists():

            raise FileNotFoundError(
                f"Dataset root not found:\n"
                f"{dataset_root}"
            )

        self.stdout.write(
            "=" * 80
        )

        self.stdout.write(
            "MCIF S3 STORAGE MAPPING"
        )

        self.stdout.write(
            "=" * 80
        )

        self.stdout.write(
            f"\nDataset root:\n{dataset_root}"
        )

        self.stdout.write(
            f"\nDry run: {dry_run}"
        )

        metadata_files = list(
            dataset_root.rglob(
                "metadata.json"
            )
        )

        self.stdout.write(
            f"\nMetadata files found: "
            f"{len(metadata_files)}"
        )

        stats = {
            "metadata_files":
                0,

            "metadata_records":
                0,

            "mapped":
                0,

            "updated":
                0,

            "already_mapped":
                0,

            "django_not_found":
                0,

            "ambiguous":
                0,

            "missing_file_id":
                0,

            "missing_storage_key":
                0,

            "metadata_errors":
                0,
        }

        unmatched_examples = []
        ambiguous_examples = []
        error_examples = []

        # -------------------------------------------------
        # Build Django lookup ONCE
        #
        # key:
        #   (audit_id, file_id)
        #
        # value:
        #   list of Image objects
        # -------------------------------------------------

        django_lookup = {}

        self.stdout.write(
            "\nBuilding Django image lookup..."
        )

        for image in Image.objects.all():

            file_id = parse_file_id(
                image.filename
            )

            if file_id is None:
                continue

            key = (
                str(
                    image.audit_id
                ).strip(),
                file_id,
            )

            django_lookup.setdefault(
                key,
                []
            ).append(
                image
            )

        self.stdout.write(
            f"Django mapping keys: "
            f"{len(django_lookup)}"
        )

        # -------------------------------------------------
        # Process metadata
        # -------------------------------------------------

        pending_updates = []

        for metadata_file in metadata_files:

            stats[
                "metadata_files"
            ] += 1

            try:

                with open(
                    metadata_file,
                    "r",
                    encoding="utf-8"
                ) as f:

                    data = json.load(
                        f
                    )

            except Exception as exc:

                stats[
                    "metadata_errors"
                ] += 1

                if len(
                    error_examples
                ) < 10:

                    error_examples.append(
                        (
                            str(
                                metadata_file
                            ),
                            str(
                                exc
                            ),
                        )
                    )

                continue

            # metadata.json may contain either:
            #
            # [
            #   {...},
            #   {...}
            # ]
            #
            # or a single object.

            if isinstance(
                data,
                dict
            ):

                records = [
                    data
                ]

            elif isinstance(
                data,
                list
            ):

                records = data

            else:

                stats[
                    "metadata_errors"
                ] += 1

                continue

            for record in records:

                stats[
                    "metadata_records"
                ] += 1

                audit_id = str(
                    record.get(
                        "audit_id",
                        ""
                    )
                ).strip()

                file_id = record.get(
                    "file_id"
                )

                file_name = str(
                    record.get(
                        "file_name",
                        ""
                    )
                ).strip()

                original_url = str(
                    record.get(
                        "original_url",
                        ""
                    )
                ).strip()

                # -----------------------------------------
                # Validate file ID
                # -----------------------------------------

                try:

                    file_id = int(
                        file_id
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    stats[
                        "missing_file_id"
                    ] += 1

                    continue

                # -----------------------------------------
                # Determine S3 bucket + key
                # -----------------------------------------

                bucket, storage_key = (
                    extract_bucket_and_key(
                        original_url
                    )
                )

                if not bucket:
                    bucket = default_bucket

                # file_name is also the S3 key in your
                # historical metadata, so use it as a
                # fallback.
                if not storage_key:
                    storage_key = file_name

                if not storage_key:

                    stats[
                        "missing_storage_key"
                    ] += 1

                    continue

                # -----------------------------------------
                # Match Django record
                # -----------------------------------------

                lookup_key = (
                    audit_id,
                    file_id,
                )

                matches = django_lookup.get(
                    lookup_key,
                    []
                )

                if len(
                    matches
                ) == 0:

                    stats[
                        "django_not_found"
                    ] += 1

                    if len(
                        unmatched_examples
                    ) < 20:

                        unmatched_examples.append({
                            "audit_id":
                                audit_id,

                            "file_id":
                                file_id,

                            "storage_key":
                                storage_key,

                            "metadata_file":
                                str(
                                    metadata_file
                                ),
                        })

                    continue

                for image in matches:

                    stats[
                        "mapped"
                    ] += 1

                    if (
                        image.storage_backend == "s3"
                        and
                        image.storage_bucket == bucket
                        and
                        image.storage_key == storage_key
                    ):

                        stats[
                            "already_mapped"
                        ] += 1

                        continue

                    image.storage_backend = "s3"
                    image.storage_bucket = bucket
                    image.storage_key = storage_key

                    pending_updates.append(
                        image
                    )

                

        # -------------------------------------------------
        # Apply updates
        # -------------------------------------------------

        if not dry_run:

            self.stdout.write(
                "\nUpdating database..."
            )

            with transaction.atomic():

                Image.objects.bulk_update(
                    pending_updates,
                    [
                        "storage_backend",
                        "storage_bucket",
                        "storage_key",
                    ],
                    batch_size=1000
                )

            stats[
                "updated"
            ] = len(
                pending_updates
            )

        else:

            stats[
                "updated"
            ] = 0

        # -------------------------------------------------
        # Final report
        # -------------------------------------------------

        self.stdout.write(
            "\n"
            +
            "=" * 80
        )

        self.stdout.write(
            "S3 MAPPING SUMMARY"
        )

        self.stdout.write(
            "=" * 80
        )

        for key, value in (
            stats.items()
        ):

            self.stdout.write(
                f"{key:24s}: "
                f"{value}"
            )

        self.stdout.write(
            f"{'pending_updates':24s}: "
            f"{len(pending_updates)}"
        )

        if unmatched_examples:

            self.stdout.write(
                "\nTop unmatched examples:"
            )

            for item in (
                unmatched_examples
            ):

                self.stdout.write(
                    str(
                        item
                    )
                )

        if ambiguous_examples:

            self.stdout.write(
                "\nAmbiguous examples:"
            )

            for item in (
                ambiguous_examples
            ):

                self.stdout.write(
                    str(
                        item
                    )
                )

        if error_examples:

            self.stdout.write(
                "\nMetadata errors:"
            )

            for item in (
                error_examples
            ):

                self.stdout.write(
                    str(
                        item
                    )
                )

        if dry_run:

            self.stdout.write(
                self.style.WARNING(
                    "\nDRY RUN ONLY - "
                    "database was not modified."
                )
            )

        else:

            self.stdout.write(
                self.style.SUCCESS(
                    "\nS3 storage mapping complete."
                )
            )



