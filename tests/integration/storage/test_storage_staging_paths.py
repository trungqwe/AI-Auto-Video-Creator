"""I-06: resolve_staging_path chặn đường dẫn thoát staging root (CT-STO-004, CT-STO-008 điều 5)."""
import os
import pathlib
import sys

import pytest

from controlplane.infrastructure.storage.staging_paths import StagingPathError, resolve_staging_path

BS = chr(92)
RESERVED = ["CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))]


@pytest.fixture
def root(tmp_path: pathlib.Path) -> pathlib.Path:
    staging = tmp_path / "staging"
    staging.mkdir()
    return staging


@pytest.mark.parametrize(
    "relative",
    [
        "",
        "../../x",
        "a/../../x",
        "a/..",
        "a/.. /x",
        "/x",
        BS + "x",
        "C:/x",
        "C:x",
        "c:" + BS + "x",
        "//server/share/x",
        BS * 2 + "server" + BS + "share" + BS + "x",
        "a//b",
        "a/./b",
        "a/",
        None,
        7,
    ],
)
def test_rejects_empty_absolute_drive_unc_parent_and_non_string(root, relative):
    with pytest.raises(StagingPathError):
        resolve_staging_path(root, relative)


@pytest.mark.parametrize(
    "relative",
    [
        "a" + chr(0) + "b.mp4",
        "a<b",
        "a>b",
        'a"b',
        "a|b",
        "a?b",
        "a*b",
        "a:b",
        "dir/a" + chr(31) + "b",
        "dir/a" + chr(10) + "b",
    ],
)
def test_rejects_nul_forbidden_windows_and_control_characters(root, relative):
    with pytest.raises(StagingPathError):
        resolve_staging_path(root, relative)


@pytest.mark.parametrize("case", [str.upper, str.lower, str.title])
@pytest.mark.parametrize("suffix", ["", ".mp4", ".tar.gz", " ", "."])
@pytest.mark.parametrize("name", RESERVED)
def test_rejects_reserved_device_names(root, name, suffix, case):
    for relative in (case(name) + suffix, "nested/" + case(name) + suffix):
        with pytest.raises(StagingPathError):
            resolve_staging_path(root, relative)


def make_symlink(link: pathlib.Path, target: pathlib.Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"không tạo được symlink trong môi trường này: {exc}")


def make_junction(link: pathlib.Path, target: pathlib.Path) -> None:
    if sys.platform != "win32":
        pytest.skip("junction chỉ tồn tại trên Windows")
    import _winapi

    _winapi.CreateJunction(str(target), str(link))


LINK_MAKERS = [pytest.param(make_symlink, id="symlink"), pytest.param(make_junction, id="junction")]


@pytest.fixture
def outside(tmp_path: pathlib.Path) -> pathlib.Path:
    out_dir = tmp_path / "outside"
    out_dir.mkdir()
    (out_dir / "secret.txt").write_text("secret", encoding="utf-8")
    return out_dir


@pytest.mark.parametrize("make_link", LINK_MAKERS)
@pytest.mark.parametrize("relative", ["link", "link/x.mp4", "link/secret.txt", "link/sub/x.mp4"])
def test_rejects_link_pointing_outside_root(root, outside, make_link, relative):
    make_link(root / "link", outside)
    with pytest.raises(StagingPathError):
        resolve_staging_path(root, relative)


@pytest.mark.parametrize("make_link", LINK_MAKERS)
def test_rejects_link_pointing_inside_root(root, make_link):
    real = root / "real"
    real.mkdir()
    make_link(root / "alias", real)
    with pytest.raises(StagingPathError):
        resolve_staging_path(root, "alias/x.mp4")


@pytest.mark.parametrize("make_link", LINK_MAKERS)
def test_rejects_intermediate_link_below_existing_directory(root, outside, make_link):
    (root / "job-01").mkdir()
    make_link(root / "job-01" / "link", outside)
    with pytest.raises(StagingPathError):
        resolve_staging_path(root, "job-01/link/x.mp4")


@pytest.mark.parametrize("make_link", LINK_MAKERS)
def test_containment_check_rejects_escape_even_if_link_detection_is_blind(root, outside, make_link, monkeypatch):
    make_link(root / "link", outside)
    monkeypatch.setattr(pathlib.Path, "is_symlink", lambda self: False)
    monkeypatch.setattr(pathlib.Path, "is_junction", lambda self: False)
    with pytest.raises(StagingPathError):
        resolve_staging_path(root, "link/secret.txt")


def test_accepts_nested_path_and_returns_resolved_absolute_path(root):
    result = resolve_staging_path(root, "job-01/stage-02/out.mp4")
    assert result == (root / "job-01" / "stage-02" / "out.mp4").resolve()
    assert result.is_absolute()
    assert result.is_relative_to(root.resolve())


def test_accepts_existing_directory_and_file(root):
    job_dir = root / "job-01"
    job_dir.mkdir()
    out_file = job_dir / "out.mp4"
    out_file.write_bytes(b"x")
    assert resolve_staging_path(root, "job-01/out.mp4") == out_file.resolve()
    assert resolve_staging_path(root, "job-01") == job_dir.resolve()


def test_accepts_backslash_separator_as_nested_path(root):
    assert resolve_staging_path(root, "job-01" + BS + "out.mp4") == (root / "job-01" / "out.mp4").resolve()


@pytest.mark.parametrize(
    "relative",
    ["CONSOLE.mp4", "COM10", "LPT0", "aux_1/x.bin", "a.b/c.d", "con-x/nul2.mp4"],
)
def test_accepts_names_that_only_resemble_reserved_names(root, relative):
    assert resolve_staging_path(root, relative) == (root / pathlib.Path(relative)).resolve()
