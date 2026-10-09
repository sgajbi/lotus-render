"""Consumer shapes match r3: unchanged r2 schemas with corrected source-cut semantics."""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.contracts.composite_eligibility import CompositeEligibilityContent
from app.contracts.composite_eligibility_selection import EligibilitySelection
from app.contracts.examples import load_composite_eligibility_render_package_example
from app.contracts.render_package import RenderPackage
from app.main import create_app


def _semantic_schema(value: Any) -> Any:
    if isinstance(value, list):
        return [_semantic_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {
        ("anyOf" if key == "oneOf" else key): _semantic_schema(item)
        for key, item in value.items()
        if key not in {"title", "description", "discriminator"}
    }
    for key in ("anyOf", "required"):
        if key in result:
            result[key] = sorted(result[key], key=lambda item: json.dumps(item, sort_keys=True))
    return result


def test_selector_and_whole_source_dtos_match_frozen_r2_constraints() -> None:
    # Union variants have disjoint required Literal evidence_kind values, so
    # oneOf/anyOf plus discriminator metadata describe the same admitted values.
    for model, name in (
        (EligibilitySelection, "eligibility_selection.v4.schema.json"),
        (CompositeEligibilityContent, "composite_review.v4.schema.json"),
    ):
        frozen = json.loads((Path("contracts/report-data") / name).read_bytes())
        assert _semantic_schema(model.model_json_schema()) == _semantic_schema(frozen)


def test_current_frozen_contract_bytes_remain_supplier_owned() -> None:
    for name, digest in (
        (
            "composite_review.v4.schema.json",
            "2214d2044980fc81007637e0504a46d13b2cbf10959fd2ca2198d2ed5f557e73",
        ),
        (
            "eligibility_selection.v4.schema.json",
            "cd71b7ab72fc9fd5493ca399e3a1f53690b426b8d652628e0b70a40c54f53171",
        ),
        (
            "composite_review.v4.interface.json",
            "348259b5add5a3a8bec679a1b6036c5ac80285392156e534df30cd0f7b9559aa",
        ),
    ):
        assert (
            hashlib.sha256((Path("contracts/report-data") / name).read_bytes()).hexdigest()
            == digest
        )


def test_client_openapi_and_golden_retain_exact_actual_worker_package() -> None:
    paths = (
        Path("src/app/contracts/examples/composite-review-render-package.v4.json"),
        Path("tests/golden/composite-review/v4/render-package.json"),
    )
    for path in paths:
        raw = path.read_bytes()
        assert len(raw) == 300045
        assert hashlib.sha256(raw).hexdigest() == (
            "6658fbc94eff3a076292a54b41e1261709629ea54dd4aed2590327e8461a7f4a"
        )
    example = load_composite_eligibility_render_package_example()
    assert example == json.loads(paths[0].read_bytes())
    package = RenderPackage.model_validate(example)
    assert package.report_data["contract_version"] == "composite_review.v4"
    examples = create_app().openapi()["paths"]["/renders"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]
    # FastAPI removes None values from inline examples, which would corrupt source hashes
    # and required null cells. The external example retains the producer's exact bytes.
    published = examples["composite_eligibility_xlsx_package"]
    assert "value" not in published
    assert published["externalValue"] == (
        "https://raw.githubusercontent.com/sgajbi/lotus-render/main/"
        "src/app/contracts/examples/composite-review-render-package.v4.json"
    )
