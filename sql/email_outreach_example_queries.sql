-- Example Queries for Email Outreach System
--
-- This file contains common queries for:
-- 1. Finding eligible candidates to email
-- 2. Checking email safety/validation
-- 3. Tracking campaign performance
-- 4. Managing opt-outs and bounces
-- 5. Analyzing engagement
--
-- Created: 2025-10-21

-- =============================================================================
-- 1. FINDING ELIGIBLE CANDIDATES TO EMAIL
-- =============================================================================

-- Get all candidates eligible for a new campaign (safe to email)
-- This is the MASTER query to use before sending any emails
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
  -- Must have validated email
  ev.is_valid = TRUE
  AND ev.hunter_status IN ('valid', 'accept_all')
  AND ev.is_disposable = FALSE
  AND ev.is_role_account = FALSE

  -- Not opted out
  AND opt.id IS NULL

  -- Not emailed recently (30 day cooldown)
  AND (recent.last_sent IS NULL OR recent.last_sent < NOW() - INTERVAL '30 days')

  -- Not withdrawn
  AND c.is_withdrawn = FALSE

  -- Add your targeting filters here
  -- AND c.party = 'Republican'
  -- AND c.source_state = 'MD'
  -- AND c.office_level = 'state'

ORDER BY c.full_name;

-- =============================================================================

-- Get candidates eligible for specific campaign (not already in campaign)
SELECT
  c.id,
  c.full_name,
  c.contact_email,
  c.party,
  c.office_name
FROM candidates c
INNER JOIN email_validations ev ON c.contact_email = ev.email_address
LEFT JOIN email_opt_outs opt ON c.contact_email = opt.email_address
LEFT JOIN email_outreach eo ON c.id = eo.candidate_id
  AND eo.campaign_id = 'YOUR_CAMPAIGN_ID_HERE'
WHERE
  ev.is_valid = TRUE
  AND opt.id IS NULL
  AND eo.id IS NULL -- Not in this campaign yet
  AND c.is_withdrawn = FALSE;

-- =============================================================================

-- Count eligible candidates by state and party (for planning)
SELECT
  c.source_state,
  c.party,
  COUNT(*) as eligible_count
FROM candidates c
INNER JOIN email_validations ev ON c.contact_email = ev.email_address
LEFT JOIN email_opt_outs opt ON c.contact_email = opt.email_address
WHERE
  ev.is_valid = TRUE
  AND opt.id IS NULL
  AND c.is_withdrawn = FALSE
GROUP BY c.source_state, c.party
ORDER BY c.source_state, c.party;

-- =============================================================================
-- 2. EMAIL SAFETY & VALIDATION CHECKS
-- =============================================================================

-- Check if specific email is safe to send to
SELECT
  c.full_name,
  c.contact_email,
  ev.is_valid,
  ev.hunter_status,
  ev.confidence_score,
  ev.is_disposable,
  ev.is_role_account,
  CASE
    WHEN opt.id IS NOT NULL THEN 'OPTED OUT - DO NOT EMAIL'
    WHEN ev.is_valid = FALSE THEN 'INVALID EMAIL'
    WHEN ev.is_disposable = TRUE THEN 'DISPOSABLE EMAIL - SKIP'
    WHEN recent.last_sent > NOW() - INTERVAL '30 days' THEN 'EMAILED RECENTLY - WAIT'
    ELSE 'SAFE TO EMAIL'
  END as send_status,
  recent.last_sent
FROM candidates c
LEFT JOIN email_validations ev ON c.contact_email = ev.email_address
LEFT JOIN email_opt_outs opt ON c.contact_email = opt.email_address
LEFT JOIN LATERAL (
  SELECT MAX(sent_at) as last_sent
  FROM email_outreach
  WHERE candidate_id = c.id
) recent ON true
WHERE c.contact_email = 'example@email.com'; -- Replace with email to check

-- =============================================================================

-- Find candidates with invalid or risky emails
SELECT
  c.id,
  c.full_name,
  c.contact_email,
  ev.is_valid,
  ev.hunter_status,
  ev.is_disposable,
  ev.is_role_account,
  CASE
    WHEN ev.is_valid = FALSE THEN 'Invalid'
    WHEN ev.is_disposable = TRUE THEN 'Disposable'
    WHEN ev.is_role_account = TRUE THEN 'Role Account'
    WHEN ev.hunter_status = 'invalid' THEN 'Hunter Invalid'
    ELSE 'Unknown Issue'
  END as issue_type
