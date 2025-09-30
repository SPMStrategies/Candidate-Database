"""Data models for Maryland candidate system."""

from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, validator
from uuid import UUID


class OfficeLevel(str, Enum):
    """Office level enumeration."""
    FEDERAL = "federal"
    STATE = "state"
    LOCAL = "local"
    JUDICIAL = "judicial"


class CandidateStatus(str, Enum):
    """Candidate status enumeration."""
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    DISQUALIFIED = "disqualified"
    PENDING = "pending"


class MatchDecision(str, Enum):
    """Match decision enumeration."""
    AUTO = "auto"
    MANUAL = "manual"
    REJECTED = "rejected"


class MarylandCandidateRaw(BaseModel):
    """Raw candidate data from Maryland CSV."""
    office_name: Optional[str]
    contest_district: Optional[str]
    ballot_last_name: Optional[str]
    first_middle_name: Optional[str]
    additional_info: Optional[str]
    party: Optional[str]
    residential_jurisdiction: Optional[str]
    gender: Optional[str]
    status: Optional[str]
    filing_type_date: Optional[str]
    mailing_address: Optional[str]
    mailing_city_state_zip: Optional[str]
    public_phone: Optional[str]
    email: Optional[str]
    website: Optional[str]
    facebook: Optional[str]
    x_twitter: Optional[str]
    other_social: Optional[str]
    committee_name: Optional[str]
    
    class Config:
        extra = "allow"  # Allow additional fields from CSV


class NormalizedCandidate(BaseModel):
    """Normalized candidate for staging table."""
    # Core fields
    full_name: str
    first_name: Optional[str]
    last_name: Optional[str]
    party: Optional[str]
    office_level: OfficeLevel
    office_name: str
    state: str = "MD"
    district_number: Optional[str]
    ocd_division_id: Optional[str]
    election_year: int
    
    # Additional fields
    gender: Optional[str]
    jurisdiction: Optional[str]
    committee_name: Optional[str]
    website: Optional[str]
    email: Optional[str]
    status: Optional[str]
    is_withdrawn: bool = False
    
    # External identifiers
    external_id_type: str = "maryland_filing_id"
    external_id_value: Optional[str]
    
    # Source reference
    source: str = "STATE"
    source_row_id: Optional[str]
    raw_ref: Optional[Dict[str, Any]]


class CandidateContactInfo(BaseModel):
    """Contact information for candidate."""
    candidate_id: UUID
    phone_primary: Optional[str]
    phone_secondary: Optional[str]
    mailing_address_street: Optional[str]
    mailing_address_city: Optional[str]
    mailing_address_state: Optional[str] = "MD"
    mailing_address_zip: Optional[str]
    residential_jurisdiction: Optional[str]


class CandidateSocialMedia(BaseModel):
    """Social media information for candidate."""
    candidate_id: UUID
    platform: str
    handle_or_url: str
    verified: bool = False


class CandidateFilingInfo(BaseModel):
    """Filing information for candidate."""
    candidate_id: UUID
    filing_type: Optional[str]
    filing_date: Optional[date]
    filing_status: Optional[str]
    additional_info: Optional[str]
    source: str = "STATE"


class IngestRun(BaseModel):
    """Ingest run tracking."""
    id: Optional[UUID] = None
    source: str
    run_key: Optional[str]
    endpoint_or_file: str
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: Optional[datetime] = None
    row_count_raw: int = 0
    row_count_stage: int = 0
    new_candidates: int = 0
    updated_candidates: int = 0
    actor: str = "github_action"
    notes: Optional[str]


class CandidateMatch(BaseModel):
    """Candidate match for deduplication."""
    stage_id: int
    candidate_id: UUID
    authority: str = "name_office"
    match_value: Optional[str]
    confidence: float
    decided_by: MatchDecision = MatchDecision.AUTO
    decided_at: datetime = Field(default_factory=datetime.now)
    note: Optional[str]


class CandidateSource(BaseModel):
    """Track candidate data sources."""
    candidate_id: UUID
    source: str = "STATE"
    external_id_type: str
    external_id_value: str
    first_seen: datetime = Field(default_factory=datetime.now)
    last_seen: datetime = Field(default_factory=datetime.now)


class DatabaseCandidate(BaseModel):
    """Existing candidate from database."""
    id: UUID
    full_name: str
    first_name: Optional[str]
    last_name: Optional[str]
    party: Optional[str]
    office_level: Optional[str]
    office_name: Optional[str]
    district_id: Optional[UUID]
    ocd_division_id: Optional[str]
    election_year: Optional[int]
    status: Optional[str]
    is_withdrawn: bool = False
    
    # For matching
    external_ids: List[Dict[str, str]] = []
    
    class Config:
        orm_mode = True


class UpdateStatistics(BaseModel):
    """Statistics from update run."""
    total_raw_records: int
    total_staged: int
    new_candidates: int
    updated_candidates: int
    skipped_duplicates: int
    errors: int
    processing_time_seconds: float
    dry_run: bool