-- automobile/schema.sql
-- Table structure for the 'automobile' topic. No data -- see
-- automobile.sql.gz for the rows, or automobile.sqlite for a
-- database you can query immediately.
--
-- SYNTHETIC DATA -- every record is invented. See README.md.

PRAGMA foreign_keys = ON;

-- manufacturers: One row per vehicle manufacturer.
CREATE TABLE "manufacturers" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL UNIQUE,
    "country" TEXT NOT NULL,
    "founded" INTEGER NOT NULL,
    "wmi" TEXT NOT NULL UNIQUE
);

-- models: One row per model produced by one manufacturer.
CREATE TABLE "models" (
    "id" INTEGER PRIMARY KEY,
    "manufacturer_id" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "segment" TEXT NOT NULL CHECK ("segment" IN ('A', 'B', 'C', 'D', 'E', 'MPV', 'SUV', 'Van')),
    "body_type" TEXT NOT NULL CHECK ("body_type" IN ('hatchback', 'saloon', 'estate', 'SUV', 'coupe', 'MPV', 'van')),
    "year_from" INTEGER NOT NULL,
    "year_to" INTEGER,
    "base_price" REAL NOT NULL,
    FOREIGN KEY ("manufacturer_id") REFERENCES "manufacturers" ("id")
);
CREATE INDEX "idx_models_manufacturer_id" ON "models" ("manufacturer_id");

-- dealerships: One row per dealership location.
CREATE TABLE "dealerships" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL,
    "manufacturer_id" INTEGER NOT NULL,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "address" TEXT NOT NULL,
    "postal_code" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "opened_at" TEXT NOT NULL,
    FOREIGN KEY ("manufacturer_id") REFERENCES "manufacturers" ("id")
);
CREATE INDEX "idx_dealerships_manufacturer_id" ON "dealerships" ("manufacturer_id");

-- parts: One row per part in the spares catalogue.
CREATE TABLE "parts" (
    "id" INTEGER PRIMARY KEY,
    "oem_code" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "category" TEXT NOT NULL CHECK ("category" IN ('Body', 'Brakes', 'Electrical', 'Engine', 'Filters', 'Suspension', 'Transmission', 'Tyres')),
    "unit_price" REAL NOT NULL,
    "stock_quantity" INTEGER NOT NULL
);

-- owners: One row per person who has owned a vehicle.
CREATE TABLE "owners" (
    "id" INTEGER PRIMARY KEY,
    "full_name" TEXT NOT NULL,
    "national_id" TEXT NOT NULL UNIQUE,
    "licence_number" TEXT NOT NULL UNIQUE,
    "birth_date" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "postal_code" TEXT NOT NULL,
    "phone" TEXT NOT NULL
);

-- vehicles: One row per individual physical vehicle.
CREATE TABLE "vehicles" (
    "id" INTEGER PRIMARY KEY,
    "vin" TEXT NOT NULL UNIQUE,
    "plate" TEXT NOT NULL UNIQUE,
    "model_id" INTEGER NOT NULL,
    "year" INTEGER NOT NULL,
    "colour" TEXT NOT NULL,
    "fuel_type" TEXT NOT NULL CHECK ("fuel_type" IN ('diesel', 'electric', 'hybrid', 'lpg', 'petrol', 'plug_in_hybrid')),
    "transmission" TEXT NOT NULL CHECK ("transmission" IN ('automatic', 'manual')),
    "engine_cc" INTEGER NOT NULL,
    "power_hp" INTEGER NOT NULL,
    "mileage_km" INTEGER NOT NULL,
    "registered_on" TEXT NOT NULL,
    FOREIGN KEY ("model_id") REFERENCES "models" ("id")
);
CREATE INDEX "idx_vehicles_model_id" ON "vehicles" ("model_id");

-- ownership_history: One row per period during which one owner held one vehicle.
CREATE TABLE "ownership_history" (
    "id" INTEGER PRIMARY KEY,
    "vehicle_id" INTEGER NOT NULL,
    "owner_id" INTEGER NOT NULL,
    "owned_from" TEXT NOT NULL,
    "owned_until" TEXT,
    "purchase_price" REAL,
    FOREIGN KEY ("vehicle_id") REFERENCES "vehicles" ("id"),
    FOREIGN KEY ("owner_id") REFERENCES "owners" ("id")
);
CREATE INDEX "idx_ownership_history_vehicle_id" ON "ownership_history" ("vehicle_id");
CREATE INDEX "idx_ownership_history_owner_id" ON "ownership_history" ("owner_id");

-- sales: One row per vehicle sold through a dealership.
CREATE TABLE "sales" (
    "id" INTEGER PRIMARY KEY,
    "vehicle_id" INTEGER NOT NULL,
    "dealership_id" INTEGER NOT NULL,
    "buyer_id" INTEGER NOT NULL,
    "sale_date" TEXT NOT NULL,
    "sale_type" TEXT NOT NULL CHECK ("sale_type" IN ('demo', 'new', 'used')),
    "sale_price" REAL NOT NULL,
    "financing" TEXT NOT NULL CHECK ("financing" IN ('cash', 'leasing', 'loan', 'renting')),
    "warranty_months" INTEGER NOT NULL,
    FOREIGN KEY ("vehicle_id") REFERENCES "vehicles" ("id"),
    FOREIGN KEY ("dealership_id") REFERENCES "dealerships" ("id"),
    FOREIGN KEY ("buyer_id") REFERENCES "owners" ("id")
);
CREATE INDEX "idx_sales_vehicle_id" ON "sales" ("vehicle_id");
CREATE INDEX "idx_sales_dealership_id" ON "sales" ("dealership_id");
CREATE INDEX "idx_sales_buyer_id" ON "sales" ("buyer_id");

-- service_records: One row per workshop visit by one vehicle.
CREATE TABLE "service_records" (
    "id" INTEGER PRIMARY KEY,
    "vehicle_id" INTEGER NOT NULL,
    "dealership_id" INTEGER,
    "service_date" TEXT NOT NULL,
    "mileage_km" INTEGER NOT NULL,
    "service_type" TEXT NOT NULL CHECK ("service_type" IN ('Air conditioning service', 'Battery replacement', 'Bodywork repair', 'Brake replacement', 'Clutch repair', 'Oil and filter change', 'Routine service', 'Suspension repair', 'Timing belt replacement', 'Tyre replacement')),
    "parts_cost" REAL NOT NULL,
    "labour_cost" REAL NOT NULL,
    "total_cost" REAL NOT NULL,
    FOREIGN KEY ("vehicle_id") REFERENCES "vehicles" ("id"),
    FOREIGN KEY ("dealership_id") REFERENCES "dealerships" ("id")
);
CREATE INDEX "idx_service_records_vehicle_id" ON "service_records" ("vehicle_id");
CREATE INDEX "idx_service_records_dealership_id" ON "service_records" ("dealership_id");

-- inspections: One row per ITV roadworthiness inspection of one vehicle.
CREATE TABLE "inspections" (
    "id" INTEGER PRIMARY KEY,
    "vehicle_id" INTEGER NOT NULL,
    "inspection_date" TEXT NOT NULL,
    "result" TEXT NOT NULL CHECK ("result" IN ('favourable', 'negative', 'unfavourable')),
    "defects" TEXT,
    "mileage_km" INTEGER NOT NULL,
    "next_due" TEXT NOT NULL,
    "station_code" TEXT NOT NULL,
    FOREIGN KEY ("vehicle_id") REFERENCES "vehicles" ("id")
);
CREATE INDEX "idx_inspections_vehicle_id" ON "inspections" ("vehicle_id");
