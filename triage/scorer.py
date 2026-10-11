"""
Scorer for triage benchmark.

Usage: python scorer.py <output.json> <expected.json>

output.json must contain:
  {"findings": [{"case_id": "...", "severity": "...", "hot_spot": "..."}, ...]}

expected.json is a flat array with one entry per case.

Scoring per case (max 1.0):
  - NONE expected + any finding reported: 0.0 (false positive)
  - severity exact match: 0.6 pts
  - severity adjacent (one level off): 0.3 pts
  - severity two+ levels off: 0.0 pts
  - hot_spot match: 0.4 pts (only when severity is not NONE)

Returns a float 0.0-1.0 printed to stdout.
Exit code 0 on success, 1 on error.
"""

import json
import sys

SEVERITY_ORDER = ["NONE", "INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def load_json(path: str):
    with open(path) as f:
        return json.load(f)


def normalize(s: str) -> str:
    return s.strip().lower().replace(" ", "_").replace("-", "_")


def severity_score(expected_sev: str, output_sev: str) -> float:
    e = expected_sev.strip().upper()
    o = output_sev.strip().upper()
    if e == o:
        return 0.6
    try:
        ei = SEVERITY_ORDER.index(e)
        oi = SEVERITY_ORDER.index(o)
        if abs(ei - oi) == 1:
            return 0.3
    except ValueError:
        pass
    return 0.0


def score_case(output: dict, expected: dict) -> float:
    exp_sev = expected.get("severity", "NONE").strip().upper()
    out_sev = output.get("severity", "NONE").strip().upper()

    if exp_sev == "NONE":
        return 0.0 if out_sev != "NONE" else 1.0

    if out_sev == "NONE":
        return 0.0

    score = severity_score(exp_sev, out_sev)

    exp_hot = normalize(expected.get("hot_spot", ""))
    out_hot = normalize(output.get("hot_spot", ""))
    if exp_hot and out_hot and exp_hot == out_hot:
        score += 0.4

    return min(1.0, score)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python scorer.py <output.json> <expected.json>", file=sys.stderr)
        sys.exit(1)

    output_path, expected_path = sys.argv[1], sys.argv[2]

    try:
        output_data = load_json(output_path)
        expected_data = load_json(expected_path)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading files: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(expected_data, list):
        print("expected.json must be a JSON array", file=sys.stderr)
        sys.exit(1)

    output_findings: list[dict] = output_data.get("findings", [])
    output_by_id: dict[str, dict] = {
        f["case_id"]: f for f in output_findings if "case_id" in f
    }

    total_cases = len(expected_data)
    if total_cases == 0:
        print("1.0")
        return

    total_score = 0.0
    for case in expected_data:
        case_id = case.get("id", "")
        if case_id not in output_by_id:
            # No answer submitted for this case: no credit. Previously an absent
            # case defaulted to severity "NONE" and scored 1.0 on clean contracts.
            continue
        total_score += score_case(output_by_id[case_id], case)

    final_score = total_score / total_cases
    print(f"{final_score:.4f}")


if __name__ == "__main__":
    main()
