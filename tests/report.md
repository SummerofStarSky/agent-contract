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

## 评测通道

`tests/run_eval.py` 接任意 OpenAI 兼容接口，提供两种通道（`CONTRACT_MODE`）：

| 通道 | 系统提示 | 校验器 | 自我重试 | 对应现实场景 |
|---|---|---|---|---|
| `web`（默认） | `dist/paste-v1.md` 压缩粘贴版 | 仅事后校验一次 | 无 | 网页 / 桌面端，读不到本地规则 |
| `agent` | `src/core.md` + `src/rules/<族>.md` | 每次产出后校验 | 有：报错回喂，最多 `CONTRACT_RETRIES` 次（默认 2） | 编码 agent，能读规则、跑校验器并修正 |

跑批命令：

```bash
set CONTRACT_BASE_URL=https://api.example.com/v1
set CONTRACT_API_KEY=sk-...
set CONTRACT_MODEL=some-model
set CONTRACT_MODE=both          # web + agent 各跑一遍；也可只填 web / agent
python tests/run_eval.py
```

- 原始产出：`tests/runs/<model>/<id>.md`（web）、`tests/runs/<model>/agent/<id>.md`（agent）。
- 汇总：`tests/runs/<model>/summary-web.json`、`summary-agent.json`（通过率、失败类型、每条用例尝试次数）。
- `tests/runs/` 已在 `.gitignore`，原始产出不进版本库；本报告只记录汇总结论。

## 实测表格（待真实跑批填入）

| 模型 | 通道 | 通过 / 20 | 格式合格率 | 主要失败类型 |
|---|---|---|---|---|
| _待填_ | web 网页粘贴（无校验器重试） | | | |
| _待填_ | agent 编码 agent（校验器 + 自我重试） | | | |

> 实跑前提：本机已配置可用的 OpenAI 兼容接口凭证。当前机器未配置任何模型 API key，两组数字均留空，未做估算或填充。

## 预期与判读

- agent 通道应显著高于 web 通道：它能读到完整任务族规则，并在校验器报错后自我重试；web 通道只有压缩粘贴版，且没有修正回路。
- 若某模型通过率低于 80%，先看失败类型：
  - **缺章节** → 模型没读到 rules，检查入口文件是否被读取。
  - **字数超限** → 字数限制对弱模型太紧，考虑放宽 schema 的 `max_chars`。
  - **自检表缺失 / 未填** → 自检要求写得太靠后，挪到 core 开头附近。
  - **接口异常** → 端点、key 或模型名不正确，或网络不可达。

## 结论（待填）

> 目标：格式合格率 ≥ 90%。
