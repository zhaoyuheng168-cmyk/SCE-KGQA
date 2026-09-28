from typing import Any, Dict, List


__all__ = [
    "serialize_schema_singlehop_candidates_for_prompt",
    "normalize_schema_singlehop_candidate_id",
]


def serialize_schema_singlehop_candidates_for_prompt(candidates: List[Dict[str, Any]]) -> List[str]:
    candidate_blocks = []
    for c in candidates:
        examples = "；".join([str(x) for x in (c.get("examples") or [])[:4]])
        positive = "；".join([str(x) for x in (c.get("positive_intents") or [])[:6]])
        negative = "；".join([str(x) for x in (c.get("negative_intents") or [])[:6]])
        phrases = "；".join([str(x) for x in (c.get("natural_phrases") or [])[:10]])
        confusable_items = []
        for item in (c.get("confusable_with") or [])[:4]:
            if isinstance(item, dict):
                confusable_items.append(f"{item.get('question_type', '')}：{item.get('difference', '')}")
            else:
                confusable_items.append(str(item))
        confusable = "；".join(confusable_items)
        candidate_blocks.append(
            f"""候选ID：{c['candidate_id']}
subject：{c['subject']}
subject_types：{c.get('subject_types', [])}
question_type：{c['question_type']}
target_type：{c.get('target_type', '')}
rel：{c.get('rel', '')}
direction：{c.get('direction', '')}
简要说明：{c.get('description', '')}
语义目标：{c.get('semantic_goal', '')}
应该选择它的意图：{positive}
不要选择它的边界：{negative}
常见自然表达：{phrases}
容易混淆及区别：{confusable}
示例问法：{examples}
"""
        )
    return candidate_blocks


def normalize_schema_singlehop_candidate_id(value: Any, allowed_ids: Any) -> str:
    candidate_id = str(value or "").strip()
    if candidate_id not in allowed_ids:
        candidate_id = ""
    return candidate_id
