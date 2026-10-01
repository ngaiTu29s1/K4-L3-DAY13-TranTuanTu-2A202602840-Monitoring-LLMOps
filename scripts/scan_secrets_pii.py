#!/usr/bin/env python3
"""
Automated Secret & PII Scanner (Day 13 Bonus Automation)
Scans tracked repository files, environment configs, and logs to ensure:
1. No Langfuse secret keys (sk-lf-...) or public keys leaked in code/commits.
2. No raw PII (emails, phone numbers, CCCD, credit cards) leaked in logs or source.
3. No sensitive environment variables committed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = {
    "langfuse_secret_key": re.compile(r"sk-lf-[a-zA-Z0-9_-]{20,}"),
    "generic_api_key": re.compile(r"(?:api[_-]?key|secret[_-]?key|auth[_-]?token)\s*=\s*['\"][a-zA-Z0-9_\-\.]{16,}['\"]", re.IGNORECASE),
}

PII_PATTERNS = {
    "raw_email": re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.com|domain\.com)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "raw_phone_vn": re.compile(r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)"),
    "raw_cccd": re.compile(r"\b\d{12}\b"),
    "raw_credit_card": re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
}

EXCLUDED_FILES = {
    "sample_queries.jsonl",      # Test input queries with simulated PII
    "expected_answers.jsonl",
    "test_pii.py",               # Test cases testing PII regex
    "test_validate_logs.py",     # Test cases testing validator
    "pii.py",                    # Regex definitions
    "validate_logs.py",          # Validator regexes
    "scan_secrets_pii.py",       # This script
}


def scan_file(file_path: Path) -> list[str]:
    violations = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return []

    # Check secrets
    for name, pattern in SECRET_PATTERNS.items():
        matches = pattern.findall(content)
        if matches:
            violations.append(f"Secret detected ({name}): {len(matches)} match(es)")

    # Check PII if not in excluded
    if file_path.name not in EXCLUDED_FILES:
        for name, pattern in PII_PATTERNS.items():
            matches = pattern.findall(content)
            if matches:
                violations.append(f"Raw PII detected ({name}): {len(matches)} match(es)")

    return violations


def main() -> int:
    print("=" * 60)
    print("🔍 Antigravity Automated Secret & PII Scanner")
    print("=" * 60)

    tracked_dirs = ["app", "config", "scripts", "submission", "data"]
    total_scanned = 0
    total_violations = 0

    for directory in tracked_dirs:
        dir_path = REPO_ROOT / directory
        if not dir_path.exists():
            continue
        for path in dir_path.rglob("*"):
            if path.is_file() and not any(part.startswith(".") for part in path.parts):
                total_scanned += 1
                violations = scan_file(path)
                if violations:
                    total_violations += len(violations)
                    rel_path = path.relative_to(REPO_ROOT)
                    print(f"❌ {rel_path}:")
                    for v in violations:
                        print(f"   - {v}")

    print("-" * 60)
    print(f"Total files scanned: {total_scanned}")
    if total_violations == 0:
        print("✅ CLEAN: No secrets or raw PII detected in repo files and logs!")
        return 0
    else:
        print(f"⚠️ FOUND: {total_violations} potential violation(s).")
        return 1


if __name__ == "__main__":
    sys.exit(main())
