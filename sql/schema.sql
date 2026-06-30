-- StayNova database schema
-- Run via scripts/init_db.py or: mysql -u root -p < sql/schema.sql (after CREATE DATABASE/USE)

CREATE DATABASE IF NOT EXISTS staynova
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE staynova;

-- ---------------------------------------------------------------
-- users
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id                   INT AUTO_INCREMENT PRIMARY KEY,
    first_name           VARCHAR(60)  NOT NULL,
    last_name            VARCHAR(60)  NOT NULL,
    email                VARCHAR(120) NOT NULL UNIQUE,
    phone                VARCHAR(20)  DEFAULT NULL,
    password_hash        VARCHAR(255) NOT NULL,
    role                 ENUM('user', 'admin') NOT NULL DEFAULT 'user',
    failed_logins        INT NOT NULL DEFAULT 0,
    locked_until         DATETIME DEFAULT NULL,
    is_active            TINYINT(1) NOT NULL DEFAULT 1,
    -- Email verification
    email_verified       TINYINT(1) NOT NULL DEFAULT 0,
    -- Password reset (only a hash of the token is ever stored)
    reset_token_hash      VARCHAR(64) DEFAULT NULL,
    reset_token_expires  DATETIME DEFAULT NULL,
    -- Two-factor authentication (TOTP)
    totp_secret          VARCHAR(32) DEFAULT NULL,
    totp_enabled         TINYINT(1) NOT NULL DEFAULT 0,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------
-- hotels
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hotels (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    city            VARCHAR(100) NOT NULL,
    address         VARCHAR(255) NOT NULL,
    description     TEXT,
    star_rating     TINYINT NOT NULL DEFAULT 3,
    image_url       VARCHAR(500) DEFAULT NULL,
    amenities       VARCHAR(500) DEFAULT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hotels_city (city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------
-- rooms
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rooms (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    hotel_id        INT NOT NULL,
    room_type       VARCHAR(100) NOT NULL,
    description     TEXT,
    price_per_night DECIMAL(10, 2) NOT NULL,
    capacity        TINYINT NOT NULL DEFAULT 2,
    total_rooms     INT NOT NULL DEFAULT 1,
    image_url       VARCHAR(500) DEFAULT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rooms_hotel FOREIGN KEY (hotel_id) REFERENCES hotels(id) ON DELETE CASCADE,
    INDEX idx_rooms_hotel (hotel_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------
-- bookings
-- ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bookings (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    room_id         INT NOT NULL,
    check_in        DATE NOT NULL,
    check_out       DATE NOT NULL,
    guests          TINYINT NOT NULL DEFAULT 1,
    total_price     DECIMAL(10, 2) NOT NULL,
    status          ENUM('confirmed', 'cancelled', 'completed') NOT NULL DEFAULT 'confirmed',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_bookings_room FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    INDEX idx_bookings_user (user_id),
    INDEX idx_bookings_room (room_id),
    INDEX idx_bookings_dates (check_in, check_out)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------
-- reviews (one per user per hotel; left after a completed stay)
-- ---------------------------------------------------------------
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
