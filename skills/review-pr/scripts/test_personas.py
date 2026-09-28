"""Contract tests for review-pr's skill-local epistemic personas."""

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
PERSONA_DIR = SKILL_DIR / "references" / "personas"
SKILL = SKILL_DIR / "SKILL.md"
ORCHESTRATION = SKILL_DIR / "orchestration.json"
PERSONAS = {
    "unit-reviewer.md": (
        '"unit_id"',
        '"status"',
        '"evidence"',
        '"boundary_inputs"',
        '"error_branches"',
        '"preserved_invariants"',
        '"file_line"',
        '"quoted_code"',
        '"trigger"',
        '"why_not_prevented"',
    ),
    "challenger.md": (
        '"unit_id"',
        '"verdict"',
        '"evidence"',
        '"file_line"',
        '"quoted_code"',
        '"trigger_or_trace"',
        '"why_not_prevented"',
    ),
    "security-reviewer.md": (
        '"verdict"',
        '"severity"',
        '"evidence"',
        '"file_line"',
        '"quoted_code"',
        '"trigger_or_trace"',
        '"why_not_prevented"',
    ),
}


WRITING_GIT_SUBCOMMANDS = {
    "checkout", "clone", "fetch", "merge", "pull", "reset", "stash", "switch", "worktree",
}


