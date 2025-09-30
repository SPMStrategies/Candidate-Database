"""Transform Maryland candidate data to normalized format."""

import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from .models import (
    MarylandCandidateRaw,
    NormalizedCandidate,
    CandidateContactInfo,
    CandidateSocialMedia,
    CandidateFilingInfo,
    OfficeLevel
)
from .config import ELECTION_YEAR, SOURCE_NAME, setup_logging

logger = setup_logging(__name__)


class MarylandTransformer:
    """Transform Maryland BOE data to normalized format."""
    
    @staticmethod
    def safe_str(value: Any, default: str = '') -> str:
        """
        Safely convert a value to string, handling None and pandas NaN values.
        
        Args:
            value: Value to convert
            default: Default value if conversion fails
            
        Returns:
            String representation of value
        """
        if value is None:
            return default
        str_val = str(value)
        if str_val in ('nan', 'None', 'NaN', 'NaT'):
            return default
        return str_val.strip()
    
    # Office level mappings
    FEDERAL_OFFICES = {
        'u.s. senator', 'united states senator',
        'representative in congress', 'u.s. representative',
        'president', 'vice president'
    }
    
    STATE_OFFICES = {
        'governor', 'lt. governor', 'lieutenant governor',
        'comptroller', 'attorney general',
        'state senator', 'delegate', 'house of delegates'
    }
    
    JUDICIAL_OFFICES = {
        'judge', 'justice', 'court of appeals',
        'circuit court', 'district court', 'orphans court',
        "orphan's court", "orphans' court"
    }
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
    
    def determine_office_level(self, office_name: str) -> OfficeLevel:
        """
        Determine the office level from office name.
        
        Args:
            office_name: Name of the office
            
        Returns:
            OfficeLevel enum value
        """
        if not office_name:
            return OfficeLevel.LOCAL
        
        office_lower = office_name.lower()
        
        # Check for federal offices
        if any(federal in office_lower for federal in self.FEDERAL_OFFICES):
            return OfficeLevel.FEDERAL
        
        # Check for state offices
        if any(state in office_lower for state in self.STATE_OFFICES):
            return OfficeLevel.STATE
        
        # Check for judicial offices
        if any(judicial in office_lower for judicial in self.JUDICIAL_OFFICES):
            return OfficeLevel.JUDICIAL
        
        # Default to local
        return OfficeLevel.LOCAL
    
    def parse_name(self, last_name: Optional[str], first_middle: Optional[str]) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Parse candidate name components.
        
        Args:
            last_name: Last name and suffix
            first_middle: First and middle names
            
        Returns:
            Tuple of (full_name, first_name, last_name)
        """
        # Clean up names - handle floats and None values
        last = str(last_name).strip() if last_name is not None and str(last_name) != 'nan' else ''
        first_middle = str(first_middle).strip() if first_middle is not None and str(first_middle) != 'nan' else ''
        
        # Extract first name from first_middle
        first_name = None
        if first_middle:
            parts = first_middle.split()
            if parts:
                first_name = parts[0]
        
        # Build full name
        full_name = f"{first_middle} {last}".strip()
        if not full_name:
            full_name = "Unknown Candidate"
        
        return full_name, first_name, last
    
    def parse_district(self, contest_district: Optional[str]) -> Optional[str]:
        """
        Extract district number from contest district string.
        
        Args:
            contest_district: Contest district description
            
        Returns:
            District number or None
        """
        if not contest_district:
            return None
        
        # Look for patterns like "District 1", "District 01", etc.
        match = re.search(r'district\s+(\d+)', contest_district.lower())
        if match:
            return match.group(1)
        
        # Look for patterns like "1st District", "2nd District", etc.
        match = re.search(r'(\d+)(?:st|nd|rd|th)\s+district', contest_district.lower())
        if match:
            return match.group(1)
        
        return None
    
    def generate_ocd_id(self, office_level: OfficeLevel, office_name: str, district: Optional[str]) -> Optional[str]:
        """
        Generate Open Civic Data division ID.
        
        Args:
            office_level: Level of office
            office_name: Name of office
            district: District number
            
        Returns:
            OCD division ID or None
        """
        base = "ocd-division/country:us/state:md"
        
        if office_level == OfficeLevel.FEDERAL:
            if "senat" in office_name.lower():
                return base
            elif "congress" in office_name.lower() or "representative" in office_name.lower():
                if district:
                    return f"{base}/cd:{district}"
        
        elif office_level == OfficeLevel.STATE:
            if "governor" in office_name.lower() or "comptroller" in office_name.lower() or "attorney" in office_name.lower():
                return base
            elif "state senator" in office_name.lower():
                if district:
                    return f"{base}/sldl:{district}"
            elif "delegate" in office_name.lower():
                if district:
                    return f"{base}/sldl:{district}"
        
        return None
    
    def parse_filing_date(self, filing_type_date: Optional[str]) -> Tuple[Optional[str], Optional[datetime]]:
        """
        Parse filing type and date from combined field.
        
        Args:
            filing_type_date: Combined filing information
            
        Returns:
            Tuple of (filing_type, filing_date)
        """
        if not filing_type_date:
            return None, None
        
        filing_type = None
        filing_date = None
        
        # Common patterns in Maryland data
        if "petition" in filing_type_date.lower():
            filing_type = "petition"
        elif "fee" in filing_type_date.lower():
            filing_type = "fee"
        elif "appointment" in filing_type_date.lower():
            filing_type = "appointment"
        
        # Try to extract date (MM/DD/YYYY or similar)
        date_match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', filing_type_date)
        if date_match:
            try:
                month, day, year = date_match.groups()
                filing_date = datetime(int(year), int(month), int(day))
            except ValueError:
                logger.warning(f"Could not parse date from: {filing_type_date}")
        
        return filing_type, filing_date
    
    def parse_address(self, address: Optional[str], city_state_zip: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Parse address components.
        
        Args:
            address: Street address
            city_state_zip: City, state, and ZIP
            
        Returns:
            Dictionary with address components
        """
        result = {
            'street': None,
            'city': None,
            'state': 'MD',
            'zip': None
        }
        
        # Safely convert address to string
        address_str = self.safe_str(address)
        if address_str:
            result['street'] = address_str
        
        # Safely convert city_state_zip to string
        city_state_zip_str = self.safe_str(city_state_zip)
        if city_state_zip_str:
            # Try to parse city, state, zip
            parts = city_state_zip_str.split(',')
            if parts:
                result['city'] = parts[0].strip()
            
            # Look for ZIP code
            zip_match = re.search(r'\b(\d{5})(?:-\d{4})?\b', city_state_zip_str)
            if zip_match:
                result['zip'] = zip_match.group(1)
        
        return result
    
    def transform_row(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        """
        Transform a single row from Maryland CSV to normalized format.
        
        Args:
            row: Pandas Series representing one candidate
            
        Returns:
            Dictionary with transformed data or None if error
        """
        try:
            # Parse name
            full_name, first_name, last_name = self.parse_name(
                row.get('candidate_ballot_last_name_and_suffix'),
                row.get('candidate_first_name_and_middle_name')
            )
            
            # Get office information - handle non-string values
            office_name_raw = row.get('office_name', '')
            office_name = str(office_name_raw).strip() if office_name_raw is not None and str(office_name_raw) != 'nan' else ''
            office_level = self.determine_office_level(office_name)
            
            # Parse district
            district = self.parse_district(row.get('contest_run_by_district_name_and_number'))
            
            # Generate OCD ID
            ocd_id = self.generate_ocd_id(office_level, office_name, district)
            
            # Parse filing information
            filing_type, filing_date = self.parse_filing_date(row.get('filing_type_and_date'))
            
            # Parse address
            address_parts = self.parse_address(
                row.get('campaign_mailing_address'),
                row.get('campaign_mailing_city_state_and_zip')
            )
            
            # Determine status - handle non-string values
            status_raw = row.get('candidate_status', 'active')
            status = str(status_raw).lower() if status_raw is not None and str(status_raw) != 'nan' else 'active'
            is_withdrawn = 'withdrawn' in status
            
            # Create normalized candidate
            normalized = {
                'full_name': full_name,
                'first_name': first_name,
                'last_name': last_name,
                'party': self.safe_str(row.get('office_political_party')),
                'office_level': office_level.value,
                'office_name': office_name,
                'state': 'MD',
                'district_number': district,
                'ocd_division_id': ocd_id,
                'election_year': ELECTION_YEAR,
                'gender': self.safe_str(row.get('candidate_gender')),
                'jurisdiction': self.safe_str(row.get('candidate_residential_jurisdiction')),
                'committee_name': self.safe_str(row.get('committee_name')),
                'website': self.safe_str(row.get('website')),
                'email': self.safe_str(row.get('email')),
                'status': status,
                'is_withdrawn': is_withdrawn,
                'source': SOURCE_NAME,
                'raw_ref': row.to_dict()
            }
            
            # Create contact info
            contact_info = {
                'phone_primary': self.safe_str(row.get('public_phone')),
                'mailing_address_street': address_parts['street'],
                'mailing_address_city': address_parts['city'],
                'mailing_address_state': address_parts['state'],
                'mailing_address_zip': address_parts['zip'],
                'residential_jurisdiction': self.safe_str(row.get('candidate_residential_jurisdiction'))
            }
            
            # Create social media info
            social_media = []
            facebook = self.safe_str(row.get('facebook'))
            if facebook:
                social_media.append({
                    'platform': 'facebook',
                    'handle_or_url': facebook
                })
            x_twitter = self.safe_str(row.get('x'))
            if x_twitter:
                social_media.append({
                    'platform': 'x',
                    'handle_or_url': x_twitter
                })
            other_social = self.safe_str(row.get('other'))
            if other_social:
                social_media.append({
                    'platform': 'other',
                    'handle_or_url': other_social
                })
            
            # Create filing info
            filing_info = {
                'filing_type': filing_type,
                'filing_date': filing_date,
                'filing_status': status,
                'additional_info': self.safe_str(row.get('additional_information')),
                'source': SOURCE_NAME
            }
            
            return {
                'candidate': normalized,
                'contact_info': contact_info,
                'social_media': social_media,
                'filing_info': filing_info
            }
            
        except Exception as e:
            logger.error(f"Error transforming row: {e}")
            logger.debug(f"Row data: {row.to_dict()}")
            self.error_count += 1
            return None
    
    def transform_dataframe(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Transform entire DataFrame of Maryland candidates.
        
        Args:
            df: DataFrame from Maryland BOE
            
        Returns:
            List of transformed candidate dictionaries
        """
        logger.info(f"Starting transformation of {len(df)} candidates")
        
        transformed = []
        for idx, row in df.iterrows():
            result = self.transform_row(row)
            if result:
                transformed.append(result)
                self.processed_count += 1
            
            if (idx + 1) % 100 == 0:
                logger.info(f"Processed {idx + 1}/{len(df)} candidates")
        
        logger.info(f"Transformation complete: {self.processed_count} successful, {self.error_count} errors")
        
        return transformed


def transform_maryland_data(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Main function to transform Maryland data.
    
    Args:
        df: DataFrame from Maryland BOE
        
    Returns:
        List of transformed candidate dictionaries
    """
    transformer = MarylandTransformer()
    return transformer.transform_dataframe(df)