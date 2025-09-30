"""Deduplication and matching logic for candidates."""

from typing import List, Dict, Any, Optional, Tuple
from fuzzywuzzy import fuzz
from .models import DatabaseCandidate
from .config import (
    EXACT_MATCH_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    REVIEW_THRESHOLD,
    setup_logging
)

logger = setup_logging(__name__)


class CandidateMatcher:
    """Match and deduplicate candidates."""
    
    def __init__(self, existing_candidates: List[DatabaseCandidate]):
        """
        Initialize matcher with existing candidates.
        
        Args:
            existing_candidates: List of existing candidates from database
        """
        self.existing_candidates = existing_candidates
        self.matches_found = 0
        self.new_candidates = 0
        
    def normalize_string(self, s: Optional[str]) -> str:
        """
        Normalize string for comparison.
        
        Args:
            s: String to normalize
            
        Returns:
            Normalized lowercase string
        """
        if not s:
            return ""
        return s.lower().strip()
    
    def match_by_external_id(self, candidate: Dict[str, Any]) -> Optional[Tuple[DatabaseCandidate, float]]:
        """
        Match candidate by external identifier.
        
        Args:
            candidate: Candidate data to match
            
        Returns:
            Tuple of (matched_candidate, confidence) or None
        """
        # For Maryland data, we don't have persistent external IDs
        # This would be used for FEC IDs or state filing numbers
        return None
    
    def match_by_name_and_office(self, candidate: Dict[str, Any]) -> Optional[Tuple[DatabaseCandidate, float]]:
        """
        Match candidate by name and office.
        
        Args:
            candidate: Candidate data to match
            
        Returns:
            Tuple of (matched_candidate, confidence) or None
        """
        candidate_name = self.normalize_string(candidate['full_name'])
        candidate_office = self.normalize_string(candidate['office_name'])
        candidate_year = candidate.get('election_year')
        candidate_party = self.normalize_string(candidate.get('party'))
        
        best_match = None
        best_score = 0.0
        
        for existing in self.existing_candidates:
            # Skip if different election year (if specified)
            if (candidate_year and existing.election_year and 
                candidate_year != existing.election_year):
                continue
            
            # Calculate name similarity
            existing_name = self.normalize_string(existing.full_name)
            name_score = fuzz.ratio(candidate_name, existing_name)
            
            # If name is very different, skip
            if name_score < 70:
                continue
            
            # Check office similarity
            existing_office = self.normalize_string(existing.office_name)
            office_score = fuzz.ratio(candidate_office, existing_office)
            
            # Check party match (if both specified)
            party_match = 1.0
            if candidate_party and existing.party:
                existing_party = self.normalize_string(existing.party)
                if candidate_party != existing_party:
                    party_match = 0.5  # Penalty for party mismatch
            
            # Calculate combined score
            combined_score = (name_score * 0.6 + office_score * 0.3) * party_match
            
            # Check for exact match
            if (name_score == 100 and office_score == 100 and 
                party_match == 1.0):
                return (existing, EXACT_MATCH_THRESHOLD)
            
            # Track best match
            if combined_score > best_score:
                best_score = combined_score
                best_match = existing
        
        # Return best match if above threshold
        if best_match and best_score >= REVIEW_THRESHOLD:
            return (best_match, best_score)
        
        return None
    
    def match_by_fuzzy_name(self, candidate: Dict[str, Any]) -> Optional[Tuple[DatabaseCandidate, float]]:
        """
        Match candidate by fuzzy name matching with additional context.
        
        Args:
            candidate: Candidate data to match
            
        Returns:
            Tuple of (matched_candidate, confidence) or None
        """
        candidate_first = self.normalize_string(candidate.get('first_name'))
        candidate_last = self.normalize_string(candidate.get('last_name'))
        candidate_district = candidate.get('district_number')
        
        if not candidate_last:
            return None
        
        best_match = None
        best_score = 0.0
        
        for existing in self.existing_candidates:
            existing_first = self.normalize_string(existing.first_name)
            existing_last = self.normalize_string(existing.last_name)
            
            if not existing_last:
                continue
            
            # Check last name similarity
            last_name_score = fuzz.ratio(candidate_last, existing_last)
            
            if last_name_score < 85:
                continue
            
            # Check first name or initial
            first_name_score = 0
            if candidate_first and existing_first:
                # Full first name comparison
                first_name_score = fuzz.ratio(candidate_first, existing_first)
                
                # Also check if one is initial of the other
                if (candidate_first[0] == existing_first[0] and 
                    (len(candidate_first) == 1 or len(existing_first) == 1)):
                    first_name_score = max(first_name_score, 85)
            
            # Check office level and district
            context_score = 0
            if (self.normalize_string(candidate.get('office_level')) == 
                self.normalize_string(existing.office_level)):
                context_score += 50
            
            if (candidate_district and existing.ocd_division_id and
                str(candidate_district) in existing.ocd_division_id):
                context_score += 50
            
            # Calculate combined score
            combined_score = (last_name_score * 0.4 + 
                            first_name_score * 0.3 + 
                            context_score * 0.3)
            
            if combined_score > best_score:
                best_score = combined_score
                best_match = existing
        
        # Return best match if above threshold
        if best_match and best_score >= REVIEW_THRESHOLD:
            return (best_match, best_score)
        
        return None
    
    def find_match(self, candidate: Dict[str, Any]) -> Tuple[Optional[DatabaseCandidate], float, str]:
        """
        Find best match for a candidate.
        
        Args:
            candidate: Candidate data to match
            
        Returns:
            Tuple of (matched_candidate, confidence, match_method)
        """
        # Try matching by external ID first (highest confidence)
        match = self.match_by_external_id(candidate)
        if match:
            return match[0], match[1], "external_id"
        
        # Try exact name and office match
        match = self.match_by_name_and_office(candidate)
        if match and match[1] >= HIGH_CONFIDENCE_THRESHOLD:
            return match[0], match[1], "name_office_exact"
        
        # Try fuzzy name matching
        fuzzy_match = self.match_by_fuzzy_name(candidate)
        
        # Return best match
        if match and fuzzy_match:
            if match[1] > fuzzy_match[1]:
                return match[0], match[1], "name_office"
            else:
                return fuzzy_match[0], fuzzy_match[1], "fuzzy_name"
        elif match:
            return match[0], match[1], "name_office"
        elif fuzzy_match:
            return fuzzy_match[0], fuzzy_match[1], "fuzzy_name"
        
        # No match found
        return None, 0.0, "no_match"
    
    def process_candidates(self, candidates: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Process all candidates and categorize them.
        
        Args:
            candidates: List of candidate data dictionaries
            
        Returns:
            Dictionary with categorized candidates
        """
        results = {
            'new': [],
            'update': [],
            'review': [],
            'skip': []
        }
        
        for candidate_data in candidates:
            candidate = candidate_data['candidate']
            
            # Find match
            match, confidence, method = self.find_match(candidate)
            
            if match:
                self.matches_found += 1
                
                # Add match info
                candidate_data['match_info'] = {
                    'candidate_id': match.id,
                    'confidence': confidence,
                    'method': method,
                    'existing_name': match.full_name
                }
                
                if confidence >= HIGH_CONFIDENCE_THRESHOLD:
                    # High confidence - auto update
                    results['update'].append(candidate_data)
                    logger.info(f"Auto-match: {candidate['full_name']} -> {match.full_name} ({confidence:.1f}%)")
                    
                elif confidence >= REVIEW_THRESHOLD:
                    # Medium confidence - needs review
                    results['review'].append(candidate_data)
                    logger.info(f"Review needed: {candidate['full_name']} ~= {match.full_name} ({confidence:.1f}%)")
                    
                else:
                    # Low confidence - treat as new
                    results['new'].append(candidate_data)
                    self.new_candidates += 1
            else:
                # No match - new candidate
                results['new'].append(candidate_data)
                self.new_candidates += 1
                logger.debug(f"New candidate: {candidate['full_name']}")
        
        # Log summary
        logger.info(f"Matching complete: {len(results['new'])} new, {len(results['update'])} updates, "
                   f"{len(results['review'])} need review, {len(results['skip'])} skipped")
        
        return results


def deduplicate_candidates(
    candidates: List[Dict[str, Any]], 
    existing: List[DatabaseCandidate]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Main function to deduplicate candidates.
    
    Args:
        candidates: List of candidate data to process
        existing: List of existing candidates from database
        
    Returns:
        Dictionary with categorized candidates
    """
    matcher = CandidateMatcher(existing)
    return matcher.process_candidates(candidates)