"""Recompute a documented strict-name candidate rate from the stored survey JSON.

No network requests are made. The 30-spec sample is provider-distinct and seeded;
it is for failure-mode inspection, not an unbiased precision estimate.
"""

import json
import random
import re
from pathlib import Path

SOURCE = Path(__file__).with_name("authz_signal_survey.json")
BIG = ("azure.com", "googleapis.com", "amazonaws.com", "microsoft.com")
VIS = re.compile(
    r"^(visibility|is_?public|is_?private|public|private|"
    r"privacy(_?(level|setting|status))?)$",
    re.I,
)
SHARE = re.compile(
    r"^(shared_?with|sharing|share_?settings|collaborators|acl|acls|"
    r"access_?control(_?list)?|allowed_?users)$",
    re.I,
)


def candidate(row):
    hits = row["hits"]
    return any(VIS.fullmatch(name) for name in hits["VIS"]) or any(
        SHARE.fullmatch(name) for name in hits["SHARE"]
    )


def main():
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    eligible = [row for row in rows if row["ok"] and row["get_ops"] > 0]
    for label, subset in (
        ("all", eligible),
        ("excluding_big_cloud", [
            row for row in eligible
            if not any(domain in row["api"] for domain in BIG)
        ]),
    ):
        found = [row for row in subset if candidate(row)]
        print(f"{label}: {len(found)}/{len(subset)} = {len(found)/len(subset):.1%}")
        print(
            "provider IDs:",
            len({row["api"].split(":")[0] for row in found}),
            "/",
            len({row["api"].split(":")[0] for row in subset}),
        )
        if label == "excluding_big_cloud":
            by_provider = {}
            for row in found:
                by_provider.setdefault(row["api"].split(":")[0], row["api"])
            sample = random.Random(20260929).sample(sorted(by_provider.values()), 30)
            print("provider-distinct sample (seed 20260929):")
            for api_id in sample:
                print(api_id)


if __name__ == "__main__":
    main()
