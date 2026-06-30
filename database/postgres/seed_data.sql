-- Minimal seed data for local development

INSERT INTO customer_risks (customer_id, risk_score, risk_level, risk_factors)
VALUES
	('cust_1001', 32.50, 'low', '{"velocity": "normal", "chargebacks": 0}'::jsonb),
	('cust_1002', 87.10, 'high', '{"velocity": "spike", "chargebacks": 3}'::jsonb)
ON CONFLICT (customer_id) DO NOTHING;
