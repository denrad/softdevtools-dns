# DNS Request Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the proposed CNAME records locally before accepting student pull requests.

**Architecture:** A read-only Python CLI scans `records/*.yaml` and a reserved-name list, parses YAML safely, and reports all errors with file names. This first slice makes no GitHub or Cloudflare API calls and does not inspect PR authorship or changed paths.

**Tech Stack:** Python 3.11+, PyYAML 6.x, standard-library `unittest`.

**Spec:** [Technical design](../../design.md).

## Global Constraints

- One YAML file describes one single-label subdomain and one DNS-only CNAME.
- Exactly four keys: `subdomain`, `type`, `target`, `repository`.
- Target is `<github-user>.github.io`; repository URL belongs to the same GitHub user.
- Validator reads files only; no network, secrets, or DNS writes.
- Existing records are not automatically changed or deleted; PR ownership and path policy are separate work.

## Review Focus

- Duplicate YAML keys must fail instead of silently replacing the first value; tested in Task 1.
- YAML aliases and unexpected scalar types must fail cleanly; tested in Task 1.
- A file name that disagrees with `subdomain` must fail; tested in Task 2.
- Case variants and two files proposing one name must fail; tested in Task 2.
- Missing reserved-name configuration must fail rather than silently allowing reserved names; tested in Task 2.

---

### Task 1: Safe parsing and one-record schema

**Files:**
- Create: `pyproject.toml`
- Create: `scripts/validate.py`
- Create: `tests/test_validate.py`

**Interfaces:**
- Produces: `parse_record(path: Path) -> tuple[dict[str, str] | None, list[str]]`.
- `parse_record` reads at most 8 KiB and returns field errors without network calls.

- [ ] Write failing tests for valid sample, malformed YAML, duplicate keys, multi-document YAML, unknown/missing keys, non-string values, and oversized file.
- [ ] Run `python3 -m unittest tests.test_validate -v` and confirm the tests fail because `parse_record` is absent.
- [ ] Implement safe loading with duplicate-key rejection and the four-field schema.
- [ ] Run `python3 -m unittest tests.test_validate -v` and confirm these tests pass.
- [ ] Commit Task 1 files.

### Task 2: Domain policy and repository scan

**Files:**
- Modify: `scripts/validate.py`
- Modify: `tests/test_validate.py`
- Create: `config/reserved-names.txt`
- Create: `records/.gitkeep`

**Interfaces:**
- Consumes: `parse_record(path)` from Task 1.
- Produces: `validate_records(root: Path) -> list[str]`.

- [ ] Write failing tests for valid tree, invalid or reserved subdomain, invalid CNAME target, mismatched repository owner, duplicate names, wrong filename, and missing config.
- [ ] Run `python3 -m unittest tests.test_validate -v` and confirm policy tests fail for the expected reason.
- [ ] Implement strict lowercase names, reserved-name loading, and scan of direct `records/*.yaml` files.
- [ ] Run the full suite and confirm it passes.
- [ ] Commit Task 2 files.

### Task 3: CLI and user-facing instructions

**Files:**
- Modify: `scripts/validate.py`
- Modify: `tests/test_validate.py`
- Modify: `README.md`
- Modify: `docs/student.md`

**Interfaces:**
- Consumes: `validate_records(root)` from Task 2.
- Produces: `python3 -m scripts.validate [repo-root]`, exit 0 for valid tree, 1 for invalid tree.

- [ ] Write a failing subprocess test for readable success and error output with proper exit codes.
- [ ] Run the test and confirm it fails because the CLI is absent.
- [ ] Implement the CLI; document local use and that PR policy and deploy are not implemented.
- [ ] Run `python3 -m unittest discover -s tests -v` and `python3 -m scripts.validate .`.
- [ ] Run `git diff --check` and check modified relative Markdown links.
- [ ] Commit Task 3 files.

## Deferred work

PR changed-path and author checks, protected-branch rules, Cloudflare deployment,
and live DNS/HTTP/HTTPS checks require separate implementation and pilot plans.
