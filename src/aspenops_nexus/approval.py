from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .hashing import canonical_hash

ApprovalStatus = Literal["PENDING", "APPROVED", "REJECTED", "EXPIRED", "INVALIDATED"]


def approval_binding_hash(
    *,
    request: dict[str, Any],
    model_sha256: str,
    registry_sha256: str,
    prediction: dict[str, Any],
    constraints: dict[str, Any],
    balances: dict[str, Any],
    commit: str,
) -> str:
    return canonical_hash(
        {
            "request": request,
            "model_sha256": model_sha256,
            "registry_sha256": registry_sha256,
            "prediction": prediction,
            "constraints": constraints,
            "balances": balances,
            "commit": commit,
        }
    )


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approval_id: str
    binding_sha256: str
    status: ApprovalStatus
    approver: str | None = None

    def __post_init__(self) -> None:
        if not self.approval_id.strip() or not self.binding_sha256.strip():
            raise ValueError("Approval ID and binding hash must not be blank")
        if self.status not in {"PENDING", "APPROVED", "REJECTED", "EXPIRED", "INVALIDATED"}:
            raise ValueError(f"Unsupported approval status: {self.status}")
        if self.status == "APPROVED" and (self.approver is None or not self.approver.strip()):
            raise ValueError("Approved records require an approver")

    def is_valid_for(self, binding_sha256: str) -> bool:
        return self.status == "APPROVED" and self.binding_sha256 == binding_sha256

    def invalidate_if_changed(self, binding_sha256: str) -> ApprovalRecord:
        if self.status == "APPROVED" and self.binding_sha256 != binding_sha256:
            return ApprovalRecord(
                approval_id=self.approval_id,
                binding_sha256=self.binding_sha256,
                status="INVALIDATED",
                approver=self.approver,
            )
        return self
