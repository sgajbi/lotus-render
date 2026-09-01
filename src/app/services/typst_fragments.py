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


# lotus-report normalises the commentary tone vocabulary before the package is built, and
# anything it does not recognise arrives as `neutral`. So a tone outside this set is a
# contract violation rather than a colour Render should invent one for -- and the template
# looks it up in `TONE_PALETTE`, where an unknown key is a compile error rather than a
# silent default. Falling back here keeps that failure out of a client's document.
COMMENTARY_TONES = frozenset({"positive", "neutral", "warning"})
NEUTRAL_TONE = "neutral"


def _commentary_tone(value: object) -> str:
    tone = str(value or "").strip()
    return tone if tone in COMMENTARY_TONES else NEUTRAL_TONE


GROUNDED = "grounded"
UNGROUNDED = "ungrounded"


def _commentary_grounding(item: Mapping[str, object]) -> str:
    """Whether the claim is checkable, as Report stated it.

    Never derived from `len(evidence_refs)`. Report states it, and a page that infers
    what the archived lineage states can contradict it. An unrecognised value is treated
    as ungrounded: the conservative reading is the one that does not tell a reader a
    claim is checkable when Render cannot tell.
    """
    return GROUNDED if str(item.get("grounding") or "").strip() == GROUNDED else UNGROUNDED


def _commentary_evidence(refs: object) -> str:
    """What a claim was grounded on, as one line under it.

    lotus-ai supplies metric label, value and source for each ref and all three are
    required; lotus-report drops any ref that is not complete. So a ref arriving here is
    whole, and a partial one is not a case to handle.
    """
    rendered = [
        f"{escape_typst_text(supplied_text(ref.get('metric_label')))} "
        f"{escape_typst_text(supplied_text(ref.get('metric_value')))} "
        f"({escape_typst_text(supplied_text(ref.get('source_ref')))})"
        for ref in (mapping(item) for item in mapping_entries(refs))
    ]
    if not rendered:
        return ""
    return "#commentary-evidence([" + escape_typst_text("Grounded on: ") + " ".join(rendered) + "])"


def render_commentary_points(
    commentary: Mapping[str, object], field: str, *, empty_message: str
) -> str:
    """Talking points or risks -- one shape, because they are the same thing to a reader.

    Each point carries the grounding Report stated. An ungrounded claim used to draw
    exactly like a grounded one minus its "Grounded on:" line, so it was distinguishable
    only by CONTRAST with grounded points on the same page -- and not at all on a page
    where none are grounded, which is the case that matters. Presence of a marker is
    legible where absence of a line is not.

    Empty when the package carries no accepted commentary, rather than a placeholder: the
    section is not drawn then, and a placeholder nobody sees still counts towards the
    empty-block metric. Two of them appeared on every review before this guard.

    The body is AI-drafted prose that a human accepted, which makes it the least trusted
    input this service takes. `escape_typst_text` neutralises every markup token, and
    `test_commentary_markup_reaches_the_page_as_text` reads each one back off a rendered
    page rather than trusting the escaper from here.
    """
    if commentary.get("status") != "included":
        return ""

    points: list[str] = []
    for entry in mapping_entries(commentary.get(field)):
        item = mapping(entry)
        headline = str(item.get("headline", "")).strip()
        detail = str(item.get("detail", "")).strip()
        if not headline and not detail:
            continue
        points.append(
            "#commentary-point("
            f"[{escape_typst_text(headline)}], "
            f"[{escape_typst_text(detail)}], "
            f'"{_commentary_tone(item.get("tone"))}", '
            f'"{_commentary_grounding(item)}", '
            f"[{_commentary_evidence(item.get('evidence_refs'))}]"
            ")"
        )
    if not points:
        return f"#empty-state([{escape_typst_text(empty_message)}])"
    return "\n".join(points)


def render_advisor_commentary_fact_rows(commentary: Mapping[str, object]) -> str:
    """The lineage a reader needs to trace an accepted commentary back to its run."""
    review = mapping(commentary.get("review"))
    context = mapping(commentary.get("context"))
    rows = (
        ("Status", supplied_text(commentary.get("advisor_brief_status"))),
        ("Coverage", supplied_text(commentary.get("coverage_state"))),
        ("Reviewed by", supplied_text(review.get("reviewed_by"))),
        ("Reviewed at", supplied_text(review.get("reviewed_at"))),
        ("Run", supplied_text(commentary.get("run_id"))),
        ("Pack", supplied_text(commentary.get("pack_id"))),
        ("Authority owner", supplied_text(commentary.get("workflow_authority_owner"))),
        ("Period", supplied_text(context.get("period"))),
        ("Content hash", supplied_text(commentary.get("content_hash"))),
    )
    # `markup_calls` prefixes the `#` per fragment, so handing it one newline-joined
    # string invokes the first row and prints the rest as source. That is the defect the
    # printed-call-syntax gate exists for, and it happened here on the first attempt.
    return markup_calls(
        [
            f"advisory-fact-row([{escape_typst_text(label)}], [{escape_typst_text(value)}])"
            for label, value in rows
        ]
    )


def render_advisor_commentary_prose(commentary: Mapping[str, object], field: str) -> str:
    """One free-prose field of the commentary, escaped for the markup slot it lands in.

    Here rather than in `typst_contexts` because that module emits Typst *string
    literals* and this is markup -- `test_a_string_literal_emitter_never_uses_the_markup_escaper`
    holds that line, and it is the line that keeps a value containing a quote from
    breaking out of a literal into code.
    """
    return escape_typst_text(supplied_text(commentary.get(field)))
