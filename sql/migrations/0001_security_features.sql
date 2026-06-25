-- Migration: add email verification, password reset, and 2FA columns.
-- Safe to run against an existing StayNova database created before these
-- columns were added to sql/schema.sql. Run once:
--   mysql -u root -p staynova < sql/migrations/0001_security_features.sql

USE staynova;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified      TINYINT(1) NOT NULL DEFAULT 0 AFTER is_active,
    ADD COLUMN IF NOT EXISTS reset_token_hash     VARCHAR(64) DEFAULT NULL AFTER email_verified,
    ADD COLUMN IF NOT EXISTS reset_token_expires  DATETIME DEFAULT NULL AFTER reset_token_hash,
    ADD COLUMN IF NOT EXISTS totp_secret          VARCHAR(32) DEFAULT NULL AFTER reset_token_expires,
    ADD COLUMN IF NOT EXISTS totp_enabled         TINYINT(1) NOT NULL DEFAULT 0 AFTER totp_secret;

-- Grandfather in accounts that already existed before email verification was
-- required, so nobody who could already log in gets locked out.
UPDATE users SET email_verified = 1 WHERE email_verified = 0;
