"""
confidence_guard.py — Guard based on data_confidence from AI Engine.

Per ai-api-contract.md:
  - data_confidence = LOW when CUR delay > 36h or CE fallback active
  - When LOW: lock containment to dry-run/alert-only
  - When LOW: signal that telemetry is not sufficiently reliable
"""
from __future__ import annotations

from workers.containment_worker.model.input import DATA_CONFIDENCE_HIGH, DATA_CONFIDENCE_LOW


def is_confidence_sufficient(data_confidence: str) -> bool:
    """
    Check whether data_confidence is sufficient to execute a real action.

    Returns:
        True if HIGH — allows apply/tag/suggest
        False if LOW — dry-run only
    """
    return data_confidence == DATA_CONFIDENCE_HIGH


def get_confidence_override_reason(data_confidence: str) -> str:
    """Return override reason if confidence is insufficient."""
    if data_confidence == DATA_CONFIDENCE_LOW:
        return (
            "data_confidence=LOW: CUR data may be delayed or incomplete "
            "(telemetry_delay_event=true). Containment locked to dry-run "
            "to prevent incorrect actions on lagged billing data."
        )
    return ""
