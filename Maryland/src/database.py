"""Database operations for Maryland candidate system."""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from supabase import create_client, Client
from models import (
    IngestRun,
    NormalizedCandidate,
    DatabaseCandidate,
    CandidateSource,
    UpdateStatistics
)
from config import SUPABASE_URL, SUPABASE_KEY, DRY_RUN, SOURCE_NAME, setup_logging

logger = setup_logging(__name__)


class SupabaseClient:
    """Client for Supabase database operations."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.ingest_run_id: Optional[UUID] = None
    
    def create_ingest_run(self, total_raw: int) -> UUID:
        """
        Create a new ingest run record.
        
        Args:
            total_raw: Total number of raw records to process
            
        Returns:
            UUID of the created ingest run
        """
        logger.info("Creating ingest run")
        
        if DRY_RUN:
            self.ingest_run_id = uuid4()
            logger.info(f"DRY RUN: Would create ingest run with ID {self.ingest_run_id}")
            return self.ingest_run_id
        
        ingest_run = IngestRun(
            source=SOURCE_NAME,
            endpoint_or_file="Maryland BOE CSVs",
            row_count_raw=total_raw,
            actor="github_action",
            notes=f"Automated update for {datetime.now().date()}"
        )
        
        result = self.client.table('ingest_runs').insert(
            ingest_run.dict(exclude={'id'})
        ).execute()
        
        self.ingest_run_id = UUID(result.data[0]['id'])
        logger.info(f"Created ingest run: {self.ingest_run_id}")
        
        return self.ingest_run_id
    
    def stage_candidates(self, candidates: List[Dict[str, Any]]) -> int:
        """
        Stage normalized candidates for processing.
        
        Args:
            candidates: List of normalized candidate dictionaries
            
        Returns:
            Number of candidates staged
        """
        logger.info(f"Staging {len(candidates)} candidates")
        
        if DRY_RUN:
            logger.info(f"DRY RUN: Would stage {len(candidates)} candidates")
            return len(candidates)
        
        # Prepare data for staging table
        staged_data = []
        for idx, candidate_data in enumerate(candidates):
            candidate = candidate_data['candidate']
            
            staged = {
                'ingest_run_id': str(self.ingest_run_id),
                'source': SOURCE_NAME,
                'source_row_id': str(idx),
                'full_name': candidate['full_name'],
                'first_name': candidate.get('first_name'),
                'last_name': candidate.get('last_name'),
                'party': candidate.get('party'),
                'office_level': candidate['office_level'],
                'office_name': candidate['office_name'],
                'state': candidate['state'],
                'district_number': candidate.get('district_number'),
                'ocd_division_id': candidate.get('ocd_division_id'),
                'election_year': candidate['election_year'],
                'external_id_type': 'maryland_row_id',
                'external_id_value': str(idx),
                'raw_ref': candidate.get('raw_ref', {})
            }
            staged_data.append(staged)
        
        # Insert in batches
        batch_size = 100
        total_staged = 0
        
        for i in range(0, len(staged_data), batch_size):
            batch = staged_data[i:i+batch_size]
            result = self.client.table('normalized_candidates_stage').insert(batch).execute()
            total_staged += len(result.data)
            logger.info(f"Staged batch {i//batch_size + 1}: {len(batch)} candidates")
        
        logger.info(f"Total candidates staged: {total_staged}")
        return total_staged
    
    def get_existing_candidates(self, election_year: int) -> List[DatabaseCandidate]:
        """
        Get existing candidates from database for matching.
        
        Args:
            election_year: Election year to filter by
            
        Returns:
            List of existing candidates
        """
        logger.info(f"Fetching existing candidates for year {election_year}")
        
        if DRY_RUN:
            logger.info("DRY RUN: Would fetch existing candidates")
            return []
        
        # Get candidates
        result = self.client.table('candidates').select(
            "*, candidate_identifiers(authority, id_value)"
        ).or_(
            f"election_year.eq.{election_year},election_year.is.null"
        ).execute()
        
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
        
        logger.info(f"Found {len(candidates)} existing candidates")
        return candidates
    
    def insert_candidate(self, candidate_data: Dict[str, Any]) -> Optional[UUID]:
        """
        Insert a new candidate with related data.
        
        Args:
            candidate_data: Dictionary with candidate and related data
            
        Returns:
            UUID of created candidate or None if dry run
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would insert candidate {candidate_data['candidate']['full_name']}")
            return None
        
        candidate = candidate_data['candidate']
        
        # Insert main candidate record
        candidate_record = {
            'full_name': candidate['full_name'],
            'first_name': candidate.get('first_name'),
            'last_name': candidate.get('last_name'),
            'party': candidate.get('party'),
            'office_level': candidate['office_level'],
            'office_name': candidate['office_name'],
            'ocd_division_id': candidate.get('ocd_division_id'),
            'election_year': candidate['election_year'],
            'gender': candidate.get('gender'),
            'jurisdiction': candidate.get('jurisdiction'),
            'committee_name': candidate.get('committee_name'),
            'website': candidate.get('website'),
            'contact_email': candidate.get('email'),
            'status': candidate.get('status', 'active'),
            'is_withdrawn': candidate.get('is_withdrawn', False)
        }
        
        result = self.client.table('candidates').insert(candidate_record).execute()
        candidate_id = UUID(result.data[0]['id'])
        
        # Insert contact info
        contact_info = candidate_data.get('contact_info', {})
        if any(contact_info.values()):
            contact_record = {
                'candidate_id': str(candidate_id),
                **{k: v for k, v in contact_info.items() if v is not None}
            }
            self.client.table('candidate_contact_info').insert(contact_record).execute()
        
        # Insert social media
        for social in candidate_data.get('social_media', []):
            social_record = {
                'candidate_id': str(candidate_id),
                'platform': social['platform'],
                'handle_or_url': social['handle_or_url']
            }
            self.client.table('candidate_social_media').insert(social_record).execute()
        
        # Insert filing info
        filing_info = candidate_data.get('filing_info', {})
        if any(filing_info.values()):
            filing_record = {
                'candidate_id': str(candidate_id),
                **{k: v for k, v in filing_info.items() if v is not None}
            }
            self.client.table('candidate_filing_info').insert(filing_record).execute()
        
        # Track source
        source_record = {
            'candidate_id': str(candidate_id),
            'source': SOURCE_NAME,
            'external_id_type': 'maryland_import',
            'external_id_value': f"{datetime.now().date()}"
        }
        self.client.table('candidate_sources').insert(source_record).execute()
        
        logger.info(f"Inserted candidate: {candidate['full_name']} ({candidate_id})")
        return candidate_id
    
    def update_candidate(self, candidate_id: UUID, updates: Dict[str, Any]) -> bool:
        """
        Update existing candidate.
        
        Args:
            candidate_id: ID of candidate to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would update candidate {candidate_id}")
            return True
        
        # Update main candidate record
        candidate_updates = {
            k: v for k, v in updates['candidate'].items()
            if k not in ['raw_ref', 'source']
        }
        
        if candidate_updates:
            self.client.table('candidates').update(
                candidate_updates
            ).eq('id', str(candidate_id)).execute()
        
        # Update or insert contact info
        contact_info = updates.get('contact_info', {})
        if any(contact_info.values()):
            # Check if contact info exists
            existing = self.client.table('candidate_contact_info').select('id').eq(
                'candidate_id', str(candidate_id)
            ).execute()
            
            contact_record = {
                'candidate_id': str(candidate_id),
                **{k: v for k, v in contact_info.items() if v is not None}
            }
            
            if existing.data:
                # Update existing
                self.client.table('candidate_contact_info').update(
                    contact_record
                ).eq('candidate_id', str(candidate_id)).execute()
            else:
                # Insert new
                self.client.table('candidate_contact_info').insert(contact_record).execute()
        
        # Update source last seen
        self.client.table('candidate_sources').update({
            'last_seen': datetime.now().isoformat()
        }).eq('candidate_id', str(candidate_id)).eq('source', SOURCE_NAME).execute()
        
        logger.info(f"Updated candidate: {candidate_id}")
        return True
    
    def record_match(self, stage_id: int, candidate_id: UUID, confidence: float, note: str) -> None:
        """
        Record a candidate match.
        
        Args:
            stage_id: ID from staging table
            candidate_id: Matched candidate ID
            confidence: Match confidence score
            note: Match note
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would record match {stage_id} -> {candidate_id} ({confidence:.1f}%)")
            return
        
        match_record = {
            'stage_id': stage_id,
            'candidate_id': str(candidate_id),
            'authority': 'name_office',
            'confidence': confidence,
            'decided_by': 'auto' if confidence >= 95 else 'manual',
            'note': note
        }
        
        self.client.table('candidate_matches').insert(match_record).execute()
    
    def finalize_ingest_run(self, stats: UpdateStatistics) -> None:
        """
        Finalize the ingest run with statistics.
        
        Args:
            stats: Update statistics
        """
        if DRY_RUN:
            logger.info(f"DRY RUN: Would finalize ingest run with stats: {stats.dict()}")
            return
        
        updates = {
            'finished_at': datetime.now().isoformat(),
            'row_count_stage': stats.total_staged,
            'new_candidates': stats.new_candidates,
            'updated_candidates': stats.updated_candidates,
            'notes': f"Processed {stats.total_raw_records} records in {stats.processing_time_seconds:.1f}s"
        }
        
        self.client.table('ingest_runs').update(updates).eq(
            'id', str(self.ingest_run_id)
        ).execute()
        
        logger.info(f"Finalized ingest run {self.ingest_run_id}")
    
    def get_districts(self) -> List[Dict[str, Any]]:
        """
        Get all districts from database.
        
        Returns:
            List of district records
        """
        if DRY_RUN:
            return []
        
        result = self.client.table('districts').select('*').execute()
        return result.data
    
    def create_district(self, ocd_id: str, district_type: str, 
                       district_number: Optional[str] = None,
                       name: Optional[str] = None) -> UUID:
        """
        Create a new district.
        
        Args:
            ocd_id: OCD division ID
            district_type: Type of district
            district_number: District number
            name: District name
            
        Returns:
            UUID of created district
        """
        if DRY_RUN:
            return uuid4()
        
        district_record = {
            'ocd_id': ocd_id,
            'district_type': district_type,
            'district_number': district_number,
            'name': name,
            'state': 'MD'
        }
        
        result = self.client.table('districts').insert(district_record).execute()
        return UUID(result.data[0]['id'])