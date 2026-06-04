from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MeasurementRecord:
    name: str
    value: Any
    unit: str
    source_layers: list[str]
    source_measurements: list[str]
    method: str
    confidence: float
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError("measurement confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        data = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source_layers": self.source_layers,
            "source_measurements": self.source_measurements,
            "method": self.method,
            "confidence": round(self.confidence, 4),
            "notes": self.notes,
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data


def measurement_record(
    name: str,
    value: Any,
    unit: str,
    source_layers: list[str],
    source_measurements: list[str],
    method: str,
    confidence: float,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return MeasurementRecord(
        name=name,
        value=value,
        unit=unit,
        source_layers=source_layers,
        source_measurements=source_measurements,
        method=method,
        confidence=confidence,
        notes=notes,
        metadata=metadata or {},
    ).to_dict()
