"""What an explicit section selection means, resolved once and failed closed.

The invariant: **an explicit scope can narrow a document or fail; it can never silently
widen it.** Before this module, an unknown requested section was silently dropped, and a
request whose every token was unknown or unavailable -- or an explicit empty list -- fell
back to the DEFAULT FULL REPORT. A caller who asked for one page could receive eleven,
which is an expansion of caller intent no document pipeline may perform.

The semantics now:

- **Absent / null `sections`**: the documented default composition -- every section this
  package can draw, in document order.
- **Explicit non-empty list**: every token must resolve to a canonical section this
  package can draw. Any unknown or unavailable token refuses the whole selection before
  compilation, naming every offending token -- a mixed request is not partially honoured,
  because drawing the valid remainder answers a request nobody made.
- **Explicit empty list**: refused. An empty document has no defined business meaning,
  and reaching the default through `[]` is the silent widening this module exists to end.
- **Not a list at all**: refused. It is explicit, and it cannot be validated.
- **The appendix, requested but explaining nothing**: dropped, not refused -- the one
  documented narrowing. The appendix explains the terms the document uses, and its
  applicability is Render's own presentation logic, unknowable to the caller at order
  time; "include it if there are terms to explain" is the only orderable meaning
  (`test_an_explicitly_requested_appendix_is_still_dropped_when_it_explains_nothing`).

Caller ordering is contractual: they asked for these sections in this sequence, and a
document that reorders a request answers a question nobody asked. Duplicates draw once,
at their first position -- deduplication is a presentation mechanic, not a scope change.

Only the portfolio review defines a section-selection surface. An explicit `sections`
field on any other template family is refused rather than ignored: silently discarding
an instruction is the same fail-open with a different face.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence

from app.contracts.render_package import RenderPackage
from app.services.appendix_glossary import applicable_glossary
from app.services.render_content import parse_portfolio_review_content

SECTIONED_TEMPLATE_ID = "portfolio-review"

# Every section the portfolio review can draw, in the order a document presents them.
DEFAULT_SECTION_ORDER = (
    "cover",
    "contents",
    "overview",
    "performance",
    "allocation",
    "positions",
    "transactions",
    "advisory_narrative",
    "advisor_memo",
    "advisor_commentary",
    "appendix",
)

# Sections that appear only when the package carries them. Everything else is on every
# portfolio review, and the appendix is on unless it would explain nothing.
OPTIONAL_SECTIONS = frozenset({"advisory_narrative", "advisor_memo", "advisor_commentary"})

# Canonical keys an explicit request may name. `scope` and `holdings` are alternate
# canonical names for pages that answer to two vocabularies.
CANONICAL_SECTIONS = frozenset({*DEFAULT_SECTION_ORDER, "scope", "holdings"})

_SECTION_KEY_ALIASES = {
    "detailed-positions": "positions",
    "holdings-appendix": "positions",
    "asset-allocation": "allocation",
    "scope-of-analysis": "overview",
    "performance-review": "performance",
    "transaction-list": "transactions",
    "additional-information": "appendix",
    "advisor-narrative": "advisory-narrative",
    "advisory": "advisory-narrative",
    "reviewed-advisory": "advisory-narrative",
    "reviewed-advisory-narrative": "advisory-narrative",
    "advisor-proposal-memo": "advisor-memo",
    "proposal-memo": "advisor-memo",
    "memo": "advisor-memo",
}


class SectionSelectionError(ValueError):
    """An explicit section selection Render cannot honour exactly as asked."""


def normalized_section_key(item: object) -> str:
    key = str(item).strip().lower().replace("_", "-")
    return _SECTION_KEY_ALIASES.get(key, key).replace("-", "_")


def included_optional_sections(report_data: Mapping[str, object]) -> set[str]:
    """Which optional sections this package carries. One set rather than one flag each,
    so a package carrying two of them draws two -- the enumerated form could only pick
    one."""
    included = set()
    for key, field in (
        ("advisory_narrative", "reviewed_advisory_narrative"),
        ("advisor_memo", "advisor_proposal_memo"),
        ("advisor_commentary", "advisor_commentary"),
    ):
        block = report_data.get(field)
        if isinstance(block, Mapping) and block.get("status") == "included":
            included.add(key)
    return included


def _is_drawable(key: str, *, included: Collection[str], include_appendix: bool) -> bool:
    """Whether this document can draw that section at all.

    One predicate, because the default list and an explicit request are bounded by the
    same thing: a section the package does not carry cannot be requested into existence.
    """
    if key in OPTIONAL_SECTIONS:
        return key in included
    return key != "appendix" or include_appendix


def default_section_keys(
    *, included: Collection[str] = (), include_appendix: bool = True
) -> list[str]:
    """Every section this document can draw, in document order."""
    return [
        key
        for key in DEFAULT_SECTION_ORDER
        if _is_drawable(key, included=included, include_appendix=include_appendix)
    ]


def resolve_section_keys(
    requested_sections: object,
    *,
    included: Collection[str] = (),
    include_appendix: bool = True,
) -> list[str]:
    """The sections to draw, or SectionSelectionError when the request cannot be honoured.

    The error message names every offending token verbatim, because the caller fixes
    tokens, not categories -- and the same request refuses identically on retry.
    """
    if requested_sections is None:
        return default_section_keys(included=included, include_appendix=include_appendix)
    if not isinstance(requested_sections, Sequence) or isinstance(
        requested_sections, (str, bytes, bytearray)
    ):
        raise SectionSelectionError(
            "`sections` must be a list of section names; omit the field for the "
            "default composition."
        )
    if not requested_sections:
        raise SectionSelectionError(
            "an explicit empty `sections` list orders no document. Omit the field for "
            "the default composition, or name the sections to draw."
        )
    return _validated_keys(requested_sections, included=included, include_appendix=include_appendix)


def _refused_tokens(
    tokens: list[tuple[str, str]], included: Collection[str]
) -> tuple[list[str], list[str]]:
    unknown = [raw for raw, key in tokens if key not in CANONICAL_SECTIONS]
    unavailable = [raw for raw, key in tokens if key in OPTIONAL_SECTIONS and key not in included]
    return unknown, unavailable


def _validated_keys(
    requested_sections: Sequence[object],
    *,
    included: Collection[str],
    include_appendix: bool,
) -> list[str]:
    tokens = [(str(item), normalized_section_key(item)) for item in requested_sections]
    unknown, unavailable = _refused_tokens(tokens, included)
    if unknown or unavailable:
        raise SectionSelectionError(_refusal_message(unknown, unavailable))
    resolved: list[str] = []
    for _, key in tokens:
        # The drawability filter only ever drops the appendix here (asking for the
        # section does not create something for it to say); a duplicate draws once,
        # at its first position.
        if (
            _is_drawable(key, included=included, include_appendix=include_appendix)
            and key not in resolved
        ):
            resolved.append(key)
    return resolved


def _refusal_message(unknown: list[str], unavailable: list[str]) -> str:
    reasons = []
    if unknown:
        named = ", ".join(repr(token) for token in unknown)
        reasons.append(f"unknown section(s) {named}")
    if unavailable:
        named = ", ".join(repr(token) for token in unavailable)
        reasons.append(f"section(s) not available in this package: {named}")
    return (
        f"explicit section selection refused: {'; '.join(reasons)}. An explicit "
        "selection is honoured exactly or not at all -- it never silently narrows "
        "further or widens to the default report."
    )


def section_selection_refusal(render_package: RenderPackage) -> str | None:
    """Why this package's explicit section selection cannot be honoured, or None.

    Checked at admission, before a render slot is taken: the same selection refuses
    identically on retry, so the caller learns everything at submit time. A package
    whose *content* is malformed returns None here -- the render pipeline states that
    failure itself, and this check must not preempt it with a worse message.
    """
    sections = render_package.render_context.get("sections")
    if sections is None:
        return None
    if render_package.template_id != SECTIONED_TEMPLATE_ID:
        return (
            f"template '{render_package.template_id}' defines no section selection; "
            "omit `sections` from the render context."
        )
    try:
        report_data = parse_portfolio_review_content(render_package).as_report_data()
    except ValueError:
        return None
    try:
        resolve_section_keys(
            sections,
            included=included_optional_sections(report_data),
            include_appendix=bool(applicable_glossary(report_data)),
        )
    except SectionSelectionError as error:
        return str(error)
    return None
