-- DuckDB 1.5+ requires MINVALUE <= START; use MINVALUE 0 to allow zero-based indexing.
CREATE SEQUENCE IF NOT EXISTS driver_seq START 0 MINVALUE 0;
CREATE SEQUENCE IF NOT EXISTS vehicle_seq START 0 MINVALUE 0;
CREATE SEQUENCE IF NOT EXISTS location_seq START 0 MINVALUE 0;

CREATE TABLE IF NOT EXISTS locations (
    location_index INT DEFAULT nextval('location_seq') UNIQUE,
    zip VARCHAR PRIMARY KEY,
    city VARCHAR NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL
);

CREATE TABLE IF NOT EXISTS drivers (
    driver_index INT DEFAULT nextval('driver_seq') UNIQUE,
    driver_id VARCHAR PRIMARY KEY,
    location_index INT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    skill_adr BOOLEAN DEFAULT false,
    skill_ehbo BOOLEAN DEFAULT false,
    FOREIGN KEY (location_index) REFERENCES locations(location_index)
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_index INT DEFAULT nextval('vehicle_seq') UNIQUE,
    vehicle_id VARCHAR PRIMARY KEY,
    license_plate VARCHAR,
    location_index INT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    spec_liftgate BOOLEAN DEFAULT false,
    spec_refrigerated BOOLEAN DEFAULT false,
    FOREIGN KEY (location_index) REFERENCES locations(location_index)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR PRIMARY KEY,
    destination_location_index INT NOT NULL,
    req_driver_adr BOOLEAN DEFAULT false,
    req_driver_ehbo BOOLEAN DEFAULT false,
    req_vehicle_liftgate BOOLEAN DEFAULT false,
    req_vehicle_refrigerated BOOLEAN DEFAULT false,
    FOREIGN KEY (destination_location_index) REFERENCES locations(location_index)
);

CREATE TABLE IF NOT EXISTS index_store (
    index_type VARCHAR,
    key_name VARCHAR,
    bitmap_data BLOB
);

CREATE TABLE IF NOT EXISTS distance_matrix (
    origin_location_index INTEGER NOT NULL,
    dest_location_index INTEGER NOT NULL,
    distance_m INTEGER NOT NULL,
    travel_time_min INTEGER NOT NULL,
    PRIMARY KEY (origin_location_index, dest_location_index),
    FOREIGN KEY (origin_location_index) REFERENCES locations(location_index),
    FOREIGN KEY (dest_location_index) REFERENCES locations(location_index)
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_orders (
    plan_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    driver_id VARCHAR,
    vehicle_id VARCHAR,
    stop_sequence INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (plan_id, order_id),
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id)
);

CREATE TABLE IF NOT EXISTS plan_evaluations (
    plan_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    driver_id VARCHAR NOT NULL,
    vehicle_id VARCHAR NOT NULL,
    stop_sequence INTEGER NOT NULL,
    origin_location_index INTEGER NOT NULL,
    destination_location_index INTEGER NOT NULL,
    driving_time_min INTEGER NOT NULL,
    departure_time TIMESTAMP NOT NULL,
    arrival_time TIMESTAMP NOT NULL,
    PRIMARY KEY (plan_id, order_id),
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    FOREIGN KEY (origin_location_index) REFERENCES locations(location_index),
    FOREIGN KEY (destination_location_index) REFERENCES locations(location_index)
);

CREATE TABLE IF NOT EXISTS plan_route_evaluations (
    plan_id VARCHAR NOT NULL,
    driver_id VARCHAR NOT NULL,
    vehicle_id VARCHAR NOT NULL,
    start_location_index INTEGER NOT NULL,
    last_stop_location_index INTEGER NOT NULL,
    return_driving_time_min INTEGER NOT NULL,
    return_departure_time TIMESTAMP NOT NULL,
    return_arrival_time TIMESTAMP NOT NULL,
    PRIMARY KEY (plan_id, driver_id, vehicle_id),
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
    FOREIGN KEY (driver_id) REFERENCES drivers(driver_id),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    FOREIGN KEY (start_location_index) REFERENCES locations(location_index),
    FOREIGN KEY (last_stop_location_index) REFERENCES locations(location_index)
);