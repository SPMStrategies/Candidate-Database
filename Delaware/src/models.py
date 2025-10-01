"""Data models for Delaware candidate data."""

from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

@dataclass
class DelawareCandidateRaw:
    """Raw candidate data from Delaware sources."""
    name: str
    office: str
    district: Optional[str] = None
    county: Optional[str] = None
    party: Optional[str] = None  # Democratic, Republican, etc.
    filing_date: Optional[str] = None
    status: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    campaign_website: Optional[str] = None
    election_type: Optional[str] = None  # primary, general, school_board
    raw_html: Optional[str] = None  # Store raw HTML for reference

@dataclass 
class TransformedCandidate:
    """Candidate data transformed to match database schema."""
    # Required fields
    full_name: str
    office_name: str  # Exact as Delaware provides (no normalization)
    election_year: int
    source_state: str
    
    # Optional fields that Delaware might provide
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    party: Optional[str] = None  # Often not provided by Delaware
    office_level: Optional[str] = None
    district_number: Optional[str] = None
    ocd_division_id: Optional[str] = None
    gender: Optional[str] = None
    jurisdiction: Optional[str] = None
    committee_name: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    status: Optional[str] = "active"
    is_withdrawn: bool = False
    
    # Store original Delaware data
    raw_ref: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion."""
        return {
            'full_name': self.full_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'party': self.party,
            'office_level': self.office_level,
            'office_name': self.office_name,
            'ocd_division_id': self.ocd_division_id,
            'district_number': self.district_number,
            'election_year': self.election_year,
            'gender': self.gender,
            'jurisdiction': self.jurisdiction,
            'committee_name': self.committee_name,
            'website': self.website,
            'contact_email': self.contact_email,
            'status': self.status,
            'is_withdrawn': self.is_withdrawn,
            'source_state': self.source_state,
            'state': self.source_state,  # Also include as 'state' for compatibility
            'raw_ref': self.raw_ref
        }