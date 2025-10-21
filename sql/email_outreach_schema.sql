-- Email Outreach System Schema
-- Supports both Gmail API (personal outreach) and SendGrid (bulk marketing)
--
-- Created: 2025-10-21
-- Updated: 2025-10-21 - Added triggers, constraints, and optimizations
-- Purpose: Track all email communications with candidates across multiple channels

-- =============================================================================
-- TABLE 1: email_campaigns
-- =============================================================================
-- Campaign management and templates for email outreach efforts

CREATE TABLE IF NOT EXISTS public.email_campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Campaign info
  campaign_name VARCHAR(255) NOT NULL,
  campaign_type VARCHAR(50) NOT NULL,
  description TEXT,

  -- Targeting
  target_filters JSONB, -- Store query filters: {party: 'Republican', state: 'MD', office_level: 'state'}

  -- Templates
  subject_template TEXT NOT NULL,
  body_text_template TEXT,
  body_html_template TEXT,

  -- Channel configuration
  channel VARCHAR(20) NOT NULL,

  -- SendGrid specific
  sendgrid_template_id VARCHAR(255), -- If using SendGrid dynamic templates
  sendgrid_list_id VARCHAR(255),
  sendgrid_asm_group_id INTEGER, -- Unsubscribe group ID

  -- Sending rules (IP reputation protection)
  daily_send_limit INTEGER DEFAULT 500,
  cooldown_days INTEGER DEFAULT 30, -- Don't email same person within X days
  respect_opt_outs BOOLEAN DEFAULT TRUE,
  skip_invalid_emails BOOLEAN DEFAULT TRUE,

  -- Status
  status VARCHAR(20) DEFAULT 'draft',
  scheduled_start TIMESTAMP WITH TIME ZONE,
  scheduled_end TIMESTAMP WITH TIME ZONE,

  -- Metadata
  created_by VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Denormalized stats (updated by triggers/application)
  total_targeted INTEGER DEFAULT 0,
  total_sent INTEGER DEFAULT 0,
  total_delivered INTEGER DEFAULT 0,
  total_bounced INTEGER DEFAULT 0,
  total_opened INTEGER DEFAULT 0,
  total_clicked INTEGER DEFAULT 0,
  total_replied INTEGER DEFAULT 0,
  total_unsubscribed INTEGER DEFAULT 0,

  -- Constraints
  CONSTRAINT chk_campaign_type CHECK (campaign_type IN ('direct_outreach', 'bulk_marketing', 'follow_up', 'event_invite')),
  CONSTRAINT chk_campaign_channel CHECK (channel IN ('gmail', 'sendgrid')),
  CONSTRAINT chk_campaign_status CHECK (status IN ('draft', 'scheduled', 'active', 'paused', 'completed', 'cancelled')),
  CONSTRAINT chk_campaign_daily_limit CHECK (daily_send_limit > 0 AND daily_send_limit <= 10000),
  CONSTRAINT chk_campaign_cooldown CHECK (cooldown_days >= 0)
);