FROM candidates c
LEFT JOIN email_validations ev ON c.contact_email = ev.email_address
WHERE
  c.contact_email IS NOT NULL
  AND (
    ev.is_valid = FALSE
    OR ev.is_disposable = TRUE
    OR ev.is_role_account = TRUE
    OR ev.hunter_status IN ('invalid', 'unknown')
  )
ORDER BY c.source_state, c.full_name;

-- =============================================================================
-- 3. CAMPAIGN PERFORMANCE TRACKING
-- =============================================================================

-- Campaign overview with key metrics
SELECT
  ec.campaign_name,
  ec.channel,
  ec.status,
  ec.created_at,
  ec.total_sent,
  ec.total_delivered,
  ec.total_bounced,
  ec.total_opened,
  ec.total_clicked,
  ec.total_replied,
  ec.total_unsubscribed,
  -- Calculate rates
  CASE WHEN ec.total_sent > 0 THEN
    ROUND((ec.total_delivered::NUMERIC / ec.total_sent * 100), 2)
  ELSE 0 END as delivery_rate_pct,
  CASE WHEN ec.total_delivered > 0 THEN
    ROUND((ec.total_opened::NUMERIC / ec.total_delivered * 100), 2)
  ELSE 0 END as open_rate_pct,
  CASE WHEN ec.total_opened > 0 THEN
    ROUND((ec.total_clicked::NUMERIC / ec.total_opened * 100), 2)
  ELSE 0 END as click_rate_pct,
  CASE WHEN ec.total_sent > 0 THEN
    ROUND((ec.total_bounced::NUMERIC / ec.total_sent * 100), 2)
  ELSE 0 END as bounce_rate_pct
FROM email_campaigns ec
ORDER BY ec.created_at DESC;

-- =============================================================================

-- Detailed campaign breakdown by status
SELECT
  ec.campaign_name,
  eo.status,
  COUNT(*) as count,
  ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER (PARTITION BY ec.id) * 100, 2) as percentage
FROM email_campaigns ec
LEFT JOIN email_outreach eo ON ec.id = eo.campaign_id
WHERE ec.id = 'YOUR_CAMPAIGN_ID_HERE'
GROUP BY ec.campaign_name, ec.id, eo.status
ORDER BY count DESC;

-- =============================================================================

-- Best performing campaigns (by reply rate)
SELECT
  ec.campaign_name,
  ec.channel,
  ec.total_sent,
  ec.total_replied,
  CASE WHEN ec.total_sent > 0 THEN
    ROUND((ec.total_replied::NUMERIC / ec.total_sent * 100), 2)
  ELSE 0 END as reply_rate_pct,
  ec.created_at
FROM email_campaigns ec
WHERE ec.total_sent > 0
ORDER BY reply_rate_pct DESC
LIMIT 10;

-- =============================================================================
-- 4. OPT-OUTS AND BOUNCES MANAGEMENT
-- =============================================================================

-- Recent opt-outs (last 30 days)
SELECT
  opt.email_address,
  c.full_name,
  c.party,
  c.source_state,
  opt.opt_out_method,
  opt.reason,
  opt.opted_out_at,
  ec.campaign_name
FROM email_opt_outs opt
LEFT JOIN candidates c ON opt.candidate_id = c.id
LEFT JOIN email_campaigns ec ON opt.campaign_id = ec.id
WHERE opt.opted_out_at > NOW() - INTERVAL '30 days'
ORDER BY opt.opted_out_at DESC;

-- =============================================================================

-- Opt-out breakdown by method
SELECT
  opt_out_method,
  COUNT(*) as count,
  ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER () * 100, 2) as percentage
FROM email_opt_outs
GROUP BY opt_out_method
ORDER BY count DESC;

-- =============================================================================

-- Emails that hard bounced (need to add to opt-out list)
SELECT
  eo.id,
  eo.recipient_email,
  c.full_name,
  eo.bounce_type,
  eo.bounce_reason,
  eo.sent_at,
  ec.campaign_name
