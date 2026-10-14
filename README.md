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
| `canon` | 核心文档系统：定义 `docs/` 下编号的概念、设计、计划、评审、实验、调查文档，统一 frontmatter、引用格式、生命周期与归档规则，L0/L1/L2 变更分级和盲审门槛，并附带 `canon.py` 用于创建、检查、查询和归档文档 | 自动触发 |
| `canon-init` | 在仓库或 monorepo 模块中初始化 canon，把已有文档（设计说明、ADR、RFC、计划、复盘、基准测试等）迁移进来，并升级项目内的 `canon.py` | 手动 |
| `canon-sync` | 让文档与代码保持一致：改动完成后执行文档步骤（更新设计、归档完成的计划和评审等、生成提交 trailer），合并分支后修复文档，以及定期审计文档健康度 | 手动 |

### execution

| 技能 | 简介 | 触发 |
|------|------|------|
| `canon-tdd` | 测试驱动开发：在约定的 seam 上逐个红绿循环，测试只通过公开接口验证行为；seam 来自计划切片的测试标准或设计 Spec 定义的接口 | 自动触发 |
| `canon-code-review` | 评审一次改动（未提交改动或某个起点之后的 diff）：Spec 轴对照治理它的设计和计划，Standards 轴对照项目文档中的标准和坏味道基线，两个子 agent 并行、分开报告；推迟的问题写成 R 文档 | 自动触发 |
| `canon-grill` | 先分诊再追问：能查的自己查，设计已规定的照做，明显正确的直接决定，能用原型或调研回答的交给对应技能，剩下的才按轮次带推荐答案问用户，答案立即写进对应文档 | 自动触发 |
| `canon-blind-review` | 盲审：启动不带当前会话任何上下文的评审者（可用不同模型家族），只传入自包含的 prompt；覆盖 Cursor、Claude Code、Codex 子 agent，跨家族 CLI 和手动送审；用于 review gate 或任何需要独立意见的评审 | 自动触发 |
| `canon-codebase-design` | 深模块设计的共享术语和原则（module、interface、depth、seam、adapter 等），按依赖类别加深模块，以及用并行子 agent 把接口设计两遍；供设计、TDD 和评审技能引用 | 自动触发 |
| `canon-prototype` | 用临时原型回答读代码和推理都定不下来的设计或逻辑问题：状态模型的单文件可点击演示、真实页面上可切换的 UI 变体、验证可行性和性能的最小 spike；问题、结论和原型记录为 E 文档 | 自动触发 |
| `canon-investigate` | 诊断疑难 bug 和性能回退：先构造稳定的复现回路，再最小化、列出可证伪的假设、插桩、写回归测试并修复、清理；全过程记录在 I 文档中，可跨会话继续 | 自动触发 |
| `canon-research` | 在后台子 agent 中依据一手来源（官方文档、规范、源码）调研问题，带引用的结论写进 E 文档，主会话继续工作，结论再吸收进设计 | 自动触发 |
| `canon-implement` | 按已接受的计划逐个切片实现（或直接实现 L0 改动）：在计划的 seam 上 TDD，每个切片提交一次，最后整体代码评审、执行 docs step 并归档计划 | 手动 |
| `canon-design` | 通过追问用户写出或修订设计（想法不成熟时写成概念），对照术语表收敛用词，决定一项写一项，最后过 review gate 并取得用户批准 | 手动 |
| `canon-plan` | 为已接受的设计写计划：先起草按依赖排序、各带 seam 和测试标准的垂直切片，再与用户敲定未决点，过 review gate 并取得批准 | 手动 |
| `canon-handoff` | 把当前工作交给新的 Agent：先把可长期保留的状态写进 canon 文档（计划、调查、设计草稿等），再在被 git 忽略的 `.canon/canon-handoff/<会话 id>-<主题>/` 下写一份只含文档之外信息的 handoff 文件，列出恢复入口和建议使用的技能 | 手动 |
| `canon-teach` | 跨多次会话教用户新技能或概念，维护有状态的教学工作区（目标、资源、课程、速查、学习记录）；在项目仓库中运行时工作区位于被 git 忽略的 `.canon/canon-teach/<topic>/`；讲当前项目时以 canon 文档和代码为一手来源 | 手动 |
| `canon-agent-writing` | 编写给 Agent 读的文档（技能、`AGENTS.md`/`CLAUDE.md`、通过指针到达的文档）的参考：上下文指针、两种负载、信息层级与渐进披露、完成标准、引导词、剪枝，以及技能的 frontmatter 和调用方式 | 手动 |
| `canon-review` | 对模块或整个仓库做定期评审，可选架构、性能、安全、功能、易用性角度，每个角度一个并行子 agent；结果写成 R 文档和可视化 HTML 报告，每条发现由用户决定修复、移入设计/计划/调查/backlog 概念，或记录理由后否决 | 手动 |

## 目录结构

```
.
├── skills/
│   ├── execution/          # 执行类技能：直接完成具体开发任务
│   │   └── <skill-name>/
│   │       ├── SKILL.md    # 必需：frontmatter + 指令
│   │       ├── *.md        # 可选：参考资料、示例
│   │       ├── scripts/    # 可选：技能调用的脚本
│   │       └── LICENSE, NOTICE  # 移植技能必需：上游许可证与来源说明
│   └── governance/         # 治理类技能：建立和维护项目文档系统
│       └── <skill-name>/
└── scripts/
    └── validate.py         # 校验所有技能的结构与 frontmatter
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

然后编辑 `SKILL.md`：`name` 与目录名一致，`description` 写清楚「做什么」和「什么时候用」，并在上面的「技能列表」中补上一行简介。完成后校验：

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
