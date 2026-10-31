import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_documentation_links", ROOT / "scripts/check_documentation_links.py"
)
assert _spec is not None and _spec.loader is not None
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)


def test_local_links_images_anchors_and_escape(tmp_path: Path) -> None:
    (tmp_path / "other.md").write_text("# Results & limits\n# Results & limits\n")
    (tmp_path / "figure.svg").write_text("<svg/>")
    page = tmp_path / "page.md"
    page.write_text(
        "[ok](other.md#results--limits-1) ![figure](figure.svg) "
        "[remote](https://example.org/absent)\n```sh\n[x](absent)\n```\n"
    )
    assert checker.check(tmp_path, ["page.md"]) == []
    page.write_text("[x](other.md#missing) ![x](missing.svg) [x](../outside.md)")
    errors = checker.check(tmp_path, ["page.md"])
    assert len(errors) == 3
    assert "missing heading anchor" in errors[0]
    assert "missing target" in errors[1]
    assert "outside repository" in errors[2]
