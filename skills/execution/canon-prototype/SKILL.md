---
name: canon-prototype
description: Builds a throwaway prototype to answer one design or logic question that reading and reasoning cannot settle. The forms are a clickable single-file demo for state models and business rules, switchable UI variants on a real page, or a minimal spike for "will this approach work, and how fast". The question, verdict and prototype are recorded as a canon experiment. Use when a design decision or non-obvious logic question needs evidence, when the user wants to sanity-check a state model or explore what a UI should look like, or when grill triage routes a decision here.
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides the shape.

## 1. Frame

Write the question in one sentence, plus the observation that would settle it.

- The verdict will feed a design or plan: create the experiment now with `canon.py new E <slug>` and fill its Question. Self-contained prototype files go in `experiments/E00X/`.
- The question is a detail inside the current task: skip the doc. Build in `.canon/canon-prototype/<topic>/`, record the verdict in the plan's Log or the commit message, and delete the prototype.

## 2. Pick a branch

- **"Does this logic or state model hold up?"** → [LOGIC.md](LOGIC.md): one shareable HTML file with free-play buttons and guided walkthroughs that push the model through cases hard to reason about on paper.
- **"What should this look like?"** → [UI.md](UI.md): several radically different variants on one route, switchable from a floating bar.
- **"Will this approach work, and how fast?"** → a spike: the smallest script that runs the approach against the real dependency and prints the result or measurement. It lives in `experiments/E00X/`, and its run command goes in Setup.

If the question is ambiguous and the user is unavailable, pick the branch matching the surrounding code (backend module → logic, page or component → UI) and state the assumption at the top of the prototype.

## Rules for every branch

1. **Throwaway from day one, and named as such.** A prototype wired into product code (UI variants, a throwaway route) lives on a `prototype/E00X-<slug>` branch, next to the code it prototypes, following the project's conventions.
2. **Trivial to run.** One command, or a file the user double-clicks.
3. **No persistence by default.** State lives in memory unless persistence is the question; then use a scratch store named so it is obviously disposable.
4. **Skip the polish.** No tests, no error handling beyond what keeps it runnable, no abstractions.
5. **Surface the state.** After every action or variant switch, render the full relevant state so the change is visible.

## 3. Capture

1. Fill the experiment:
   - **Setup**: `Commit:` is the commit holding the prototype, either on the prototype branch or the one that added `experiments/E00X/`. Also fill `Environment:` and the `Command:` that runs it.
   - **Results**: what the runs or the user's walkthrough showed.
   - **Conclusion**: the verdict and where it was absorbed.
2. Fold the validated decision into the real code and into the design. While a design is being written, write the decision straight into it. An accepted or active design changes only through the tier flow in the `canon` skill, so take the verdict to the user.
3. Main keeps the decision, the experiment and its `experiments/E00X/` files. Code wired into the product stays only on the prototype branch.
4. The docs step archives the experiment as `concluded` once a design absorbs it.