-- Indexes for campaigns
CREATE INDEX IF NOT EXISTS idx_email_campaigns_status ON email_campaigns(status);
CREATE INDEX IF NOT EXISTS idx_email_campaigns_channel ON email_campaigns(channel);
CREATE INDEX IF NOT EXISTS idx_email_campaigns_created ON email_campaigns(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_campaigns_updated ON email_campaigns(updated_at DESC);

COMMENT ON TABLE email_campaigns IS 'Email campaign definitions and templates for both Gmail and SendGrid channels';
COMMENT ON COLUMN email_campaigns.target_filters IS 'JSONB filters for candidate selection (e.g., party, state, office)';
COMMENT ON COLUMN email_campaigns.cooldown_days IS 'Minimum days between emails to same candidate (prevents spam)';

-- =============================================================================
-- TABLE 2: email_outreach
-- =============================================================================
-- Individual email sends - core tracking table for all channels

CREATE TABLE IF NOT EXISTS public.email_outreach (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Relationships
  candidate_id UUID NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,
  campaign_id UUID REFERENCES public.email_campaigns(id) ON DELETE SET NULL,

  -- Recipient (lowercase enforced by trigger)
  recipient_email VARCHAR(255) NOT NULL,
  recipient_name VARCHAR(255),

  -- Email content (actual sent content, may differ from template due to personalization)
  subject TEXT NOT NULL,
  body_text TEXT,
  body_html TEXT,

  -- Channel
  channel VARCHAR(20) NOT NULL,

  -- Gmail API specific fields
  gmail_message_id VARCHAR(255), -- From Gmail API response: id
  gmail_thread_id VARCHAR(255),  -- From Gmail API response: threadId (for reply tracking)
  gmail_label_ids TEXT[],        -- From Gmail API response: labelIds

  -- SendGrid API specific fields
  sendgrid_message_id VARCHAR(255),    -- From x-message-id header
  sendgrid_batch_id VARCHAR(255),      -- If part of batch send
  sendgrid_template_id VARCHAR(255),   -- If using dynamic template

  -- Send status tracking
  status VARCHAR(50) DEFAULT 'pending',

  queued_at TIMESTAMP WITH TIME ZONE,
  sent_at TIMESTAMP WITH TIME ZONE,
  delivered_at TIMESTAMP WITH TIME ZONE,

  -- Bounce/failure tracking
  bounce_type VARCHAR(50), -- 'hard', 'soft', 'blocked'
  bounce_reason TEXT,      -- From SendGrid webhook or Gmail API error
  bounce_classification VARCHAR(100), -- SendGrid: 'Invalid', 'Content', 'Reputation', etc.

  -- Engagement tracking (from webhooks/tracking pixels)
  opened BOOLEAN DEFAULT FALSE,
  first_opened_at TIMESTAMP WITH TIME ZONE,
  open_count INTEGER DEFAULT 0,
  last_opened_at TIMESTAMP WITH TIME ZONE,

  clicked BOOLEAN DEFAULT FALSE,
  first_clicked_at TIMESTAMP WITH TIME ZONE,
  click_count INTEGER DEFAULT 0,
  last_clicked_at TIMESTAMP WITH TIME ZONE,
  clicked_urls TEXT[], -- Array of URLs clicked

  -- Reply tracking (Gmail only)
  reply_received BOOLEAN DEFAULT FALSE,
  first_reply_at TIMESTAMP WITH TIME ZONE,
  reply_count INTEGER DEFAULT 0,
  last_reply_at TIMESTAMP WITH TIME ZONE,

  -- Unsubscribe/spam tracking
  unsubscribed BOOLEAN DEFAULT FALSE,
  unsubscribed_at TIMESTAMP WITH TIME ZONE,
  spam_reported BOOLEAN DEFAULT FALSE,
  spam_reported_at TIMESTAMP WITH TIME ZONE,

  -- Webhook/event tracking
  last_event_type VARCHAR(50),
  last_event_at TIMESTAMP WITH TIME ZONE,
  raw_events JSONB, -- Store all webhook events for debugging [{event_type, timestamp, data}]

  -- Metadata
  sent_by VARCHAR(100),
  user_agent TEXT,  -- If opened, capture user agent
  ip_address INET,  -- If opened, capture IP

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Constraints
  CONSTRAINT chk_outreach_channel CHECK (channel IN ('gmail', 'sendgrid')),
  CONSTRAINT chk_outreach_status CHECK (status IN (
    'pending', 'queued', 'sent', 'delivered', 'deferred',
    'bounce', 'dropped', 'spam_report', 'failed'
  )),
  CONSTRAINT chk_outreach_bounce_type CHECK (bounce_type IN ('hard', 'soft', 'blocked')),
  CONSTRAINT chk_outreach_counts CHECK (
    open_count >= 0 AND click_count >= 0 AND reply_count >= 0
  ),
  -- Prevent duplicate sends in same campaign
  CONSTRAINT unique_candidate_campaign UNIQUE(candidate_id, campaign_id)
);

-- Indexes for outreach
CREATE INDEX IF NOT EXISTS idx_email_outreach_candidate ON email_outreach(candidate_id);
CREATE INDEX IF NOT EXISTS idx_email_outreach_campaign ON email_outreach(campaign_id);
CREATE INDEX IF NOT EXISTS idx_email_outreach_status ON email_outreach(status);
CREATE INDEX IF NOT EXISTS idx_email_outreach_channel ON email_outreach(channel);
CREATE INDEX IF NOT EXISTS idx_email_outreach_sent_at ON email_outreach(sent_at DESC) WHERE sent_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_email_outreach_gmail_thread ON email_outreach(gmail_thread_id) WHERE gmail_thread_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_email_outreach_sendgrid_msg ON email_outreach(sendgrid_message_id) WHERE sendgrid_message_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_email_outreach_recipient ON email_outreach(recipient_email);
CREATE INDEX IF NOT EXISTS idx_email_outreach_bounced ON email_outreach(bounce_type) WHERE bounce_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_email_outreach_replied ON email_outreach(reply_received) WHERE reply_received = TRUE;
CREATE INDEX IF NOT EXISTS idx_email_outreach_updated ON email_outreach(updated_at DESC);

COMMENT ON TABLE email_outreach IS 'Individual email sends across all channels with engagement tracking';
COMMENT ON COLUMN email_outreach.gmail_thread_id IS 'Used to match replies to original sends';
COMMENT ON COLUMN email_outreach.raw_events IS 'Complete webhook payloads for debugging';
COMMENT ON COLUMN email_outreach.status IS 'Current delivery status (updated by webhooks)';

-- =============================================================================
-- TABLE 3: email_replies
-- =============================================================================
-- Detailed reply tracking for Gmail personal outreach

CREATE TABLE IF NOT EXISTS public.email_replies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Relationships
  outreach_id UUID NOT NULL REFERENCES public.email_outreach(id) ON DELETE CASCADE,
  candidate_id UUID NOT NULL REFERENCES public.candidates(id) ON DELETE CASCADE,

  -- Gmail data
  gmail_message_id VARCHAR(255) NOT NULL UNIQUE, -- The reply message ID
  gmail_thread_id VARCHAR(255) NOT NULL,  -- Should match outreach.gmail_thread_id

  -- Reply content (lowercase enforced by trigger)
  from_email VARCHAR(255) NOT NULL,
  from_name VARCHAR(255),
  subject TEXT,
  body_text TEXT,
  body_html TEXT,
  snippet TEXT, -- First 200 chars for quick preview

  -- Attachments
  has_attachments BOOLEAN DEFAULT FALSE,
  attachment_count INTEGER DEFAULT 0,
  attachment_metadata JSONB, -- Array of {filename, mimeType, size}

  -- Analysis (manual or automated)
  sentiment VARCHAR(20),
  requires_follow_up BOOLEAN DEFAULT FALSE,
  auto_categorized BOOLEAN DEFAULT FALSE, -- If categorized by AI/rules vs. manual
  notes TEXT, -- Manual notes from staff

  -- Timestamps
  received_at TIMESTAMP WITH TIME ZONE NOT NULL,
  processed_at TIMESTAMP WITH TIME ZONE,

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Constraints
  CONSTRAINT chk_reply_sentiment CHECK (sentiment IN ('positive', 'neutral', 'negative', 'interested', 'not_interested', 'unsubscribe')),
  CONSTRAINT chk_reply_attachment_count CHECK (attachment_count >= 0)
);

