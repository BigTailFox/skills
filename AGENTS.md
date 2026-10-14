# AGENTS.md

本仓库是个人 Agent Skills 集合，通过 `npx skills`（vercel-labs/skills）安装和分发。每个技能是一个包含 `SKILL.md` 的目录，位于 `skills/execution/` 或 `skills/governance/` 下。

不要在 `skills/` 之外创建 `SKILL.md`（包括模板、示例），CLI 会把它们识别为可安装的技能。也不要添加自定义的安装脚本，安装、更新、卸载都交给 `npx skills`。

## 分类规则

- `governance/`：建立和维护一套跟随项目生命周期的文档系统，作为跨会话、跨模型长期开发的统一规范、指导、记录和信息中心。
- `execution/`：完成具体开发任务（澄清需求、写代码、测试、调试、评审等），读写项目文档时一律经由 governance 定义的文档系统。
- 拿不准时，问自己：这个技能是在建立/维护文档系统本身，还是借助它完成开发工作？前者放 `governance/`，后者放 `execution/`。

## 移植上游技能

`execution/` 主要移植自 [mattpocock/skills](https://github.com/mattpocock/skills)（MIT）。移植时：

- `SKILL.md` 及其引用的文件里不写上游链接、出处或改动说明，这些内容会占用上下文并干扰 Agent。
- 来源信息放在技能目录下：`LICENSE` 原样复制上游许可证，`NOTICE` 写明上游仓库、对应的上游技能名，并说明已做修改。
- 文档约定只遵循 governance 层的规则。上游的约定（`GLOSSARY.md`、ADR、issue tracker、`setup-matt-pocock-skills` 等）有可取之处的，先吸收进 governance，再由技能引用；移植后的技能不能再依赖或提及上游的约定。

## 技能规范

- 目录名即技能名：小写字母、数字、连字符，不超过 64 字符。技能名在整个仓库内必须唯一（跨分类也不能重复）。
- 所有技能都属于 canon 文档系统：核心技能叫 `canon`，其他技能一律用 `canon-<任务>` 命名，任务词尽量对应文档类型（`canon-design`、`canon-plan`、`canon-investigate`）。
- `npx skills` 按技能名平铺安装，分类目录不会保留。技能之间按名字引用（如「遵循 `canon` 技能」），不要用跨技能目录的相对路径；调用 `canon.py` 时使用项目 `AGENTS.md` 中给出的路径。
- `SKILL.md` 必须以 YAML frontmatter 开头，包含：
  - `name`：与目录名一致。
  - `description`：非空，不超过 1024 字符，第三人称，同时写明「做什么」和「何时使用」，包含触发关键词。
- 默认加 `disable-model-invocation: true`，只有确实需要根据上下文自动触发的技能才去掉。
- `SKILL.md` 正文控制在 500 行以内；详细资料拆到同目录的其他 `.md` 文件，并从 `SKILL.md` 直接链接（只引用一层）。
- 只写 Agent 不知道的内容，不解释常识。给一个默认做法，而不是罗列多个选项。
- 路径使用 `/`，不写有时效性的内容（如「2026 年之前用旧 API」）。
- 技能附带的脚本放在 `scripts/` 下，并在 `SKILL.md` 中说明是「执行」还是「阅读参考」。

## 工作流程

- 新建技能：在 `skills/<分类>/` 下运行 `npx skills init <name>`，然后按上面的规范补全 frontmatter（包括 `disable-model-invocation`）。
- 新增、删除技能，或改变技能的用途、触发方式时，同步更新 `README.md` 的「技能列表」。
- 修改任何技能后运行 `python3 scripts/validate.py` 和 `npx skills add . --list`，两者都通过后再提交。
- 提交信息使用 Conventional Commits，scope 用技能名，例如 `feat(canon-code-review): add security checklist`；仓库级改动不带 scope 或用 `repo`。
- 文档（`README.md`、`AGENTS.md`）用中文；技能内容用英文。
