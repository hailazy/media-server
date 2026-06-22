"""Provider abstraction + registry.

Adding a provider (see README "Extending"): subclass ImageProvider, set `name`
+ `default_model`, implement generate() + estimate_cost(), decorate with
@register. Override edit() only if the backend supports reference/img2img;
otherwise the ABC default raises a clear NotImplementedError.
"""

from __future__ import annotations

import abc
from collections.abc import Iterator

from ..spec import GenSpec, ImageResult


class ImageProvider(abc.ABC):
    name: str = ""
    default_model: str = ""

    @abc.abstractmethod
    def generate(self, spec: GenSpec) -> Iterator[ImageResult]:
        """Yield 1+ ImageResult. Stream providers also yield is_partial frames."""

    def edit(self, spec: GenSpec) -> Iterator[ImageResult]:
        raise NotImplementedError(
            f"provider '{self.name}' has no edit/reference mode "
            f"(spec.edit_ref set but unsupported)"
        )

    @abc.abstractmethod
    def estimate_cost(self, spec: GenSpec) -> float:
        """Best-effort pre-call USD estimate. 0.0 for free/local providers."""


_REGISTRY: dict[str, type[ImageProvider]] = {}


def register(cls: type[ImageProvider]) -> type[ImageProvider]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} must set a non-empty `name`")
    _REGISTRY[cls.name] = cls
    return cls


def get_provider(name: str) -> ImageProvider:
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown provider '{name}'. Registered: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]()


def available() -> list[str]:
    return sorted(_REGISTRY)


# Import built-in providers so @register populates the registry on package load.
from . import gpt_image_2  # noqa: E402,F401
from . import forge  # noqa: E402,F401
