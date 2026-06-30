-- Migration: add the reviews table (ratings + comments per user/hotel).
-- Safe to run against an existing StayNova database created before this
-- table existed in sql/schema.sql. Run once:
--   mysql -u root -p staynova < sql/migrations/0002_reviews.sql

USE staynova;

CREATE TABLE IF NOT EXISTS reviews (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    hotel_id        INT NOT NULL,
    booking_id      INT DEFAULT NULL,
    rating          TINYINT NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_reviews_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_reviews_hotel FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE,
    CONSTRAINT fk_reviews_booking FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE SET NULL,
    CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5),
    UNIQUE KEY uq_reviews_user_hotel (user_id, hotel_id),
    INDEX idx_reviews_hotel (hotel_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
