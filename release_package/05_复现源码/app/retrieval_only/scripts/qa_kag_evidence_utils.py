"""Pure KAG evidence result envelope helpers."""

from typing import Any, Dict


def normalize_kag_evidence_result(
    result: Any,
    default_answer_source: str = "kag_fallback",
) -> Dict[str, Any]:
    if not isinstance(result, dict):
        result = {}

    answers = result.get("answers", [])
    if not isinstance(answers, list):
        answers = []

    cleaned_answers = []
    for item in answers:
        value = str(item or "").strip()
        if value and value not in cleaned_answers:
            cleaned_answers.append(value)

    answer_source = str(result.get("answer_source", "") or "").strip()
    if not answer_source:
        answer_source = str(default_answer_source or "kag_fallback")

    return {
        "ok": bool(result.get("ok", False)),
        "answers": cleaned_answers,
        "answer": str(result.get("answer", "") or ""),
        "answer_source": answer_source,
        "evidence_note": str(result.get("evidence_note", "") or ""),
    }


__all__ = ["normalize_kag_evidence_result"]
