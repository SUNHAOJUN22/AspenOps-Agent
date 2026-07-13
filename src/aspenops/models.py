"""Typed public request and result models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunState(StrEnum):
    CONVERGED = "converged"
    FAILED = "failed"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"
    NOT_RUN = "not_run"


class SessionState(StrEnum):
    OPEN = "open"
    DEAD = "dead"
    CLOSED = "closed"


class AccessMode(StrEnum):
    READ_ONLY = "read_only"
    WRITE_ONLY = "write_only"
    READ_WRITE = "read_write"


class ValueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    identifiers: dict[str, str] = Field(default_factory=dict)
    unit: str | None = None


class ValueWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: float | int | str | bool
    identifiers: dict[str, str] = Field(default_factory=dict)
    unit: str | None = None


class ValueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: float | int | str | bool | None
    unit: str | None = None
    resolved_path: str


class RunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: RunState
    elapsed_s: float = 0.0
    messages: list[str] = Field(default_factory=list)
    simulator_status: str | None = None


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inputs: dict[str, float]
    outputs: dict[str, float]
    run: RunReport
    objective: float | None = None
    constraint_violation: float = 0.0
    balance_violation: float = 0.0
    feasible: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    backend: str
    case_path: str
    alive: bool
    state: SessionState = SessionState.OPEN
    read_only: bool = False
