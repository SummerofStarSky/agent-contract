#!/usr/bin/env python3
"""把 tests/cases.jsonl 喂给任意 OpenAI 兼容接口，并逐条校验产出。

两种通道（环境变量 CONTRACT_MODE）：

- ``web``（默认）：系统提示只用 ``dist/paste-v1.md`` 粘贴版，单次调用、不重试。
  模拟网页 / 桌面端：读不到本地规则，也跑不了校验器，只能靠末尾自检表。
- ``agent``：系统提示 = ``src/core.md`` + ``src/rules/<任务族>.md``；首次产出后
  跑校验器，未通过则把报错回喂给模型自我重试（最多 CONTRACT_RETRIES 次）。
  模拟编码 agent：能读本地规则、能跑校验器并自我修正。
- ``both``：同一模型先跑 web，再跑 agent，两组汇总分别落盘。

用法::

    set CONTRACT_BASE_URL=https://api.example.com/v1
    set CONTRACT_API_KEY=sk-...
    set CONTRACT_MODEL=some-model
    set CONTRACT_MODE=web|agent|both   # 默认 web
    set CONTRACT_RETRIES=2             # 仅 agent 通道，默认 2 次
    python tests/run_eval.py

只依赖标准库，不需要 pip install。
产出写到 ``tests/runs/<model>/``，汇总写 ``summary-<mode>.json``。
``tests/runs/`` 已在 .gitignore 中，不进版本库。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "checks"))
from validate_output import validate  # noqa: E402

CASES = ROOT / "tests" / "cases.jsonl"
PASTE = ROOT / "dist" / "paste-v1.md"
CORE = ROOT / "src" / "core.md"
RULES = ROOT / "src" / "rules"
RUNS = ROOT / "tests" / "runs"

MODES = ("web", "agent")


def load_cases() -> list[dict]:
    out = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def call_api(
    base_url: str, api_key: str, model: str, messages: list[dict]
) -> str:
    payload = {"model": model, "messages": messages, "temperature": 0}
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


def web_system() -> str:
    return PASTE.read_text(encoding="utf-8")


def agent_system(family: str) -> str:
    core = CORE.read_text(encoding="utf-8")
    rule = (RULES / f"{family}.md").read_text(encoding="utf-8")
    return core + "\n\n" + rule


def categorize(errors: list[str]) -> str:
    """把校验报错归并成报告里用的失败类型。"""
    if not errors:
        return ""
    if any("缺少章节" in e for e in errors):
        return "缺章节"
    if any("未填" in e for e in errors):
        return "自检表未填"
    if any("自检表" in e for e in errors):
        return "自检表缺失"
    if any("字数超限" in e for e in errors):
        return "字数超限"
    return "其他"


def fix_instruction(errors: list[str]) -> str:
    bullet = "\n".join(f"- {e}" for e in errors)
    return (
        "上一份产出未通过本地校验器，问题如下：\n"
        f"{bullet}\n\n"
        "请严格按本任务族的固定骨架修正，重新输出完整产出；"
        "不要解释修改过程，不要省略自检表。"
    )


def run_one(
    case: dict,
    mode: str,
    base_url: str,
    api_key: str,
    model: str,
    retries: int,
) -> dict:
    family = case["family"]
    system = web_system() if mode == "web" else agent_system(family)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": case["prompt"]},
    ]

    text = call_api(base_url, api_key, model, messages)
    errors = validate(family, text, allow_long=False)
    attempts = 1

    # agent 通道：校验器报错回喂，自我重试；web 通道不重试。
    while mode == "agent" and errors and attempts <= retries:
        messages.append({"role": "assistant", "content": text})
        messages.append({"role": "user", "content": fix_instruction(errors)})
        text = call_api(base_url, api_key, model, messages)
        errors = validate(family, text, allow_long=False)
        attempts += 1

    return {
        "id": case["id"],
        "family": family,
        "mode": mode,
        "attempts": attempts,
        "passed": not errors,
        "errors": errors,
        "failure_type": categorize(errors),
        "output": text,
    }


def summarize(model: str, mode: str, records: list[dict]) -> dict:
    passed = sum(r["passed"] for r in records)
    total = len(records)
    failure_types: dict[str, int] = {}
    for r in records:
        if not r["passed"]:
            failure_types[r["failure_type"]] = failure_types.get(r["failure_type"], 0) + 1
    return {
        "model": model,
        "mode": mode,
        "total": total,
        "passed": passed,
        "rate": round(passed / total, 4) if total else 0,
        "failure_types": failure_types,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": [
            {k: v for k, v in r.items() if k != "output"} for r in records
        ],
    }


def run_mode(
    cases: list[dict],
    mode: str,
    base_url: str,
    api_key: str,
    model: str,
    retries: int,
) -> dict:
    out_dir = RUNS / model.replace("/", "_")
    if mode == "agent":
        out_dir = out_dir / "agent"
    out_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for case in cases:
        try:
            record = run_one(case, mode, base_url, api_key, model, retries)
        except (urllib.error.URLError, KeyError, TimeoutError) as exc:
            print(f"{case['id']:<4} ERROR {exc}")
            records.append(
                {
                    "id": case["id"],
                    "family": case["family"],
                    "mode": mode,
                    "attempts": 0,
                    "passed": False,
                    "errors": [f"接口异常: {exc}"],
                    "failure_type": "接口异常",
                }
            )
            continue

        (out_dir / f"{case['id']}.md").write_text(
            record["output"], encoding="utf-8", newline="\n"
        )
        if record["passed"]:
            print(f"{case['id']:<4} PASS  (attempts={record['attempts']})")
        else:
            print(f"{case['id']:<4} FAIL  {record['errors'][0]}")
        records.append(record)

    summary = summarize(model, mode, records)
    summary_path = RUNS / model.replace("/", "_") / f"summary-{mode}.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"\n[{mode}] {model}: {summary['passed']}/{summary['total']} "
        f"通过（{summary['rate']:.0%}）"
    )
    return summary


def main() -> int:
    base_url = os.environ.get("CONTRACT_BASE_URL")
    api_key = os.environ.get("CONTRACT_API_KEY")
    model = os.environ.get("CONTRACT_MODEL")
    mode = os.environ.get("CONTRACT_MODE", "web").lower()
    retries = int(os.environ.get("CONTRACT_RETRIES", "2"))

    cases = load_cases()
    if not (base_url and api_key and model):
        print("未配置接口环境变量，跳过实跑。设置后重试：")
        print("  CONTRACT_BASE_URL / CONTRACT_API_KEY / CONTRACT_MODEL")
        print("  CONTRACT_MODE=web|agent|both（默认 web）")
        print(f"用例数: {len(cases)}")
        return 0

    if mode == "both":
        modes = list(MODES)
    elif mode in MODES:
        modes = [mode]
    else:
        print(f"ERROR: CONTRACT_MODE 只能是 web / agent / both，收到 {mode}")
        return 1

    if not PASTE.exists():
        print("ERROR: 先运行 python scripts/build.py 生成 dist/paste-v1.md")
        return 1

    summaries = [
        run_mode(cases, m, base_url, api_key, model, retries) for m in modes
    ]

    # 门禁口径沿用原脚本：任一通道通过率低于 90% 即返回 1。
    low = [s for s in summaries if s["rate"] < 0.9]
    return 1 if low else 0


if __name__ == "__main__":
    raise SystemExit(main())
