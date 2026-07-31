#!/usr/bin/env python3
"""
Run every suite and summarise.

    python3 tests/run_all.py            # all suites
    python3 tests/run_all.py tak        # only suites matching "tak"

Each suite runs in its own process. That is deliberate: they set module-level
state (database path, patched smtplib, in-memory stores) that would otherwise
bleed between suites and produce results that depend on import order.

Use the interpreter that runs the app, so the dependencies are present:

    /opt/wmd-plotter/.venv/bin/python tests/run_all.py
"""

import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

# Ordered cheapest-first so an obvious break surfaces quickly.
SUITES = [
    ("TAK org scoping",   "test_tak_scoping.py"),
    ("User isolation",    "test_user_isolation.py"),
    ("Impact assessment", "test_impact.py"),
    ("Notifications",     "test_notifications.py"),
    ("Account approval",  "test_approval.py"),
    ("Password reset",    "test_password_reset.py"),
]


def main() -> int:
    pattern = sys.argv[1].lower() if len(sys.argv) > 1 else None
    suites = [(n, f) for n, f in SUITES
              if not pattern or pattern in n.lower() or pattern in f.lower()]
    if not suites:
        print(f"No suite matches {pattern!r}. Available:")
        for name, filename in SUITES:
            print(f"  {name}  ({filename})")
        return 2

    results = []
    for name, filename in suites:
        path = TESTS_DIR / filename
        if not path.exists():
            print(f"SKIP  {name} — {filename} not found")
            continue
        proc = subprocess.run([sys.executable, str(path)],
                              capture_output=True, text=True)
        output = proc.stdout
        # Suites print "N/M passed" as their last summary line.
        counts = [ln for ln in output.splitlines() if "passed" in ln and "/" in ln]
        summary = counts[-1] if counts else "no summary"
        results.append((name, proc.returncode == 0, summary, output, proc.stderr))
        status = "PASS" if proc.returncode == 0 else "FAIL"
        print(f"{status}  {name:22} {summary}")

    failed = [r for r in results if not r[1]]
    print("\n" + "=" * 64)
    print(f"{len(results) - len(failed)}/{len(results)} suites passed")

    for name, _, _, output, stderr in failed:
        print(f"\n{'-' * 64}\nFAILED: {name}\n{'-' * 64}")
        for line in output.splitlines():
            if line.startswith("FAIL") or "FAILED:" in line:
                print(" ", line)
        if stderr.strip():
            tail = [ln for ln in stderr.strip().splitlines()
                    if "bcrypt" not in ln and "passlib" not in ln][-12:]
            if tail:
                print("  stderr:")
                for line in tail:
                    print("   ", line)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
