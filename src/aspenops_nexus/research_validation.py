"""Research document parsing and fail-closed graph validation facade."""

from .research_document import (
    ResearchIssue as ResearchIssue,
    ResearchStudyDocument as ResearchStudyDocument,
    ResearchValidationReport as ResearchValidationReport,
)
from .research_graph import validate_document


def validate_research_document(data: dict[str, object]) -> ResearchValidationReport:
    return ResearchStudyDocument.from_dict(data).validate()


__all__ = [
    "ResearchIssue",
    "ResearchStudyDocument",
    "ResearchValidationReport",
    "validate_research_document",
]
