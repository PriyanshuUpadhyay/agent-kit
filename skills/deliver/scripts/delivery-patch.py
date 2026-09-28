#!/usr/bin/env python3
"""Build a delivery patch that is proven to rebuild the working tree from a baseline."""

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

APPLY_PROOF_FAILED = 2
INPUT_REJECTED = 3


class PatchError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def git(arguments, cwd, data=None):
    result = subprocess.run(["git"] + arguments, cwd=str(cwd), input=data, capture_output=True)
    if result.returncode > 1:
        raise PatchError(
            f"git {arguments[0]} failed: {result.stderr.decode('utf-8', 'replace').strip()}",
            INPUT_REJECTED,
        )
    return result


def stage_tree(source, files, destination):
    for relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)


def rewrite(patch, relative):
    name = relative.encode("utf-8")
    source = b"--- a/baseline/" + name
    target = b"+++ b/current/" + name
    lines = []
    header = True
    for line in patch.splitlines(keepends=True):
        if header and line.startswith(b"diff --git "):
            line = b"diff --git a/" + name + b" b/" + name + b"\n"
        elif header and line.startswith(source):
            line = b"--- a/" + name + line[len(source):]
        elif header and line.startswith(target):
            line = b"+++ b/" + name + line[len(target):]
        elif line.startswith(b"@@") or line.startswith(b"GIT binary patch"):
            header = False
        lines.append(line)
    return b"".join(lines)


def pair(relative):
    return ["--", f"baseline/{relative}", f"current/{relative}"]


def diff_file(work, relative):
    arguments = ["diff", "--no-index", "--binary", "--no-renames", "--src-prefix=a/", "--dst-prefix=b/"]
    return rewrite(git(arguments + pair(relative), work).stdout, relative)


def numstat(work, relative):
    output = git(["diff", "--no-index", "--numstat", "--no-renames"] + pair(relative), work).stdout
    if not output.strip():
        return 0, 0
    added, removed = output.split(b"\t")[:2]
    if added == b"-":
        return 0, 0
    return int(added), int(removed)


def prove(baseline, repo, files, patch):
    with tempfile.TemporaryDirectory() as name:
        proof = pathlib.Path(name) / "proof"
        stage_tree(baseline, files, proof)
        if patch:
            git(["apply", "-p1", "--binary", "-"], proof, data=patch)
        return [r for r in files if (proof / r).read_bytes() != (repo / r).read_bytes()]


def check_inputs(baseline, repo, files):
    cleaned = []
    for relative in files:
        path = pathlib.PurePosixPath(relative)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise PatchError(f"{relative} must be a relative path inside both trees", INPUT_REJECTED)
        cleaned.append(str(path))
    missing = [
        f"{r} (absent from {label})"
        for r in cleaned
        for label, root in (("baseline", baseline), ("repo", repo))
        if not (root / r).is_file()
    ]
    if missing:
        raise PatchError(
            "v1 needs every listed file in both trees; a file absent from one side is not supported: "
            + ", ".join(missing),
            INPUT_REJECTED,
        )
    return cleaned


def build(baseline, repo, files, out):
    files = check_inputs(baseline, repo, files)
    chunks, changed, added, removed = [], [], 0, 0
    with tempfile.TemporaryDirectory() as name:
        work = pathlib.Path(name)
        stage_tree(baseline, files, work / "baseline")
        stage_tree(repo, files, work / "current")
        for relative in files:
            piece = diff_file(work, relative)
            if not piece:
                continue
            changed.append(relative)
            chunks.append(piece)
            gained, lost = numstat(work, relative)
            added, removed = added + gained, removed + lost
    patch = b"".join(chunks)
    mismatched = prove(baseline, repo, files, patch)
    if mismatched:
        raise PatchError("apply proof did not reproduce: " + ", ".join(mismatched), APPLY_PROOF_FAILED)
    write_atomically(out, patch)
    return {
        "patch": str(out), "sha256": hashlib.sha256(patch).hexdigest(), "files": len(files),
        "changed": changed, "added": added, "removed": removed, "net": added - removed,
        "apply_proof": "pass",
    }


def write_atomically(out, patch):
    handle = tempfile.NamedTemporaryFile(dir=str(out.parent), prefix=out.name, suffix=".tmp", delete=False)
    with handle:
        handle.write(patch)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(handle.name, out)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build a proven delivery patch.")
    parser.add_argument("--baseline", type=pathlib.Path, required=True)
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("files", nargs="+")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        result = build(args.baseline, args.repo, args.files, args.out)
    except (OSError, PatchError) as error:
        print(f"delivery-patch: {error}", file=sys.stderr)
        return getattr(error, "code", INPUT_REJECTED)
    if args.json:
        print(json.dumps(result))
    else:
        result["changed"] = ",".join(result["changed"]) or "none"
        print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
