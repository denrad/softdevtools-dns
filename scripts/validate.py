"""Read-only validation of student DNS request files."""

from pathlib import Path
import re

import yaml


FIELDS = frozenset({"subdomain", "type", "target", "repository"})
MAX_BYTES = 8192
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
REPOSITORY = re.compile(
    r"https://github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,62})/([A-Za-z0-9._-]+)\Z"
)


class RequestLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("YAML aliases are not allowed")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in result:
                raise yaml.YAMLError(f"duplicate YAML key: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse_record(path: Path) -> tuple[dict[str, str] | None, list[str]]:
    """Return one four-field YAML record or errors; never write to disk."""
    try:
        with path.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
    except OSError as exc:
        return None, [f"cannot read file: {exc}"]
    if len(raw) > MAX_BYTES:
        return None, [f"file size exceeds {MAX_BYTES} bytes"]
    try:
        data = yaml.load(raw.decode("utf-8"), Loader=RequestLoader)
    except (UnicodeDecodeError, yaml.YAMLError, TypeError) as exc:
        return None, [f"invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return None, ["YAML document must be a mapping"]

    errors = []
    for field in sorted(FIELDS - data.keys()):
        errors.append(f"missing field: {field}")
    for field in sorted(data.keys() - FIELDS, key=str):
        errors.append(f"unknown field: {field}")
    for field in sorted(FIELDS & data.keys()):
        if type(data[field]) is not str:
            errors.append(f"field {field} must be a string")
    if errors:
        return None, errors
    return data, []


def validate_records(root: Path) -> list[str]:
    """Validate the local record tree without contacting external services."""
    errors = []
    reserved_path = root / "config" / "reserved-names.txt"
    try:
        reserved = {
            line.strip().lower()
            for line in reserved_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError as exc:
        errors.append(f"config/reserved-names.txt: cannot read: {exc}")
        reserved = set()

    records_dir = root / "records"
    if not records_dir.is_dir():
        return errors + ["records/: directory is missing"]

    seen = {}
    for path in sorted(records_dir.iterdir()):
        label = f"records/{path.name}"
        if path.name == ".gitkeep":
            continue
        if path.is_symlink():
            errors.append(f"{label}: symlinks are not allowed")
            continue
        if not path.is_file() or path.suffix != ".yaml":
            errors.append(f"{label}: expected a .yaml record file")
            continue
        record, file_errors = parse_record(path)
        errors.extend(f"{label}: {error}" for error in file_errors)
        if record is None:
            continue

        name = record["subdomain"]
        if not LABEL.fullmatch(name):
            reason = "use one lowercase DNS label of 1–63 characters"
            errors.append(f"{label}: invalid subdomain {name!r}; {reason}")
        if name in reserved:
            errors.append(f"{label}: subdomain {name!r} is reserved")
        if path.stem != name:
            errors.append(f"{label}: filename must be {name}.yaml")
        key = name.casefold()
        if key in seen:
            errors.append(f"{label}: duplicate subdomain {name!r} in {seen[key]}")
        else:
            seen[key] = label

        if record["type"] != "CNAME":
            errors.append(f"{label}: type must be CNAME")
        target = record["target"]
        target_user = target.removesuffix(".github.io")
        if not target.endswith(".github.io") or not LABEL.fullmatch(target_user):
            errors.append(f"{label}: target must be username.github.io")
        repository = REPOSITORY.fullmatch(record["repository"])
        if repository is None:
            errors.append(f"{label}: repository must be a GitHub HTTPS URL")
        elif target.endswith(".github.io") and repository.group(1).casefold() != target_user.casefold():
            errors.append(f"{label}: repository owner must match target user")
    return errors
