-- Fraud Analytics Platform PostgreSQL schema

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS customer_risks (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	customer_id VARCHAR(100) NOT NULL UNIQUE,
	risk_score NUMERIC(5, 2) NOT NULL,
	risk_level VARCHAR(20) NOT NULL,
	risk_factors JSONB NOT NULL DEFAULT '{}'::jsonb,
	last_evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transactions (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	transaction_ref VARCHAR(120) NOT NULL UNIQUE,
	customer_id VARCHAR(100) NOT NULL,
	amount NUMERIC(18, 2) NOT NULL,
	currency CHAR(3) NOT NULL,
	merchant_name VARCHAR(200) NOT NULL,
	merchant_category VARCHAR(120),
	transaction_type VARCHAR(60) NOT NULL,
	channel VARCHAR(60) NOT NULL,
	device_id VARCHAR(120),
	ip_address VARCHAR(45),
	location JSONB NOT NULL DEFAULT '{}'::jsonb,
	status VARCHAR(30) NOT NULL DEFAULT 'received',
	transaction_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
	occurred_at TIMESTAMPTZ NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fraud_scores (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
	score NUMERIC(6, 4) NOT NULL,
	model_version VARCHAR(50) NOT NULL,
	risk_level VARCHAR(20) NOT NULL,
	is_fraud_predicted BOOLEAN NOT NULL DEFAULT FALSE,
	reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
	generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
	fraud_score_id UUID REFERENCES fraud_scores(id) ON DELETE SET NULL,
	alert_type VARCHAR(60) NOT NULL,
	severity VARCHAR(20) NOT NULL,
	status VARCHAR(30) NOT NULL DEFAULT 'open',
	title VARCHAR(200) NOT NULL,
	description TEXT,
	assigned_to VARCHAR(120),
	acknowledged_at TIMESTAMPTZ,
	resolved_at TIMESTAMPTZ,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS investigations (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
	investigator VARCHAR(120),
	status VARCHAR(30) NOT NULL DEFAULT 'pending',
	priority VARCHAR(20) NOT NULL DEFAULT 'medium',
	notes TEXT,
	findings JSONB NOT NULL DEFAULT '{}'::jsonb,
	started_at TIMESTAMPTZ,
	closed_at TIMESTAMPTZ,
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_customer_id ON transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_transactions_occurred_at ON transactions(occurred_at);
CREATE INDEX IF NOT EXISTS idx_fraud_scores_transaction_id ON fraud_scores(transaction_id);
CREATE INDEX IF NOT EXISTS idx_fraud_scores_score ON fraud_scores(score);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_investigations_alert_id ON investigations(alert_id);
CREATE INDEX IF NOT EXISTS idx_customer_risks_customer_id ON customer_risks(customer_id);
