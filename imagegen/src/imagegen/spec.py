"""Normalized request/result types — the stable seam between core and providers.

GenSpec is the *union superset* of every provider's call shape (GPT Image 2
today; Forge tomorrow — sync/async, key/no-key, seed/no-seed, negative-prompt
or not, batch-N or 1, stream or not, moderation or not). A provider reads the
fields it understands and ignores the rest. This is why adding a provider needs
no change here. GenSpec fields are part of the STABLE contract (see README).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenSpec:
    """One image-generation request, provider-agnostic."""

    prompt: str
    provider: str = "gpt-image-2"
    model: str = ""  # "" → provider default
    size: str = "1024x1024"
    quality: str = "low"
    n: int = 1
    output_format: str = "jpeg"
    output_compression: int = 85
    moderation: str = "low"  # provider MAY ignore (Forge has none)
    seed: int | None = None  # provider MAY ignore (GPT Image 2 has none)
    negative_prompt: str = ""  # provider MAY ignore (GPT Image 2 has none)
    stream: bool = False
    partial_images: int = 2
    edit_ref: Path | None = None  # set → reference/edit mode
    extra: dict = field(default_factory=dict)  # raw provider passthrough

    @property
    def mode(self) -> str:
        return "edit" if self.edit_ref else "generate"


@dataclass
class ImageResult:
    """One decoded image (or partial preview) yielded by a provider."""

    data: bytes
    index: int = 0
    is_partial: bool = False
    partial_index: int = 0
