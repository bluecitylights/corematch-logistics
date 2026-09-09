-- DuckDB 1.5+ requires MINVALUE <= START; use MINVALUE 0 to allow zero-based indexing.
CREATE SEQUENCE driver_seq START 0 MINVALUE 0;
CREATE SEQUENCE vehicle_seq START 0 MINVALUE 0;

CREATE TABLE drivers (
    driver_index INT DEFAULT nextval('driver_seq') UNIQUE,
    driver_id VARCHAR UNIQUE,
    location VARCHAR,
    is_active BOOLEAN DEFAULT true,
    skill_adr BOOLEAN DEFAULT false,
    skill_ehbo BOOLEAN DEFAULT false
);

CREATE TABLE vehicles (
    vehicle_index INT DEFAULT nextval('vehicle_seq') UNIQUE,
    vehicle_id VARCHAR UNIQUE,
    license_plate VARCHAR,
    location VARCHAR,
    is_active BOOLEAN DEFAULT true,
    spec_liftgate BOOLEAN DEFAULT false,
    spec_refrigerated BOOLEAN DEFAULT false
);

CREATE TABLE orders (
    order_id VARCHAR UNIQUE,
    destination VARCHAR,
    -- Driver requirements
    req_driver_adr BOOLEAN DEFAULT false,
    req_driver_ehbo BOOLEAN DEFAULT false,
    -- Vehicle requirements
    req_vehicle_liftgate BOOLEAN DEFAULT false,
    req_vehicle_refrigerated BOOLEAN DEFAULT false
);

CREATE TABLE index_store (
    index_type VARCHAR,
    key_name VARCHAR,
    bitmap_data BLOB
);
