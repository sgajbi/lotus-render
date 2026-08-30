"""Advisory, wave, outcome and proof-pack fragment emitters.

Pure functions that turn governed report data into Typst source fragments.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.services.typst_values import (
    escape_typst_text,
    mapping,
    mapping_entries,
    string_list,
)


def markup_calls(fragments: Iterable[str], *, separator: str = "\n") -> str:
    """Join call fragments so each is invoked at a markup substitution site.

    In Typst markup, a bare ``name(...)`` is text, not a call. Every fragment here is
    substituted into markup, and every one of them omitted the ``#`` -- so three
    families printed their main content tables as their own source. The outcome
    review's dimension evidence read, on the page::

        dimension-row([PERFORMANCE], [READY], [4.10], [4.22], [0.12], [...])

    Emitters whose output is spliced into a *code* context -- the dense position and
    transaction rows, which land inside ``..( ... ).flatten()`` -- must not use this:
    there a ``#`` is a syntax error, not a fix.
    """
    return separator.join(f"#{fragment}" for fragment in fragments)


def render_wave_item_rows(items: object) -> str:
    if not isinstance(items, list) or not items:
        return (
            "#wave-item-row([Not available], [not_available], [not_available], "
            "[not_available], [not_available], [No item evidence supplied.])"
        )
    rows = []
    for item in items:
        row = mapping(item)
        reasons = ", ".join(string_list(row.get("reason_codes"))) or "none"
        alternative_id = escape_typst_text(str(row.get("selected_alternative_id", "not_available")))
        rows.append(
            "wave-item-row("
            f"[{escape_typst_text(str(row.get('portfolio_id', 'not_available')))}], "
            f"[{escape_typst_text(str(row.get('state', 'not_available')))}], "
            f"[{escape_typst_text(str(row.get('proof_pack_id', 'not_available')))}], "
            f"[{escape_typst_text(str(row.get('proof_pack_state', 'not_available')))}], "
            f"[{alternative_id}], "
            f"[{escape_typst_text(reasons)}]"
            ")"
        )
    return markup_calls(rows)


def render_wave_event_rows(events: object) -> str:
    if not isinstance(events, list) or not events:
        return "#key-value-row([Latest event], [No event evidence supplied.])"
    rows = []
    for item in events:
        event = mapping(item)
        label = f"{event.get('event_type', 'event')} -> {event.get('to_state', 'not_available')}"
        value = (
            f"{event.get('reason_code', 'not_available')} / "
            f"{event.get('actor_id', 'not_available')} / "
            f"{event.get('created_at', 'not_available')}"
        )
        rows.append(f"key-value-row([{escape_typst_text(label)}], [{escape_typst_text(value)}])")
    return markup_calls(rows)


def render_outcome_dimension_rows(dimensions: object) -> str:
    if not isinstance(dimensions, list) or not dimensions:
        return (
            "#dimension-row([Not available], [not_available], [not_available], "
            "[not_available], [not_available], [No dimension evidence supplied.])"
        )
    rows = []
    for item in dimensions:
        dimension = mapping(item)
        rows.append(
            "dimension-row("
            f"[{escape_typst_text(str(dimension.get('dimension', 'not_available')))}], "
            f"[{escape_typst_text(str(dimension.get('state', 'not_available')))}], "
            f"[{escape_typst_text(str(dimension.get('expected', 'not_available')))}], "
            f"[{escape_typst_text(str(dimension.get('realized', 'not_available')))}], "
            f"[{escape_typst_text(str(dimension.get('variance', 'not_available')))}], "
            f"[{escape_typst_text(str(dimension.get('explanation', '')))}]"
            ")"
        )
    return markup_calls(rows)


def render_proof_pack_section_rows(sections: object) -> str:
    if not isinstance(sections, list) or not sections:
        return (
            "#section-row([Not available], [not_available], [not_available], "
            "[No section evidence supplied.], [none])"
        )
    rows = []
    for item in sections:
        section = mapping(item)
        reasons = ", ".join(string_list(section.get("reason_codes"))) or "none"
        rows.append(
            "section-row("
            f"[{escape_typst_text(str(section.get('title', 'Not available')))}], "
            f"[{escape_typst_text(str(section.get('section_type', 'not_available')))}], "
            f"[{escape_typst_text(str(section.get('state', 'not_available')))}], "
            f"[{escape_typst_text(str(section.get('summary', '')))}], "
            f"[{escape_typst_text(reasons)}]"
            ")"
        )
    return markup_calls(rows)


def render_source_lineage_rows(source_lineage: object) -> str:
    if not isinstance(source_lineage, list) or not source_lineage:
        return "#key-value-row([Source lineage], [No source lineage supplied.])"
    rows = []
    for item in source_lineage:
        source_ref = mapping(item)
        source_system = str(source_ref.get("source_system", "not_available"))
        source_type = str(source_ref.get("source_type", "not_available"))
        source_id = str(source_ref.get("source_id", "not_available"))
        content_hash = str(source_ref.get("content_hash", "not_available"))
        rows.append(
            "key-value-row("
            f"[{escape_typst_text(source_system + ':' + source_type)}], "
            f"[{escape_typst_text(source_id + ' / ' + content_hash)}]"
            ")"
        )
    return markup_calls(rows)


def render_key_value_rows(values: Mapping[str, object]) -> str:
    if not values:
        return "#key-value-row([Not available], [not_available])"
    return markup_calls(
        f"key-value-row([{escape_typst_text(str(key))}], [{escape_typst_text(str(value))}])"
        for key, value in sorted(values.items())
    )


def render_reviewed_advisory_fact_rows(narrative: Mapping[str, object]) -> str:
    if narrative.get("status") != "included":
        return ""

    review = mapping(narrative.get("review"))
    source_lineage = mapping(narrative.get("source_lineage"))
    facts = {
        "Package status": narrative.get("package_status", "not_available"),
        "Usage": narrative.get("usage", "not_available"),
        "Audience": narrative.get("audience", "not_available"),
        "Proposal": narrative.get("proposal_id", "not_available"),
        "Proposal version": narrative.get("proposal_version_no", "not_available"),
        "Narrative": narrative.get("narrative_id", "not_available"),
        "Narrative status": narrative.get("narrative_status", "not_available"),
        "Review state": review.get("review_state", "not_available"),
        "Reviewed by": review.get("reviewed_by", "not_available"),
        "Reviewed at": review.get("reviewed_at", "not_available"),
        "Policy version": narrative.get("policy_version", "not_available"),
        "Source narrative hash": source_lineage.get(
            "source_narrative_hash",
            "not_available",
        ),
    }
    return render_advisory_fact_rows(facts)


def render_advisory_fact_rows(facts: Mapping[str, object]) -> str:
    rows = []
    for key, value in facts.items():
        rows.append(
            "advisory-fact-row("
            f"[{escape_typst_text(str(key))}], "
            f"[{escape_typst_text(str(value if value is not None else 'not_available'))}]"
            ")"
        )
    return markup_calls(rows)


def render_advisor_memo_fact_rows(memo: Mapping[str, object]) -> str:
    if memo.get("status") != "included":
        return ""

    review = mapping(memo.get("review"))
    facts = {
        "Package status": memo.get("package_status", "not_available"),
        "Usage": memo.get("usage", "not_available"),
        "Proposal": memo.get("proposal_id", "not_available"),
        "Proposal version": memo.get("proposal_version_no", "not_available"),
        "Memo": memo.get("memo_id", "not_available"),
        "Memo status": memo.get("memo_status", "not_available"),
        "Review action": review.get("review_action", "not_available"),
        "Reviewed by": review.get("reviewed_by", "not_available"),
        "Reviewed at": review.get("reviewed_at", "not_available"),
        "Client-ready publication": memo.get("client_ready_publication", "BLOCKED"),
        "Memo hash": memo.get("memo_hash", "not_available"),
    }
    return render_advisory_fact_rows(facts)


def render_advisor_memo_section_blocks(sections: object) -> str:
    blocks: list[str] = []
    for item in mapping_entries(sections):
        section = mapping(item)
        summary = str(section.get("summary", "")).strip()
        if not summary:
            continue
        title = str(section.get("title", "Advisor proposal memo section")).strip()
        status = str(section.get("status", "not_available")).strip()
        blocks.append(
            "advisory-narrative-block("
            f"[{escape_typst_text(title + ' - ' + status)}], "
            f"[{escape_typst_text(summary)}]"
            ")"
        )
    if not blocks:
        return (
            "#advisory-narrative-block([No advisor memo section supplied.], "
            "[No advisor proposal memo body was included in the render package.])"
        )
    return markup_calls(blocks, separator="\n#v(8pt)\n")


def render_advisory_narrative_blocks(sections: object) -> str:
    blocks: list[str] = []
    for item in mapping_entries(sections):
        section = mapping(item)
        body = str(section.get("body", "")).strip()
        if not body:
            continue
        title = str(section.get("title", "Reviewed advisory section")).strip()
        blocks.append(
            f"advisory-narrative-block([{escape_typst_text(title)}], [{escape_typst_text(body)}])"
        )
    if not blocks:
        return (
            "#advisory-narrative-block([No approved narrative section supplied.], "
            "[No reviewed narrative body was included in the render package.])"
        )
    return markup_calls(blocks, separator="\n#v(8pt)\n")


def render_advisory_disclosure_blocks(disclosures: object) -> str:
    blocks: list[str] = []
    for item in mapping_entries(disclosures):
        disclosure = mapping(item)
        disclosure_id = str(disclosure.get("disclosure_id", "not_available")).strip()
        text = str(disclosure.get("text", "")).strip()
        if not text:
            continue
        blocks.append(
            "advisory-disclosure-block("
            f"[{escape_typst_text(disclosure_id)}], "
            f"[{escape_typst_text(text)}]"
            ")"
        )
    if not blocks:
        return (
            "#advisory-disclosure-block([not_available], "
            "[No reviewed narrative disclosure text supplied.])"
        )
    return "\n#v(6pt)\n".join(blocks)
