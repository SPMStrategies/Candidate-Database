"""Transform Delaware candidate data to normalized format."""

import re
from typing import List, Dict, Any, Optional, Tuple
from .models import DelawareCandidateRaw, TransformedCandidate
from .config import ELECTION_YEAR, SOURCE_STATE, OFFICE_LEVEL_KEYWORDS, DEFAULT_VALUES
import logging

logger = logging.getLogger(__name__)


class DelawareTransformer:
    """Transform Delaware candidate data to database schema."""
    
    def __init__(self):
        """Initialize transformer."""
        self.transformed_count = 0
        self.error_count = 0
    
    def parse_name(self, full_name: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Parse full name into components.
        
        Args:
            full_name: Full candidate name
            
        Returns:
            Tuple of (full_name, first_name, last_name)
        """
        if not full_name:
            return "Unknown Candidate", None, None
        
        # Clean the name
        full_name = full_name.strip()
        
        # Handle common patterns
        # Remove titles like Jr., Sr., III, etc.
        name_parts = re.sub(r'\s+(Jr\.?|Sr\.?|III|II|IV)$', '', full_name, flags=re.I)
        
        # Split into parts
        parts = name_parts.split()
        
        if len(parts) == 0:
            return full_name, None, None
        elif len(parts) == 1:
            return full_name, parts[0], None
        elif len(parts) == 2:
            return full_name, parts[0], parts[1]
        else:
            # Assume first word is first name, rest is last name
            first = parts[0]
            last = ' '.join(parts[1:])
            return full_name, first, last
    
    def determine_office_level(self, office_name: str) -> str:
        """
        Determine the level of office.
        
        Args:
            office_name: Name of the office
            
        Returns:
            Office level (federal, state, local, judicial, other)
        """
        if not office_name:
            return "other"
        
        office_lower = office_name.lower()
        
        for level, keywords in OFFICE_LEVEL_KEYWORDS.items():
            if any(keyword in office_lower for keyword in keywords):
                return level
        
        return "other"
    
    def extract_district(self, office_name: str, district_field: Optional[str] = None) -> Optional[str]:
        """
        Extract district number from office name or district field.
        
        Args:
            office_name: Office name that might contain district
            district_field: Explicit district field if available
            
        Returns:
            District number or None
        """
        if district_field:
            # Extract numbers from district field
            match = re.search(r'\d+', district_field)
            if match:
                return match.group()
        
        # Try to extract from office name
        # Patterns like "State Senate District 5" or "House District 12"
        patterns = [
            r'district\s+(\d+)',
            r'dist\.\s+(\d+)',
            r'dist\s+(\d+)',
            r'(\d+)(?:st|nd|rd|th)\s+district'
        ]
        
        office_lower = office_name.lower()
        for pattern in patterns:
            match = re.search(pattern, office_lower)
            if match:
                return match.group(1)
        
        return None
    
    def generate_ocd_id(self, office_level: str, office_name: str, 
                        district: Optional[str] = None, county: Optional[str] = None) -> Optional[str]:
        """
        Generate Open Civic Data division ID for Delaware.
        
        Args:
            office_level: Level of office
            office_name: Name of office
            district: District number if applicable
            county: County if applicable
            
        Returns:
            OCD division ID or None
        """
        base = "ocd-division/country:us/state:de"
        
        if office_level == "federal":
            if "president" in office_name.lower():
                return "ocd-division/country:us"
            elif "senate" in office_name.lower():
                return base
            elif "congress" in office_name.lower() or "representative" in office_name.lower():
                # Delaware has only one congressional district
                return f"{base}/cd:1"
        
        elif office_level == "state":
            if any(x in office_name.lower() for x in ["governor", "lieutenant", "attorney", "treasurer"]):
                return base
            elif "senate" in office_name.lower() and district:
                return f"{base}/sldu:{district}"
            elif "house" in office_name.lower() and district:
                return f"{base}/sldl:{district}"
        
        elif office_level == "local" and county:
            county_clean = county.lower().replace(" ", "_").replace("county", "").strip()
            return f"{base}/county:{county_clean}"
        
        return None
    
    
    def transform_candidate(self, raw: DelawareCandidateRaw) -> Optional[TransformedCandidate]:
        """
        Transform raw Delaware candidate to standard format.
        
        Args:
            raw: Raw candidate data from Delaware
            
        Returns:
            Transformed candidate or None if error
        """
        try:
            # Parse name
            full_name, first_name, last_name = self.parse_name(raw.name)
            
            # Determine office level
            office_level = self.determine_office_level(raw.office)
            
            # Extract district if applicable
            district = self.extract_district(raw.office, raw.district)
            
            # Generate OCD ID
            ocd_id = self.generate_ocd_id(office_level, raw.office, district, raw.county)
            
            # Determine status
            status = "active"
            is_withdrawn = False
            if raw.status:
                status_lower = raw.status.lower()
                if "withdrawn" in status_lower or "dropped" in status_lower:
                    status = "withdrawn"
                    is_withdrawn = True
            
            # Create transformed candidate
            candidate = TransformedCandidate(
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                party=raw.party if hasattr(raw, 'party') else None,  # Use party from raw data if available
                office_level=office_level,
                office_name=raw.office,  # Keep exact Delaware office name
                ocd_division_id=ocd_id,
                district_number=district,
                election_year=ELECTION_YEAR,
                gender=None,  # Delaware doesn't typically provide
                jurisdiction=raw.county,
                committee_name=None,
                website=raw.campaign_website,
                contact_email=raw.email,
                status=status,
                is_withdrawn=is_withdrawn,
                source_state=SOURCE_STATE,
                raw_ref={
                    'name': raw.name,
                    'office': raw.office,
                    'district': raw.district,
                    'county': raw.county,
                    'party': raw.party if hasattr(raw, 'party') else None,
                    'filing_date': raw.filing_date,
                    'status': raw.status,
                    'email': raw.email,
                    'phone': raw.phone,
                    'address': raw.address,
                    'website': raw.campaign_website,
                    'election_type': raw.election_type
                }
            )
            
            self.transformed_count += 1
            return candidate
            
        except Exception as e:
            logger.error(f"Error transforming candidate {raw.name}: {e}")
            self.error_count += 1
            return None
    
    def transform_batch(self, raw_candidates: List[DelawareCandidateRaw]) -> List[Dict[str, Any]]:
        """
        Transform a batch of raw candidates.
        
        Args:
            raw_candidates: List of raw candidate data
            
        Returns:
            List of transformed candidate dictionaries
        """
        transformed = []
        
        for raw in raw_candidates:
            candidate = self.transform_candidate(raw)
            if candidate:
                # Package for database insertion (matching Maryland structure)
                candidate_data = {
                    'candidate': candidate.to_dict(),
                    'contact_info': {
                        'phone_primary': raw.phone,
                        'mailing_address_street': raw.address,
                        'mailing_address_city': raw.county,
                        'mailing_address_state': 'DE',
                    } if (raw.phone or raw.address) else {},
                    'social_media': [],  # Delaware doesn't typically provide
                    'filing_info': {
                        'filing_date': raw.filing_date,
                        'filing_status': raw.status,
                        'filing_type': raw.election_type
                    } if raw.filing_date else {}
                }
                transformed.append(candidate_data)
        
        logger.info(f"Transformed {self.transformed_count} candidates successfully")
        if self.error_count > 0:
            logger.warning(f"Failed to transform {self.error_count} candidates")
        
        return transformed