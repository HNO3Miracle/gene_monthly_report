"""Parse package names from commit messages."""

import re


# Patterns to extract package name from commit messages like:
#   SPECS: python-foo: Update to 1.2.3
#   SPECS: Add python-foo.
#   SPECS: python-foo: Rename package & ...
#   .github: build: prefer libomp   (non-SPECS commit)

_SPECS_COLON_RE = re.compile(r"^SPECS:\s+([^:]+?):\s+", re.IGNORECASE)
_SPECS_ADD_RE   = re.compile(r"^SPECS:\s+Add\s+([^.]+)", re.IGNORECASE)


def extract_package_name(commit_message: str) -> str | None:
    """
    Try to extract a package name from a single commit message first line.
    Returns None if the message doesn't match any known pattern.
    """
    msg = commit_message.strip().split("\n")[0]

    m = _SPECS_COLON_RE.match(msg)
    if m:
        return m.group(1).strip()

    m = _SPECS_ADD_RE.match(msg)
    if m:
        # "Add python-foo." or "Add python-foo, python-bar."
        raw = m.group(1).strip().rstrip(".")
        # take only the first package if comma-separated
        return raw.split(",")[0].strip()

    return None


def packages_from_commits(commit_messages: list[str]) -> list[str]:
    """
    Extract unique package names from a list of commit messages,
    preserving insertion order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for msg in commit_messages:
        name = extract_package_name(msg)
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result
