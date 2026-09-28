#!/usr/bin/env python3
"""Generate KoPL candidates from question-only input.

The script intentionally accepts no gold program, SPARQL, answer, choices, or
entity labels. Its JSONL output is suitable for a blinded non-oracle run.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import torch
from transformers import BartForConditionalGeneration, BartTokenizer


def parse_program(text: str) -> list[dict[str, object]]:
    if "<b>" in text or re.search(r"\w+\(.*\)", text):
        program = []
        for chunk in text.split("<b>"):
            chunk = chunk.strip()
            match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)\((.*)\)", chunk)
            if not match:
                if chunk:
                    program.append({"function": chunk, "inputs": []})
                continue
            function, raw_inputs = match.groups()
            inputs = [] if raw_inputs == "" else [item.strip() for item in raw_inputs.split("<c>")]
            program.append({"function": function, "inputs": inputs})
        return program

    program = []
    for chunk in text.split("<func>"):
        parts = [part.strip() for part in chunk.strip().split("<arg>")]
        if not parts or not parts[0]:
            continue
        program.append({"function": parts[0], "inputs": parts[1:]})
    return program


def read_jsonl(path: Path, start_index: int, limit: int) -> list[dict[str, object]]:
    rows = []
    seen = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if seen < start_index:
                seen += 1
                continue
            rows.append(json.loads(line))
            seen += 1
            if limit > 0 and len(rows) >= limit:
                break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work" / "kqapro_val_questions_only.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "work" / "kqapro_val_bart_top5_candidates.jsonl",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--num-beams", type=int, default=5)
    parser.add_argument("--num-candidates", type=int, default=5)
    parser.add_argument("--max-source-length", type=int, default=256)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite and not args.resume:
        raise FileExistsError(f"Refusing to overwrite: {args.output}")
    if args.num_candidates > args.num_beams:
        raise ValueError("--num-candidates cannot exceed --num-beams")

    rows = read_jsonl(args.input, args.start_index, args.limit)
    completed_ids: set[str] = set()
    if args.resume and args.output.exists():
        with args.output.open("r", encoding="utf-8") as existing:
            for line in existing:
                line = line.strip()
                if line:
                    completed_ids.add(str(json.loads(line)["question_id"]))
        rows = [row for row in rows if str(row["question_id"]) not in completed_ids]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = BartTokenizer.from_pretrained(str(args.checkpoint), local_files_only=True)
    model = BartForConditionalGeneration.from_pretrained(
        str(args.checkpoint),
        local_files_only=True,
    ).to(device)
    model.eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.resume and args.output.exists() else "w"
    with args.output.open(mode, encoding="utf-8") as handle, torch.no_grad():
        for start in range(0, len(rows), args.batch_size):
            batch = rows[start : start + args.batch_size]
            encoded = tokenizer(
                [str(row["question"]) for row in batch],
                padding=True,
                truncation=True,
                max_length=args.max_source_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            generated = model.generate(
                **encoded,
                num_beams=args.num_beams,
                num_return_sequences=args.num_candidates,
                max_new_tokens=args.max_new_tokens,
                early_stopping=True,
                return_dict_in_generate=True,
                output_scores=True,
            )
            sequences = generated.sequences
            sequence_scores = generated.sequences_scores.detach().cpu().tolist()
            decoded = tokenizer.batch_decode(
                sequences,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=True,
            )

            for offset, row in enumerate(batch):
                candidates = []
                base = offset * args.num_candidates
                for rank in range(args.num_candidates):
                    text = decoded[base + rank]
                    candidates.append(
                        {
                            "rank": rank + 1,
                            "model_score": float(sequence_scores[base + rank]),
                            "serialized_program": text,
                            "program": parse_program(text),
                        }
                    )
                output = {
                    "question_id": row["question_id"],
                    "source_index": row["source_index"],
                    "question": row["question"],
                    "generator": "official_finetuned_bart_program",
                    "checkpoint": str(args.checkpoint),
                    "candidates": candidates,
                }
                handle.write(json.dumps(output, ensure_ascii=False) + "\n")
                handle.flush()
                print(
                    f"generated {len(completed_ids) + start + offset + 1}/"
                    f"{len(completed_ids) + len(rows)} {row['question_id']}",
                    flush=True,
                )

    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(completed_ids) + len(rows),
                "new_rows": len(rows),
                "start_index": args.start_index,
                "num_candidates": args.num_candidates,
                "device": str(device),
                "gold_fields_read": [],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
