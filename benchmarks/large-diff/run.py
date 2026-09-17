"""Compare model completion on a pinned public PR; never execute its source."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
MODELS = {
    "opus-4.8": "global.anthropic.claude-opus-4-8[1m]",
    "opus-5": "global.anthropic.claude-opus-5[1m]",
}


def git(repository: Path, *arguments: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True, capture_output=True,
    ).stdout


def load_fixture(path: Path) -> dict:
    fixture = json.loads(path.read_text())
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", fixture["repository"]):
        raise ValueError("fixture repository must be owner/name")
    for name in ("base_sha", "head_sha", "harness_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", fixture[name]):
            raise ValueError(f"{name} must be a full commit SHA")
    for paths in fixture["variants"].values():
        for name in paths:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("excluded paths must stay inside the fixture")
    return fixture


def export_tree(repository: Path, sha: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    archive = git(repository, "archive", "--format=tar", sha)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        # Mirrors quarantine's exclusion of symlinks; Git metadata is not archived.
        members = [member for member in source.getmembers()
                   if member.isfile() or member.isdir()]
        source.extractall(destination, members=members, filter="data")


def prepare(repository: Path, fixture: dict, variant: str, destination: Path) -> dict:
    """Build a fresh context and independent snapshots for one trial."""
    excluded = fixture["variants"][variant]
    paths = [".", *(f":(exclude){path}" for path in excluded)]
    base, head = fixture["base_sha"], fixture["head_sha"]
    diff = git(repository, "diff", "--no-ext-diff", "--no-textconv",
               "--no-renames", "--binary", base, head, "--", *paths)
    changed = git(repository, "diff", "--name-only", "--no-renames", "-z",
                  base, head, "--", *paths)
    files = [name.decode() for name in changed.split(b"\0") if name]
    if destination.exists():
        raise ValueError("each trial requires a fresh fixture directory")
    export_tree(repository, base, destination / "base")
    export_tree(repository, head, destination / "head")
    for name in excluded:
        for tree in ("base", "head"):
            (destination / tree / name).unlink(missing_ok=True)
    context = destination / "context"
    context.mkdir()
    (context / "diff.patch").write_bytes(diff)
    (context / "changed_files.json").write_text(json.dumps(files))
    (context / "pr.json").write_text(json.dumps({
        "number": fixture["pull_request"],
        "title": fixture["title"],
        "body": fixture["body"],
        "base_sha": base,
        "head_sha": head,
    }))
    return {
        "source": f"https://github.com/{fixture['repository']}/pull/{fixture['pull_request']}",
        "base_sha": base,
        "head_sha": head,
        "variant": variant,
        "omitted_paths": excluded,
        "diff_bytes": len(diff),
        "changed_files": len(files),
        "diff_sha256": hashlib.sha256(diff).hexdigest(),
    }


def summarize(output: Path, exit_code: int, elapsed: float) -> dict:
    transcript = output / "transcript.jsonl"
    events = ([json.loads(line) for line in transcript.read_text().splitlines()]
              if transcript.exists() else [])
    start = next((e for e in events if e["event"] == "run_start"), {})
    context = next((e for e in events if e["event"] == "context"), {})
    failure = next((e for e in reversed(events) if e["event"] == "run_failed"), {})
    usage = [e for e in events if e["event"] == "session_usage"]
    timeout = next((e for e in reversed(events) if e["event"] == "wall_clock_timeout"), None)
    accepted = exit_code == 0 and (output / "review.json").exists()
    submissions = [e for e in events if e["event"] == "tool_request"
                   and "submit_review" in e.get("tool", "")]
    return {
        "accepted": accepted,
        "exit_code": exit_code,
        "elapsed_seconds": round(elapsed, 3),
        "timed_out": timeout is not None,
        "failure_reason": failure.get("reason"),
        "tool_calls": sum(e["event"] == "tool_request" for e in events),
        "submission_calls": len(submissions),
        "api_messages": sum(e.get("api_messages", 0) for e in usage)
                        + (timeout or {}).get("api_messages", 0),
        "system_prompt_sha256": start.get("prompt_sha256"),
        "policy_sha256": start.get("policy_sha256"),
        "context_sha256": context.get("sha256"),
        "context_bytes": context.get("bytes"),
        "session_usage": usage,
        "timeout": timeout,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=HERE / "fixture.json")
    parser.add_argument("--variant", choices=["full", "reduced"], required=True)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, choices=[1, 3], default=1)
    parser.add_argument("--prompt", help="Optional committed file under benchmarks/large-diff/prompts")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    fixture = load_fixture(args.fixture)
    harness = args.harness.resolve()
    actual_sha = git(harness, "rev-parse", "HEAD").decode().strip()
    if actual_sha != fixture["harness_sha"]:
        parser.error(f"harness must be {fixture['harness_sha']}, got {actual_sha}")
    git(harness, "diff", "--no-ext-diff", "--no-textconv", "--exit-code", "HEAD", "--")
    if args.output_dir.exists():
        parser.error("output directory already exists; use a fresh path for each comparison")
    if args.work_dir.exists():
        parser.error("work directory already exists; use a fresh path for each comparison")
    prompt = None
    if args.prompt:
        prompt_root = (HERE / "prompts").resolve()
        prompt = (prompt_root / args.prompt).resolve()
        if (not prompt_root.is_relative_to(HERE)
                or not prompt.is_relative_to(prompt_root) or not prompt.is_file()):
            parser.error("--prompt must name a file inside this benchmark's prompts directory")
    args.work_dir.mkdir(parents=True)
    repository = args.work_dir / "source.git"
    subprocess.run(["git", "init", "--bare", str(repository)], check=True,
                   capture_output=True)
    git(repository, "fetch", "--depth=1", "--no-tags",
        f"https://github.com/{fixture['repository']}.git",
        fixture["base_sha"], fixture["head_sha"])
    args.output_dir.mkdir(parents=True)
    sys.path.insert(0, str(harness / "src/aceiro"))
    import cc_loop

    if prompt:
        cc_loop.PROMPT_PATH = prompt
    os.environ.pop("CC_MODEL", None)
    os.environ["ANTHROPIC_MODEL"] = MODELS[args.model]
    os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
    os.environ["ACEIRO_PROJECT_DESCRIPTION"] = fixture["project_description"]
    results = []
    for trial in range(1, args.runs + 1):
        # Stable input paths keep tool guidance identical across model trials.
        session = args.work_dir / "session"
        if session.exists():
            shutil.rmtree(session)
        metadata = prepare(repository, fixture, args.variant, session)
        metadata.update({
            "harness_sha": actual_sha, "model": MODELS[args.model], "trial": trial,
            "python": platform.python_version(), "budget_minutes": 50,
            "prompt_source_sha256": hashlib.sha256(cc_loop.PROMPT_PATH.read_bytes()).hexdigest(),
            "prompt_variant": args.prompt or "harness-default",
        })
        output = args.output_dir / f"trial-{trial}"
        output.mkdir()
        if args.prepare_only:
            (output / "summary.json").write_text(json.dumps(metadata, indent=2) + "\n")
            print(json.dumps(metadata))
            return 0
        # Each trial gets the production 50-minute budget, including the harness's
        # own reserve for output/cleanup. Never reuse redacted input between runs.
        os.environ["ACEIRO_AGENT_DEADLINE"] = str(int(time.time()) + 50 * 60)
        os.environ["CLAUDE_CONFIG_DIR"] = str(session / "claude-config")
        started = time.monotonic()
        code = cc_loop.run(session / "base", session / "head", session / "context", output)
        result = {**metadata, **summarize(output, code, time.monotonic() - started)}
        (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        results.append(result)
        (args.output_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps(result))
    return 0 if all(result["accepted"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
