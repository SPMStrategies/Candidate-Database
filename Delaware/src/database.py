"""Database operations for Delaware candidates.

Simplified version - no special presidential candidate handling.
Each state's candidates are independent.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

# Add parent directory to path to import shared modules
sys.path.append(str(Path(__file__).parent.parent.parent))

# Import from Maryland implementation (will be moved to shared later)
from Maryland.src.database import SupabaseClient as BaseSupabaseClient
from Maryland.src.models import UpdateStatistics

from .config import SOURCE_STATE, SOURCE_NAME, DRY_RUN

logger = logging.getLogger(__name__)


class DelawareSupabaseClient(BaseSupabaseClient):
    """Delaware-specific database operations."""
    
    def __init__(self):
        """Initialize Delaware database client."""
        super().__init__()
        self.source_state = SOURCE_STATE
    
    def insert_candidate(self, candidate_data: Dict[str, Any]) -> Optional[UUID]:
        """
        Insert a new Delaware candidate.
        
        Args:
            candidate_data: Candidate data dictionary
            
        Returns:
            UUID of created candidate or None
        """
        # Add source_state to candidate data
        candidate_data['candidate']['source_state'] = SOURCE_STATE
        
        # Use parent class insert method
        return super().insert_candidate(candidate_data)
    
    def get_delaware_candidates(self) -> List[Dict[str, Any]]:
        """
        Get all candidates from Delaware.
        
        Returns:
            List of Delaware candidates
        """
        if DRY_RUN:
            logger.info("DRY RUN: Would fetch Delaware candidates")
            return []
        
        try:
            # Get candidates where Delaware is the source
            result = self.client.table('candidates').select('*').eq(
                'source_state', SOURCE_STATE
            ).execute()
            
            logger.info(f"Found {len(result.data)} Delaware candidates")
            return result.data
            
        except Exception as e:
            logger.error(f"Error fetching Delaware candidates: {e}")
            return []
    
    def get_existing_delaware_candidates(self, election_year: int) -> List[Any]:
        """
        Get existing Delaware candidates for deduplication.
        Only checks within Delaware candidates (no cross-state).
        
        Args:
            election_year: Election year to filter by
            
        Returns:
            List of existing Delaware candidates
        """
        logger.info(f"Fetching existing Delaware candidates for year {election_year}")
        
        if DRY_RUN:
            logger.info("DRY RUN: Would fetch existing Delaware candidates")
            return []
        
        try:
            # Only get Delaware candidates for deduplication
            result = self.client.table('candidates').select(
                "*, candidate_identifiers(authority, id_value)"
            ).eq('election_year', election_year).eq('source_state', SOURCE_STATE).execute()
            
            # Convert to DatabaseCandidate objects (reusing Maryland's model)
            from Maryland.src.models import DatabaseCandidate
            
            candidates = []
            for row in result.data:
                # Extract external IDs
                external_ids = []
                if 'candidate_identifiers' in row:
                    for id_row in row['candidate_identifiers']:
                        external_ids.append({
                            'authority': id_row['authority'],
                            'value': id_row['id_value']
                        })
                
                candidate = DatabaseCandidate(
                    id=row['id'],
                    full_name=row['full_name'],
                    first_name=row.get('first_name'),
                    last_name=row.get('last_name'),
                    party=row.get('party'),
                    office_level=row.get('office_level'),
                    office_name=row.get('office_name'),
                    district_id=row.get('district_id'),
                    ocd_division_id=row.get('ocd_division_id'),
                    election_year=row.get('election_year'),
                    status=row.get('status'),
                    is_withdrawn=row.get('is_withdrawn', False),
                    external_ids=external_ids
                )
                candidates.append(candidate)
            
            logger.info(f"Found {len(candidates)} existing Delaware candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Error fetching existing Delaware candidates: {e}")
            return []