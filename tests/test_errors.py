from aspenops_nexus.errors import (
    ERROR_BY_CODE,
    AspenOpsError,
    ComTransportError,
    UnitError,
    WorkerCrashError,
    classify_exception,
)


def test_error_codes_are_unique_and_stable() -> None:
    assert len(ERROR_BY_CODE) == 20
    assert len(ERROR_BY_CODE) == len(set(ERROR_BY_CODE))
    assert ERROR_BY_CODE["UNIT_ERROR"] is UnitError


def test_structured_error_preserves_context() -> None:
    error = UnitError("invalid pressure unit", context={"field": "pressure"})
    assert error.to_dict() == {
        "code": "UNIT_ERROR",
        "message": "invalid pressure unit",
        "retryable": False,
        "context": {"field": "pressure"},
    }


def test_retryable_errors_are_explicitly_allowlisted() -> None:
    retryable = {code for code, error_type in ERROR_BY_CODE.items() if error_type.retryable}
    assert retryable == {"COM_TRANSPORT_ERROR", "WORKER_CRASH_ERROR"}
    assert ComTransportError.retryable
    assert WorkerCrashError.retryable


def test_unknown_errors_default_to_nonretryable() -> None:
    classified = classify_exception(ValueError("bad input"))
    assert classified == {
        "code": "UNCLASSIFIED_ERROR",
        "message": "bad input",
        "retryable": False,
        "context": {"exception_type": "ValueError"},
    }


def test_known_errors_keep_stable_classification() -> None:
    classified = classify_exception(AspenOpsError("failure", context={"stage": "solve"}))
    assert classified["code"] == "ASPENOPS_ERROR"
    assert classified["retryable"] is False
    assert classified["context"] == {"stage": "solve"}
