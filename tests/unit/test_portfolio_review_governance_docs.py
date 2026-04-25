from pathlib import Path

INVENTORY = Path("docs/portfolio-review-attribute-inventory.md")
DESIGN_SYSTEM = Path("docs/portfolio-review-typst-design-system.md")
TEMPLATE_WIKI = Path("wiki/Template-Registry.md")
TEMPLATE_DIR = Path("templates/typst/portfolio-review/v1")


def test_portfolio_review_attribute_inventory_tracks_source_ownership_and_gaps() -> None:
    inventory = INVENTORY.read_text(encoding="utf-8")

    for heading in [
        "| Attribute | Business meaning | Report section | Source application |",
        "available and used",
        "available but not yet placed properly",
        "missing from upstream",
        "needs clarification",
    ]:
        assert heading in inventory

    for source in [
        "lotus-core",
        "lotus-performance",
        "lotus-risk",
        "lotus-report",
        "lotus-manage",
        "lotus-advise",
        "lotus-ai",
    ]:
        assert source in inventory

    for governed_gap in [
        "Target allocation / strategic asset allocation gap",
        "Risk-free rate and benchmark supportability",
        "Advisory recommendation / suitability rationale",
        "AI-generated narrative",
    ]:
        assert governed_gap in inventory


def test_portfolio_review_docs_link_design_system_and_inventory() -> None:
    design_system = DESIGN_SYSTEM.read_text(encoding="utf-8")
    wiki = TEMPLATE_WIKI.read_text(encoding="utf-8")

    assert "docs/portfolio-review-attribute-inventory.md" in design_system
    assert "docs/portfolio-review-attribute-inventory.md" in wiki
    assert "source-backed" in design_system
    assert "Source-Backed Attribute Model" in design_system


def test_portfolio_review_templates_use_shared_design_tokens_for_page_furniture() -> None:
    main_template = (TEMPLATE_DIR / "main.typ").read_text(encoding="utf-8")
    theme = (TEMPLATE_DIR / "_theme.typ").read_text(encoding="utf-8")
    components = (TEMPLATE_DIR / "_components.typ").read_text(encoding="utf-8")

    assert "page-margin-x" in theme
    assert "page-margin-y" in theme
    assert "panel-radius" in theme
    assert "hairline" in theme
    assert "margin: (x: page-margin-x, y: page-margin-y)" in main_template
    assert "#let page-header(" in components
    assert "#let report-panel(" in components
    assert "#let section-lead(" in components
