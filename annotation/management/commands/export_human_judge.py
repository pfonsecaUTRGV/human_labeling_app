import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from annotation.models import VLMHumanReview


VERDICT_MAP = {
    "supported": "SUPPORTED",
    "partially_supported": "PARTIALLY_SUPPORTED",
    "unsupported": "UNSUPPORTED",
    "cannot_determine": "UNANSWERABLE",
}


SCALAR_FIELDS = {
    "worker_count",
    "ppe_compliance",
    "stage",
}


LIST_FIELDS = {
    "equipment",
    "materials_components",
    "hazards",
    "activities",
    "quality_observations",
}


def short_condition(model_version):
    value = (model_version or "").lower()

    if "v2" in value:
        return "V2_taxonomy"

    if "v3" in value:
        return "V3_finetuned"

    return model_version or "UNKNOWN"


def compute_grounding_score(
    supported,
    partially_supported,
    unsupported,
    unanswerable,
):
    """
    Temporary Human Judge grounding score.

    IMPORTANT:
    This assumes:
        SUPPORTED = 1.0
        PARTIALLY_SUPPORTED = 0.5
        UNSUPPORTED = 0.0

    UNANSWERABLE claims are excluded from the denominator.

    Replace this formula if the Gemini judge script
    uses a different equation.
    """

    answerable = (
        supported
        + partially_supported
        + unsupported
    )

    if answerable == 0:
        return None

    return (
        supported
        + 0.5 * partially_supported
    ) / answerable


class Command(BaseCommand):

    help = (
        "Export Human Judge results using the same "
        "schema as the Gemini Judge JSONL."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--output-dir",
            default="vlm_review_exports",
            type=str,
        )

    def handle(self, *args, **options):

        output_dir = Path(
            options["output_dir"]
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        reviews = (
            VLMHumanReview.objects
            .filter(completed=True)
            .select_related(
                "reviewer",
                "extraction",
                "extraction__image",
            )
            .prefetch_related(
                "claim_judgments__claim",
                "missing_claims__taxonomy_item",
            )
            .order_by(
                "extraction__model_version",
                "extraction__image__image_id",
                "reviewer_id",
            )
        )

        grouped = {}

        for review in reviews:

            condition = short_condition(
                review.extraction.model_version
            )

            grouped.setdefault(
                condition,
                [],
            ).append(review)

        if not grouped:

            self.stdout.write(
                self.style.WARNING(
                    "No completed Human Judge reviews found."
                )
            )

            return

        for condition, model_reviews in grouped.items():

            if condition == "V2_taxonomy":
                filename = (
                    "human_judge_v2_results.jsonl"
                )

            elif condition == "V3_finetuned":
                filename = (
                    "human_judge_v3_results.jsonl"
                )

            else:
                filename = (
                    f"human_judge_{condition}.jsonl"
                )

            output_path = (
                output_dir
                / filename
            )

            with output_path.open(
                "w",
                encoding="utf-8",
            ) as f:

                for review in model_reviews:

                    record = (
                        self.build_record(
                            review
                        )
                    )

                    f.write(
                        json.dumps(
                            record,
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"{condition}: {output_path}"
                )
            )

    def build_record(self, review):

        extraction = review.extraction
        image = extraction.image

        condition = short_condition(
            extraction.model_version
        )

        judgments = (
            review.claim_judgments
            .select_related("claim")
            .order_by(
                "claim__field",
                "claim__claim_order",
                "claim__id",
            )
        )

        prediction = {
            "worker_count": None,
            "ppe_compliance": None,
            "equipment": [],
            "materials_components": [],
            "hazards": [],
            "activities": [],
            "quality_observations": [],
            "stage": None,
        }

        judge = {
            "worker_count": None,
            "ppe_compliance": None,
            "equipment": [],
            "materials_components": [],
            "hazards": [],
            "activities": [],
            "quality_observations": [],
            "stage": None,
        }

        counts = Counter()

        for judgment in judgments:

            claim = judgment.claim
            field = claim.field

            verdict = VERDICT_MAP.get(
                judgment.verdict,
                judgment.verdict.upper(),
            )

            counts[verdict] += 1

            judge_item = {
                "claim": claim.claim_value,
                "verdict": verdict,

                # Human reviewer notes are the closest
                # equivalent to Gemini's evidence field.
                "evidence": (
                    judgment.notes
                    if judgment.notes
                    else ""
                ),

                # Human Judge currently evaluates visual
                # grounding rather than taxonomy correctness.
                "taxonomy_verdict":
                    "NOT_APPLICABLE",

                "matched_taxonomy_label":
                    None,
            }

            if field in SCALAR_FIELDS:

                prediction[field] = (
                    self.parse_scalar_value(
                        field,
                        claim.claim_value,
                    )
                )

                judge[field] = (
                    judge_item
                )

            elif field in LIST_FIELDS:

                prediction[field].append(
                    claim.claim_value
                )

                judge[field].append(
                    judge_item
                )

        supported = counts[
            "SUPPORTED"
        ]

        partial = counts[
            "PARTIALLY_SUPPORTED"
        ]

        unsupported = counts[
            "UNSUPPORTED"
        ]

        unanswerable = counts[
            "UNANSWERABLE"
        ]

        grounding_score = (
            compute_grounding_score(
                supported,
                partial,
                unsupported,
                unanswerable,
            )
        )

        # For the human judge, we treat each UNSUPPORTED
        # visual claim as a potential hallucination.
        visual_hallucination_count = (
            unsupported
        )

        hallucination_flag = (
            visual_hallucination_count > 0
        )

        judge.update({
            "grounding_score":
                grounding_score,

            "supported_claim_count":
                supported,

            "partially_supported_claim_count":
                partial,

            "unsupported_claim_count":
                unsupported,

            "unanswerable_claim_count":
                unanswerable,

            "visual_hallucination_count":
                visual_hallucination_count,

            "hallucination_flag":
                hallucination_flag,

            # Human review does not currently make
            # taxonomy-error judgments.
            "taxonomy_error_count":
                0,

            "overall_notes":
                review.overall_notes,
        })

        return {
            "success": True,

            "condition":
                condition,

            "human_image_id":
                image.image_id,

            "audit_id":
                self.parse_int(
                    image.audit_id
                ),

            "filename":
                image.filename,

            "prediction":
                prediction,

            "judge":
                judge,

            "judge_model":
                "human_reviewer",

            # Additional metadata that Gemini does not have,
            # but is useful for inter-rater analysis.
            "human_judge_metadata": {
                "review_id":
                    review.id,

                "reviewer_id":
                    review.reviewer_id,

                "reviewer_username":
                    review.reviewer.username,

                "started_at":
                    (
                        review.started_at.isoformat()
                        if review.started_at
                        else None
                    ),

                "completed_at":
                    (
                        review.completed_at.isoformat()
                        if review.completed_at
                        else None
                    ),
            },
        }

    def parse_scalar_value(
        self,
        field,
        value,
    ):

        if field == "worker_count":

            try:
                return int(value)

            except (
                ValueError,
                TypeError,
            ):
                return value

        return value

    def parse_int(
        self,
        value,
    ):

        try:
            return int(value)

        except (
            ValueError,
            TypeError,
        ):
            return value