FROM email_outreach eo
LEFT JOIN candidates c ON eo.candidate_id = c.id
LEFT JOIN email_campaigns ec ON eo.campaign_id = ec.id
WHERE
  eo.bounce_type = 'hard'
  AND eo.recipient_email NOT IN (SELECT email_address FROM email_opt_outs)
ORDER BY eo.sent_at DESC;

-- =============================================================================

-- Spam complaints (CRITICAL - review immediately)
SELECT
  eo.id,
  eo.recipient_email,
  c.full_name,
  c.party,
  c.source_state,
  eo.spam_reported_at,
  ec.campaign_name,
  eo.subject
FROM email_outreach eo
LEFT JOIN candidates c ON eo.candidate_id = c.id
LEFT JOIN email_campaigns ec ON eo.campaign_id = ec.id
WHERE eo.spam_reported = TRUE
ORDER BY eo.spam_reported_at DESC;

-- =============================================================================
-- 5. ENGAGEMENT ANALYSIS
-- =============================================================================

-- Emails awaiting reply (opened but no response yet)
SELECT
  eo.id,
  c.full_name,
  c.party,
  c.office_name,
  eo.recipient_email,
  eo.subject,
  eo.first_opened_at,
  eo.open_count,
  ec.campaign_name,
  EXTRACT(DAY FROM NOW() - eo.first_opened_at) as days_since_opened
FROM email_outreach eo
INNER JOIN candidates c ON eo.candidate_id = c.id
LEFT JOIN email_campaigns ec ON eo.campaign_id = ec.id
WHERE
  eo.channel = 'gmail'
  AND eo.opened = TRUE
  AND eo.reply_received = FALSE
  AND eo.first_opened_at > NOW() - INTERVAL '14 days'
ORDER BY eo.first_opened_at DESC;

-- =============================================================================

-- Replies requiring follow-up
SELECT
  er.id,
  c.full_name,
  c.party,
  c.office_name,
  er.from_email,
  er.snippet,
  er.sentiment,
  er.received_at,
  ec.campaign_name,
  EXTRACT(DAY FROM NOW() - er.received_at) as days_since_reply
FROM email_replies er
INNER JOIN candidates c ON er.candidate_id = c.id
INNER JOIN email_outreach eo ON er.outreach_id = eo.id
LEFT JOIN email_campaigns ec ON eo.campaign_id = ec.id
WHERE
  er.requires_follow_up = TRUE
  AND er.sentiment IN ('positive', 'interested')
ORDER BY er.received_at DESC;

-- =============================================================================

-- Engagement by party (are Republicans more responsive?)
SELECT
  c.party,
  COUNT(DISTINCT eo.id) as emails_sent,
  COUNT(DISTINCT CASE WHEN eo.opened THEN eo.id END) as emails_opened,
  COUNT(DISTINCT CASE WHEN eo.clicked THEN eo.id END) as emails_clicked,
  COUNT(DISTINCT CASE WHEN eo.reply_received THEN eo.id END) as emails_replied,
  ROUND(COUNT(DISTINCT CASE WHEN eo.opened THEN eo.id END)::NUMERIC / COUNT(DISTINCT eo.id) * 100, 2) as open_rate_pct,
  ROUND(COUNT(DISTINCT CASE WHEN eo.reply_received THEN eo.id END)::NUMERIC / COUNT(DISTINCT eo.id) * 100, 2) as reply_rate_pct
FROM email_outreach eo
INNER JOIN candidates c ON eo.candidate_id = c.id
WHERE eo.sent_at IS NOT NULL
GROUP BY c.party
ORDER BY reply_rate_pct DESC;

-- =============================================================================

-- Engagement by state
SELECT
  c.source_state,
  COUNT(DISTINCT eo.id) as emails_sent,
  COUNT(DISTINCT CASE WHEN eo.opened THEN eo.id END) as emails_opened,
  COUNT(DISTINCT CASE WHEN eo.reply_received THEN eo.id END) as emails_replied,
  ROUND(COUNT(DISTINCT CASE WHEN eo.opened THEN eo.id END)::NUMERIC / COUNT(DISTINCT eo.id) * 100, 2) as open_rate_pct,
  ROUND(COUNT(DISTINCT CASE WHEN eo.reply_received THEN eo.id END)::NUMERIC / COUNT(DISTINCT eo.id) * 100, 2) as reply_rate_pct