-- Indexes for replies
CREATE INDEX IF NOT EXISTS idx_email_replies_outreach ON email_replies(outreach_id);
CREATE INDEX IF NOT EXISTS idx_email_replies_candidate ON email_replies(candidate_id);
CREATE INDEX IF NOT EXISTS idx_email_replies_thread ON email_replies(gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_email_replies_received ON email_replies(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_replies_follow_up ON email_replies(requires_follow_up) WHERE requires_follow_up = TRUE;
CREATE INDEX IF NOT EXISTS idx_email_replies_sentiment ON email_replies(sentiment) WHERE sentiment IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_email_replies_updated ON email_replies(updated_at DESC);

COMMENT ON TABLE email_replies IS 'Replies received via Gmail API with sentiment tracking';
COMMENT ON COLUMN email_replies.snippet IS 'First 200 characters for quick preview/notifications';
COMMENT ON COLUMN email_replies.sentiment IS 'Categorized response type for reporting';

-- =============================================================================
-- TABLE 4: email_opt_outs
-- =============================================================================
-- Global opt-out/unsubscribe list - CRITICAL for compliance and IP reputation

CREATE TABLE IF NOT EXISTS public.email_opt_outs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who opted out (lowercase enforced by trigger)
  email_address VARCHAR(255) NOT NULL UNIQUE,
  candidate_id UUID REFERENCES public.candidates(id) ON DELETE SET NULL, -- May be NULL if email not in candidates

  -- How they opted out
  opt_out_method VARCHAR(50) NOT NULL,

  -- Context
  outreach_id UUID REFERENCES public.email_outreach(id) ON DELETE SET NULL, -- Which email triggered opt-out
  campaign_id UUID REFERENCES public.email_campaigns(id) ON DELETE SET NULL,

  -- Reason/notes
  reason TEXT,
  notes TEXT, -- Admin notes

  -- Scope (future: allow campaign-specific opt-outs)
  scope VARCHAR(20) DEFAULT 'global',

  -- Timestamps
  opted_out_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Metadata
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Constraints
  CONSTRAINT chk_opt_out_method CHECK (opt_out_method IN (
    'unsubscribe_link', 'email_reply', 'sendgrid_webhook',
    'spam_complaint', 'manual_entry', 'hard_bounce'
  )),
  CONSTRAINT chk_opt_out_scope CHECK (scope IN ('global', 'campaign_type'))
);

-- Indexes for opt-outs
CREATE INDEX IF NOT EXISTS idx_email_opt_outs_email ON email_opt_outs(email_address);
CREATE INDEX IF NOT EXISTS idx_email_opt_outs_candidate ON email_opt_outs(candidate_id);
CREATE INDEX IF NOT EXISTS idx_email_opt_outs_method ON email_opt_outs(opt_out_method);
CREATE INDEX IF NOT EXISTS idx_email_opt_outs_date ON email_opt_outs(opted_out_at DESC);

COMMENT ON TABLE email_opt_outs IS 'Global opt-out list - checked before every email send';
COMMENT ON COLUMN email_opt_outs.scope IS 'Future: allow campaign-type-specific opt-outs';
COMMENT ON COLUMN email_opt_outs.opt_out_method IS 'How the opt-out was recorded (for compliance tracking)';

-- =============================================================================
-- TABLE 5: sendgrid_events
-- =============================================================================
-- Raw SendGrid webhook events for debugging and audit trail

CREATE TABLE IF NOT EXISTS public.sendgrid_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Link to outreach (may be NULL if event arrives before we match it)
  outreach_id UUID REFERENCES public.email_outreach(id) ON DELETE SET NULL,

  -- SendGrid webhook payload
  event_type VARCHAR(50) NOT NULL,

  email VARCHAR(255) NOT NULL,
  timestamp BIGINT NOT NULL, -- Unix timestamp from SendGrid
  event_time TIMESTAMP WITH TIME ZONE NOT NULL, -- Converted timestamp for queries

  sg_message_id VARCHAR(255),
  sg_event_id VARCHAR(255) UNIQUE,

  -- Event-specific data
  url TEXT,              -- For 'click' events
  reason TEXT,           -- For 'bounce', 'deferred', 'dropped'
  status TEXT,           -- SMTP status code
  response TEXT,         -- SMTP response
  attempt INTEGER,       -- Delivery attempt number
  useragent TEXT,        -- For 'open', 'click'
  ip VARCHAR(45),        -- IP address

  -- Categories/tags
  category TEXT[],
  asm_group_id INTEGER,  -- Unsubscribe group

  -- Full raw payload for debugging
  raw_payload JSONB NOT NULL,

  -- Processing status
  processed BOOLEAN DEFAULT FALSE,
  processed_at TIMESTAMP WITH TIME ZONE,
  processing_error TEXT,

  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Constraints
  CONSTRAINT chk_sendgrid_event_type CHECK (event_type IN (
    'processed', 'deferred', 'delivered', 'open', 'click',
    'bounce', 'dropped', 'spamreport', 'unsubscribe',
    'group_unsubscribe', 'group_resubscribe'
  )),
  CONSTRAINT chk_sendgrid_attempt CHECK (attempt IS NULL OR attempt >= 0)
);

