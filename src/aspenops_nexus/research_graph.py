from __future__ import annotations

from typing import Literal

from .research_document import ResearchStudyDocument, ResearchValidationReport
from .research_graph_basic import validate_basic
from .research_graph_claims import validate_claims
from .research_graph_runs import validate_runs
from .research_graph_support import GraphContext


def validate_document(document: ResearchStudyDocument) -> ResearchValidationReport:
    """Validate P0 scientific governance without opening Aspen or adding execution paths."""

    context = GraphContext(document=document, objects=document._objects(), issues=[])
    validate_basic(context)
    validation_ceiling = validate_runs(context)
    computed_ceiling = validate_claims(context, validation_ceiling)
    context.issues.sort(
        key=lambda item: (
            0 if item.severity == "error" else 1,
            item.code,
            "" if item.object_ref is None else item.object_ref.object_id,
            "" if item.path is None else item.path,
        )
    )
    status: Literal["PASS", "FAIL"] = (
        "FAIL" if any(item.severity == "error" for item in context.issues) else "PASS"
    )
    return ResearchValidationReport(
        status=status,
        issues=tuple(context.issues),
        object_counts={
            "study": 1,
            "dataset": len(document.datasets),
            "target": len(document.targets),
            "parameter": len(document.parameters),
            "assumption": len(document.assumptions),
            "calibration": len(document.calibrations),
            "validation": len(document.validations),
            "claim": len(document.claims),
        },
        canonical_sha256=document.canonical_sha256(),
        computed_claim_ceiling=computed_ceiling,
    )
