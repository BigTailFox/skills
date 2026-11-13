---
status: active
created: 2026-11-10
updated: 2026-11-13
revision: 6
modules: [canon]
summary: Prototypes and research (canon-prototype, canon-research): quick answers, the research brief, logic, UI and spike prototypes, verdicts in E docs.
refs: [D000, D003, D006, R003, D007, D009]
owns: [prototypes, research]
paths: [skills/execution/canon-prototype/SKILL.md, skills/execution/canon-prototype/LOGIC.md, skills/execution/canon-prototype/UI.md, skills/execution/canon-research/SKILL.md]
reviewed: 6
reviewers: [claude-opus-5.5]
approved: 5
implemented: 6
---

# D008: Prototypes and research

## Goals

1. A question a design or decision depends on gets evidence that reading and reasoning cannot give: a throwaway prototype (`canon-prototype`) or primary sources (`canon-research`), recorded with its verdict in an E doc a design can cite.
2. A fact one or two sources settle, or a detail inside the current task that a logic prototype or spike answers, costs no doc.
3. Recorded research runs beside the main work, every finding traces to a primary source, and a researcher that stops loses no finding it has made.
4. Prototype code wired into the product stays off the main branch, which keeps the decision, the experiment and its self-contained files.

Out of scope: the E doc type, its sections, statuses and archiving ([D006: Doc model](D006-doc-model.md)); the subagents of the canon workflow and the rule that every subagent is new, never a fork of the session ([D003: Subagents](D003-subagents.md)); grill triage, which routes questions to these skills ([D009§triage: Triage](D009-settling-decisions.md#triage)).

## Spec

"The session" is the agent following the skill. `E00X` stands for the experiment's id, and `experiments/E00X/` for its attachment directory beside it.

### Triggers

Both are auto skills ([D000§glossary: Glossary](D000-project-overview.md#glossary)): besides running as a command, each loads when the context matches its description, whose triggers are:

- `canon-research`: a design or decision depends on facts about an external library, service, protocol or standard; the user wants a topic researched or API facts gathered; grill triage routes a question here.
- `canon-prototype`: a design decision or non-obvious logic question needs evidence that reading and reasoning cannot give; the user wants to sanity-check a state model or explore what a UI should look like; grill triage routes a decision here.

Grill triage ([D009§triage: Triage](D009-settling-decisions.md#triage)) and `canon-plan`, whose slice that depends on an unanswered design question starts with a `canon-prototype` experiment, send work here by their own rules.

### Quick answers

A fact one or two primary sources settle, such as a signature, a default, a limit or a supported version, gets a direct answer: the session looks it up and replies with the source links, and writes no doc. [Recorded research](#recorded-research) applies instead when the answer will back a design decision, needs several sources weighed, or is worth running in the background.

### Recorded research

1. **Frame**: the session writes the question, the answer that would settle it, and the doc that will absorb the answer, usually the design being written or revised.
2. **Reserve**: in the main session, before any subagent starts, it looks for experiments on the same question with `canon.py find --archived`. It extends one it finds that is `planned` or `running`, or `answered` and cited by no live doc, as [D006§doc-types: doc types](D006-doc-model.md#doc-types) states, setting a `planned` or `answered` one `running` with `canon.py status`; otherwise it runs `canon.py new E <slug>`, fills Question, links each earlier experiment it found on the question, and sets it `running` with `canon.py status`.
3. **Launch**: it starts a background subagent, new as [D003§launch: launch](D003-subagents.md#launch) states, with the [research brief](#research-brief) where the host supports one, and otherwise does the research inline under the brief's rules. For a subagent it keeps the filled brief and the subagent's id in `.canon/canon-research/<E00X>/` as `brief.md` and `id.txt`; inline research keeps neither. It keeps working on what does not depend on the answer. The skill names no model.
4. **Recover**, when the host reports that the researcher stopped before finishing: the launching session resumes it once by its id where the host allows, and otherwise reruns `brief.md` once in a new subagent; a second stop goes to the user. Another session finding an experiment still `running` reruns `brief.md` only once the user confirms that no other session is running it.
5. **Absorb**, when the subagent finishes: the session opens the sources behind the findings its decision depends on and confirms they say what the experiment claims, sets the experiment `answered` with `canon.py status`, then absorbs the conclusion as [Absorbing a conclusion](#absorbing-a-conclusion) states.

### Research brief

The brief gives the subagent the experiment's path, the question, what answer would settle it, the attachment directory, the documentation language and the experiment's id, and has it research the question and record its findings in the experiment under the rules below; step 3 of [canon-research's SKILL.md](../../skills/execution/canon-research/SKILL.md) holds its wording.

- Evidence comes from primary sources only: official documentation, specifications, source code and first-party APIs. Every claim traces to the source that owns it; a secondary write-up is a lead, never evidence, and the subagent's memory is never evidence.
- The version or date each source describes is noted.
- Setup: empty `Commit`, `Environment` and `Command` lines become `- Sources:` followed by one indented line per source, as a markdown link; filled ones, from an earlier run of the same question, stay, and `- Sources:` follows them.
- Results: one finding per bullet, each linked to its source; inferences are marked as inferences, and conflicts between sources are reported.
- Conclusion: the answer, the subagent's confidence and what remains open.
- `summary`: one line that leads with the question's subject and states the answer.
- The subagent writes each finding into the experiment as soon as it has its source, so a run that stops loses nothing; a rerun keeps the findings the doc already holds and researches only what they leave open.
- Long excerpts worth keeping go in the attachment directory, linked from the doc. Each link and image target in an excerpt that is relative or starts with `/` is resolved against the source's URL into an absolute URL, so the excerpt's text stays verbatim while its links pass `check` ([D006§links-and-references: links and references](D006-doc-model.md#links-and-references)).
- Every `<!-- canon: ... -->` comment is replaced, and the doc is written in the documentation language.
- Before finishing, the subagent runs `canon.py check <E00X> --fix` and fixes the errors it reports, checking only its own doc ([D006§concurrent-work: concurrent work](D006-doc-model.md#concurrent-work)).
- The subagent modifies nothing but the experiment and its attachment directory, and keeps scratch files in `.canon/canon-research/<E00X>/scratch/`, never in the OS temp directory, reading paths there directly, since search tools that honor `.gitignore` skip `.canon/`.

### Prototype framing

A prototype is throwaway code that answers one question; the question decides its kind.

1. The session writes the question in one sentence, with the observation that would settle it.
2. When the verdict will feed a design or plan, it creates the experiment at once with `canon.py new E <slug>`, fills Question and sets it `running` with `canon.py status`, or extends or links an earlier experiment on the same question as research's Reserve step does. When the question is a detail inside the current task and the prototype is self-contained files, a logic prototype or a spike, it writes no doc: it builds in `.canon/canon-prototype/<topic>/`, records the verdict in the plan's Log or the commit message, and deletes the prototype. A UI prototype always gets an experiment, and so does a question with no design, plan or task in view, such as a state model the user wants to sanity-check, so a later design can cite its verdict.
3. It picks the kind by the question:

| Question | Kind |
|---|---|
| Does this logic or state model hold up? | [Logic prototype](#logic-prototype) |
| What should this look like? | [UI prototype](#ui-prototype) |
| Will this approach work, and how fast? | [Spike](#spike) |

When the question is ambiguous and the user is unavailable, the session picks by the surrounding code, a logic prototype for a backend module and a UI prototype for a page or component, and states the assumption at the top of the prototype.

### Prototype rules

Every kind of prototype:

1. Is throwaway from the start and named as such, its files where [Prototype files](#prototype-files) puts them.
2. Runs with one command, or is a file the user opens by double-clicking.
3. Keeps state in memory unless persistence is the question; then it uses a scratch store named so it is plainly disposable.
4. Has no tests, no error handling beyond what keeps it running, and no abstractions.
5. Renders the full relevant state after every action or variant switch.

### Logic prototype

For business logic, state transitions or data shape. The process and anti-patterns are in [LOGIC.md](../../skills/execution/canon-prototype/LOGIC.md).

- One self-contained HTML file in plain HTML, CSS and JavaScript, everything inline, with no framework, bundler or server, so it opens by double-click and can be handed to a non-developer.
- A visible intro at the top states, in one paragraph, the state model and the question.
- The logic that answers the question is a small pure module in a single `<script>` block, in the shape that fits the question: a reducer `(state, action) => state`, a state machine, pure functions over a plain data type, or a class with a clear method surface. It references no DOM, `document` or button handler; the page calls into it.
- Labels and explanations use the domain's language, not the code's.
- From top to bottom: a title with a one-line explanation; the current state as labelled fields, re-rendered after every click; one free-play button per action, always available; guided walkthroughs, one scenario per tab, each a plain-language description above its ordered step buttons, where each step performs its action and starting a walkthrough resets to a known initial state.
- The scenarios cover the happy path, a tricky edge case and an attempt at something that should be illegal.
- Styling is restrained: one accent colour and no animations.
- The session sends the file to whoever judges the model, or opens it for them, and adds actions or scenarios on request.

### UI prototype

For what a page, or a part of one, should look like. The process, an example switcher and anti-patterns are in [UI.md](../../skills/execution/canon-prototype/UI.md).

- Several variants, 3 by default and at most 5, that differ in layout, information hierarchy and primary affordance, not only in colour or copy. Each is a component with a clear exported name, `VariantA`, `VariantB`, ..., held to the page's purpose and data and built with the project's component library or styling system. Variants may share a small component such as a header but no layout, and a variant that must mutate calls a stub.
- **On an existing page**, the default, also for something that would live inside an existing page: the variants render on its route, chosen by the `?variant=` URL search parameter. The route's data fetching, parameters and auth stay; only the rendered subtree changes.
- **On a new page**, only when nothing has an existing page to live in: a throwaway route that follows the project's routing convention and is named as a prototype, such as `/prototype/<name>`, with the same parameter.
- One switcher component on the route renders the variant the parameter names, `A` when it is absent, and the floating switcher.
- The floating switcher is one shared component, placed where the project's shared UI lives: a fixed bar at the bottom centre holding a left arrow, the current variant's key with its exported name when it has one (`B (Sidebar layout)`), and a right arrow. The arrows and the `←` and `→` keys cycle through the variants, wrapping around, and set the parameter through the framework's router, so a variant can be shared and survives a reload. The keys do nothing while an `<input>`, `<textarea>` or `[contenteditable]` element has focus. The bar looks plainly separate from the page and is hidden in production builds, by `process.env.NODE_ENV !== 'production'` or an equivalent check.
- A one-line plan, such as "Three variants of the settings page, switchable via `?variant=`, on the existing `/settings` route.", sits in the prototype's location or a top-of-file comment.
- The session gives the user the URL and the variant keys.

### Spike

The smallest script that runs the approach against the real dependency and prints the result or measurement. The command that runs it goes in the experiment's Setup.

### Prototype files

- Self-contained prototype files of an experiment, such as a logic prototype's HTML file and a spike's script: `experiments/E00X/`, kept on the main branch.
- Code wired into the product, such as UI variants, the switcher and a throwaway route: a `prototype/E00X-<slug>` branch, next to the code it prototypes and following the project's conventions, never on the main branch. The branch is kept, and pushed wherever the project shares branches, so the experiment's `Commit:` stays reachable.
- A logic prototype or spike for a detail inside the current task, which has no experiment: `.canon/canon-prototype/<topic>/`, deleted once its verdict is recorded.

### Prototype verdicts

Once a prototype has answered its question, the session:

1. Fills the experiment. Setup: `Commit:` is the commit holding the prototype, on the prototype branch or the one that added `experiments/E00X/`, so the prototype is committed before Setup records it, with `Environment:` and the `Command:` that runs it; an extended experiment keeps the earlier run's lines above them. Results: what the runs or the user's walkthrough showed. Conclusion: the verdict, which for a UI prototype names the winning variant and why. `summary`: as the [research brief](#research-brief) states. Then it sets the experiment `answered` with `canon.py status`.
2. Writes the validated decision into the design or plan, as [Absorbing a conclusion](#absorbing-a-conclusion) states. The real code follows through the change's tier, in a plan slice or an L0 change, never at verdict time. There, a logic prototype's pure module lifts into the real module, and a winning UI variant is rewritten to the project's standards: into the existing page, or as a real route in place of the throwaway one.
3. Keeps the decision, the experiment and its `experiments/E00X/` files on the main branch. Code wired into the product, such as the full set of UI variants, the switcher and a throwaway route, stays only on the prototype branch.

### Absorbing a conclusion

- Research: the conclusion goes into the doc named when framing, with a link to the experiment: a design as a Spec constraint, a Budget or a Decision, a plan in its Notes.
- Prototype: while a design is being written, the session writes the decision straight into it, with a link to the experiment; a detail a plan settles within its design goes into the plan's Notes with the link ([D007§design-problems: design problems](D007-change-tiers.md#design-problems)).
- An accepted or active design changes only through the change tiers ([D007§change-tiers: change tiers](D007-change-tiers.md#change-tiers)); a prototype's session takes the verdict to the user.
- Once a design or plan links the experiment for its conclusion, the session that wrote the link sets the experiment `concluded` with `canon.py status`. Which other steps set it, what the step that does so archives of earlier experiments on the question, and when and as what an experiment is archived, is [D006§doc-types: doc types](D006-doc-model.md#doc-types)'s.

## Decisions

- Recorded research runs in a background subagent so the main work continues while it reads (a06989b, the skill's first description).
- The main session reserves the experiment's id before the subagent starts, which keeps ids unique while both sessions write docs (`canon-research`, step 2).
- The researcher writes each finding as soon as it has its source, and the launching session keeps the brief and the subagent's id, so a stopped run loses nothing and can be resumed or rerun: a researcher that wrote only at the end lost its work when it stopped, and a resume from another session failed (R003-F15; the user's decision, 2026-11-11).
- The research brief keeps the subagent's scratch files in `.canon/canon-research/<E00X>/` and says that search tools honoring `.gitignore` skip `.canon/`: subagents wrote scratch files to `/tmp`, and Cursor's Grep and Glob skipped the ignored `.canon/` ([R003: Silk design phase](../archived/reviews/R003-silk-design-phase.md), F41; 80b9688).
- A logic prototype is one self-contained file so a non-developer can open it with nothing to install, and its logic is a pure module so it lifts into the real codebase once validated (LOGIC.md).
- A UI prototype goes on an existing page whenever one could host it: on an empty route every variant looks fine, hiding problems a populated page exposes. More than 5 variants stop being radically different (UI.md).
- Code wired into the product stays on the prototype branch, since variant components and a switcher left on the main branch rot and confuse the next reader (UI.md, step 6).
- A verdict's code reaches the product through the change's tier, never at verdict time, so no code lands ahead of the design gate and plan it depends on (the user's decision, 2026-11-10).
- A UI prototype always gets an experiment: its variants render on a real route and its code lives on a branch named by the experiment's id (the user's decision, 2026-11-10).
- Both skills are auto skills, the exception the repository's Skill rules allow to the manual default for a skill that must trigger from context (`README.md`, Skills tables; reason unknown, kept as found).
