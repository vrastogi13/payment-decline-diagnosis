-- Decline Knowledge Base schema
-- For the agentic decline-diagnosis study. Works on PostgreSQL and DuckDB.
-- Descriptions are written in our own words; source wording is never copied.

-- 1. Sources: every public document the knowledge base draws on
CREATE TABLE kb_source (
    source_id        TEXT PRIMARY KEY,          -- e.g. 'adyen_raw_responses'
    publisher        TEXT NOT NULL,             -- 'Adyen', 'Visa Acceptance', 'Mastercard'
    title            TEXT NOT NULL,
    url              TEXT NOT NULL,
    source_kind      TEXT NOT NULL CHECK (source_kind IN ('network', 'processor', 'secondary')),
    accessed_on      DATE NOT NULL,
    notes            TEXT
);

-- 2. Controlled vocabularies used as benchmark labels
CREATE TABLE decline_category (
    category         TEXT PRIMARY KEY,
    description      TEXT NOT NULL
);

CREATE TABLE recommended_action (
    action           TEXT PRIMARY KEY,
    description      TEXT NOT NULL,
    actor            TEXT NOT NULL CHECK (actor IN ('merchant', 'cardholder', 'provider'))
);

-- 3. Codes: one row per (network, code system, code)
CREATE TABLE decline_code (
    code_id              TEXT PRIMARY KEY,      -- e.g. 'visa:iso:51'
    network              TEXT NOT NULL CHECK (network IN ('visa', 'mastercard', 'amex', 'discover', 'diners', 'any')),
    code_system          TEXT NOT NULL CHECK (code_system IN ('iso_response', 'merchant_advice', 'network_decision')),
    code                 TEXT NOT NULL,         -- keep as text: '05' is not 5
    short_name           TEXT NOT NULL,
    meaning              TEXT NOT NULL,         -- our own paraphrase
    category             TEXT NOT NULL REFERENCES decline_category(category),
    decline_type         TEXT NOT NULL CHECK (decline_type IN ('soft', 'hard', 'depends')),
    retryable            TEXT NOT NULL CHECK (retryable IN ('yes', 'no', 'conditional')),
    retry_guidance       TEXT,                  -- e.g. 'after 24 hours, at most N attempts'
    primary_action       TEXT NOT NULL REFERENCES recommended_action(action),
    secondary_action     TEXT REFERENCES recommended_action(action),
    cardholder_message   TEXT NOT NULL,         -- safe, non-specific wording a shopper may see
    merchant_explanation TEXT NOT NULL,         -- fuller explanation for merchants and support
    escalate_to_human    BOOLEAN NOT NULL DEFAULT FALSE,
    confidence           TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    last_verified        DATE NOT NULL,
    UNIQUE (network, code_system, code)
);

-- 4. Evidence: which sources support each code entry, and whether they agree
CREATE TABLE code_evidence (
    code_id          TEXT NOT NULL REFERENCES decline_code(code_id),
    source_id        TEXT NOT NULL REFERENCES kb_source(source_id),
    source_summary   TEXT NOT NULL,             -- our paraphrase of what this source says
    agrees           BOOLEAN NOT NULL,          -- FALSE flags a conflict to resolve
    PRIMARY KEY (code_id, source_id)
);

-- 5. Processor codes mapped to network meaning (e.g. a processor's '302' -> Visa 51)
CREATE TABLE processor_code_map (
    processor        TEXT NOT NULL,
    processor_code   TEXT NOT NULL,
    processor_label  TEXT,
    code_id          TEXT REFERENCES decline_code(code_id),  -- NULL if no network equivalent
    source_id        TEXT NOT NULL REFERENCES kb_source(source_id),
    PRIMARY KEY (processor, processor_code)
);

-- 6. Decision rules: a merchant advice code can override the response code
-- e.g. response 51 (normally retry later) + Mastercard advice 03 (do not try again) -> do not retry
CREATE TABLE decision_rule (
    rule_id          TEXT PRIMARY KEY,
    response_code_id TEXT REFERENCES decline_code(code_id),  -- NULL = any response code
    advice_code_id   TEXT REFERENCES decline_code(code_id),  -- NULL = any advice code, or none
    is_recurring     BOOLEAN,                                -- NULL = applies to both
    resulting_action TEXT NOT NULL REFERENCES recommended_action(action),
    priority         INTEGER NOT NULL,                       -- higher wins
    rationale        TEXT NOT NULL,
    source_id        TEXT REFERENCES kb_source(source_id)
);

-- 7. Snapshot used for each experiment run (retrieval and fine-tuning must use the same one)
CREATE TABLE kb_snapshot (
    snapshot_id      TEXT PRIMARY KEY,          -- e.g. 'kb-2026-11-15'
    created_on       DATE NOT NULL,
    code_count       INTEGER NOT NULL,
    notes            TEXT
);

-- Seed vocabularies
INSERT INTO decline_category VALUES
 ('insufficient_funds',     'Not enough balance or credit available'),
 ('expired_card',           'Card past its expiry date'),
 ('invalid_account',        'Card number or account does not exist or is closed'),
 ('lost_stolen',            'Card reported lost or stolen'),
 ('fraud_suspected',        'Issuer or network suspects fraud'),
 ('issuer_generic',         'Issuer declined without a specific reason, such as Do Not Honor'),
 ('authentication_required','Issuer requires stronger customer authentication'),
 ('limit_exceeded',         'Amount or frequency limit exceeded'),
 ('restricted_card',        'Card not permitted for this transaction type or merchant'),
 ('invalid_data',           'Request data wrong or missing, such as CVV, expiry or address'),
 ('issuer_unavailable',     'Issuer or network could not be reached or timed out'),
 ('merchant_config',        'Problem with the merchant account or setup'),
 ('recurring_cancelled',    'Cardholder or issuer stopped recurring payments to this merchant');

INSERT INTO recommended_action VALUES
 ('retry_later',              'Retry after a waiting period within network retry limits', 'merchant'),
 ('retry_with_authentication','Retry with 3-D Secure or other strong authentication',     'merchant'),
 ('update_credential',        'Get updated card details through an account updater or network token', 'merchant'),
 ('request_new_payment',      'Ask the customer for a different payment method',          'merchant'),
 ('contact_issuer',           'Customer should contact their bank',                       'cardholder'),
 ('do_not_retry',             'Do not retry this card for this transaction',              'merchant'),
 ('stop_recurring',           'Stop recurring charges on this card and notify the customer', 'merchant'),
 ('fix_request_data',         'Correct the request data and resubmit',                    'merchant'),
 ('check_merchant_setup',     'Review merchant account configuration with the provider',  'provider'),
 ('escalate_to_engineer',     'Hand off to an on-call engineer for investigation',        'provider');
