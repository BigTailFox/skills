# skills

个人 Agent Coding 技能仓库，用于保存和定制日常开发中使用的 Agent Skills。技能遵循 [Agent Skills 规范](https://agentskills.io)，通过 [`skills`](https://github.com/vercel-labs/skills) CLI（`npx skills`）安装到 Cursor、Claude Code、Codex 等 Agent。

## 目录结构

```
.
├── skills/
│   ├── execution/          # 执行类技能：直接完成具体开发任务
│   │   └── <skill-name>/
│   │       ├── SKILL.md    # 必需：frontmatter + 指令
│   │       ├── *.md        # 可选：参考资料、示例
│   │       └── scripts/    # 可选：技能调用的脚本
│   └── governance/         # 治理类技能：规范、评审与流程把关
│       └── <skill-name>/
└── scripts/
    └── validate.py         # 校验所有技能的结构与 frontmatter
```

技能必须放在 `skills/<分类>/<技能名>/SKILL.md`，这是 `npx skills` 能识别的分类目录布局。不要在 `skills/` 之外放 `SKILL.md`，否则会被 CLI 当成可安装的技能。

### 分类

| 分类 | 放什么 | 例子 |
|------|--------|------|
| `execution/` | 产出代码或改动的技能 | 脚手架生成、调试流程、重构、写测试、提交信息 |
| `governance/` | 约束和检查工作方式的技能 | 代码规范、Code Review、安全检查、架构决策记录、发布流程 |

## 新增技能

```bash
cd skills/execution && npx skills init my-skill && cd -
```

然后编辑 `SKILL.md`：`name` 与目录名一致，`description` 写清楚「做什么」和「什么时候用」。完成后校验：

```bash
python3 scripts/validate.py
npx skills add . --list        # 确认 CLI 能发现该技能
```

## 安装与分发

推送到远程仓库后，在任意机器上安装（`-g` 为用户级安装，所有项目可用）：

```bash
npx skills add <git-url> -g                         # 交互式选择技能和 Agent
npx skills add <git-url> -g --skill my-skill -a cursor -a claude-code -y
npx skills update -g                                # 拉取仓库最新版本
npx skills ls -g                                    # 查看已安装技能
npx skills remove my-skill -g
```

本地调试未推送的改动时，直接从本地路径安装：

```bash
npx skills add ~/my/skills -g --skill my-skill -a cursor -y
```

本地路径安装的是一份副本，`npx skills update` 不会跟踪本地来源；修改后重新执行同一条 `add` 命令即可覆盖。
