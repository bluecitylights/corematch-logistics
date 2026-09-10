-- DuckDB 1.5+ requires MINVALUE <= START; use MINVALUE 0 to allow zero-based indexing.
CREATE SEQUENCE driver_seq START 0 MINVALUE 0;
CREATE SEQUENCE vehicle_seq START 0 MINVALUE 0;
CREATE SEQUENCE location_seq START 0 MINVALUE 0;

CREATE TABLE drivers (
    driver_index INT DEFAULT nextval('driver_seq') UNIQUE,
    driver_id VARCHAR UNIQUE,
    location_id INT,
    is_active BOOLEAN DEFAULT true,
    skill_adr BOOLEAN DEFAULT false,
    skill_ehbo BOOLEAN DEFAULT false
);

CREATE TABLE vehicles (
    vehicle_index INT DEFAULT nextval('vehicle_seq') UNIQUE,
    vehicle_id VARCHAR UNIQUE,
    license_plate VARCHAR,
    location_id INT,
    is_active BOOLEAN DEFAULT true,
    spec_liftgate BOOLEAN DEFAULT false,
    spec_refrigerated BOOLEAN DEFAULT false
);

CREATE TABLE orders (
    order_id VARCHAR UNIQUE,
    destination_location_id INT,
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

CREATE TABLE locations (
    location_id INT DEFAULT nextval('location_seq') UNIQUE,
    zip VARCHAR PRIMARY KEY,
    city VARCHAR NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL
);

CREATE TABLE distance_matrix (
    origin_zip VARCHAR NOT NULL,
    dest_zip VARCHAR NOT NULL,
    distance_m INTEGER NOT NULL,
    travel_time_min INTEGER NOT NULL,
    PRIMARY KEY (origin_zip, dest_zip)
);

CREATE TABLE plans (
    plan_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL
);

CREATE TABLE plan_orders (
    plan_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    driver_id VARCHAR,
    vehicle_id VARCHAR,
    stop_sequence INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (plan_id, order_id)
);

CREATE TABLE plan_evaluations (
    plan_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    driver_id VARCHAR NOT NULL,
    vehicle_id VARCHAR NOT NULL,
    stop_sequence INTEGER NOT NULL,
    origin_zip VARCHAR NOT NULL,
    destination_zip VARCHAR NOT NULL,
    driving_time_min INTEGER NOT NULL,
    departure_time VARCHAR NOT NULL,
    arrival_time VARCHAR NOT NULL,
    PRIMARY KEY (plan_id, order_id)
);
