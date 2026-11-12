# agent-contract

一份**模型无关的工作契约**：让 Kimi、千问、GPT、Claude、WorkBuddy、编码 agent 在同一类任务上产出结构一致的结果。

不是提示词集合，是**可校验的产出规范**：每类任务有固定骨架，骨架有 schema，schema 有校验器，校验器有测试集。

## 快速开始

### 1. 编码 agent（Claude Code / Codex / Cursor / Trae / Qwen Code / Kimi Code）

在仓库根目录启动 agent 即可，它会自己读入口文件：

```
AGENTS.md  → src/core.md → src/rules/<任务族>.md
CLAUDE.md / QWEN.md / .github/copilot-instructions.md / .cursor/rules/contract.mdc 都是同一入口的指针
```

把本仓库 clone 到你的工作目录旁边，或直接把 `AGENTS.md` 指过去。

### 2. 网页 / 桌面端（ChatGPT、Kimi、千问、WorkBuddy）

这些应用**读不到本地文件**，用粘贴版：

```bash
python scripts/build.py           # 生成 dist/
```

把 `dist/paste-v1.md` 全文粘进：

| 应用 | 粘到哪 |
|---|---|
| ChatGPT | Projects → 自定义指令（或对话开头） |
| Kimi 网页 | 对话开头 / 知识库文件 |
| 千问 | 智能体设定 / 对话开头 |
| WorkBuddy | 角色设定 / 知识库 |

粘贴版 ≤1200 token，是为了让弱模型也能完整吃进去。

### 3. 验证产出

```bash
python checks/validate_output.py --family learn --file 我的产出.md
python checks/validate_output.py --family write --file 我的产出.md
python checks/validate_output.py --family code  --file 我的产出.md
```

## 三个任务族

| 族 | 用途 | 骨架 |
|---|---|---|
| `learn` | 解题、概念讲解 | 结论 → 关键步骤 → 易错点 → 自检 → 延伸 |
| `write` | 文档、笔记、汇报 | 一句话结论 → 正文 → 待确认 → 自检 |
| `code` | 代码、工程改动 | 改动清单 → diff 摘要 → 验证方式 → 回滚点 → 自检 |

只有这三族。加第四族之前，先问：现有三族真的装不下吗。

## 目录

```
src/core.md                  常驻契约（唯一必读，≤900 token）
src/rules/<族>.md            任务族细则，一次只读一个
src/schemas/<族>.json        骨架 schema，供校验器使用
src/examples/<族>/good.md    正例：必须通过校验
src/examples/<族>/bad.md     反例：必须通不过校验
scripts/build.py             从 src/ 生成 dist/ 与各入口文件
checks/lint_rules.py         检查规则自身（空泛词、不可判定、冲突、重复）
checks/validate_output.py    检查产出是否符合骨架
tests/cases.jsonl            20 条评测用例
tests/run_eval.py            接任意 OpenAI 兼容接口批量评测
dist/paste-v1.md             网页端粘贴版（生成）
```

## 怎么改规则

1. 只改 `src/`，**不要手改 `dist/` 和根目录入口文件**（它们是生成物，CI 会打回）。
2. 改完跑 `python scripts/build.py`。
3. 跑 `python checks/lint_rules.py`，确认没有空泛词和冲突。
4. 跑正反例校验，确认 `good.md` 仍通过、`bad.md` 仍失败。

规则的目标是**变少**，不是变多。新增一条之前先问：这条能不能被机器判定？不能，就写进 examples，不要写进 rules。

## 预算

| 项 | 上限 | 原因 |
|---|---|---|
| `core.md` | 900 token | 常驻，每次都要读完 |
| `dist/paste-v1.md` | 1200 token | 网页端粘贴，超了会被截断 |
| 单个 rules 文件 | 60 行 | 细则只在需要时加载 |

超了 `build.py` 直接失败，不生成。

## 三类通道的一致性上限

| 通道 | 有没有校验器 | 一致性 |
|---|---|---|
| 编码 agent（有工具） | 有，能跑 `validate_output.py` | 最高 |
| 网页/桌面（只能粘贴） | 无，靠末尾自检表 | 中等 |
| 手工复制粘贴 | 无 | 低 |

**这是物理限制，不是文档能解决的。** 想要高一致性，就要让 agent 能跑校验器；跑不了，就接受它只能达到"结构大致对齐"。

## License

个人使用，未授权分发。
