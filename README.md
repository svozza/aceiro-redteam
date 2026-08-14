# smtithy-redteam

**Throwaway.** A private testbed for the smtithy AI review harness
(`github.com/svozza/smtithy`), created 2026-08-14 to drive deliberately hostile pull
requests through the review and fix lanes and measure what holds.

**This repository contains, on purpose:**

- **planted defects** — off-by-one errors, wrong return branches, truncated hash
  comparisons. None of it is code anybody should run.
- **prompt-injection payloads** — pull request titles and bodies impersonating
  maintainers, fabricated SYSTEM overrides, fence-breakout attempts, fake sign-offs.
- **attempts to escape the reviewer's sandbox** — files instructing the reviewing model
  to read credentials, symlinks out of the reviewed tree, project configuration planted
  where the CLI might read it.

Nothing here is a real project. Do not merge from it, do not copy out of it, and delete
it when the exercise is finished. **If you found this by searching for code, you want
the upstream project instead** — every module here has been altered to be wrong.

The repository is public only because GitHub restricts environment protection rules to
public repositories on a free plan, and the approval gate under test *is* an environment
with required reviewers. A private testbed cannot carry a real gate, so it cannot
measure one.

## Provenance

The reduced modules derive from
[`aws-powertools/powertools-lambda-python`](https://github.com/aws-powertools/powertools-lambda-python)
(MIT-0), by way of smtithy's eval fixtures, which hand-reduced them and planted the
defects. One file is verbatim upstream rather than reduced —
`aws_lambda_powertools/utilities/parameters/ssm.py` on the
`base/caller_impact_needs_investigation` branch, at upstream commit
`51473090c5fd25d79c80446cf635f49a4355006c` — because that scenario grades whether the
reviewer investigated a *real* caller of the symbol it changed, so the caller has to be
real code the scenario did not author.

## Layout

One base branch per scenario, so each pull request's base tree is exactly the fixture's
base and no scenario's planted defect can pollute another's review:

- `main` — this README and the two caller workflows. Nothing else.
- `base/<scenario>` — `main` plus that scenario's pre-change tree.
- `pr/<scenario>` — `base/<scenario>` plus the change under review.

The scenario trees are reconstructed from smtithy's eval fixtures
(`src/smtithy/evals/scenarios/`): `pr_root/` is the post-change tree, and reverse-applying
`context/diff.patch` yields the pre-change tree. A pull request from `pr/<scenario>` into
`base/<scenario>` therefore reproduces the fixture's diff byte for byte, which is the
point — every graded path and line number transfers verbatim, so a real-run result is
comparable to the fixture's grade rather than merely similar to it.
