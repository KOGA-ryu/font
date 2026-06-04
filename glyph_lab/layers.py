from __future__ import annotations

from dataclasses import dataclass


DEFAULT_LAYER_NAMES = [
    "background",
    "mass",
    "base_fill",
    "shadow",
    "highlight",
    "edge",
    "detail",
    "ornament",
    "measurement",
]

OUTPUT_LAYER_NAMES = [name for name in DEFAULT_LAYER_NAMES if name != "background"]


@dataclass(frozen=True)
class LayerSpec:
    name: str
    order: int
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "normal"


def default_layers() -> list[LayerSpec]:
    return [LayerSpec(name=name, order=index) for index, name in enumerate(DEFAULT_LAYER_NAMES)]


def default_layer_order() -> list[str]:
    return [layer.name for layer in default_layers()]


def output_layer_order() -> list[str]:
    return list(OUTPUT_LAYER_NAMES)


def layer_sort_key(name: str) -> tuple[int, str]:
    order = {layer.name: layer.order for layer in default_layers()}
    return (order.get(name, len(order)), name)


def layer_schema() -> list[dict]:
    return [
        {
            "name": layer.name,
            "order": layer.order,
            "visible": layer.visible,
            "opacity": layer.opacity,
            "blend_mode": layer.blend_mode,
        }
        for layer in default_layers()
    ]
