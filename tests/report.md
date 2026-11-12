# 跨模型评测报告

## 当前状态

- 用例：20 条（learn 7 / write 6 / code 7），见 `tests/cases.jsonl`
- 已通过的门禁（本机实测，2026-11-12）：

| 门禁 | 命令 | 结果 |
|---|---|---|
| 规则自检 | `python checks/lint_rules.py` | OK，3 个规则文件，0 问题 |
| 生成物零漂移 | `python scripts/build.py --check` | OK，build=ae4cd345 |
| 正例通过 | `validate_output.py --family <f> --file src/examples/<f>/good.md` | 3/3 通过 |
| 反例失败 | 同上，指向 `bad.md` | 3/3 正确失败 |
| 预算 | `build.py` 内置 | core 389t ≤ 900，paste 486t ≤ 1200 |

- **跨模型实跑：未执行**（本机没有配置各模型的 API key）。要跑：

```bash
set CONTRACT_BASE_URL=https://api.moonshot.cn/v1
set CONTRACT_API_KEY=...
set CONTRACT_MODEL=kimi-k3
python tests/run_eval.py
```

对每个模型重复一遍，把 `tests/runs/<model>/` 的结果和通过率记到下面。

## 实测表格（待填）

| 模型 | 通道 | 通过 / 20 | 格式合格率 | 主要失败类型 |
|---|---|---|---|---|
| _待填_ | 编码 agent（有校验器） | | | |
| _待填_ | 网页粘贴（无校验器） | | | |

## 预期与判读

- 编码 agent 通道应显著高于网页通道，原因是它能跑 `validate_output.py` 并自我重试。
- 若某模型通过率低于 80%，先看失败类型：
  - **缺章节** → 模型没读到 rules，检查入口文件是否被读取。
  - **超字数** → 字数限制对弱模型太紧，考虑放宽 schema 的 `max_chars`。
  - **自检表缺失** → 自检要求写得太靠后，挪到 core 开头附近。

## 结论（待填）

> 目标：格式合格率 ≥ 90%。
