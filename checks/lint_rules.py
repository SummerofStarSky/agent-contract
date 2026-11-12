#!/usr/bin/env python3
"""检查契约文档自身的质量：结构、可判定性、冲突、重复。

用法:
    python checks/lint_rules.py

退出码 1 表示存在必须修的问题。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
RULES = SRC / "rules"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REQUIRED_SECTIONS = ("## 骨架", "## 硬约束", "## 例外")
MAX_RULE_LINES = 60
MAX_CORE_LINES = 60

# 空泛词：出现在规则条目里通常意味着不可判定
SOFT_WORDS = ("尽量", "适当", "酌情", "视情况", "灵活", "差不多", "大概", "比较好")

# 一条规则至少要含其中一个可判定标记
CHECKABLE_MARKERS = (
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "≤", "≥", "「", "必须", "禁止", "不得", "不要", "不",
    "每", "最多", "至少", "只", "仅", "先", "后",
)

# 互斥词组：同时出现说明规则自相矛盾
CONFLICT_PAIRS = (
    ("不外泄", "公开"),
    ("不要泄露", "公开"),
    ("private", "public"),
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def bullet_lines(text: str) -> list[tuple[str, str]]:
    """返回 (所在小节, 条目正文)，只看 - 与数字开头的条目。"""
    out: list[tuple[str, str]] = []
    section = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            section = line
            continue
        if re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            out.append((section, line.strip()))
    return out


def check_rule_file(path: Path) -> list[str]:
    problems: list[str] = []
    text = read(path)
    name = path.name

    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"{name}: 缺少小节 `{section}`")

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > MAX_RULE_LINES:
        problems.append(
            f"{name}: 行数 {len(lines)} 超过上限 {MAX_RULE_LINES}"
        )

    for section, bullet in bullet_lines(text):
        if section != "## 硬约束":
            continue
        for word in SOFT_WORDS:
            if word in bullet:
                problems.append(f"{name}: 空泛词「{word}」出现在硬约束里 → {bullet}")
        if not any(mark in bullet for mark in CHECKABLE_MARKERS):
            problems.append(f"{name}: 条目不可判定（无标记） → {bullet}")

    return problems


def check_core(path: Path) -> list[str]:
    problems: list[str] = []
    text = read(path)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) > MAX_CORE_LINES:
        problems.append(f"core.md: 行数 {len(lines)} 超过上限 {MAX_CORE_LINES}")
    if "## 5. 自检" not in text:
        problems.append("core.md: 缺少自检小节")
    for section, bullet in bullet_lines(text):
        for word in SOFT_WORDS:
            if word in bullet:
                problems.append(f"core.md: 空泛词「{word}」 → {bullet}")
    return problems


def check_duplicates(files: list[Path]) -> list[str]:
    problems: list[str] = []
    seen: dict[str, str] = {}
    for path in files:
        for section, bullet in bullet_lines(read(path)):
            if section != "## 硬约束":
                continue
            key = re.sub(r"\s+", "", bullet)
            if key in seen and seen[key] != path.name:
                problems.append(
                    f"重复条目: {seen[key]} 与 {path.name} 存在同一条 → {bullet}"
                )
            seen.setdefault(key, path.name)
    return problems


def check_conflicts(files: list[Path]) -> list[str]:
    problems: list[str] = []
    blob = "\n".join(read(p) for p in files)
    for a, b in CONFLICT_PAIRS:
        if a in blob and b in blob:
            problems.append(f"规则冲突：同时出现「{a}」与「{b}」")
    return problems


def main() -> int:
    rule_files = sorted(RULES.glob("*.md"))
    if not rule_files:
        print("ERROR: src/rules/ 下没有规则文件", file=sys.stderr)
        return 1

    problems: list[str] = []
    for path in rule_files:
        problems += check_rule_file(path)
    problems += check_core(SRC / "core.md")
    problems += check_duplicates([SRC / "core.md", *rule_files])
    problems += check_conflicts([SRC / "core.md", *rule_files])

    if problems:
        for p in problems:
            print(f"ERROR: {p}")
        print(f"\n共 {len(problems)} 个问题")
        return 1

    print(f"OK {len(rule_files)} 个规则文件，0 个问题")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
