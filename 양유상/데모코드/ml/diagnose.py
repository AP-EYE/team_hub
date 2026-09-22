"""Development-only sanity checks, separate from fixed 24-case evaluation."""
import hashlib
import json
import time
from pathlib import Path
from ml.engine import LocalClassifier, SYSTEM, LABELS

ROOT = Path(__file__).resolve().parents[1]


def run(engine=None):
    engine = engine or LocalClassifier()
    cases = [
        {"id": "original-health-debug", "system": SYSTEM, "user": json.dumps({"field_path": "memo", "description": "가상 회원의 상담 내용", "value": "지난달 당뇨 진단을 받고 약물 치료를 시작했습니다."}, ensure_ascii=False), "options": list(LABELS), "expected": "A"},
        {"id": "short-en-health", "system": "Classify the text. A = a person's health information. B = an order identifier. Respond with one letter only.", "user": "Text: I was diagnosed with diabetes and started taking medication.", "options": ["A", "B"], "expected": "A"},
        {"id": "short-en-account", "system": "Classify the field. A = account identifier. B = telephone number. Respond with one letter only.", "user": "Field: member_id. Description: Unique user account identifier.", "options": ["A", "B"], "expected": "A"},
        {"id": "short-ko-health", "system": "다음 문장이 개인의 건강 상태에 관한 내용인지 분류하세요. A: 개인의 건강 정보. B: 일반적인 조언. 설명 없이 A 또는 B 하나만 답하세요.", "user": "지난주 우울증 진단을 받고 약을 먹기 시작했습니다.", "options": ["A", "B"], "expected": "A"},
        {"id": "short-ko-general", "system": "다음 문장이 개인의 건강 상태에 관한 내용인지 분류하세요. A: 개인의 건강 정보. B: 일반적인 조언. 설명 없이 A 또는 B 하나만 답하세요.", "user": "모두가 규칙적으로 운동하고 충분히 잠을 자는 것이 좋습니다.", "options": ["A", "B"], "expected": "B"},
    ]
    rows = []
    for case in cases:
        prompt = engine.tokenizer.apply_chat_template([{"role": "system", "content": case["system"]}, {"role": "user", "content": case["user"]}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        ids = engine.tokenizer.encode(prompt, add_special_tokens=False)
        slots = [engine.tokenizer.encode(letter, add_special_tokens=False) for letter in case["options"]]
        checks = [{"option": letter, "ids": token, "roundtrip": engine.tokenizer.decode(token) == letter,
                   "boundary": engine.tokenizer.encode(prompt + letter, add_special_tokens=False) == ids + token}
                  for letter, token in zip(case["options"], slots)]
        started = time.perf_counter()
        with engine.torch.inference_mode():
            logits = engine.model(input_ids=engine.torch.tensor([ids]), use_cache=False, logits_to_keep=1).logits[0, -1, :].float()
            distribution = engine.torch.softmax(logits, dim=-1)
            top = engine.torch.topk(distribution, 5)
            selected = engine.torch.softmax(logits[[token[0] for token in slots]], dim=-1).tolist()
        row = {"id": case["id"], "scope": "development diagnostic, not held-out test", "expected": case["expected"],
               "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "input_tokens": len(ids),
               "latency_ms": (time.perf_counter()-started)*1000, "slot_checks": checks,
               "top5_unconstrained": [{"token_id": int(token), "token": engine.tokenizer.decode([int(token)]), "probability": float(prob)} for token, prob in zip(top.indices, top.values)],
               "option_probabilities": dict(zip(case["options"], selected)),
               "prediction": case["options"][max(range(len(selected)), key=selected.__getitem__)]}
        rows.append(row)
        print(json.dumps({key: row[key] for key in ["id", "expected", "prediction", "top5_unconstrained", "latency_ms"]}), flush=True)
    (ROOT / "evidence/model/development-diagnostics.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


if __name__ == "__main__":
    run()
