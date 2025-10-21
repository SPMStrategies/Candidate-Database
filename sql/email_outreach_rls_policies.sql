-- Row Level Security (RLS) Policies for Email Outreach Tables
--
-- These policies ensure that:
-- 1. Service role (admin/automation) has full access
-- 2. Anonymous users have no access
-- 3. Future: Authenticated users can only see data they're authorized for
--
-- Created: 2025-10-21
-- Updated: 2025-10-21 - Added safe re-run with DROP IF EXISTS, improved grants

-- =============================================================================
-- ENABLE RLS ON TABLES
-- =============================================================================

ALTER TABLE public.email_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_outreach ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.email_opt_outs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sendgrid_events ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- SERVICE ROLE POLICIES (Full Access for Admin/Automation)
-- =============================================================================
-- These policies allow the service role key (used by GitHub Actions and admin scripts)
-- to bypass RLS and have full access to all tables

-- Drop existing policies if they exist (safe re-run)
DROP POLICY IF EXISTS "Service role has full access to email_campaigns" ON public.email_campaigns;
DROP POLICY IF EXISTS "Service role has full access to email_outreach" ON public.email_outreach;
DROP POLICY IF EXISTS "Service role has full access to email_replies" ON public.email_replies;
DROP POLICY IF EXISTS "Service role has full access to email_opt_outs" ON public.email_opt_outs;
DROP POLICY IF EXISTS "Service role has full access to sendgrid_events" ON public.sendgrid_events;

-- email_campaigns: Service role full access
CREATE POLICY "Service role has full access to email_campaigns"
  ON public.email_campaigns
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- email_outreach: Service role full access
CREATE POLICY "Service role has full access to email_outreach"
  ON public.email_outreach
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- email_replies: Service role full access
CREATE POLICY "Service role has full access to email_replies"
  ON public.email_replies
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- email_opt_outs: Service role full access
CREATE POLICY "Service role has full access to email_opt_outs"
  ON public.email_opt_outs
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- sendgrid_events: Service role full access
CREATE POLICY "Service role has full access to sendgrid_events"
  ON public.sendgrid_events
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- =============================================================================
-- AUTHENTICATED USER POLICIES (Future: Role-Based Access)
-- =============================================================================
-- Currently commented out - enable when you add authentication
-- Uncomment and customize based on your auth.users roles/claims

-- Example: Campaign managers can read all campaigns
-- DROP POLICY IF EXISTS "Campaign managers can read campaigns" ON public.email_campaigns;
-- CREATE POLICY "Campaign managers can read campaigns"
--   ON public.email_campaigns
--   FOR SELECT
--   TO authenticated
--   USING (
--     auth.jwt() ->> 'role' = 'campaign_manager'
--     OR auth.jwt() ->> 'role' = 'admin'
--   );

-- Example: Campaign managers can only update campaigns they created
-- DROP POLICY IF EXISTS "Campaign managers can update own campaigns" ON public.email_campaigns;
-- CREATE POLICY "Campaign managers can update own campaigns"
--   ON public.email_campaigns
--   FOR UPDATE
--   TO authenticated
--   USING (created_by = auth.jwt() ->> 'email')
--   WITH CHECK (created_by = auth.jwt() ->> 'email');

-- Example: Read-only access to outreach summary
-- DROP POLICY IF EXISTS "Authenticated users can read outreach summary" ON public.email_outreach;
-- CREATE POLICY "Authenticated users can read outreach summary"
--   ON public.email_outreach
--   FOR SELECT
--   TO authenticated
--   USING (true);

