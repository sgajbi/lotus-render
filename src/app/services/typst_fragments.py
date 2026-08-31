"""Advisory, wave, outcome and proof-pack fragment emitters.

Pure functions that turn governed report data into Typst source fragments.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.services.absence import supplied_text
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
            "#wave-item-row([Not available], [Not available], [Not available], "
            "[Not available], [Not available], [No item evidence supplied.])"
        )
    rows = []
    for item in items:
        row = mapping(item)
        reasons = ", ".join(string_list(row.get("reason_codes"))) or "none"
        alternative_id = escape_typst_text(supplied_text(row.get("selected_alternative_id")))
        rows.append(
            "wave-item-row("
            f"[{escape_typst_text(supplied_text(row.get('portfolio_id')))}], "
            f"[{escape_typst_text(supplied_text(row.get('state')))}], "
            f"[{escape_typst_text(supplied_text(row.get('proof_pack_id')))}], "
            f"[{escape_typst_text(supplied_text(row.get('proof_pack_state')))}], "
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
        label = f"{event.get('event_type', 'event')} -> {supplied_text(event.get('to_state'))}"
        value = (
            f"{supplied_text(event.get('reason_code'))} / "
            f"{supplied_text(event.get('actor_id'))} / "
            f"{supplied_text(event.get('created_at'))}"
        )
        rows.append(f"key-value-row([{escape_typst_text(label)}], [{escape_typst_text(value)}])")
    return markup_calls(rows)


def render_outcome_dimension_rows(dimensions: object) -> str:
    if not isinstance(dimensions, list) or not dimensions:
        return (
            "#dimension-row([Not available], [Not available], [Not available], "
            "[Not available], [Not available], [No dimension evidence supplied.])"
        )
    rows = []
    for item in dimensions:
        dimension = mapping(item)
        rows.append(
            "dimension-row("
            f"[{escape_typst_text(supplied_text(dimension.get('dimension')))}], "
            f"[{escape_typst_text(supplied_text(dimension.get('state')))}], "
            f"[{escape_typst_text(supplied_text(dimension.get('expected')))}], "
            f"[{escape_typst_text(supplied_text(dimension.get('realized')))}], "
            f"[{escape_typst_text(supplied_text(dimension.get('variance')))}], "
            f"[{escape_typst_text(str(dimension.get('explanation', '')))}]"
            ")"
        )
    return markup_calls(rows)


def render_proof_pack_section_rows(sections: object) -> str:
    if not isinstance(sections, list) or not sections:
        return (
            "#section-row([Not available], [Not available], [Not available], "
            "[No section evidence supplied.], [none])"
        )
    rows = []
    for item in sections:
        section = mapping(item)
        reasons = ", ".join(string_list(section.get("reason_codes"))) or "none"
        rows.append(
            "section-row("
            f"[{escape_typst_text(str(section.get('title', 'Not available')))}], "
            f"[{escape_typst_text(supplied_text(section.get('section_type')))}], "
            f"[{escape_typst_text(supplied_text(section.get('state')))}], "
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
        source_system = supplied_text(source_ref.get("source_system"))
        source_type = supplied_text(source_ref.get("source_type"))
        source_id = supplied_text(source_ref.get("source_id"))
        content_hash = supplied_text(source_ref.get("content_hash"))
        rows.append(
            "key-value-row("
            f"[{escape_typst_text(source_system + ':' + source_type)}], "
            f"[{escape_typst_text(source_id + ' / ' + content_hash)}]"
            ")"
        )
    return markup_calls(rows)


def render_key_value_rows(values: Mapping[str, object]) -> str:
    if not values:
        return "#key-value-row([Not available], [Not available])"
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
        "Package status": supplied_text(narrative.get("package_status")),
        "Usage": supplied_text(narrative.get("usage")),
        "Audience": supplied_text(narrative.get("audience")),
        "Proposal": supplied_text(narrative.get("proposal_id")),
        "Proposal version": supplied_text(narrative.get("proposal_version_no")),
        "Narrative": supplied_text(narrative.get("narrative_id")),
        "Narrative status": supplied_text(narrative.get("narrative_status")),
        "Review state": supplied_text(review.get("review_state")),
        "Reviewed by": supplied_text(review.get("reviewed_by")),
        "Reviewed at": supplied_text(review.get("reviewed_at")),
        "Policy version": supplied_text(narrative.get("policy_version")),
        "Source narrative hash": supplied_text(source_lineage.get("source_narrative_hash")),
    }
    return render_advisory_fact_rows(facts)


def render_advisory_fact_rows(facts: Mapping[str, object]) -> str:
    rows = []
    for key, value in facts.items():
        rows.append(
            "advisory-fact-row("
            f"[{escape_typst_text(str(key))}], "
            f"[{escape_typst_text(supplied_text(value))}]"
            ")"
        )
    return markup_calls(rows)


def render_advisor_memo_fact_rows(memo: Mapping[str, object]) -> str:
    if memo.get("status") != "included":
        return ""

    review = mapping(memo.get("review"))
    facts = {
        "Package status": supplied_text(memo.get("package_status")),
        "Usage": supplied_text(memo.get("usage")),
        "Proposal": supplied_text(memo.get("proposal_id")),
        "Proposal version": supplied_text(memo.get("proposal_version_no")),
        "Memo": supplied_text(memo.get("memo_id")),
        "Memo status": supplied_text(memo.get("memo_status")),
        "Review action": supplied_text(review.get("review_action")),
        "Reviewed by": supplied_text(review.get("reviewed_by")),
        "Reviewed at": supplied_text(review.get("reviewed_at")),
        "Client-ready publication": memo.get("client_ready_publication", "BLOCKED"),
        "Memo hash": supplied_text(memo.get("memo_hash")),
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
        status = supplied_text(section.get("status")).strip()
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
        disclosure_id = supplied_text(disclosure.get("disclosure_id")).strip()
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
            "#advisory-disclosure-block([Not available], "
            "[No reviewed narrative disclosure text supplied.])"
        )
    # Invoked, not printed. The empty-state literal above carries its own "#" and the
    # populated path joined the fragments without one, so a governed advisor memo
    # printed the call that should have drawn its disclosure -- the compliance line
    # rendered as source, on the page, under the heading "Disclosures". Exactly the
    # defect `markup_calls` was written for, in the one emitter that did not use it.
    return markup_calls(blocks, separator="\n#v(6pt)\n")
