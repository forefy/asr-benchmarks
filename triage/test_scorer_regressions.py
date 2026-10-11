"""Regression tests for triage/scorer.py.

Run from the repo root with the triage corpus checked out:
    python test_scorer_regressions.py triage/scorer.py triage/expected.json

Both tests FAIL against scorer.py as of commit 3343c9ef and PASS once
scorer.patch is applied.

The empty-submission bug lives in scorer.main()'s aggregation loop, not in
score_case(), so that test must run the scorer as a subprocess exactly the way
a benchmark run invokes it. Reimplementing the aggregation in the test would
silently re-add the fix and the test would pass against unpatched code.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile


def load_scorer(path):
    spec = importlib.util.spec_from_file_location("scorer_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_scorer(scorer_path, findings, expected_path):
    """Invoke the scorer as a real run does and return the float it prints."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "output.json")
        with open(out, "w") as f:
            json.dump({"findings": findings}, f)
        proc = subprocess.run(
            [sys.executable, "-I", scorer_path, out, expected_path],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"scorer exited {proc.returncode}: {proc.stderr.strip()}")
        return float(proc.stdout.strip())


def test_empty_submission_scores_zero(scorer_path, expected_path):
    """An answer sheet with no answers must score 0.0.

    Before the fix, an absent case fell through to `output = {}`, whose severity
    defaulted to "NONE", which then matched every expected-NONE case for full
    credit. With 5 of 12 cases expected NONE, an empty file scored 0.4167 --
    identical to the benchmark's published best_score at the time.
    """
    got = run_scorer(scorer_path, [], expected_path)
    assert got == 0.0, f"empty submission scored {got:.4f}, expected 0.0"


def test_partial_submission_gets_no_free_credit(scorer_path, expected_path):
    """Answering only the cases you are sure of must not beat answering none."""
    expected = json.load(open(expected_path))
    first = expected[0]
    findings = [{
        "case_id": first["id"],
        "severity": first.get("severity", "NONE"),
        "hot_spot": first.get("hot_spot", ""),
        "rationale": "single answered case",
    }]
    got = run_scorer(scorer_path, findings, expected_path)
    ceiling = 1.0 / len(expected)
    assert got <= ceiling + 1e-9, (
        f"one correct answer out of {len(expected)} scored {got:.4f}, "
        f"which exceeds the {ceiling:.4f} ceiling -- unanswered cases earned credit"
    )


def test_info_is_on_the_severity_ladder(scorer_path):
    """program.md defines INFO between LOW and NONE, so it needs adjacency credit.

    SEVERITY_ORDER omitted INFO, so severity_score() raised ValueError and
    returned 0.0 for every INFO comparison except an exact string match.
    """
    scorer = load_scorer(scorer_path)
    assert "INFO" in scorer.SEVERITY_ORDER, "INFO missing from SEVERITY_ORDER"
    adjacent = scorer.severity_score("INFO", "LOW")
    assert adjacent == 0.3, f"INFO vs LOW scored {adjacent}, expected 0.3 (adjacent)"


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(2)
    scorer_path, expected_path = sys.argv[1], sys.argv[2]

    tests = [
        ("empty_submission_scores_zero",
         lambda: test_empty_submission_scores_zero(scorer_path, expected_path)),
        ("partial_submission_gets_no_free_credit",
         lambda: test_partial_submission_gets_no_free_credit(scorer_path, expected_path)),
        ("info_is_on_the_severity_ladder",
         lambda: test_info_is_on_the_severity_ladder(scorer_path)),
    ]

    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures.append(name)
            print(f"FAIL  {name}: {e}")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
