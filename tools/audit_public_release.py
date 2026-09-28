#!/usr/bin/env python3
"""Scan a release tree without printing possible secret values.

The report records rule names, paths, line numbers and short SHA-256
fingerprints. It never copies the matched value into the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


TEXT_SUFFIXES = {
    ".cfg", ".conf", ".csv", ".env", ".ini", ".json", ".jsonl", ".md",
    ".properties", ".py", ".rst", ".sh", ".toml", ".tsv", ".txt", ".xml",
    ".yaml", ".yml",
}

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

CRITICAL_RULES = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "generic_sk_token": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "credential_in_url": re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@", re.I),
}

REVIEW_RULES = {
    "prc_id_candidate": re.compile(
        r"(?<!\d)[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])"
        r"(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)"
    ),
    "cn_mobile_candidate": re.compile(r"(?<![A-Za-z0-9_.])1[3-9]\d{9}(?![A-Za-z0-9_])"),
    "email_candidate": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "private_server_reference": re.compile(r"(?:root@|js3\.blockelite\.cn)", re.I),
}

PASSWORD_ASSIGNMENT = re.compile(
    r"(?i)\b(?P<name>(?:[A-Za-z0-9_]*_)?(?:password|passwd|pwd|api[_-]?key|secret|token))\b[\"']?\s*[:=]\s*[\"'](?P<value>[^\"'\r\n]+)[\"']"
)

NLP_TOKEN_FIELDS = {'bos_token', 'eos_token', 'unk_token', 'sep_token', 'pad_token', 'cls_token', 'mask_token'}

PLACEHOLDER_PARTS = {
    "", "change_me", "change-this-local-password", "example", "export-in-shell-only",
    "none", "null", "placeholder", "set", "your_key_here", "your-password", "请自行设置",
}


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Dockerfile", "LICENSE"}


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


def looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().strip("<>[](){}\"'").lower()
    if lowered in PLACEHOLDER_PARTS:
        return True
    return (
        lowered.startswith("${")
        or "example" in lowered
        or "placeholder" in lowered
        or "change_me" in lowered
        or "自行设置" in lowered
    )


def scan(root: Path) -> dict:
    findings: list[dict] = []
    scanned_files = 0
    scanned_bytes = 0
    skipped_binary = 0
    read_errors = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name.startswith("PUBLIC_RELEASE_SAFETY_SCAN"):
            continue
        if path.relative_to(root).parts[0] == "runtime_data":
            continue
        if not is_text_file(path):
            skipped_binary += 1
            continue
        scanned_files += 1
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, 1):
                    scanned_bytes += len(line.encode("utf-8", errors="replace"))
                    for severity, rules in (("critical", CRITICAL_RULES), ("review", REVIEW_RULES)):
                        for rule, pattern in rules.items():
                            for match in pattern.finditer(line):
                                findings.append(
                                    {
                                        "severity": severity,
                                        "rule": rule,
                                        "path": path.relative_to(root).as_posix(),
                                        "line": line_no,
                                        "fingerprint": fingerprint(match.group(0)),
                                    }
                                )
                    for match in PASSWORD_ASSIGNMENT.finditer(line):
                        if match.group('name').lower() in NLP_TOKEN_FIELDS:
                            continue
                        value = match.group('value')
                        if (match.group('name').lower() in {'confirm_token', 'confirmation_token'}
                                and re.fullmatch(r'RUN_[A-Z0-9_]+', value)):
                            continue
                        if not looks_like_placeholder(value):
                            findings.append(
                                {
                                    "severity": "critical",
                                    "rule": "nonplaceholder_credential_assignment",
                                    "path": path.relative_to(root).as_posix(),
                                    "line": line_no,
                                    "fingerprint": fingerprint(value),
                                }
                            )
        except OSError as exc:
            read_errors.append({"path": path.relative_to(root).as_posix(), "error_type": type(exc).__name__})

    findings.sort(key=lambda item: (item["severity"], item["rule"], item["path"], item["line"]))
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "skipped_binary_files": skipped_binary,
        "critical_count": sum(f["severity"] == "critical" for f in findings),
        "review_count": sum(f["severity"] == "review" for f in findings),
        "read_errors": read_errors,
        "findings": findings,
    }


def write_markdown(result: dict, path: Path) -> None:
    counts = Counter((item["severity"], item["rule"]) for item in result["findings"])
    lines = [
        "# Public release safety scan",
        "",
        f"- Generated (UTC): `{result['generated_at_utc']}`",
        f"- Text files scanned: `{result['scanned_files']}`",
        f"- Text bytes scanned: `{result['scanned_bytes']}`",
        f"- Critical findings: `{result['critical_count']}`",
        f"- Review findings: `{result['review_count']}`",
        "",
        "Possible secret values are intentionally omitted. Fingerprints are truncated SHA-256 values.",
        "",
        "## Summary",
        "",
        "| Severity | Rule | Count |",
        "|---|---|---:|",
    ]
    for (severity, rule), count in sorted(counts.items()):
        lines.append(f"| {severity} | `{rule}` | {count} |")
    lines.extend(["", "## Findings", "", "| Severity | Rule | File | Line | Fingerprint |", "|---|---|---|---:|---|"])
    for item in result["findings"]:
        lines.append(
            f"| {item['severity']} | `{item['rule']}` | `{item['path']}` | "
            f"{item['line']} | `{item['fingerprint']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    result = scan(root)
    json_path = args.json or root / "PUBLIC_RELEASE_SAFETY_SCAN.json"
    markdown_path = args.markdown or root / "PUBLIC_RELEASE_SAFETY_SCAN.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(result, markdown_path)
    print(
        json.dumps(
            {
                "scanned_files": result["scanned_files"],
                "critical_count": result["critical_count"],
                "review_count": result["review_count"],
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
        )
    )
    return 1 if result["critical_count"] or result["read_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
