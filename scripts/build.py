#!/usr/bin/env python3
"""从 src/ 生成 dist/ 与各工具入口文件。

用法:
    python scripts/build.py           # 生成
    python scripts/build.py --check   # 只校验磁盘内容是否与生成结果一致（CI 用）

设计要点:
- src/ 是唯一手写处，dist/ 与各入口文件都是生成物，改动会被 CI 打回。
- 入口文件只做指针，正文一律留在 src/，避免多份副本漂移。
- 预算超限直接失败，不写文件。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
FAMILIES = ("learn", "write", "code")

BUDGET_CORE = 900      # 常驻契约 token 上限
BUDGET_PASTE = 1200    # 粘贴版 token 上限

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FAMILY_LABEL = {
    "learn": "解题讲解",
    "write": "文档笔记",
    "code": "工程改动",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def estimate_tokens(text: str) -> int:
    """粗略估算：CJK 字符按 1 token，其余按 4 字符 1 token。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk) // 4 + 1


def strip_h1(text: str) -> str:
    """去掉首个一级标题，便于嵌入其它文档。"""
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).rstrip() + "\n"


def load_sources() -> tuple[str, dict[str, str], dict[str, dict]]:
    core = read(SRC / "core.md")
    rules = {fam: read(SRC / f"rules/{fam}.md") for fam in FAMILIES}
    schemas = {
        fam: json.loads(read(SRC / f"schemas/{fam}.json")) for fam in FAMILIES
    }
    return core, rules, schemas


def build_id(core: str, rules: dict[str, str], schemas: dict[str, dict]) -> str:
    payload = core + "\n".join(rules[f] for f in FAMILIES) + json.dumps(
        schemas, ensure_ascii=False, sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def render_paste(core: str, schemas: dict[str, dict], build: str) -> str:
    lines = [
        f"<!-- build: {build} -->",
        "",
        strip_h1(core).rstrip(),
        "",
        "## 任务族骨架速查",
        "",
    ]
    for fam in FAMILIES:
        sections = " → ".join(schemas[fam]["sections"])
        lines.append(f"- **{fam}** {FAMILY_LABEL[fam]}：{sections}")
    lines += ["", "> 细则见仓库 `src/rules/<任务族>.md`。"]
    return "\n".join(lines).rstrip() + "\n"


def render_one_pager(core: str, build: str) -> str:
    return (
        f"<!-- build: {build} -->\n\n"
        + strip_h1(core).rstrip()
        + "\n\n> 任务族与细则：learn / write / code，见 `src/rules/`。\n"
    )


def render_entries(build: str) -> dict[str, str]:
    tail = f"\n<!-- build: {build} -->\n"
    return {
        "AGENTS.md": (
            "# AGENTS.md\n\n"
            "本仓库是**模型无关的工作契约**。动手前按顺序读：\n\n"
            "1. `src/core.md` —— 常驻契约，必读，很短。\n"
            "2. 判定任务族后，只读一个：`src/rules/learn.md` / "
            "`src/rules/write.md` / `src/rules/code.md`。\n"
            "3. 判断不了任务族时，先问一句，不要猜。\n\n"
            "不要在输出里复述规则，直接遵守。\n" + tail
        ),
        "CLAUDE.md": (
            "# CLAUDE.md\n\n"
            "先读 `AGENTS.md`，再按其中顺序读 `src/core.md` 与对应任务族规则。\n"
            + tail
        ),
        "QWEN.md": (
            "# QWEN.md\n\n"
            "先读 `AGENTS.md`，再按其中顺序读 `src/core.md` 与对应任务族规则。\n"
            + tail
        ),
        ".github/copilot-instructions.md": (
            "# Copilot instructions\n\n"
            "读 `src/core.md`（常驻），再读 `src/rules/<任务族>.md` 之一。"
            "完整入口见 `AGENTS.md`。\n" + tail
        ),
        ".cursor/rules/contract.mdc": (
            "---\n"
            "description: 跨模型工作契约（先读 core，再读一个任务族规则）\n"
            "alwaysApply: true\n"
            "---\n\n"
            "读 `src/core.md`，再按任务族读 `src/rules/learn.md` | "
            "`src/rules/write.md` | `src/rules/code.md` 之一。"
            "完整说明见 `AGENTS.md`。\n" + tail
        ),
    }


def main(argv: list[str]) -> int:
    check_only = "--check" in argv

    core, rules, schemas = load_sources()
    build = build_id(core, rules, schemas)

    outputs: dict[str, str] = {
        "dist/paste-v1.md": render_paste(core, schemas, build),
        "dist/one-pager.md": render_one_pager(core, build),
        **render_entries(build),
    }

    core_tokens = estimate_tokens(core)
    paste_tokens = estimate_tokens(outputs["dist/paste-v1.md"])

    errors: list[str] = []
    if core_tokens > BUDGET_CORE:
        errors.append(f"core.md 超预算：{core_tokens} > {BUDGET_CORE} tokens")
    if paste_tokens > BUDGET_PASTE:
        errors.append(
            f"dist/paste-v1.md 超预算：{paste_tokens} > {BUDGET_PASTE} tokens"
        )
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    stale: list[str] = []
    for rel, content in outputs.items():
        path = ROOT / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(rel)
            if not check_only:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")

    if check_only:
        for rel in stale:
            print(f"DRIFT: {rel} 与 src/ 不一致，请运行 python scripts/build.py")
        if stale:
            return 1
        print(f"OK build={build} core={core_tokens}t paste={paste_tokens}t")
        return 0

    for rel in stale:
        print(f"wrote {rel}")
    print(f"build={build} core={core_tokens}t paste={paste_tokens}t")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
