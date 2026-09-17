# Large diff model comparison

Measure whether Opus 4.8 and Opus 5 finish a large review within the same
50-minute budget. Prompt experiments belong here, not in production callers.

The fixture is the public [ferrumio/rboto PR #5](https://github.com/ferrumio/rboto/pull/5).
Its base and head commits are pinned in `fixture.json`. Source snapshots are
fetched at run time and treated as data; their workflows, tests, and build scripts
are never executed. No private Rito source is copied into this repository.

Two variants bracket the size of the Rito review that motivated this experiment:

| Variant | Approximate diff size | Files | Difference |
|---|---:|---:|---|
| full | 565 KB | 46 | Complete public PR |
| reduced | 228 KB | 45 | Omits `codegen/models/sns.json` from the diff and snapshots |

Both retain the generator, Python/Rust bridge, packaging, CI, tests, and examples.
The reduced case changes available evidence as well as size; it is not a pure
token-padding experiment. Compare models within the same variant first.

Use **Actions -> Large diff model benchmark -> Run workflow** on `main`.
Start with both models, the full variant, one run, and no prompt override.
Then use three repetitions and both sizes to check repeatability. Jobs run
serially to reduce provider contention. This consumes Bedrock usage.

The workflow uses the repository's existing `BEDROCK_ROLE_ARN` and runtime
environment, with an inline session policy for only the selected model.
The underlying role must also permit each selected model in `eu-west-1`.
GitHub permissions are read-only plus OIDC; nothing publishes a PR review.
The benchmark does not use the Rito CodeBuild runner or deployment role.

For prompt experiments, commit a variant under `benchmarks/large-diff/prompts/`
and pass its filename in the workflow input. The baseline uses the pinned
harness prompt. The runner records both prompt-file and assembled-prompt hashes.
First establish the unchanged-prompt model comparison, then vary one thing.

Each trial gets fresh snapshots because Aceiro redacts context and source files
in place. `PYTHONHASHSEED=0` makes redaction ordering more reproducible.
Artifacts contain per-trial `summary.json`, aggregate `results.json`, and the
harness's redacted transcript and review outputs. Summaries record elapsed time,
completion, submission/tool counts, API message counts, input sizes/hashes,
model, harness revision, and available usage data. A timeout preserves partial
counts; missing cost or output-token totals are not estimated.

An accepted artifact means it passed Aceiro's policy verifier. It does not prove
that its findings are correct. This public PR has no defects planted by this
benchmark; inspect finding quality separately from timing and completion.

To validate fixture preparation locally without invoking a model, check out the
pinned Aceiro revision and run with its installed dependencies:

```sh
PYTHONHASHSEED=0 harness/.venv/bin/python benchmarks/large-diff/run.py \
  --harness harness --model opus-4.8 --variant full --prepare-only \
  --work-dir /tmp/large-diff-work --output-dir /tmp/large-diff-results
```

Use fresh work/output directories for each invocation.
