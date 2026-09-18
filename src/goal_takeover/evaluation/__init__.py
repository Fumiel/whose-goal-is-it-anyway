"""External outcomes and action-candidate scores."""

from goal_takeover.evaluation.outcomes import classify_outcome
from goal_takeover.evaluation.tool_logprob import (
    CandidateSequenceScore,
    ToolCallMargins,
    compare_candidate_sequences,
    sequence_log_probability,
    tool_margin,
)

__all__ = [
    "CandidateSequenceScore",
    "ToolCallMargins",
    "classify_outcome",
    "compare_candidate_sequences",
    "sequence_log_probability",
    "tool_margin",
]
