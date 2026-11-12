#!/usr/bin/env python3
"""校验某份产出是否符合任务族骨架。

用法:
    python checks/validate_output.py --family learn --file out.md
    python checks/validate_output.py --family write --file out.md --allow-long

退出码 0 = 合格，1 = 不合格。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "src" / "schemas"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize(line: str) -> str:
    s = line.strip()
    s = s.lstrip("#").strip()
    s = re.sub(r"^\d+[.、]\s*", "", s)
    s = s.replace("**", "").strip()
    return s


def matches(line: str, name: str) -> bool:
    s = normalize(line)
    if s == name:
        return True
    for sep in (" ", "—", "：", ":", "·"):
        if s.startswith(name + sep):
            return True
    return False


def body_chars(text: str, exclude_table: bool) -> int:
    total = 0
    for line in text.splitlines():
        if exclude_table and line.strip().startswith("|"):
            continue
        total += len(line.strip())
    return total


def validate(family: str, text: str, allow_long: bool) -> list[str]:
    schema = json.loads(read(SCHEMAS / f"{family}.json"))
    errors: list[str] = []
    lines = text.splitlines()

    for section in schema["sections"]:
        if not any(matches(line, section) for line in lines):
            errors.append(f"缺少章节: {section}")

    if schema.get("requires_self_check"):
        header = schema.get("self_check_header", "| 依据")
        if header not in text:
            errors.append("缺少自检表（表头应为 `| 依据 | ...`）")
        if "✔" not in text and "✓" not in text:
            errors.append("自检表未填（未发现 ✔）")

    limit = schema["max_chars"]
    counted = body_chars(
        text, exclude_table=not schema.get("count_self_check_in_length", False)
    )
    if not allow_long and counted > limit:
        errors.append(f"字数超限: {counted} > {limit}（可用 --allow-long 放行）")

    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=["learn", "write", "code"])
    parser.add_argument("--file", required=True)
    parser.add_argument("--allow-long", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: 文件不存在 {path}", file=sys.stderr)
        return 1

    errors = validate(args.family, read(path), args.allow_long)
    if errors:
        for e in errors:
            print(f"FAIL {path.name}: {e}")
        return 1

    print(f"OK {args.family}: {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
