from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar

from .research_common import IssueSeverity, ObjectRef, ResearchObjectType
from .research_document import ResearchIssue, ResearchStudyDocument

T = TypeVar("T")


@dataclass(slots=True)
class GraphContext:
    document: ResearchStudyDocument
    objects: dict[tuple[ResearchObjectType, str], Any]
    issues: list[ResearchIssue]

    def add(
        self,
        severity: IssueSeverity,
        code: str,
        message: str,
        ref: ObjectRef | None = None,
        path: str | None = None,
    ) -> None:
        self.issues.append(
            ResearchIssue(
                severity=severity,
                code=code,
                message=message,
                object_ref=ref,
                path=path,
            )
        )

    def resolve(self, ref: ObjectRef, *, owner: ObjectRef, path: str) -> Any | None:
        value = self.objects.get((ref.object_type, ref.object_id))
        if value is None:
            self.add(
                "error",
                "unresolved_reference",
                f"Reference does not resolve: {ref.object_type}:{ref.object_id}",
                owner,
                path,
            )
        return value

    def resolve_typed(
        self,
        ref: ObjectRef,
        expected_type: ResearchObjectType,
        expected_class: type[T],
        *,
        owner: ObjectRef,
        path: str,
        code: str,
        label: str,
    ) -> T | None:
        value = self.resolve(ref, owner=owner, path=path)
        if ref.object_type != expected_type or not isinstance(value, expected_class):
            self.add(
                "error",
                code,
                f"{label} must reference {expected_type} objects",
                owner,
                path,
            )
            return None
        return value
