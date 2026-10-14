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

暂无。

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
