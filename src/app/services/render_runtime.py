from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderRuntimeAvailability:
    available: bool
    reason: str


class RenderRuntimeProbe:
    def check_available(self) -> RenderRuntimeAvailability:
        if shutil.which("docker") or shutil.which("typst"):
            return RenderRuntimeAvailability(available=True, reason="render_runtime_available")
        return RenderRuntimeAvailability(
            available=False,
            reason="runtime_configuration_unavailable",
        )
