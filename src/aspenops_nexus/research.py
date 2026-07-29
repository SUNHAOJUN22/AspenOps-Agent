"""Fail-closed Research Study Layer contracts.

This public facade keeps the eight scientific objects separate from the Aspen execution
control plane. Phase 1 validates immutable study manifests only; it never opens a simulator.
"""

from .research_common import (
    MAX_DOCUMENT_BYTES as MAX_DOCUMENT_BYTES,
)
from .research_common import (
    MAX_JSON_DEPTH as MAX_JSON_DEPTH,
)
from .research_common import (
    RESEARCH_SCHEMA as RESEARCH_SCHEMA,
)
from .research_common import (
    ArtifactRef as ArtifactRef,
)
from .research_common import (
    Maturity as Maturity,
)
from .research_common import (
    ObjectRef as ObjectRef,
)
from .research_common import (
    ResearchObjectType as ResearchObjectType,
)
from .research_common import (
    ResearchValidationError as ResearchValidationError,
)
from .research_common import (
    SemanticBinding as SemanticBinding,
)
from .research_common import (
    SourceRef as SourceRef,
)
from .research_common import (
    _boolean as _boolean,
)
from .research_common import (
    _canonical_bytes as _canonical_bytes,
)
from .research_common import (
    _enum as _enum,
)
from .research_common import (
    _finite_number as _finite_number,
)
from .research_common import (
    _id as _id,
)
from .research_common import (
    _json_object as _json_object,
)
from .research_common import (
    _mapping as _mapping,
)
from .research_common import (
    _optional_sha256 as _optional_sha256,
)
from .research_common import (
    _optional_text as _optional_text,
)
from .research_common import (
    _refs as _refs,
)
from .research_common import (
    _reject_unknown as _reject_unknown,
)
from .research_common import (
    _safe_json as _safe_json,
)
from .research_common import (
    _scalar as _scalar,
)
from .research_common import (
    _sequence as _sequence,
)
from .research_common import (
    _sources as _sources,
)
from .research_common import (
    _strings as _strings,
)
from .research_common import (
    _text as _text,
)
from .research_common import (
    canonical_hash as canonical_hash,
)
from .research_objects import (
    Assumption as Assumption,
)
from .research_objects import (
    Calibration as Calibration,
)
from .research_objects import (
    Claim as Claim,
)
from .research_objects import (
    Dataset as Dataset,
)
from .research_objects import (
    DatasetVariable as DatasetVariable,
)
from .research_objects import (
    DatasetVariableRef as DatasetVariableRef,
)
from .research_objects import (
    Parameter as Parameter,
)
from .research_objects import (
    Study as Study,
)
from .research_objects import (
    Target as Target,
)
from .research_objects import (
    Validation as Validation,
)
from .research_validation import (
    ResearchIssue as ResearchIssue,
)
from .research_validation import (
    ResearchStudyDocument as ResearchStudyDocument,
)
from .research_validation import (
    ResearchValidationReport as ResearchValidationReport,
)
from .research_validation import (
    validate_research_document as validate_research_document,
)

__all__ = [
    "RESEARCH_SCHEMA",
    "ArtifactRef",
    "Assumption",
    "Calibration",
    "Claim",
    "Dataset",
    "DatasetVariable",
    "DatasetVariableRef",
    "Maturity",
    "ObjectRef",
    "Parameter",
    "ResearchIssue",
    "ResearchObjectType",
    "ResearchStudyDocument",
    "ResearchValidationError",
    "ResearchValidationReport",
    "SemanticBinding",
    "SourceRef",
    "Study",
    "Target",
    "Validation",
    "canonical_hash",
    "validate_research_document",
]
