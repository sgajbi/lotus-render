"""Read a failed compile: what killed it, and whether the document is why.

A compile can fail in three unrelated ways that all arrive as a non-zero exit, and only
one of them is anything the caller can act on. `render_recovery` takes the category from
here and decides what an operator is told; this module decides which category it is.

The hard case is a silent death. A compile killed by a signal writes nothing to either
stream, so the signal number is the only evidence there is about why it died.
"""

from __future__ import annotations

import subprocess

from app.domain.render_attempts.models import RenderFailureCategory

# Linux signal numbers. A compile that dies on one reports it as `-n` when it is a direct
# child and as `128 + n` through a shell or Docker, and it arrives with both streams
# empty -- so the number is the only evidence there is about why it died.
_SIGNAL_NAMES = {
    1: "SIGHUP",
    2: "SIGINT",
    3: "SIGQUIT",
    4: "SIGILL",
    6: "SIGABRT",
    7: "SIGBUS",
    8: "SIGFPE",
    9: "SIGKILL",
    11: "SIGSEGV",
    15: "SIGTERM",
    24: "SIGXCPU",
    25: "SIGXFSZ",
}

# A bound was hit. SIGXCPU and SIGXFSZ exist for no other reason, and SIGKILL and SIGABRT
# are how the two bounds this service sets are measured to arrive: the container's memory
# limit kills the process (137, at 2,500 rows), and `ulimit -v` makes the allocator abort.
# SIGKILL is also what `docker kill` sends and the exit code cannot separate them -- but
# an operator who killed a container knows they did, and the automated case is the one
# that produces a caller-facing answer.
_BOUND_SIGNALS = frozenset({6, 9, 24, 25})

# Something told the process to stop: a deploy, an eviction, an operator. No resource
# bound sends any of these, so none of them is the document's fault.
_STOPPED_SIGNALS = frozenset({1, 2, 3, 15})


def signal_failure(signal_number: int) -> tuple[RenderFailureCategory, str]:
    """Three answers, because a killed compile is not always the document's doing.

    Every signal used to be `resource_limit_exceeded`, which is answered "not retryable,
    lotus-report owns it, send fewer rows". So a rolling deploy's SIGTERM reported a
    document permanently over the envelope, and a segfault in the compiler sent the
    caller looking for rows to remove. A smaller package fixes neither, and the first
    clears on its own.

    What is left in that category is only what a bound can produce.
    """
    name = _SIGNAL_NAMES.get(signal_number, "an unrecognised signal")
    killed = (
        f"the compile was killed by {name} (signal {signal_number}) without producing diagnostics"
    )
    if signal_number in _BOUND_SIGNALS:
        return (
            RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED,
            f"{killed}, which is what exceeding the render memory or CPU bound looks "
            "like. The document is too large for the governed envelope.",
        )
    if signal_number in _STOPPED_SIGNALS:
        return (
            RenderFailureCategory.ENGINE_UNAVAILABLE,
            f"{killed}. Nothing about the document caused it -- the runtime was shut "
            "down or evicted mid-compile -- so resubmitting the identical package is "
            "the recovery.",
        )
    return (
        RenderFailureCategory.UNEXPECTED_RENDER_ERROR,
        f"{killed}. The engine died rather than the document being too large, so a "
        "smaller package will not help and there is nothing here for the caller to fix.",
    )


def classify_compile_failure(
    process: "subprocess.CompletedProcess[str]",
) -> tuple[RenderFailureCategory, str]:
    """Tell a document that was too big from a template that was wrong.

    Both arrive as a non-zero exit. A compile killed for exceeding its memory bound
    exits ``128 + SIGKILL`` with **empty stderr**, so it used to be reported as
    ``template_render_failed`` with the summary "typst compile failed" -- the same
    words a broken template produces, and nothing an operator could act on. Measured:
    a portfolio review of 2,500 positions and 2,500 transactions exits 137 with no
    output at all, while 1,000 of each renders in about four seconds.

    The distinction matters because the two have opposite responses. A template error
    needs a fix and will fail again identically; a document over the bound needs a
    smaller document or a larger envelope, and says something about capacity rather
    than correctness.

    Which signal killed it decides between three answers, not two: see
    :func:`signal_failure`.
    """
    diagnostic = process.stderr.strip() or process.stdout.strip()
    if diagnostic:
        return RenderFailureCategory.TEMPLATE_RENDER_FAILED, diagnostic

    # No output at all: the process did not get to report anything, which on this path
    # means it was killed rather than that it disagreed with the source.
    if process.returncode < 0 or process.returncode > 128:
        signal_number = -process.returncode if process.returncode < 0 else process.returncode - 128
        return signal_failure(signal_number)
    return RenderFailureCategory.TEMPLATE_RENDER_FAILED, "typst compile failed"