-- Indexes for sendgrid events
CREATE INDEX IF NOT EXISTS idx_sendgrid_events_outreach ON sendgrid_events(outreach_id);
CREATE INDEX IF NOT EXISTS idx_sendgrid_events_type ON sendgrid_events(event_type);
CREATE INDEX IF NOT EXISTS idx_sendgrid_events_email ON sendgrid_events(email);
CREATE INDEX IF NOT EXISTS idx_sendgrid_events_msg_id ON sendgrid_events(sg_message_id);
CREATE INDEX IF NOT EXISTS idx_sendgrid_events_time ON sendgrid_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_sendgrid_events_unprocessed ON sendgrid_events(processed) WHERE processed = FALSE;

COMMENT ON TABLE sendgrid_events IS 'Raw SendGrid webhook events for audit trail and debugging';
COMMENT ON COLUMN sendgrid_events.raw_payload IS 'Complete webhook payload for forensics';
COMMENT ON COLUMN sendgrid_events.processed IS 'Whether event has been applied to email_outreach table';

-- =============================================================================
-- TRIGGERS: Auto-update timestamps
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if they exist (safe re-run)
DROP TRIGGER IF EXISTS update_email_campaigns_updated_at ON email_campaigns;
DROP TRIGGER IF EXISTS update_email_outreach_updated_at ON email_outreach;
DROP TRIGGER IF EXISTS update_email_replies_updated_at ON email_replies;

