#!/usr/bin/env python3
"""把 tests/cases.jsonl 喂给任意 OpenAI 兼容接口，并逐条校验产出。

用法:
    set CONTRACT_BASE_URL=https://api.example.com/v1
    set CONTRACT_API_KEY=sk-...
    set CONTRACT_MODEL=some-model
    python tests/run_eval.py

只依赖标准库，不需要 pip install。
产出写到 tests/runs/<model>/<id>.md，校验结果打印成一张表。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "checks"))
from validate_output import validate  # noqa: E402

CASES = ROOT / "tests" / "cases.jsonl"
PASTE = ROOT / "dist" / "paste-v1.md"
RUNS = ROOT / "tests" / "runs"


def load_cases() -> list[dict]:
    out = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def call_api(base_url: str, api_key: str, model: str, system: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def main() -> int:
    base_url = os.environ.get("CONTRACT_BASE_URL")
    api_key = os.environ.get("CONTRACT_API_KEY")
    model = os.environ.get("CONTRACT_MODEL")

    cases = load_cases()
    if not (base_url and api_key and model):
        print("未配置接口环境变量，跳过实跑。设置后重试：")
        print("  CONTRACT_BASE_URL / CONTRACT_API_KEY / CONTRACT_MODEL")
        print(f"用例数: {len(cases)}")
        return 0

    if not PASTE.exists():
        print("ERROR: 先运行 python scripts/build.py 生成 dist/paste-v1.md")
        return 1

    system = PASTE.read_text(encoding="utf-8")
    out_dir = RUNS / model.replace("/", "_")
    out_dir.mkdir(parents=True, exist_ok=True)

    passed = 0
    for case in cases:
        try:
            text = call_api(base_url, api_key, model, system, case["prompt"])
        except (urllib.error.URLError, KeyError, TimeoutError) as exc:
            print(f"{case['id']:<4} ERROR {exc}")
            continue
        (out_dir / f"{case['id']}.md").write_text(text, encoding="utf-8", newline="\n")
        errors = validate(case["family"], text, allow_long=False)
        if errors:
            print(f"{case['id']:<4} FAIL  {errors[0]}")
        else:
            passed += 1
            print(f"{case['id']:<4} PASS")

    rate = passed / len(cases) if cases else 0
    print(f"\n{model}: {passed}/{len(cases)} 通过（{rate:.0%}）")
    return 0 if rate >= 0.9 else 1


if __name__ == "__main__":
    raise SystemExit(main())