class PersonaContracts(unittest.TestCase):
    def persona(self, filename):
        return (PERSONA_DIR / filename).read_text()

    def test_personas_exist_and_are_referenced_by_skill(self):
        skill = SKILL.read_text()
        for filename in PERSONAS:
            self.assertTrue((PERSONA_DIR / filename).is_file(), filename)
            self.assertIn(f"references/personas/{filename}", skill)

    def test_personas_do_not_select_routing(self):
        forbidden_routing_terms = re.compile(
            r"(?i)\b(provider|model|runner|profile|sandbox|effort|visibility|"
            r"service[-_ ]?tier)\b"
        )
        for filename in PERSONAS:
            text = (PERSONA_DIR / filename).read_text()
            self.assertIsNone(forbidden_routing_terms.search(text), filename)

    def test_orchestration_contract_keeps_all_review_pr_roles(self):
        import json

        review_roles = set(json.loads(ORCHESTRATION.read_text())["roles"])
        self.assertEqual(
            review_roles,
            {
                "review.deep",
                "review.challenger",
            },
        )
        self.assertTrue(all(review_roles))

    def test_persona_outputs_keep_required_verdict_and_evidence_fields(self):
        for filename, required in PERSONAS.items():
            text = self.persona(filename)
            for field in required:
                self.assertIn(field, text, f"{filename}: {field}")

    def test_all_personas_keep_cq_mcp_only_failure_and_feedback_protocol(self):
        for filename in PERSONAS:
            text = self.persona(filename)
            flat = " ".join(text.split())
            self.assertIn("Query CQ through its MCP tools only", flat, filename)
            self.assertIn("never use a CLI or shell command for CQ", flat, filename)
            self.assertIn("note that once in the returned artifact", flat, filename)
            self.assertIn("continue without retrying", flat, filename)
            self.assertIn("Verify any consulted guidance", flat, filename)
            self.assertIn("confirm guidance that holds or flag guidance", flat, filename)

    def test_unit_persona_has_separate_code_unit_and_ripple_identities(self):
        text = self.persona("unit-reviewer.md")
        per_unit = text.split("## Per-unit output contract", 1)[1].split(
            "## Ripple output contract", 1
        )[0]
        ripple = text.split("## Ripple output contract", 1)[1]
        self.assertIn('"unit_id"', per_unit)
        self.assertNotIn('"symbol"', per_unit)
        self.assertNotIn('"unit_id"', ripple)
        for field in (
            '"symbol"',
            '"change_type"',
            '"status"',
            '"reviewed_callers"',
            '"dropped"',
            '"evidence"',
            '"findings"',
        ):
            self.assertIn(field, ripple)

    def test_prompt_review_requires_explicit_testable_obligations(self):
        text = " ".join(self.persona("unit-reviewer.md").split())
        self.assertIn("every obligation, tool assumption, failure behavior, and evidence", text)
        self.assertIn("explicit and testable", text)
        self.assertIn("never rely on unstated inference", text)

    def test_ripple_verdicts_never_enter_code_unit_gate_namespace(self):
        skill = SKILL.read_text()
        self.assertIn("`$RPDIR/ripple-verdicts.json`", skill)
        self.assertIn("never receive a `unit_id`", skill)
        self.assertIn("never enter `worklist.json`, `verdicts.json`, or the code-unit gate inputs", skill)
        self.assertIn("do not merge their identity namespaces", skill)

        challenger = self.persona("challenger.md")
        code_unit = challenger.split("## Code-unit disposition contract", 1)[1].split(
            "## Ripple disposition contract", 1
        )[0]
        ripple = challenger.split("## Ripple disposition contract", 1)[1]
        self.assertIn('"unit_id"', code_unit)
        self.assertNotIn('"symbol"', code_unit)
        self.assertNotIn('"unit_id"', ripple)
        self.assertIn('"symbol"', ripple)
        self.assertIn('"change_type"', ripple)

    def test_skill_never_writes_to_the_reviewed_repository(self):
        """Post-change state must come from the run-scoped clone, not the user's checkout."""
        text = SKILL.read_text()
        self.assertNotIn("gh pr checkout", text)
        for line in (raw.strip() for raw in text.splitlines()):
            if line.startswith("gh repo clone"):
                self.assertIn('"$HEAD_DIR"', line)
                continue
            if not line.startswith("git "):
                continue
            tokens = line.split()
            scoped, index = False, 1
            while tokens[index] == "-C":
                scoped = tokens[index + 1] == '"$HEAD_DIR"'
                index += 2
            if tokens[index] in WRITING_GIT_SUBCOMMANDS:
                self.assertTrue(scoped, line)

    def test_repository_qualified_target_is_normalized_for_every_gh_call(self):
        skill = SKILL.read_text()
        self.assertIn('PR_ARGS=(--repo "$PR_REPO" "$PR_NUMBER_INPUT")', skill)
        self.assertIn("''|*[!0-9]*", skill)
        for line in (raw.strip() for raw in skill.splitlines()):
            if line.startswith("gh pr ") or "$(gh pr view " in line:
                self.assertIn('"${PR_ARGS[@]}"', line)

    def test_local_mode_includes_non_ignored_untracked_files(self):
        skill = SKILL.read_text()
        start = skill.index('git ls-files --others --exclude-standard -z > "$RPDIR/untracked.zlist"')
        block = skill[start:].split("```", 1)[0]
        self.assertIn("git ls-files --others --exclude-standard -z", block)
        self.assertIn("git diff --no-index -- /dev/null", block)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Review Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "review@example.invalid"], cwd=root, check=True)
            (root / "tracked.py").write_text("before\n")
            subprocess.run(["git", "add", "tracked.py"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
            (root / "tracked.py").write_text("after\n")
            (root / "untracked.py").write_text("new file\n")
            with tempfile.TemporaryDirectory() as scratch_temp:
                scratch = Path(scratch_temp)
                env = os.environ.copy()
                env["RPDIR"] = str(scratch)
                subprocess.run(["bash", "-c", block], cwd=root, env=env, check=True)
                diff = (scratch / "diff.patch").read_text()
                self.assertIn("tracked.py", diff)
                self.assertIn("untracked.py", diff)
                self.assertIn("+new file", diff)

    def test_behavior_ownership_audit_is_referenced_and_evidence_gated(self):
        skill = SKILL.read_text()
        audit_path = SKILL_DIR / "references" / "behavior-ownership-audit.md"
        self.assertTrue(audit_path.is_file())
        self.assertIn("references/behavior-ownership-audit.md", skill)
        self.assertIn("`$RPDIR/ownership-audit.md`", skill)
        self.assertIn("The matrix is supporting evidence and never", skill)
        self.assertIn("enters the code-unit gate as a new identity", skill)

        audit = audit_path.read_text()
        for required in (
            "Use the final base-to-head diff",
            "Behavior | Candidate layers | Owner",
            "Distinguish redundancy from defense in depth",
            "The removed layer does not protect an independent trust, durability, race, or resource boundary",
            "Map each supported finding to the changed worklist unit",
        ):
            self.assertIn(required, audit)


if __name__ == "__main__":
    unittest.main()
