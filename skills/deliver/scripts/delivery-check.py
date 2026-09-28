#!/usr/bin/env python3
"""Fail-closed stage checker for one Deliver record."""

import argparse
import contextlib
import datetime
import hashlib
import os
import pathlib
import re
import stat
import subprocess
import sys

MAX_RECORD_BYTES = 16 * 1024 * 1024
STAGE_NAMES = {
    1: "The outcome first",
    2: "One shared language",
    3: "The pattern pass",
    4: "Design on boards",
    5: "Enumerate before you build",
    6: "Model the data first",
    7: "The requirement ledger",
    8: "The plan as a contract",
    9: "Orchestration",
    10: "Implementation discipline",
    11: "Verification in layers",
    12: "The live integrity layer",
    13: "The close ritual",
    14: "The improvement loop",
}
STAGE_FIELDS = {
    1: ("BLIND-BRIEF", "ACCEPTANCE-BAR", "OWNER-SIGNATURE"),
    2: ("ONTOLOGY", "GENERATED-VIEW", "VOCABULARY-SWEEP"),
    3: ("DOMAIN-CENSUS", "PLAYBOOK-LIBRARY", "PATTERN-DECISIONS"),
    4: ("SIGNED-BOARD", "WORKED-EXAMPLES", "KILL-LIST", "WALK-VIEWS"),
    5: ("CASE-MATRIX", "INPUT-MATRICES", "CONSERVATION-LAWS"),
    6: ("DATA-MODEL", "MODULE-MAP", "REBUILD-PROOF"),
    7: ("TRACE-LEDGER", "TRACE-CHECK", "STANDINS"),
    8: ("EXECUTE-CONTRACT", "STATUS-TABLE", "LIVE-POINTER", "ARCHIVE", "ENTRY-TEST"),
    9: ("HOST-EVIDENCE", "LANE-CONTRACTS", "LANE-REPORTS", "RETURN-VERIFICATION"),
    10: ("DIFF", "LINE-DELTA", "IMPACT-VERDICTS", "LEAST-CODE", "GENERATED-SOURCE-CHECK"),
    11: ("PROOF-RUN", "RED-PROOF", "COVERAGE-MAP", "CONSERVATION-PROOF", "FULL-READ", "MEMBER-WALK", "REHEARSAL"),
    12: ("DOCTOR-COMMAND", "DOCTOR-EXIT", "ERROR-SHAPE", "STALENESS-SIGNAL"),
    13: ("FINDINGS", "CLOSURE", "DEFERRED-OWNERS", "INDEPENDENT-REVIEW", "REPUBLISHED", "CLOSE-REPORT"),
    14: ("SURPRISES", "INSTRUMENT-REPAIRS", "PERMANENT-TESTS", "METHOD-UPDATE"),
}
HEADER_FIELDS = {
    "schema_version", "delivery_id", "repository_root", "git_common_dir", "goal",
    "status", "current_stage", "revision", "owner_session", "base_head",
    "explicit_invocation", "commit_authority", "commit_request", "created_at", "updated_at",
}
PLACEHOLDER = re.compile(r"\b(?:TBD|UNRESOLVED|INFERRED|DEFAULTED|UNVERIFIED)\b", re.IGNORECASE)
REQUIREMENT = re.compile(r"^- (R[1-9]\d*):[ \t]*(\S.*)$", re.M)
FIELD = re.compile(r"^- ([A-Z][A-Z0-9-]*):[ \t]*(\S.*)$", re.M)
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def parse_header(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    values = {}
    for line in text[4:end].splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key or key in values:
            return None
        values[key.strip()] = value.strip()
    return values


def section(text, heading):
    match = re.search(
        rf"^## {re.escape(heading)}[ \t]*$\n(.*?)(?=^## |\Z)",
        text,
        re.M | re.S,
    )
    return match.group(1) if match else None


def stage_section(text, stage):
    match = re.search(
        rf"^## STAGE {stage:02d} (?:—|-) {re.escape(STAGE_NAMES[stage])}[ \t]*$\n"
        r"(.*?)(?=^## |\Z)",
        text,
        re.M | re.S,
    )
    return match.group(1) if match else None


def fields(body, label, problems):
    rows = FIELD.findall(body)
    names = [name for name, _value in rows]
    if len(names) != len(set(names)):
        problems.append(f"{label} contains duplicate fields")
    return dict(rows)


def iso_timestamp(value):
    try:
        datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (AttributeError, ValueError):
        return False


def git_common_dir(repo):
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return None
    value = pathlib.Path(result.stdout.strip())
    if not value.is_absolute():
        value = repo / value
    return value.resolve()


def record_relative_path(record_path, state_root):
    if not record_path.is_absolute():
        raise ValueError("record path must be absolute")
    root = state_root.absolute()
    try:
        relative = record_path.absolute().relative_to(root)
    except ValueError as error:
        raise ValueError(f"record must stay under {state_root}") from error
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("record path must be canonical below the state root")
    return relative


@contextlib.contextmanager
def open_state_record(record_path, state_root):
    relative = record_relative_path(record_path, state_root)
    opened = [os.open(state_root.resolve(strict=True), DIRECTORY_FLAGS)]
    try:
        current = opened[0]
        for component in relative.parts[:-1]:
            current = os.open(component, DIRECTORY_FLAGS, dir_fd=current)
            opened.append(current)
        descriptor = os.open(
            relative.parts[-1],
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=current,
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("record is not a regular file")
            yield descriptor
        finally:
            os.close(descriptor)
    finally:
        for descriptor in reversed(opened):
            os.close(descriptor)


def validate_record_path(record_path, state_root, problems):
    if record_path.suffix != ".md":
        problems.append("record path must end in .md")
    try:
        record_relative_path(record_path, state_root)
    except (OSError, ValueError) as error:
        problems.append(str(error))


def validate_header(header, stage, repo, problems):
    if header is None:
        problems.append("record requires one flat YAML header")
        return
    missing = sorted(HEADER_FIELDS - set(header))
    extra = sorted(set(header) - HEADER_FIELDS)
    if missing:
        problems.append("header missing: " + ", ".join(missing))
    if extra:
        problems.append("header has unknown fields: " + ", ".join(extra))
    if missing:
        return
    expected_root = str(repo.resolve())
    common = git_common_dir(repo)
    repository_id = hashlib.sha256(expected_root.encode()).hexdigest()[:12]
    if header["schema_version"] != "1":
        problems.append("schema_version must be 1")
    if not re.fullmatch(rf"{repository_id}/[a-z0-9][a-z0-9-]*", header["delivery_id"]):
        problems.append("delivery_id does not match repository identity and task slug")
    if header["repository_root"] != expected_root:
        problems.append("repository_root does not match the canonical repository")
    if common is None or header["git_common_dir"] != str(common):
        problems.append("git_common_dir does not match the current repository")
    if not header["goal"]:
        problems.append("goal must be non-empty")
    expected_status = "closed" if stage == 14 else "active"
    if header["status"] != expected_status:
        problems.append(f"status must be {expected_status} for a passing stage {stage}")
    if header["current_stage"] != str(stage):
        problems.append(f"current_stage must be {stage}")
    if not re.fullmatch(r"[1-9]\d*", header["revision"]):
        problems.append("revision must be a positive integer")
    if not header["owner_session"]:
        problems.append("owner_session must be non-empty")
    if not re.fullmatch(r"unborn|[0-9a-f]{7,40}", header["base_head"]):
        problems.append("base_head must be unborn or a 7-to-40-character commit")
    if header["explicit_invocation"] != "true":
        problems.append("explicit_invocation must be true")
    authority = header["commit_authority"]
    request = header["commit_request"]
    if authority == "not-granted" and request != "none":
        problems.append("commit_request must be none without commit authority")
    elif authority == "granted" and request in {"", "none"}:
        problems.append("granted commit authority requires the exact request")
    elif authority not in {"not-granted", "granted"}:
        problems.append("commit_authority must be not-granted or granted")
    for name in ("created_at", "updated_at"):
        if not iso_timestamp(header[name]):
            problems.append(f"{name} must be an ISO-8601 timestamp")


def require_exit_zero(value, label, problems):
    if not re.search(r"(?:^|[ \t])exit 0(?:$|[ \t])", value):
        problems.append(f"{label} must record exit 0")


def validate_stage_details(stage, values, requirement_ids, problems):
    if stage == 2:
        require_exit_zero(values["VOCABULARY-SWEEP"], "stage 02 VOCABULARY-SWEEP", problems)
    elif stage == 5 and re.search(r"\bUNDECIDED\b", " ".join(values.values()), re.I):
        problems.append("stage 05 contains an undecided cell")
    elif stage == 6:
        require_exit_zero(values["REBUILD-PROOF"], "stage 06 REBUILD-PROOF", problems)
    elif stage == 7:
        missing = [rid for rid in requirement_ids if not re.search(rf"\b{rid}\b", values["TRACE-LEDGER"])]
        if missing:
            problems.append("stage 07 TRACE-LEDGER misses: " + ", ".join(missing))
        require_exit_zero(values["TRACE-CHECK"], "stage 07 TRACE-CHECK", problems)
    elif stage == 8:
        require_exit_zero(values["ENTRY-TEST"], "stage 08 ENTRY-TEST", problems)
    elif stage == 9:
        match = re.fullmatch(r"DECLARED (\d+) VERIFIED (\d+)", values["RETURN-VERIFICATION"])
        if not match or int(match.group(1)) < 1 or match.group(1) != match.group(2):
            problems.append("stage 09 RETURN-VERIFICATION needs equal positive counts")
    elif stage == 10:
        match = re.fullmatch(r"ADDED (\d+) REMOVED (\d+) NET (-?\d+)", values["LINE-DELTA"])
        if not match or int(match.group(3)) != int(match.group(1)) - int(match.group(2)):
            problems.append("stage 10 LINE-DELTA does not reconcile")
        if not re.match(r"YES\b", values["LEAST-CODE"], re.I):
            problems.append("stage 10 LEAST-CODE must start with YES")
    elif stage == 11:
        for name in ("PROOF-RUN", "CONSERVATION-PROOF", "MEMBER-WALK", "REHEARSAL"):
            require_exit_zero(values[name], f"stage 11 {name}", problems)
        red = re.fullmatch(
            r"PASS (R[1-9]\d*) RED-EXIT ([1-9]\d*) GREEN-EXIT 0 COMMAND \S.*",
            values["RED-PROOF"],
        )
        if not red or red.group(1) not in requirement_ids:
            problems.append("stage 11 RED-PROOF must name a declared requirement and red-to-green command")
    elif stage == 12:
        if values["DOCTOR-EXIT"] != "0":
            problems.append("stage 12 DOCTOR-EXIT must be 0")
    elif stage == 13:
        match = re.fullmatch(r"FOUND (\d+) FIXED (\d+) DEFERRED (\d+) OPEN (\d+)", values["CLOSURE"])
        if not match:
            problems.append("stage 13 CLOSURE has invalid shape")
        else:
            found, fixed, deferred, open_count = map(int, match.groups())
            if found != fixed + deferred or open_count != 0:
                problems.append("stage 13 CLOSURE must reconcile and have OPEN 0")
            if deferred == 0 and values["DEFERRED-OWNERS"] != "none":
                problems.append("stage 13 DEFERRED-OWNERS must be none when DEFERRED is 0")
            if deferred > 0 and values["DEFERRED-OWNERS"] == "none":
                problems.append("stage 13 deferred findings require owners")
        if not values["INDEPENDENT-REVIEW"].startswith("PASS "):
            problems.append("stage 13 INDEPENDENT-REVIEW must start with PASS")
        require_exit_zero(values["REPUBLISHED"], "stage 13 REPUBLISHED", problems)
    elif stage == 14:
        surprise = values["SURPRISES"] != "none"
        repair_fields = ("INSTRUMENT-REPAIRS", "PERMANENT-TESTS", "METHOD-UPDATE")
        if surprise and any(values[name] == "none" for name in repair_fields):
            problems.append("stage 14 surprises require instrument repair, permanent proof, and method update")
        if not surprise and any(values[name] != "none" for name in repair_fields):
            problems.append("stage 14 no-surprise record must use none for every repair field")


def check(stage, text, repo, record_path, state_root=None):
    problems = []
    if stage not in STAGE_NAMES:
        return ["stage must be an integer from 1 through 14"]
    repo = repo.resolve()
    state_root = state_root or pathlib.Path.home() / ".local/state/deliver"
    validate_record_path(record_path, state_root, problems)
    header = parse_header(text)
    validate_header(header, stage, repo, problems)

    requirements_body = section(text, "REQUIREMENTS")
    requirements = REQUIREMENT.findall(requirements_body or "")
    requirement_ids = [rid for rid, _text in requirements]
    if not requirements:
        problems.append("REQUIREMENTS needs at least one stable R<number> row")
    if len(requirement_ids) != len(set(requirement_ids)):
        problems.append("requirement IDs must be unique")
    for heading in ("DECISIONS", "EVIDENCE"):
        if section(text, heading) is None:
            problems.append(f"missing global section: {heading}")
    if PLACEHOLDER.search(text):
        problems.append("record contains an unresolved or placeholder authority value")

    for current in range(1, stage + 1):
        body = stage_section(text, current)
        if body is None:
            problems.append(f"missing stage section: {current:02d} {STAGE_NAMES[current]}")
            continue
        values = fields(body, f"stage {current:02d}", problems)
        if values.get("STATUS") != "PASS":
            problems.append(f"stage {current:02d} STATUS must be PASS")
        for name in (*STAGE_FIELDS[current], "GATE-EVIDENCE"):
            value = values.get(name)
            if not value:
                problems.append(f"stage {current:02d} missing: {name}")
        if all(values.get(name) for name in STAGE_FIELDS[current]):
            validate_stage_details(current, values, requirement_ids, problems)
    return problems


def read_record(path, state_root=None):
    state_root = state_root or pathlib.Path.home() / ".local/state/deliver"
    with open_state_record(path, state_root) as descriptor:
        size = os.fstat(descriptor).st_size
        if size > MAX_RECORD_BYTES:
            raise ValueError("record exceeds 16 MiB")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RECORD_BYTES:
                raise ValueError("record exceeds 16 MiB")
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Check one Deliver stage transition.")
    parser.add_argument("--stage", type=int, required=True)
    parser.add_argument("--record", type=pathlib.Path, required=True)
    parser.add_argument("--repo", type=pathlib.Path, required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        text = read_record(args.record)
        problems = check(args.stage, text, args.repo, args.record)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        print(f"delivery-check: {error}", file=sys.stderr)
        return 2
    if problems:
        print(f"FAIL stage {args.stage}: {len(problems)} problem(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"PASS stage {args.stage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
