---
status: concluded
created: 2026-11-24
updated: 2026-11-25
revision: 1
modules: [canon]
summary: Of 60 sampled commits, six touched governed paths. One omitted Refs entirely and two cited some of the designs governing shared files.
refs: [D002, R006]
---

# E006: Design references in recent Canon and Silk commits

## Question

Which recent Canon and Silk commits would fail a CI check for the design IDs in a commit's `Refs:` trailer? [R006: Silk feedback on review scope and commit checks](../archived/reviews/R006-silk-review-scope-and-commit-checks.md)

## Setup

- Commit: Canon `19d59da` (v0.9.3, tool 81) and Silk `c444098`. Sample the last 30 reachable non-merge commits at each tip using Git revision order.
- Environment: Linux, Git 2.43.0 and Python 3.12.3, with both repositories' local history. The runner uses disposable clones on a filesystem supporting hard links.
- Command: `python3 docs/experiments/E006/refs-trial.py /path/to/skills /path/to/silk`; compare stdout with the [60 classified commits](E006/commits.tsv). Add `--explain 1a5d3e7` to print path-level evidence for the Silk scaffold.

The [runner](E006/refs-trial.py) calls the pinned Canon tool's `which` on historical trees. It looks up additions and modifications at the commit and deletions at the parent. Renames contribute a deletion and an addition. It also asks whether adding the parent's owners for modifications changes any verdict. A governed path contributes every governing design exactly once to the required set. The recorded trailer follows the case-insensitive line and case-sensitive ID matching used by audit. Extra IDs are allowed. [D002§unchecked-commits-in-audit: audit semantics](../designs/D002-overview-and-as-built.md#unchecked-commits-in-audit)

## Results

| Project | No governed path | No Refs line on governed change | Missing some governing IDs | Complete | Total |
|---|---:|---:|---:|---:|---:|
| Canon | 26 | 0 | 2 | 2 | 30 |
| Silk | 28 | 1 | 0 | 1 | 30 |
| Total | 54 | 1 | 2 | 3 | 60 |

- Silk `1a5d3e7` added 98 paths, of which 71 were governed by D001 through D005. Its message had no `Refs:` line. Silk `892377f` named all five owners, including the owners of deleted files. [Commit rows](E006/commits.tsv)
- Canon `26b8a9c` omitted six governing IDs and `c44410b` omitted four. Both touched shared files with nine governing designs. The messages establish which IDs were cited. They cannot establish what the authors actually reviewed. [Commit rows](E006/commits.tsv)
- The two samples contained 499 changed path entries. The parent-union check added no governing IDs for modifications. An independent rerun reproduced the table byte for byte (SHA-256 `32c020b8def0792ad1216c04d6e8db973abcd20b64cf54fab9c4cbc89ca46c1b`). [Raw data](E006/commits.tsv) · [Runner](E006/refs-trial.py)

## Conclusion

In these two 30-commit samples, requiring a relevant design reference would flag one commit. Requiring every governing ID would flag three. A future check should identify each missing design and a path that brought it into scope, restrict validation to new non-merge commits in the supplied range, and exempt commits with no governed files. An opt-in strict check would implement the full ownership rule. Before changing the default CI exit status for partial coverage, examine more shared-file changes with their maintainers. Only six commits in this sample exercised the rule.

The maintainer subsequently chose full coverage by default. On the same 60 historical commits, the implemented check reported each of the three expected failing commits and exactly its missing design IDs. [D002§design-references-in-commits: adopted behavior](../designs/D002-overview-and-as-built.md#design-references-in-commits)
