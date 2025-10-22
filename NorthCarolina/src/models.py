"""Data models for North Carolina candidate system.

Reuses shared models from Maryland implementation.
"""

import sys
from pathlib import Path

# Add parent directory to path to import from Maryland
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import shared models from Maryland
from Maryland.src.models import (
    OfficeLevel,
    CandidateStatus,
    MatchDecision,
    NormalizedCandidate,
    CandidateContactInfo,
    CandidateSocialMedia,
    CandidateFilingInfo,
    IngestRun,
    CandidateMatch,
    CandidateSource,
    DatabaseCandidate,
    UpdateStatistics
)

__all__ = [
    'OfficeLevel',
    'CandidateStatus',
    'MatchDecision',
    'NormalizedCandidate',
    'CandidateContactInfo',
    'CandidateSocialMedia',
    'CandidateFilingInfo',
    'IngestRun',
    'CandidateMatch',
    'CandidateSource',
    'DatabaseCandidate',
    'UpdateStatistics'
]
