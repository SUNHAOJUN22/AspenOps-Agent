"""Research document parsing and fail-closed graph validation facade."""

from .research_document import (
    ResearchIssue as ResearchIssue,
)
from .research_document import (
    ResearchStudyDocument as ResearchStudyDocument,
)
from .research_document import (
    ResearchValidationReport as ResearchValidationReport,
)


def validate_research_document(data: dict[str, object]) -> ResearchValidationReport:
    return ResearchStudyDocument.from_dict(data).validate()


__all__ = [
    "ResearchIssue",
    "ResearchStudyDocument",
    "ResearchValidationReport",
    "validate_research_document",
]
