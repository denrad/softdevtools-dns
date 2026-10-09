"""Read-only validation of student DNS request files."""

from pathlib import Path

import yaml


FIELDS = frozenset({"subdomain", "type", "target", "repository"})
MAX_BYTES = 8192


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