-- =============================================================================
-- ANONYMOUS/PUBLIC POLICIES (No Access)
-- =============================================================================
-- No policies for anon role = no public access to email data
-- This is intentional for privacy/security

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function: Check if Email is Opted Out
-- Example: SELECT is_opted_out('example@email.com');
CREATE OR REPLACE FUNCTION is_opted_out(p_email VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM email_opt_outs
    WHERE email_address = LOWER(p_email)
    AND scope = 'global'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION is_opted_out IS 'Check if email address is on global opt-out list (returns TRUE if opted out)';

-- Function: Check if Candidate Recently Emailed
-- Prevents sending to same candidate within cooldown period
-- Example: SELECT recently_emailed('uuid-here', 30);
CREATE OR REPLACE FUNCTION recently_emailed(p_candidate_id UUID, p_cooldown_days INTEGER DEFAULT 30)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1
    FROM email_outreach
    WHERE candidate_id = p_candidate_id
    AND sent_at IS NOT NULL
    AND sent_at > NOW() - INTERVAL '1 day' * p_cooldown_days
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION recently_emailed IS 'Check if candidate was emailed within cooldown period (returns TRUE if recently emailed)';

-- Function: Get Safe to Email Candidates
-- Returns candidates who are safe to email (validated, not opted out, not recently emailed)
-- Example: SELECT * FROM get_safe_to_email_candidates(30, 'MD', 'Republican');
CREATE OR REPLACE FUNCTION get_safe_to_email_candidates(
  p_cooldown_days INTEGER DEFAULT 30,
  p_state VARCHAR DEFAULT NULL,
  p_party VARCHAR DEFAULT NULL,
  p_office_level VARCHAR DEFAULT NULL
)
RETURNS TABLE (
  candidate_id UUID,
  full_name TEXT,
  email VARCHAR,
  party TEXT,
  state VARCHAR,
  office_name TEXT,
  office_level TEXT,
  hunter_status VARCHAR,
  confidence_score NUMERIC
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    c.full_name,
    c.contact_email,
    c.party,
    c.source_state,
    c.office_name,
    c.office_level,
    ev.hunter_status,
    ev.confidence_score
  FROM candidates c
  INNER JOIN email_validations ev ON c.contact_email = ev.email_address
  LEFT JOIN email_opt_outs opt ON c.contact_email = opt.email_address
  LEFT JOIN LATERAL (
    SELECT MAX(sent_at) as last_sent
    FROM email_outreach
    WHERE candidate_id = c.id
    AND sent_at IS NOT NULL
  ) recent ON true
  WHERE
    -- Valid email
    ev.is_valid = TRUE
    AND ev.hunter_status IN ('valid', 'accept_all')
    AND ev.is_disposable = FALSE
    AND ev.is_role_account = FALSE

    -- Not opted out
    AND opt.id IS NULL

    -- Not recently emailed
    AND (recent.last_sent IS NULL OR recent.last_sent < NOW() - INTERVAL '1 day' * p_cooldown_days)

    -- Not withdrawn
    AND c.is_withdrawn = FALSE

    -- Optional filters
    AND (p_state IS NULL OR c.source_state = p_state)
    AND (p_party IS NULL OR c.party = p_party)
    AND (p_office_level IS NULL OR c.office_level = p_office_level)
  ORDER BY c.full_name;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_safe_to_email_candidates IS 'Returns candidates safe to email with optional filters (state, party, office_level)';

-- =============================================================================
-- GRANT EXECUTE PERMISSIONS
-- =============================================================================

-- Service role can execute all functions
GRANT EXECUTE ON FUNCTION is_opted_out TO service_role;
GRANT EXECUTE ON FUNCTION recently_emailed TO service_role;
GRANT EXECUTE ON FUNCTION get_safe_to_email_candidates TO service_role;
GRANT EXECUTE ON FUNCTION update_campaign_stats TO service_role;

-- Authenticated users can call helper functions (for future web apps)
GRANT EXECUTE ON FUNCTION is_opted_out TO authenticated;
GRANT EXECUTE ON FUNCTION recently_emailed TO authenticated;
GRANT EXECUTE ON FUNCTION get_safe_to_email_candidates TO authenticated;

-- Anonymous users can check opt-out status (for unsubscribe pages)
GRANT EXECUTE ON FUNCTION is_opted_out TO anon;

COMMENT ON FUNCTION is_opted_out IS 'Public function - can be called by anonymous users for unsubscribe verification';
