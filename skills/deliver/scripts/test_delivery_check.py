#!/usr/bin/env python3
import hashlib
import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest


sys.dont_write_bytecode = True
SCRIPT = pathlib.Path(__file__).with_name("delivery-check.py")
SPEC = importlib.util.spec_from_file_location("delivery_check", SCRIPT)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class DeliveryCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.state_root = self.root / "state" / "deliver"
        repository_id = hashlib.sha256(str(self.repo.resolve()).encode()).hexdigest()[:12]
        self.record = self.state_root / repository_id / "example-task.md"
        self.record.parent.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def valid_text(self, stage=14):
        status = "closed" if stage == 14 else "active"
        common = (self.repo / ".git").resolve()
        repository_id = hashlib.sha256(str(self.repo.resolve()).encode()).hexdigest()[:12]
        stage_values = {
            1: {
                "BLIND-BRIEF": "path=brief.md digest=" + "a" * 64,
                "ACCEPTANCE-BAR": "journey=signed safety=signed loud=signed endpoint=signed",
                "OWNER-SIGNATURE": "owner approved R1 in the current run",
            },
            2: {
                "ONTOLOGY": "path=ontology.md digest=" + "b" * 64,
                "GENERATED-VIEW": "path=ontology.html source=ontology.md",
                "VOCABULARY-SWEEP": "command=check-vocabulary exit 0",
            },
            3: {
                "DOMAIN-CENSUS": "count=1 domains=workflow-engine",
                "PLAYBOOK-LIBRARY": "count=1 workflow-engine=source:delivery-manual",
                "PATTERN-DECISIONS": "stage-gate uses named standard pattern",
            },
            4: {
                "SIGNED-BOARD": "path=board.md digest=" + "c" * 64,
                "WORKED-EXAMPLES": "normal=E1 boundary=E2",
                "KILL-LIST": "automatic-entry,implicit-commit",
                "WALK-VIEWS": "path=board.html source=board.md",
            },
            5: {
                "CASE-MATRIX": "R1 normal=P1 failure=P2",
                "INPUT-MATRICES": "explicit x host-present=continue; explicit x host-missing=block",
                "CONSERVATION-LAWS": "declared-returns=verified-returns",
            },
            6: {
                "DATA-MODEL": "delivery-record=authoritative generated-status=derived",
                "MODULE-MAP": "record-writer=root record-readers=lanes",
                "REBUILD-PROOF": "command=rebuild-status exit 0",
            },
            7: {
                "TRACE-LEDGER": "R1 design=S1 code=C1 proof=P1",
                "TRACE-CHECK": "command=check-trace exit 0",
                "STANDINS": "none",
            },
            8: {
                "EXECUTE-CONTRACT": "path=execute.md digest=" + "d" * 64,
                "STATUS-TABLE": "path=status.md source=record",
                "LIVE-POINTER": "next=lane-1 facts=F1 choices=none waits=none",
                "ARCHIVE": "path=archive.md blocks=0",
                "ENTRY-TEST": "command=fresh-entry exit 0",
            },
            9: {
                "HOST-EVIDENCE": "runtime=loaded pane=visible-owned-1",
                "LANE-CONTRACTS": "lane-1 files=src/a role=implementer permission=write report=lane-1.json",
                "LANE-REPORTS": "lane-1 digest=" + "e" * 64,
                "RETURN-VERIFICATION": "DECLARED 1 VERIFIED 1",
            },
            10: {
                "DIFF": "files=src/a digest=" + "f" * 64,
                "LINE-DELTA": "ADDED 8 REMOVED 3 NET 5",
                "IMPACT-VERDICTS": "surface=a before=old after=new",
                "LEAST-CODE": "YES removed duplicate branch",
                "GENERATED-SOURCE-CHECK": "PASS changed canonical source only",
            },
            11: {
                "PROOF-RUN": "command=test-all exit 0",
                "RED-PROOF": "PASS R1 RED-EXIT 1 GREEN-EXIT 0 COMMAND test-r1",
                "COVERAGE-MAP": "declared=1 accounted=1",
                "CONSERVATION-PROOF": "command=test-balance exit 0",
                "FULL-READ": "question=day-one-shape verdict=accept",
                "MEMBER-WALK": "command=walk-real-input exit 0",
                "REHEARSAL": "command=clean-rehearsal exit 0",
            },
            12: {
                "DOCTOR-COMMAND": "doctor --full",
                "DOCTOR-EXIT": "0",
                "ERROR-SHAPE": "source location message offending-input renderer=one",
                "STALENESS-SIGNAL": "last-success=now age=0 rejected=0 surface=main",
            },
            13: {
                "FINDINGS": "path=findings.json digest=" + "1" * 64,
                "CLOSURE": "FOUND 0 FIXED 0 DEFERRED 0 OPEN 0",
                "DEFERRED-OWNERS": "none",
                "INDEPENDENT-REVIEW": "PASS reviewer=review-1 digest=" + "2" * 64,
                "REPUBLISHED": "command=republish exit 0",
                "CLOSE-REPORT": "done=yes proof=P1 issue=none question=none",
            },
            14: {
                "SURPRISES": "none",
                "INSTRUMENT-REPAIRS": "none",
                "PERMANENT-TESTS": "none",
                "METHOD-UPDATE": "none",
            },
        }
        blocks = []
        for number, values in stage_values.items():
            lines = [f"## STAGE {number:02d} — {CHECKER.STAGE_NAMES[number]}", "- STATUS: PASS"]
            lines.extend(f"- {name}: {value}" for name, value in values.items())
            lines.append(f"- GATE-EVIDENCE: stage-{number:02d}-evidence")
            blocks.append("\n".join(lines))
        return f'''---
schema_version: 1
delivery_id: {repository_id}/example-task
repository_root: {self.repo.resolve()}
git_common_dir: {common}
goal: deliver one example
status: {status}
current_stage: {stage}
revision: 3
owner_session: test-run
base_head: unborn
explicit_invocation: true
commit_authority: not-granted
commit_request: none
created_at: 2026-08-20T10:00:00Z
updated_at: 2026-08-20T10:05:00Z
---

## REQUIREMENTS
- R1: WHEN deliver is invoked THE SYSTEM SHALL pass every stage

## DECISIONS
- ASK entry: REQUEST: explicit invocation

## EVIDENCE
- CLAIM source: {{"path":"src/a","digest":"{'3' * 64}"}}

{chr(10).join(chr(10) + block for block in blocks)}
'''

    def problems(self, text, stage=14, path=None):
        target = path or self.record
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        return CHECKER.check(stage, text, self.repo, target, self.state_root)

    def test_complete_stage_fourteen_record_passes(self):
        self.assertEqual(self.problems(self.valid_text()), [])

    def test_explicit_invocation_is_required(self):
        text = self.valid_text().replace("explicit_invocation: true", "explicit_invocation: false")
        self.assertIn("explicit_invocation must be true", self.problems(text))

    def test_missing_prior_stage_fails_ordered_gate(self):
        text = self.valid_text(stage=6)
        start = text.index("## STAGE 05")
        end = text.index("## STAGE 06")
        text = text[:start] + text[end:]
        self.assertTrue(any("missing stage section: 05" in item for item in self.problems(text, 6)))

    def test_stage_nine_requires_all_returns_verified(self):
        text = self.valid_text(stage=9).replace("DECLARED 1 VERIFIED 1", "DECLARED 2 VERIFIED 1")
        self.assertTrue(any("equal positive counts" in item for item in self.problems(text, 9)))

    def test_stage_eleven_red_proof_names_declared_requirement(self):
        text = self.valid_text(stage=11).replace("PASS R1 RED-EXIT", "PASS R2 RED-EXIT")
        self.assertTrue(any("RED-PROOF" in item for item in self.problems(text, 11)))

    def test_stage_twelve_requires_clean_doctor(self):
        text = self.valid_text(stage=12).replace("- DOCTOR-EXIT: 0", "- DOCTOR-EXIT: 1")
        self.assertIn("stage 12 DOCTOR-EXIT must be 0", self.problems(text, 12))

    def test_stage_thirteen_reconciles_zero_open_closure(self):
        text = self.valid_text(stage=13).replace(
            "FOUND 0 FIXED 0 DEFERRED 0 OPEN 0", "FOUND 1 FIXED 0 DEFERRED 0 OPEN 1"
        )
        self.assertTrue(any("must reconcile" in item for item in self.problems(text, 13)))

    def test_stage_fourteen_pairs_surprise_with_instrument_repair(self):
        text = self.valid_text().replace("- SURPRISES: none", "- SURPRISES: D1 parser-drop")
        self.assertTrue(any("surprises require" in item for item in self.problems(text)))

    def test_commit_authority_needs_exact_request(self):
        text = self.valid_text().replace("commit_authority: not-granted", "commit_authority: granted")
        self.assertIn("granted commit authority requires the exact request", self.problems(text))

    def test_record_must_stay_under_external_state_root(self):
        outside = self.root / "record.md"
        problems = self.problems(self.valid_text(), path=outside)
        self.assertTrue(any("must stay under" in item for item in problems))

    def test_symlink_record_is_rejected_by_bound_read(self):
        outside = self.root / "outside.md"
        outside.write_text(self.valid_text())
        self.record.symlink_to(outside)
        with self.assertRaises(OSError):
            CHECKER.read_record(self.record, self.state_root)

    def test_line_delta_must_reconcile(self):
        text = self.valid_text(stage=10).replace("ADDED 8 REMOVED 3 NET 5", "ADDED 8 REMOVED 3 NET 8")
        self.assertIn("stage 10 LINE-DELTA does not reconcile", self.problems(text, 10))


if __name__ == "__main__":
    unittest.main()
