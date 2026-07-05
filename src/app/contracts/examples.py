from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH = (
    Path(__file__).resolve().parent / "examples" / "portfolio-review-render-package.v1.json"
)


def load_portfolio_review_render_package_example() -> dict[str, Any]:
    payload = json.loads(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload)
