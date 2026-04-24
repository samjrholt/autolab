"""Guard against personal machine details leaking into core code/tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK_ROOTS = [ROOT / "src", ROOT / "tests"]
FORBIDDEN = (
    "C:\\Users\\holtsamu",
    "/home/sam",
    "ssh wsl2",
    "wsl2",
)


def test_core_code_and_default_tests_do_not_embed_personal_setup() -> None:
    offenders: list[str] = []
    for root in CHECK_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".jsx", ".js", ".md"}:
                continue
            if path.name == "test_no_local_setup_literals.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in FORBIDDEN:
                if needle in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {needle!r}")
    assert offenders == []
