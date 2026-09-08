from __future__ import annotations

from aspenops_nexus.batch import expand_batch_document


def test_expanded_requests_inherit_the_selected_backend() -> None:
    requests = expand_batch_document(
        {
            "model_path": "case.bkp",
            "registry_path": "registry.json",
            "points": [{}, {}],
        },
        default_backend="aspen_plus",
    )

    assert [request.backend for request in requests] == ["aspen_plus", "aspen_plus"]


def test_explicit_backend_still_overrides_the_default() -> None:
    requests = expand_batch_document(
        {
            "backend": "hysys",
            "model_path": "case.hsc",
            "registry_path": "registry.json",
            "points": [{}],
        },
        default_backend="aspen_plus",
    )

    assert requests[0].backend == "hysys"
