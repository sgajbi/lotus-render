"""One field of a GitHub API answer, read from the body `gh api` wrote to stdout.

`gh api` prints the response body on stdout whether the request succeeded or was
refused, and on any HTTP error exits 1 with a one-line rendering on stderr, such as
`gh: Not Found (HTTP 404)`. The merged-PR dispatcher has to classify GitHub's refusals
-- the tag is absent, the one permitted fallback, or fatal -- and it must do so on what
GitHub said, not on how gh phrased it: the body carries `status` and `message` as
GitHub wrote them, and a successful ref lookup carries `object.sha`.

This reads the body once and prints the requested field, or nothing. Nothing when the
body is empty (a transport failure produced no answer at all), is not JSON, is not an
object, or lacks the field. It never exits non-zero: a failure inside `$(...)` under
`set -e` would abort the step before it could say which answer it could not classify,
and the caller already treats an empty value as "no observation" and refuses.

Usage::

    python scripts/read_github_api_answer.py status     "$RUNNER_TEMP/lookup-ref.stdout"
    python scripts/read_github_api_answer.py message    "$RUNNER_TEMP/create-ref.stdout"
    python scripts/read_github_api_answer.py object.sha "$RUNNER_TEMP/lookup-ref.stdout"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def read_field(body: str, field_path: str) -> str:
    """The scalar at a dotted path in a JSON object body, as text; "" when absent.

    GitHub writes `status` as a JSON string ("404"), so the value is returned as text
    for equality comparison in shell, and a number is rendered the same way in case
    that ever changes. Containers and booleans are not answers to any question the
    dispatcher asks, so they read as absent rather than as their Python spelling.
    """
    try:
        value: object = json.loads(body)
    except ValueError:
        return ""
    for segment in field_path.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(segment)
    if value is None or isinstance(value, bool | dict | list):
        return ""
    return str(value)


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        print("usage: read_github_api_answer.py <field.path> <body-file>", file=sys.stderr)
        return 2
    field_path, body_path = arguments
    try:
        body = Path(body_path).read_text(encoding="utf-8")
    except OSError:
        body = ""
    value = read_field(body, field_path)
    if value:
        print(value)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess
    sys.exit(main(sys.argv[1:]))
