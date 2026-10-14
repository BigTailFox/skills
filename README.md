# skills

个人 Agent Coding 技能仓库，用于保存和定制日常开发中使用的 Agent Skills。技能遵循 [Agent Skills 规范](https://agentskills.io)，通过 [`skills`](https://github.com/vercel-labs/skills) CLI（`npx skills`）安装到 Cursor、Claude Code、Codex 等 Agent。

## 定位

技能分为两层：

- **governance（治理层）**：建立并维护一套跟随项目生命周期的文档系统，作为跨会话、跨模型长期开发的统一规范、指导、记录和信息中心。
- **execution（执行层）**：完成具体开发任务。主要移植 [mattpocock/skills](https://github.com/mattpocock/skills)（MIT）中的常用技能，文档约定统一改用 governance 层的规则；上游约定中可取的部分会选择性吸收进 governance。

## 技能列表

「自动触发」表示 Agent 会根据上下文自行加载；其余技能需要手动调用（如 `/canon-init`）。

### governance

| 技能 | 简介 | 触发 |
|------|------|------|
| `canon` | 核心文档系统：定义 `docs/` 下编号的概念、设计、计划、评审、实验、调查文档，统一 frontmatter、引用格式、生命周期与归档规则，L0/L1/L2 变更分级和盲审门槛，评审模型与推理等级的默认配置，并附带 `canon.py` 用于创建、检查、查询和归档文档 | 自动触发 |
| `canon-init` | 在仓库或 monorepo 模块中初始化 canon，把已有文档（设计说明、ADR、RFC、计划、复盘、基准测试等）迁移进来，在 `AGENTS.md` 记下跨家族评审模型（`Reviewers:` 行），并升级项目内的 `canon.py` | 手动 |
| `canon-sync` | 让文档与代码保持一致：改动完成后执行文档步骤（更新设计、归档完成的计划和评审等、生成 `Refs:` 提交 trailer），合并分支后修复文档，以及定期审计文档健康度（有未核对代码提交的设计、闲置文档、到期的评审） | 手动 |

### execution

| 技能 | 简介 | 触发 |
|------|------|------|
| `canon-tdd` | 测试驱动开发：在约定的 seam 上逐个红绿循环，变绿后顺手重构，测试只通过公开接口验证行为；seam 来自计划切片的测试标准或设计 Spec 定义的接口；完成标准是测试标准通过且原本绿的没有变红 | 自动触发 |
| `canon-code-review` | 评审一次完整的改动（未提交改动、未跟踪的新文件或某个起点之后的 diff）：Spec 轴对照治理它的设计和计划，Standards 轴对照项目文档中的标准和坏味道基线。强度按层级分三档：不改行为的小 L0 自查，其他 L0 和 L1 一个子 agent 兼看两轴，L2 或大范围改动两轴并行且 L2 首轮加跨家族评审者；修复后由原评审者确认一次，推迟的问题写成 R 文档 | 自动触发 |
| `canon-grill` | 先分诊再追问：能查的自己查，设计已规定的照做，明显正确的直接决定，能用原型或调研回答的交给对应技能，剩下的才按轮次带推荐答案问用户，答案立即写进对应文档 | 自动触发 |
| `canon-blind-review` | 盲审：首轮启动不带当前会话任何上下文的评审者（可用不同模型家族），只传入自包含的 prompt；修复后恢复同一批评审者的会话确认问题是否解决；优先用宿主原生子 agent（Cursor 从 `Reviewers:` 行读评审模型，GPT 模型一律走 codex CLI），其次跨家族 CLI（codex、claude、gemini、agent），最后手动送审；用于 review gate 或任何需要独立意见的评审 | 自动触发 |
| `canon-codebase-design` | 深模块设计的共享术语和原则（module、interface、depth、seam、adapter 等），按依赖类别加深模块，以及用并行子 agent 把接口设计两遍；供设计、TDD 和评审技能引用 | 自动触发 |
| `canon-prototype` | 用临时原型回答读代码和推理都定不下来的设计或逻辑问题：状态模型的单文件可点击演示、真实页面上可切换的 UI 变体、验证可行性和性能的最小 spike；问题、结论和原型记录为 E 文档 | 自动触发 |
| `canon-investigate` | 诊断疑难 bug 和性能回退（快速修复无效、原因不明、偶发或变慢，或用户要求诊断时）：先构造稳定的复现回路，再最小化、列出可证伪的假设、插桩、写回归测试并修复、清理；全过程记录在 I 文档中，可跨会话继续。原因一眼可见的 bug 直接按 L0 修 | 自动触发 |
| `canon-research` | 依据一手来源（官方文档、规范、源码）回答问题：一两个来源就能定的事实直接带链接回答；要支撑设计决策的，在后台子 agent 中调研，带引用的结论写进 E 文档，主会话继续工作，结论再吸收进设计 | 自动触发 |
| `canon-implement` | 按已接受的计划逐个切片实现（或直接实现 L0 改动、无需计划的 L1 设计修订）：主会话负责编排，每个切片交给一个新的 worker 子 agent 在计划的 seam 上 TDD；普通切片 medium 推理，标了 `Risk:` 的切片 high，worker 解释不了失败时自动换 high 重试；主会话验证后每个切片提交一次，最后整体代码评审、执行 docs step（记录设计的 `implemented`）并归档计划 | 手动 |
| `canon-design` | 通过追问用户写出或修订设计（想法不成熟时写成概念），对照术语表收敛用词，决定一项写一项，最后过 review gate，并给出下一阶段的命令；L2 设计由用户启动下一阶段时批准 | 手动 |
| `canon-plan` | 为已接受的设计写计划：先起草按依赖排序、各带 seam 和测试标准的垂直切片（涉及复杂逻辑、并发、性能、安全或数据迁移的切片标 `Risk:`），再与用户敲定未决点，过 review gate，并给出实现命令；L2 计划由用户启动实现时批准 | 手动 |
| `canon-handoff` | 把当前工作交给新的 Agent：先把可长期保留的状态写进 canon 文档（计划、调查、设计草稿等），再在被 git 忽略的 `.canon/canon-handoff/<会话 id>-<主题>/` 下写一份只含文档之外信息的 handoff 文件，列出恢复入口和建议使用的技能 | 手动 |
| `canon-teach` | 教用户新技能或概念：单个问题直接讲一次；要系统学习时跨多次会话授课，维护有状态的教学工作区（目标、资源、课程、速查、学习记录）；在项目仓库中运行时工作区位于被 git 忽略的 `.canon/canon-teach/<topic>/`；讲当前项目时以 canon 文档和代码为一手来源 | 手动 |
| `canon-agent-writing` | 编写给 Agent 读的文档（技能、`AGENTS.md`/`CLAUDE.md`、通过指针到达的文档）的参考：上下文指针、两种负载、信息层级与渐进披露、完成标准、引导词、剪枝，以及技能的 frontmatter 和各宿主的调用开关 | 手动 |
| `canon-review` | 对模块或整个仓库做定期评审，可选架构、性能、安全、功能、易用性角度，每个角度一个并行子 agent；结果写成 R 文档，需要时再生成可视化 HTML 报告，每条发现由用户决定修复、移入设计/计划/调查/backlog 概念，或记录理由后否决；能当场修的 L0/L1 问题先给出修复计划，用户批准后执行 | 手动 |

## 目录结构

```
.
├── skills/
│   ├── execution/          # 执行类技能：直接完成具体开发任务
│   │   └── <skill-name>/
│   │       ├── SKILL.md    # 必需：frontmatter + 指令
│   │       ├── *.md        # 可选：参考资料、示例
│   │       ├── scripts/    # 可选：技能调用的脚本
│   │       ├── agents/openai.yaml  # 手动技能必需：让 Codex 也不隐式调用
│   │       └── LICENSE, NOTICE  # 移植技能必需：上游许可证与来源说明
│   └── governance/         # 治理类技能：建立和维护项目文档系统
│       └── <skill-name>/
├── scripts/
│   └── validate.py         # 校验技能结构、frontmatter、链接、README 技能列表和 CANON_VERSION，并运行 tests/
└── tests/
    └── test_canon.py       # canon.py 的回归测试
```

技能必须放在 `skills/<分类>/<技能名>/SKILL.md`，这是 `npx skills` 能识别的分类目录布局。不要在 `skills/` 之外放 `SKILL.md`，否则会被 CLI 当成可安装的技能。

### 分类

| 分类 | 放什么 | 例子 |
|------|--------|------|
| `execution/` | 借助文档系统完成开发工作的技能 | 需求澄清、TDD、调试、Code Review（多移植自 mattpocock/skills） |
| `governance/` | 建立和维护项目文档系统本身的技能 | 文档系统初始化、规范与决策记录、随生命周期更新文档 |

## 新增技能

```bash
cd skills/execution && npx skills init canon-my-task && cd -
```

然后编辑 `SKILL.md`：`name` 与目录名一致，`description` 按 `AGENTS.md` 的规范写（自动触发的技能把触发条件放在前面，手动技能写一行摘要）；手动技能再加 `agents/openai.yaml`。最后在上面的「技能列表」中补上一行简介。完成后校验：

```bash
python3 scripts/validate.py
npx skills add . --list        # 确认 CLI 能发现该技能
```

## 安装与分发

推送到远程仓库后，在任意机器上安装（`-g` 为用户级安装，所有项目可用）：

```bash
npx skills add <git-url> -g                         # 交互式选择技能和 Agent
npx skills add <git-url> -g --skill canon-my-task -a cursor -a claude-code -y
npx skills update -g                                # 拉取仓库最新版本
npx skills ls -g                                    # 查看已安装技能
npx skills remove canon-my-task -g
```

本地调试未推送的改动时，直接从本地路径安装：

```bash
npx skills add ~/my/skills -g --skill canon-my-task -a cursor -y
```

本地路径安装的是一份副本，`npx skills update` 不会跟踪本地来源；修改后重新执行同一条 `add` 命令即可覆盖。

## 宿主验证清单

装到新宿主、宿主大版本升级，或改了 description、调用开关、盲审启动方式之后，在 Cursor、Claude Code、Codex 上各做一遍：

| 项目 | 做法 | 期望 |
|------|------|------|
| 技能发现 | 打开宿主的技能列表（Codex 用 `/skills`） | 18 个技能都在，自动触发技能的触发条件没有被截掉 |
| 手动调用 | 输入 `/canon-sync`（Codex 用 `$canon-sync`） | 技能加载并按步骤执行 |
| 手动技能不被隐式调用 | 新会话里说「帮我同步一下文档」，不点名技能 | `canon-sync` 不会自动加载 |
| 隐式调用 | 新会话里说「这个测试偶发失败，帮我查原因」 | 自动加载 `canon-investigate` |
| 子 agent | 对一份 L2 设计跑 review gate | A1、A2 都是新的子 agent，只收到评审 prompt；确认轮恢复的是同一批评审者 |
| 降级路径 | 在不能直接启动其他家族模型的宿主上跑 A2 | 依次尝试已安装的 CLI，都不可用时给出可复制的手动送审 prompt |
| Cursor 调 GPT | 在 Cursor 里用 GPT 作 A2 跑 review gate | A2 通过 `codex exec` 在 Cursor 沙箱外运行，确认轮用 `codex exec resume` 恢复同一会话 |
| 按切片派发 worker | 用 `/canon-implement` 实现一份含 `Risk:` 切片的计划 | 每个切片一个新 worker，`Risk:` 切片以 high 推理运行；主会话不停下来请你切换推理等级，由它更新计划并提交 |

Cursor 里 GPT 模型一律通过 codex CLI 调用，并且要在 Cursor 的沙箱外运行，因为 codex 要把会话写进 `~/.codex`，确认轮靠它恢复。其他模型用 Task 工具，而 Task 只有在用户明确要求时才换模型，推理等级也由模型名决定。所以评审模型要写进项目 `AGENTS.md` 或用户规则，GPT 用 codex 的模型 id，例如 `Reviewers: A2 = gpt-6-astra, gemini-4-argon-medium`。codex 不指定模型时用的是它自己的默认模型，不一定是旗舰。实现阶段的 worker 同理：Cursor 里 worker 默认继承会话的模型和推理等级，要让 `Risk:` 切片用 high，就在 `Workers:` 行写明对应的模型名，例如会话用 Sonnet 5.5 medium 时写 `Workers: high = claude-sonnet-5-5-high`。