-- Apply to all tables with updated_at
CREATE TRIGGER update_email_campaigns_updated_at
  BEFORE UPDATE ON email_campaigns
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_email_outreach_updated_at
  BEFORE UPDATE ON email_outreach
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_email_replies_updated_at
  BEFORE UPDATE ON email_replies
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- TRIGGERS: Enforce lowercase emails
-- =============================================================================

-- Function to lowercase email addresses
CREATE OR REPLACE FUNCTION lowercase_email_addresses()
RETURNS TRIGGER AS $$
BEGIN
  -- Lowercase email fields
  IF TG_TABLE_NAME = 'email_outreach' THEN
    NEW.recipient_email = LOWER(NEW.recipient_email);
  ELSIF TG_TABLE_NAME = 'email_replies' THEN
    NEW.from_email = LOWER(NEW.from_email);
  ELSIF TG_TABLE_NAME = 'email_opt_outs' THEN
    NEW.email_address = LOWER(NEW.email_address);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if they exist (safe re-run)
DROP TRIGGER IF EXISTS enforce_lowercase_email_outreach ON email_outreach;
DROP TRIGGER IF EXISTS enforce_lowercase_email_replies ON email_replies;
DROP TRIGGER IF EXISTS enforce_lowercase_email_opt_outs ON email_opt_outs;

