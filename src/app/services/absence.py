"""What a reader sees where a value did not arrive.

Three things reached rendered documents because absence was handled three ways and none
of them ended in a sentence:

- `str(report_data.get("source_contract_version", "not_available"))` put the literal
  **None** on a governed proof pack. The default only fires when the key is missing, and
  that field is declared `str | None`, so it was present and empty and `str()` did the
  rest.
- Twenty-two call sites fell back to the string `not_available`, which is a sentinel and
  not a sentence. It reached the page unchanged, in snake case, on the degraded
  portfolio review and on every rebalance wave.
- Two modules had already grown their own idea of what counts as absent -- one in
  `appendix_glossary`, one in `statement_tables` -- with different lists.

So absence is decided once, here, and it renders as "Not available": the wording the
design system's own empty state already uses, so a missing value reads the same whether
it is a field or a whole section.
"""

from __future__ import annotations

NOT_AVAILABLE = "Not available"

# How report data spells "there is nothing here". Everything is compared case-folded, so
# `None`, `none` and `NONE` are one entry.
_ABSENT = frozenset(
    {
        "",
        "-",
        "--",
        "n/a",
        "na",
        "nan",
        "none",
        "not available",
        "not_available",
        "null",
        "undefined",
        "unknown",
    }
)


def is_supplied(value: object) -> bool:
    """Whether this value is something a document can show a reader."""
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.casefold() not in _ABSENT


def supplied_text(value: object, *, absent: str = NOT_AVAILABLE) -> str:
    """The value as a reader should see it, or how the document says it is missing.

    `absent` is for the places that say it differently -- a table cell that reads "No
    detail supplied", say -- not for passing a sentinel through under a new name.
    """
    return str(value).strip() if is_supplied(value) else absent
