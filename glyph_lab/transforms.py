from __future__ import annotations

from PIL import Image


def scale_nearest(image: Image.Image, factor: int) -> Image.Image:
    width, height = image.size
    return image.resize((width * factor, height * factor), Image.Resampling.NEAREST)