FROM email_outreach eo
INNER JOIN candidates c ON eo.candidate_id = c.id
WHERE eo.sent_at IS NOT NULL
GROUP BY c.source_state
ORDER BY emails_sent DESC;

-- =============================================================================
-- 6. IP REPUTATION MONITORING
-- =============================================================================

-- Bounce rate by campaign (alert if >2%)
SELECT
  ec.campaign_name,
  ec.channel,
  ec.total_sent,
  ec.total_bounced,
  ROUND((ec.total_bounced::NUMERIC / NULLIF(ec.total_sent, 0) * 100), 2) as bounce_rate_pct,
  CASE
    WHEN ec.total_sent = 0 THEN 'NOT STARTED'
    WHEN (ec.total_bounced::NUMERIC / ec.total_sent * 100) > 5 THEN '🔴 CRITICAL - STOP SENDING'
    WHEN (ec.total_bounced::NUMERIC / ec.total_sent * 100) > 2 THEN '⚠️  WARNING - INVESTIGATE'
    ELSE '✅ HEALTHY'
  END as status
FROM email_campaigns ec
WHERE ec.total_sent > 0
ORDER BY bounce_rate_pct DESC;

-- =============================================================================

-- Spam complaint rate (alert if >0.1%)
SELECT
  ec.campaign_name,
  ec.total_sent,
  COUNT(CASE WHEN eo.spam_reported THEN 1 END) as spam_complaints,
  ROUND((COUNT(CASE WHEN eo.spam_reported THEN 1 END)::NUMERIC / NULLIF(ec.total_sent, 0) * 100), 3) as spam_rate_pct,
  CASE
    WHEN ec.total_sent = 0 THEN 'NOT STARTED'
    WHEN (COUNT(CASE WHEN eo.spam_reported THEN 1 END)::NUMERIC / ec.total_sent * 100) > 0.1 THEN '🔴 CRITICAL'
    ELSE '✅ HEALTHY'
  END as status
FROM email_campaigns ec
LEFT JOIN email_outreach eo ON ec.id = eo.campaign_id
WHERE ec.total_sent > 0
GROUP BY ec.id, ec.campaign_name, ec.total_sent
ORDER BY spam_rate_pct DESC;

-- =============================================================================

-- Daily send volume (ensure not exceeding limits)
SELECT
  DATE(sent_at) as send_date,
  channel,
  COUNT(*) as emails_sent,
  CASE
    WHEN COUNT(*) > 500 THEN '⚠️  Exceeded daily limit (500)'
    ELSE '✅ Within limit'
  END as status
FROM email_outreach
WHERE sent_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(sent_at), channel
ORDER BY send_date DESC, channel;

-- =============================================================================
-- 7. ADMINISTRATIVE QUERIES
-- =============================================================================

-- Update campaign stats manually (normally done by function)
-- SELECT update_campaign_stats('YOUR_CAMPAIGN_ID_HERE');

-- =============================================================================

-- Add hard bounces to opt-out list (run periodically)
INSERT INTO email_opt_outs (email_address, candidate_id, opt_out_method, reason, outreach_id, campaign_id)
SELECT
  eo.recipient_email,
  eo.candidate_id,
  'hard_bounce'::VARCHAR,
  eo.bounce_reason,
  eo.id,
  eo.campaign_id
FROM email_outreach eo
WHERE
  eo.bounce_type = 'hard'
  AND eo.recipient_email NOT IN (SELECT email_address FROM email_opt_outs)
ON CONFLICT (email_address) DO NOTHING;

-- =============================================================================

-- Find candidates who need email validation
SELECT
  c.id,
  c.full_name,
  c.contact_email,
  c.source_state
FROM candidates c
LEFT JOIN email_validations ev ON c.contact_email = ev.email_address
WHERE
  c.contact_email IS NOT NULL
  AND ev.id IS NULL
ORDER BY c.created_at DESC;
