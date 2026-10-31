#!/usr/bin/env python3
"""Check tracked Markdown local links, image files and heading anchors without network access."""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Frozen report links are preserved; the current reader notice supplies these destinations.
FROZEN_LINK_CORRECTIONS = {
    (
        "results/studies/synthetic_pretraining_transfer/public-native/report.md",
        link,
    ): "studies/synthetic_pretraining_transfer/" + name
    for name in ("historical-lineage.md", "protocol.json")
    for link in ("../../../studies/synthetic_pretraining_transfer/" + name,)
}


def anchors(content: str) -> set[str]:
    counts: Counter[str] = Counter()
    result: set[str] = set()
    for line in re.sub(r"```.*?```|~~~.*?~~~", "", content, flags=re.S).splitlines():
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            heading = re.sub(r"<[^>]+>", "", match[1]).lower()
            slug = re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")
            result.add(slug if not counts[slug] else f"{slug}-{counts[slug]}")
            counts[slug] += 1
    result.update(re.findall(r"<(?:a|h[1-6])\s+[^>]*(?:id|name)=[\'\"]([^\'\"]+)", content))
    return result


def check(root: Path, paths: list[str]) -> list[str]:
    errors: list[str] = []
    for name in paths:
        source = root / name
        content = re.sub(r"```.*?```|~~~.*?~~~", "", source.read_text(), flags=re.S)
        # shortcut: inline Markdown destinations only; add reference-link parsing if adopted.
        for match in re.finditer(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", content):
            link = match[1].strip("<>")
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            correction = FROZEN_LINK_CORRECTIONS.get((name, link))
            if correction:
                target = root / correction
            reason = ""
            if not target.is_relative_to(root.resolve()):
                reason = "outside repository"
            elif not target.exists():
                reason = "missing target"
            elif parsed.fragment and target.is_file() and target.suffix == ".md":
                if unquote(parsed.fragment) not in anchors(target.read_text()):
                    reason = "missing heading anchor"
            if reason:
                line = content.count("\n", 0, match.start()) + 1
                errors.append(f"{name}:{line}: {reason}: {link}")
    return errors


def main() -> int:
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT
        )
        .decode()
        .split("\0")
    )
    markdown = sorted({name for name in paths if name.endswith(".md")})
    errors = check(ROOT, markdown)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: local links, image targets and heading anchors in {len(markdown)} Markdown files")
    print(
        "Two frozen report links use the corrections in docs/studies/g4-reader-corrections-v1.md."
    )
    print("External URLs are not fetched; reference-style destinations are not checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
