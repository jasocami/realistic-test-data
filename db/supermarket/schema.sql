-- supermarket/schema.sql
-- Table structure for the 'supermarket' topic. No data -- see
-- supermarket.sql.gz for the rows, or supermarket.sqlite for a
-- database you can query immediately.
--
-- SYNTHETIC DATA -- every record is invented. See README.md.

PRAGMA foreign_keys = ON;

-- stores: One row per physical store in the chain.
CREATE TABLE "stores" (
    "id" INTEGER PRIMARY KEY,
    "code" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL UNIQUE,
    "format" TEXT NOT NULL CHECK ("format" IN ('Express', 'Hipermercado', 'Supermercado')),
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "address" TEXT NOT NULL,
    "postal_code" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "floor_area_sqm" INTEGER NOT NULL,
    "opened_at" TEXT NOT NULL
);

-- categories: One row per product category, at any level of the hierarchy.
CREATE TABLE "categories" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL,
    "parent_id" INTEGER,
    "level" INTEGER NOT NULL,
    "vat_rate" REAL NOT NULL,
    FOREIGN KEY ("parent_id") REFERENCES "categories" ("id")
);
CREATE INDEX "idx_categories_parent_id" ON "categories" ("parent_id");

-- suppliers: One row per company that supplies products to the chain.
CREATE TABLE "suppliers" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL UNIQUE,
    "tax_id" TEXT NOT NULL UNIQUE,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "phone" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "lead_time_days" INTEGER NOT NULL,
    "active" INTEGER NOT NULL
);

-- employees: One row per member of store staff.
CREATE TABLE "employees" (
    "id" INTEGER PRIMARY KEY,
    "store_id" INTEGER NOT NULL,
    "employee_code" TEXT NOT NULL UNIQUE,
    "full_name" TEXT NOT NULL,
    "national_id" TEXT NOT NULL UNIQUE,
    "role" TEXT NOT NULL CHECK ("role" IN ('Baker', 'Butcher', 'Cashier', 'Department manager', 'Fishmonger', 'Security', 'Shelf stacker', 'Store manager')),
    "hired_at" TEXT NOT NULL,
    "hourly_rate" REAL NOT NULL,
    "active" INTEGER NOT NULL,
    FOREIGN KEY ("store_id") REFERENCES "stores" ("id")
);
CREATE INDEX "idx_employees_store_id" ON "employees" ("store_id");

-- products: One row per distinct product line carried by the chain.
CREATE TABLE "products" (
    "id" INTEGER PRIMARY KEY,
    "sku" TEXT NOT NULL UNIQUE,
    "ean13" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "category_id" INTEGER NOT NULL,
    "supplier_id" INTEGER NOT NULL,
    "brand" TEXT NOT NULL,
    "unit" TEXT NOT NULL CHECK ("unit" IN ('ud', 'kg', 'L', 'pack')),
    "unit_price" REAL NOT NULL,
    "cost_price" REAL NOT NULL,
    "vat_rate" REAL NOT NULL,
    "active" INTEGER NOT NULL,
    FOREIGN KEY ("category_id") REFERENCES "categories" ("id"),
    FOREIGN KEY ("supplier_id") REFERENCES "suppliers" ("id")
);
CREATE INDEX "idx_products_category_id" ON "products" ("category_id");
CREATE INDEX "idx_products_supplier_id" ON "products" ("supplier_id");

-- inventory: One row per product held at one store.
CREATE TABLE "inventory" (
    "id" INTEGER PRIMARY KEY,
    "store_id" INTEGER NOT NULL,
    "product_id" INTEGER NOT NULL,
    "quantity_on_hand" INTEGER NOT NULL,
    "reorder_level" INTEGER NOT NULL,
    "last_restocked_at" TEXT NOT NULL,
    FOREIGN KEY ("store_id") REFERENCES "stores" ("id"),
    FOREIGN KEY ("product_id") REFERENCES "products" ("id")
);
CREATE INDEX "idx_inventory_store_id" ON "inventory" ("store_id");
CREATE INDEX "idx_inventory_product_id" ON "inventory" ("product_id");

-- customers: One row per loyalty-card holder.
CREATE TABLE "customers" (
    "id" INTEGER PRIMARY KEY,
    "loyalty_card" TEXT NOT NULL UNIQUE,
    "full_name" TEXT NOT NULL,
    "email" TEXT,
    "phone" TEXT,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "postal_code" TEXT NOT NULL,
    "birth_date" TEXT,
    "segment" TEXT NOT NULL CHECK ("segment" IN ('new', 'occasional', 'premium', 'regular')),
    "signed_up_at" TEXT NOT NULL
);

-- promotions: One row per promotional offer on one product.
CREATE TABLE "promotions" (
    "id" INTEGER PRIMARY KEY,
    "product_id" INTEGER NOT NULL,
    "type" TEXT NOT NULL CHECK ("type" IN ('fixed_discount', 'percentage', 'second_unit_half_price', 'three_for_two')),
    "discount_percent" REAL NOT NULL,
    "starts_on" TEXT NOT NULL,
    "ends_on" TEXT NOT NULL,
    FOREIGN KEY ("product_id") REFERENCES "products" ("id")
);
CREATE INDEX "idx_promotions_product_id" ON "promotions" ("product_id");

-- transactions: One row per completed till transaction.
CREATE TABLE "transactions" (
    "id" INTEGER PRIMARY KEY,
    "receipt_number" TEXT NOT NULL UNIQUE,
    "store_id" INTEGER NOT NULL,
    "customer_id" INTEGER,
    "cashier_id" INTEGER NOT NULL,
    "occurred_at" TEXT NOT NULL,
    "payment_method" TEXT NOT NULL CHECK ("payment_method" IN ('card', 'cash', 'mobile', 'voucher')),
    "item_count" INTEGER NOT NULL,
    "subtotal" REAL NOT NULL,
    "vat_amount" REAL NOT NULL,
    "total" REAL NOT NULL,
    FOREIGN KEY ("store_id") REFERENCES "stores" ("id"),
    FOREIGN KEY ("customer_id") REFERENCES "customers" ("id"),
    FOREIGN KEY ("cashier_id") REFERENCES "employees" ("id")
);
CREATE INDEX "idx_transactions_store_id" ON "transactions" ("store_id");
CREATE INDEX "idx_transactions_customer_id" ON "transactions" ("customer_id");
CREATE INDEX "idx_transactions_cashier_id" ON "transactions" ("cashier_id");

-- transaction_items: One row per product scanned at the till within one transaction.
CREATE TABLE "transaction_items" (
    "id" INTEGER PRIMARY KEY,
    "transaction_id" INTEGER NOT NULL,
    "line_number" INTEGER NOT NULL,
    "product_id" INTEGER NOT NULL,
    "quantity" REAL NOT NULL,
    "unit_price" REAL NOT NULL,
    "discount_percent" REAL NOT NULL,
    "vat_rate" REAL NOT NULL,
    "line_total" REAL NOT NULL,
    FOREIGN KEY ("transaction_id") REFERENCES "transactions" ("id"),
    FOREIGN KEY ("product_id") REFERENCES "products" ("id")
);
CREATE INDEX "idx_transaction_items_transaction_id" ON "transaction_items" ("transaction_id");
CREATE INDEX "idx_transaction_items_product_id" ON "transaction_items" ("product_id");
