"""Command-line entry point for the sample engine."""

from __future__ import annotations

import json
import sys

from .engine import load_default_engine


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        question = input("请输入问题：").strip()
    result = load_default_engine().answer(question)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
