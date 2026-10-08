"""Write or check the manifest generated from the typed temporal training protocol."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from powerlifting_state_research.contracts.serialization import canonical_json_bytes  # noqa: E402
from powerlifting_state_research.models.training import training_protocol_manifest  # noqa: E402

OUTPUT = ROOT / "artifacts/training-protocols/public-native-temporal-expert.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = canonical_json_bytes(training_protocol_manifest()) + b"\n"
    if args.check:
        if OUTPUT.read_bytes() != expected:
            parser.exit(1, "FAIL: generated training protocol manifest is stale\n")
        print("PASS: generated training protocol manifest")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(expected)
    print(OUTPUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
