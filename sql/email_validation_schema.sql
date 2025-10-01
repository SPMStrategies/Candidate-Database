-- Email validation tracking system
-- Validates all candidate emails and tracks results

-- Email validation tracking
CREATE TABLE IF NOT EXISTS public.email_validations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email_address VARCHAR(255) NOT NULL UNIQUE,
    candidate_id UUID REFERENCES public.candidates(id) ON DELETE CASCADE,
    
    -- Overall validation status
    is_valid BOOLEAN,
    validation_method VARCHAR(50), -- 'free_checks', 'hunter_api', 'hunter_full'
    confidence_score DECIMAL(3,2), -- 0.00 to 1.00
    
    -- Free check results
    syntax_valid BOOLEAN,
    dns_valid BOOLEAN,
    mx_records_found BOOLEAN,
    is_disposable BOOLEAN DEFAULT FALSE,
    is_role_account BOOLEAN DEFAULT FALSE,
    
    -- Hunter.io results (if used)
    hunter_status VARCHAR(50), -- valid, invalid, accept_all, webmail, disposable, etc.
    hunter_score INTEGER, -- 0-100 confidence score from Hunter
    hunter_result JSONB, -- Full API response for debugging
    hunter_regexp BOOLEAN, -- Email matches expected pattern
    hunter_gibberish BOOLEAN, -- Detected as random string
    
    -- Error tracking
    validation_error TEXT,
    
    -- Temporal tracking
    first_validated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_validated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    next_validation_due TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '60 days',
    validation_count INTEGER DEFAULT 1,
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_email_val_candidate ON email_validations(candidate_id);
CREATE INDEX IF NOT EXISTS idx_email_val_due ON email_validations(next_validation_due);
CREATE INDEX IF NOT EXISTS idx_email_val_valid ON email_validations(is_valid);
CREATE INDEX IF NOT EXISTS idx_email_val_email ON email_validations(email_address);

-- Validation run tracking
CREATE TABLE IF NOT EXISTS public.email_validation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Statistics
    total_emails_checked INTEGER DEFAULT 0,
    new_emails_validated INTEGER DEFAULT 0,
    emails_revalidated INTEGER DEFAULT 0,
    valid_count INTEGER DEFAULT 0,
    invalid_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Hunter.io usage
    hunter_credits_used INTEGER DEFAULT 0,
    
    -- Run metadata
    run_type VARCHAR(20), -- 'all', 'new', 'revalidation', 'manual'
    triggered_by VARCHAR(100), -- 'github_action', 'manual', 'post_ingest'
    error_log TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- View for easy querying of email validation status
CREATE OR REPLACE VIEW email_validation_status AS
SELECT 
    c.id as candidate_id,
    c.full_name,
    c.contact_email,
    c.source_state,
    ev.is_valid,
    ev.validation_method,
    ev.confidence_score,
    ev.hunter_status,
    ev.is_disposable,
    ev.is_role_account,
    ev.last_validated_at,
    ev.next_validation_due,
    CASE 
        WHEN ev.is_valid IS NULL THEN 'Not Validated'
        WHEN ev.is_valid = true THEN 'Valid'
        ELSE 'Invalid'
    END as status,
    CASE
        WHEN ev.validation_error IS NOT NULL THEN ev.validation_error
        WHEN ev.is_disposable = true THEN 'Disposable Email'
        WHEN ev.syntax_valid = false THEN 'Invalid Syntax'
        WHEN ev.dns_valid = false THEN 'Domain Not Found'
        WHEN ev.mx_records_found = false THEN 'No Mail Server'
        WHEN ev.hunter_status = 'invalid' THEN 'Invalid (Hunter.io)'
        ELSE NULL
    END as issue
FROM candidates c
LEFT JOIN email_validations ev ON c.contact_email = ev.email_address
WHERE c.contact_email IS NOT NULL;

COMMENT ON TABLE email_validations IS 'Tracks validation status of all candidate email addresses';
COMMENT ON TABLE email_validation_runs IS 'Logs each validation run for auditing and monitoring';
COMMENT ON VIEW email_validation_status IS 'Current validation status for all candidate emails';