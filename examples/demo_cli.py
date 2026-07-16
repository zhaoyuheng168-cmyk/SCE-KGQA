"""Run several public sample questions without Streamlit."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sce_kgqa import load_default_engine  # noqa: E402


def main() -> int:
    engine = load_default_engine()
    questions = json.loads(
        (REPO_ROOT / "examples" / "questions.json").read_text(encoding="utf-8")
    )
    for item in questions:
        result = engine.answer(item["question"])
        print(f"\nQ: {item['question']}")
        if result.refused:
            print(f"A: [拒答] {result.refusal_reason}")
        else:
            print("A: " + "；".join(result.answers))
        print(f"Route: {result.route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
