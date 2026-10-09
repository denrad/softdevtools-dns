"""Check that a student pull request only adds new DNS request files."""

import argparse
from pathlib import Path
import subprocess


def validate_pr_changes(root: Path, base: str, head: str) -> list[str]:
    """Compare the PR head with its merge base, without reading file contents."""
    result = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", "-z", f"{base}...{head}", "--"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return [f"cannot compare PR changes: {result.stderr.decode('utf-8', 'replace').strip()}"]

    fields = result.stdout.rstrip(b"\0").split(b"\0") if result.stdout else []
    if len(fields) % 2:
        return ["cannot parse git diff --name-status output"]

    errors = []
    added_records = 0
    for status_bytes, path_bytes in zip(fields[::2], fields[1::2]):
        status = status_bytes.decode("ascii", "replace")
        path = path_bytes.decode("utf-8", "replace")
        parts = path.split("/")
        if status == "A" and len(parts) == 2 and parts[0] == "records" and parts[1].endswith(".yaml"):
            added_records += 1
        else:
            errors.append(f"{status} {path}: student PRs may only add records/*.yaml")
    if not added_records:
        errors.append("PR must add at least one records/*.yaml file")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check files changed by a student DNS request PR")
    parser.add_argument("base", help="base branch commit SHA")
    parser.add_argument("head", help="PR head commit SHA")
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    args = parser.parse_args()
    errors = validate_pr_changes(args.root, args.base, args.head)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("PR changes valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
