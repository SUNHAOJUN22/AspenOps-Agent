from pathlib import Path

import pytest

from aspenops_nexus.errors import AuthorizationError, ValidationError, classify_exception
from aspenops_nexus.policy import Policy, PolicyError


def test_policy_validates_mode_and_normalizes_roots(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported policy mode"):
        Policy("unsafe", ())
    policy = Policy("default", (tmp_path, tmp_path / "."))
    assert policy.allowed_roots == (tmp_path.resolve(),)


def test_path_must_remain_inside_allowed_roots(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    policy = Policy("default", (root,))
    assert policy.assert_path(root / "case.bkp") == (root / "case.bkp").resolve()
    with pytest.raises(PolicyError, match="outside"):
        policy.assert_path(tmp_path / "outside.bkp")


def test_input_file_checks_type_size_suffix_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    source = root / "request.json"
    source.write_text("{}", encoding="utf-8")
    policy = Policy("default", (root,))
    assert policy.assert_input_file(source, max_bytes=2, suffixes=(".json",)) == source.resolve()
    with pytest.raises(ValidationError, match="maximum"):
        policy.assert_input_file(source, max_bytes=1)
    with pytest.raises(ValidationError, match="suffix"):
        policy.assert_input_file(source, suffixes=(".bkp",))
    with pytest.raises(ValidationError, match="regular file"):
        policy.assert_input_file(root)

    link = root / "request-link.json"
    link.symlink_to(source)
    with pytest.raises(PolicyError, match="Symbolic-link"):
        policy.assert_input_file(link)


def test_output_path_checks_parent_suffix_root_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    policy = Policy("default", (root,))
    target = policy.assert_output_path(
        root / "nested" / "results.json",
        suffixes=(".json",),
        create_parent=True,
    )
    assert target.parent.is_dir()
    with pytest.raises(ValidationError, match="suffix"):
        policy.assert_output_path(root / "results.txt", suffixes=(".json",))
    with pytest.raises(PolicyError, match="outside"):
        policy.assert_output_path(tmp_path / "outside.json", create_parent=True)

    real = root / "real.json"
    real.write_text("{}", encoding="utf-8")
    link = root / "link.json"
    link.symlink_to(real)
    with pytest.raises(PolicyError, match="Symbolic-link"):
        policy.assert_output_path(link)


def test_mode_errors_have_stable_authorization_classification() -> None:
    readonly = Policy("readonly", ())
    with pytest.raises(PolicyError) as captured:
        readonly.assert_writes_allowed()
    assert isinstance(captured.value, AuthorizationError)
    assert classify_exception(captured.value)["code"] == "AUTHORIZATION_ERROR"

    default = Policy("default", ())
    with pytest.raises(PolicyError):
        default.assert_enhanced()
    Policy("enhanced", ()).assert_enhanced()


def test_path_rejects_blank_nul_and_excessive_text() -> None:
    policy = Policy("default", ())
    for invalid in ("", "   ", "a\x00b", "x" * 4097):
        with pytest.raises(ValidationError):
            policy.assert_path(invalid)
