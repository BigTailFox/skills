Excerpt of [Extend Claude with skills](https://code.claude.com/docs/en/skills) (raw page `https://code.claude.com/docs/en/skills.md`, fetched 2026-11-12), lines 153-220: the sections "Choose where skills load" through "Resolve skills that share a name". Fragment-only links are resolved against the page URL.

## Choose where skills load

Where you save a skill decides which sessions load it. Save it under your home directory to get it in every project, commit it to a repository to share it with everyone who works there, or distribute it through a plugin or managed settings to reach a whole team.

| Location | Path | Loads in |
| :- | :- | :- |
| Enterprise | `.claude/skills/<skill-name>/SKILL.md` in the [managed settings directory](https://code.claude.com/docs/en/managed-settings.md#delivery-mechanisms) | All users on machines where your organization deploys it |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` | All your projects on this machine, but not [Cowork or cloud sessions](https://code.claude.com/docs/en/skills#skills-in-cowork-and-cloud-sessions) |
| Project | `.claude/skills/<skill-name>/SKILL.md` | Sessions in this repository, but not [cloud threads in a project](https://code.claude.com/docs/en/claude-projects.md#what-threads-pick-up-from-your-repositories). Commit it so your team gets it too |
| Nested | `<subdir>/.claude/skills/<skill-name>/SKILL.md` | Sessions started in or below `<subdir>`, but not cloud threads in a project. Outside those threads, a session started above it loads the skill once Claude works on files there. See [monorepos and subdirectories](https://code.claude.com/docs/en/skills#discovery-from-parent-and-nested-directories) |
| Additional directory | `.claude/skills/<skill-name>/SKILL.md` in a directory you pass with `--add-dir` | That session. See [directories outside the project](https://code.claude.com/docs/en/skills#skills-from-additional-directories) |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md` | Wherever the [plugin](https://code.claude.com/docs/en/plugins/overview.md) is enabled, as `/plugin-name:skill-name` |
| claude.ai account | Skills enabled for your claude.ai account | Cowork sessions, cloud sessions, and terminal sessions where you sign in with that account. See [Skills synced from claude.ai](https://code.claude.com/docs/en/skills#how-synced-skills-behave) |

Skill folders also follow these rules:

* **Symlinked folders**: a `<skill-name>` entry in the enterprise, personal, or project location can be a symlink to a directory elsewhere on disk. Claude Code reads `SKILL.md` from the target and loads the skill once even if several locations point at the same target. Plugin skills [handle symlinks differently](https://code.claude.com/docs/en/plugins/host-marketplace.md#share-files-within-a-marketplace-with-symlinks).
* **Reserved name `synced`**: don't name a skill folder `synced`, in any capitalization. Claude Code uses `~/.claude/skills/synced/` for [skills downloaded from claude.ai](https://code.claude.com/docs/en/skills#where-synced-skills-load) and skips a skill you author at that name in the enterprise, personal, and project locations.
* **Reserved name `anthropic-skills`**: outside a plugin, a skill folder or command file whose name is `anthropic-skills` or starts with `anthropic-skills:` doesn't load. See [Names reserved for synced skills](https://code.claude.com/docs/en/skills#names-reserved-for-synced-skills).
* **Characters in the name**: outside a plugin, a skill folder doesn't load when its name has a character such as a zero-width space or `<`. See [Characters a skill name can't hold](https://code.claude.com/docs/en/skills#characters-a-skill-name-cant-hold).
* **Command files**: a Markdown file in `.claude/commands/` is the older format and still works. It supports the same [frontmatter](https://code.claude.com/docs/en/skills#frontmatter-reference) except `name` and `paths`. To find the name you type to invoke it, see [How a skill gets its command name](https://code.claude.com/docs/en/skills#how-a-skill-gets-its-command-name). Prefer a skill for new work, since skills also support [supporting files](https://code.claude.com/docs/en/skills#add-supporting-files).
* **Skill folder as a plugin**: add a `.claude-plugin/plugin.json` to a personal or project skill folder and Claude Code can load it as a [plugin](https://code.claude.com/docs/en/plugins/loading.md#plugins-shared-through-a-repository) named `<name>@skills-dir` with its own agents, hooks, and MCP servers. In a project's `.claude/skills/`, this requires accepting the workspace trust dialog first, and in either location it requires that your administrator hasn't [blocked skills-directory plugins](https://code.claude.com/docs/en/plugins/loading.md#skills-directory-plugins-blocked-by-managed-settings).

### Load skills in monorepos and subdirectories

Claude Code loads project skills from `.claude/skills/` in the directory where you start it and in every parent directory up to the repository root, so starting in `packages/frontend/` still picks up skills defined at the root. When you [move the session with `/cd`](https://code.claude.com/docs/en/permissions#move-the-session-to-another-directory) on v2.1.246 or later, Claude Code adds the new directory's project skills.

In a session running in a linked [git worktree](https://code.claude.com/docs/en/worktrees.md) that you created with `--worktree` or `git worktree add`, Claude Code searches parent directories only up to the worktree root. On Claude Code v2.1.277 or later, when the worktree checkout has no `.claude/skills` directory at its root, Claude Code loads the main checkout's project skills instead. See [What worktrees share with the main checkout](https://code.claude.com/docs/en/worktrees.md#what-worktrees-share-with-the-main-checkout).

Skills in a `.claude/skills/` directory below where you started don't load at startup. They load the first time Claude reads or edits a file in that subdirectory and stay available for the rest of the session. Until then they don't appear in the `/` menu and you can't invoke them by name. To load them sooner, run `/add-dir` with the subdirectory's path, which requires Claude Code v2.1.257 or later. For a worktree session that you start from the desktop app, see [What worktrees share with the main checkout](https://code.claude.com/docs/en/worktrees.md#what-worktrees-share-with-the-main-checkout).

When a nested skill's directory name matches another skill's name, both stay available. With a `deploy` skill at the repository root and another in `apps/web/.claude/skills/`:

* `/deploy` runs the root skill. Claude Code also lists the directory-qualified variants for Claude, with an instruction to invoke the one whose directory holds the files it's working on, so the nested skill still applies to work in `apps/web/`.
* `/apps/web:deploy` runs the nested skill on its own. Its description names the directory it applies to.

### Load skills from a directory outside the project

When you add a directory with `--add-dir` or `/add-dir`, Claude Code loads the skills in that directory's `.claude/skills/`, along with its `.claude/commands/` and `.claude/agents/`. Directories the Agent SDK adds through [`additionalDirectories`](https://code.claude.com/docs/en/agent-sdk/typescript#options) in TypeScript or [`add_dirs`](https://code.claude.com/docs/en/agent-sdk/python#claudeagentoptions) in Python load the same way, because the SDK passes them as `--add-dir`. The `permissions.additionalDirectories` setting in `settings.json` grants file access only and loads none of these.

Claude Code watches `.claude/skills/` in a directory you pass with `--add-dir` at launch, as [Edit a skill during a session](https://code.claude.com/docs/en/skills#live-change-detection) describes. It doesn't watch the added directory's `.claude/commands/` or `.claude/agents/`, so restart the session after changing a file there.

These loads depend on the `project` [setting source](https://code.claude.com/docs/en/agent-sdk/claude-code-features.md#control-filesystem-settings-with-settingsources), which is on by default. A [`strictPluginOnlyCustomization`](https://code.claude.com/docs/en/settings-reference#strictpluginonlycustomization) policy, [bare mode](https://code.claude.com/docs/en/headless.md#start-faster-with-bare-mode), and [`--safe-mode`](https://code.claude.com/docs/en/cli-reference#cli-flags) each restrict them further, as those pages describe. See [Additional directories grant file access, not configuration](https://code.claude.com/docs/en/permissions.md#additional-directories-grant-file-access-not-configuration) for the full table of what an added directory loads, including `CLAUDE.md` and plugin settings.

#### Run a same-named skill from an added directory

An added directory's skill gets a prefix when its folder name clashes with an enterprise, personal, or project skill, or one in a directory added earlier. To run it, type `/<prefix>:<skill-name>` at the Claude Code prompt. The `/` menu lists the skill under its prefixed name, and [How a skill gets its command name](https://code.claude.com/docs/en/skills#how-a-skill-gets-its-command-name) describes where the prefix comes from. That name requires Claude Code v2.1.309 or later.

For example, with `--add-dir ../cli` and a `verify` skill in both your project and `../cli`:

* `/verify` runs your project's skill
* `/cli:verify` runs the skill from `../cli`

### Resolve skills that share a name

When two skills share a directory or file name, where each one came from decides which one `/name` runs. For a name set by the frontmatter `name` field, see [How a skill gets its command name](https://code.claude.com/docs/en/skills#how-a-skill-gets-its-command-name).

| Same name in | Which one runs |
| :- | :- |
| Two of enterprise, personal, and project | Enterprise over personal, and personal over project. With `deploy` in both `~/.claude/skills/` and the project's `.claude/skills/`, `/deploy` runs the personal one |
| Any of those locations and a [bundled skill](https://code.claude.com/docs/en/skills#bundled-skills) | Your skill replaces the bundled command, but not its aliases. A project `code-review` skill replaces `/code-review`, and the bundled alias `/review` never runs your skill |
| Any of those locations and a [built-in command](https://code.claude.com/docs/en/commands.md) | In a local terminal session, your skill replaces the built-in command, but not its aliases. A project `usage` skill replaces `/usage`, and the built-in alias `/cost` still runs the built-in command |
| A skill and a file in `.claude/commands/` | The skill |
| A project-root skill and a nested skill | Both load. See [monorepos and subdirectories](https://code.claude.com/docs/en/skills#discovery-from-parent-and-nested-directories) |
| An enterprise, personal, or project skill and a skill in an [added directory outside the project](https://code.claude.com/docs/en/skills#skills-from-additional-directories) | The enterprise, personal, or project skill, while the added directory's skill runs under a prefixed name. See [run a same-named skill from an added directory](https://code.claude.com/docs/en/skills#run-a-same-named-skill-from-an-added-directory) |
| Two [added directories](https://code.claude.com/docs/en/skills#skills-from-additional-directories) outside the project | The skill from the directory added first, in `--add-dir` or `/add-dir` order. The other runs under a [prefixed name](https://code.claude.com/docs/en/skills#run-a-same-named-skill-from-an-added-directory) |
| A plugin skill and a skill at any of the locations above | Both load, because plugin skills are namespaced as `/plugin-name:skill-name` |
| Any of the above and the short name of a skill [synced from your claude.ai account](https://code.claude.com/docs/en/skills#how-synced-skills-behave) | The other skill or command. The synced skill is then listed and runs only under its full name. See [When a synced skill name matches another command](https://code.claude.com/docs/en/skills#when-a-synced-skill-name-matches-another-command) |
