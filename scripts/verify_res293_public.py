from __future__ import annotations

import sys

from powerlifting_state_research.studies.res293_public_verification import (
    PublicVerificationError,
    verify_public_run,
)


def main() -> int:
    try:
        receipt = verify_public_run()
    except PublicVerificationError as error:
        print(f"RES-293 public verification: FAIL ({error})", file=sys.stderr)
        return 1
    print(
        "RES-293 public verification: PASS "
        f"(truth={receipt['truth_source']}; "
        f"{receipt['published_artifacts_verified']} public artifacts; "
        f"{receipt['validation_metrics_recomputed']} validation metrics; "
        f"{receipt['primary_contrasts_recomputed']} primary contrasts; "
        "checkpoint files read=0)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