-- Apply to tables with email fields
CREATE TRIGGER enforce_lowercase_email_outreach
  BEFORE INSERT OR UPDATE ON email_outreach
  FOR EACH ROW
  EXECUTE FUNCTION lowercase_email_addresses();

CREATE TRIGGER enforce_lowercase_email_replies
  BEFORE INSERT OR UPDATE ON email_replies
  FOR EACH ROW
  EXECUTE FUNCTION lowercase_email_addresses();

CREATE TRIGGER enforce_lowercase_email_opt_outs
  BEFORE INSERT OR UPDATE ON email_opt_outs
  FOR EACH ROW
  EXECUTE FUNCTION lowercase_email_addresses();

-- =============================================================================
-- VIEW: email_outreach_summary
-- =============================================================================
-- Convenient view for reporting and dashboards

CREATE OR REPLACE VIEW email_outreach_summary AS
SELECT
  eo.id,
  eo.candidate_id,
  c.full_name,
  c.party,
  c.source_state,
  c.office_name,
  c.office_level,
  eo.recipient_email,
  eo.campaign_id,
  ec.campaign_name,
  ec.campaign_type,
  eo.channel,
  eo.status,
  eo.sent_at,
  eo.delivered_at,
  eo.opened,
  eo.first_opened_at,
  eo.open_count,
  eo.clicked,
  eo.first_clicked_at,
  eo.click_count,
  eo.reply_received,
  eo.first_reply_at,
  eo.reply_count,
  eo.bounce_type,
  eo.bounce_reason,
  eo.unsubscribed,
  eo.spam_reported,
  ev.is_valid as email_is_valid,
  ev.hunter_status,
  ev.confidence_score as email_confidence,
  CASE
    WHEN opt.id IS NOT NULL THEN TRUE
    ELSE FALSE
  END as is_opted_out,
  opt.opt_out_method,
  eo.created_at,
  eo.updated_at
FROM email_outreach eo
LEFT JOIN candidates c ON eo.candidate_id = c.id
LEFT JOIN email_campaigns ec ON eo.campaign_id = ec.id
LEFT JOIN email_validations ev ON eo.recipient_email = ev.email_address
LEFT JOIN email_opt_outs opt ON eo.recipient_email = opt.email_address;

COMMENT ON VIEW email_outreach_summary IS 'Comprehensive view combining outreach with candidate info, validation status, and opt-outs';

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Function to update campaign stats (optimized - single query)
CREATE OR REPLACE FUNCTION update_campaign_stats(p_campaign_id UUID)
RETURNS VOID AS $$
BEGIN
  UPDATE email_campaigns
  SET
    total_sent = stats.sent_count,
    total_delivered = stats.delivered_count,
    total_bounced = stats.bounced_count,
    total_opened = stats.opened_count,
    total_clicked = stats.clicked_count,
    total_replied = stats.replied_count,
    total_unsubscribed = stats.unsubscribed_count,
    updated_at = NOW()
  FROM (
    SELECT
      COUNT(*) FILTER (WHERE sent_at IS NOT NULL) as sent_count,
      COUNT(*) FILTER (WHERE status = 'delivered') as delivered_count,
      COUNT(*) FILTER (WHERE bounce_type IS NOT NULL) as bounced_count,
      COUNT(*) FILTER (WHERE opened = TRUE) as opened_count,
      COUNT(*) FILTER (WHERE clicked = TRUE) as clicked_count,
      COUNT(*) FILTER (WHERE reply_received = TRUE) as replied_count,
      COUNT(*) FILTER (WHERE unsubscribed = TRUE) as unsubscribed_count
    FROM email_outreach
    WHERE campaign_id = p_campaign_id
  ) as stats
  WHERE id = p_campaign_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_campaign_stats IS 'Recalculates denormalized stats for a campaign (optimized single query)';
