"""Names for lexical and role controls used by goal-readout datasets."""

from __future__ import annotations

from enum import StrEnum


class ControlType(StrEnum):
    EXPLANATION = "explanation"
    QUOTATION = "quotation"
    NEGATION = "negation"
    PROHIBITION = "prohibition"
    PAST_ACTION_DESCRIPTION = "past_action_description"
    LENGTH_MATCHED_BENIGN = "length_matched_benign"
