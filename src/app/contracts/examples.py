from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH = (
    Path(__file__).resolve().parent / "examples" / "portfolio-review-render-package.v1.json"
)


def load_portfolio_review_render_package_example() -> dict[str, Any]:
    return _load_example(PORTFOLIO_REVIEW_RENDER_PACKAGE_EXAMPLE_PATH)


def load_composite_review_render_package_example() -> dict[str, Any]:
    return _load_example(
        Path(__file__).resolve().parent / "examples" / "composite-review-render-package.v1.json"
    )


def _load_example(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], payload)
