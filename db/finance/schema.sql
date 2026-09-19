-- finance/schema.sql
-- Table structure for the 'finance' topic. No data -- see
-- finance.sql.gz for the rows, or finance.sqlite for a
-- database you can query immediately.
--
-- SYNTHETIC DATA -- every record is invented. See README.md.

PRAGMA foreign_keys = ON;

-- branches: One row per physical bank branch.
CREATE TABLE "branches" (
    "id" INTEGER PRIMARY KEY,
    "branch_code" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "address" TEXT NOT NULL,
    "postal_code" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "opened_at" TEXT NOT NULL
);

-- customers: One row per banking customer.
CREATE TABLE "customers" (
    "id" INTEGER PRIMARY KEY,
    "customer_number" TEXT NOT NULL UNIQUE,
    "full_name" TEXT NOT NULL,
    "national_id" TEXT NOT NULL UNIQUE,
    "birth_date" TEXT NOT NULL,
    "email" TEXT,
    "phone" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "province" TEXT NOT NULL CHECK ("province" IN ('A Coruña', 'Albacete', 'Alicante', 'Almería', 'Asturias', 'Badajoz', 'Baleares', 'Barcelona', 'Bizkaia', 'Burgos', 'Cantabria', 'Castellón', 'Ceuta', 'Ciudad Real', 'Cuenca', 'Cáceres', 'Cádiz', 'Córdoba', 'Gipuzkoa', 'Girona', 'Granada', 'Guadalajara', 'Huelva', 'Huesca', 'Jaén', 'La Rioja', 'Las Palmas', 'León', 'Lleida', 'Lugo', 'Madrid', 'Melilla', 'Murcia', 'Málaga', 'Navarra', 'Ourense', 'Palencia', 'Pontevedra', 'Salamanca', 'Santa Cruz de Tenerife', 'Segovia', 'Sevilla', 'Soria', 'Tarragona', 'Teruel', 'Toledo', 'Valencia', 'Valladolid', 'Zamora', 'Zaragoza', 'Álava', 'Ávila')),
    "postal_code" TEXT NOT NULL,
    "kyc_status" TEXT NOT NULL CHECK ("kyc_status" IN ('expired', 'pending', 'verified')),
    "risk_score" INTEGER NOT NULL,
    "annual_income" REAL,
    "customer_since" TEXT NOT NULL
);

-- accounts: One row per bank account.
CREATE TABLE "accounts" (
    "id" INTEGER PRIMARY KEY,
    "iban" TEXT NOT NULL UNIQUE,
    "customer_id" INTEGER NOT NULL,
    "branch_id" INTEGER NOT NULL,
    "account_type" TEXT NOT NULL CHECK ("account_type" IN ('business', 'checking', 'payroll', 'savings')),
    "currency" TEXT NOT NULL CHECK ("currency" IN ('EUR')),
    "balance" REAL NOT NULL,
    "overdraft_limit" REAL NOT NULL,
    "status" TEXT NOT NULL CHECK ("status" IN ('active', 'closed', 'dormant')),
    "opened_at" TEXT NOT NULL,
    FOREIGN KEY ("customer_id") REFERENCES "customers" ("id"),
    FOREIGN KEY ("branch_id") REFERENCES "branches" ("id")
);
CREATE INDEX "idx_accounts_customer_id" ON "accounts" ("customer_id");
CREATE INDEX "idx_accounts_branch_id" ON "accounts" ("branch_id");

-- cards: One row per payment card issued against one account.
CREATE TABLE "cards" (
    "id" INTEGER PRIMARY KEY,
    "account_id" INTEGER NOT NULL,
    "card_number_masked" TEXT NOT NULL,
    "card_number_last4" TEXT NOT NULL,
    "brand" TEXT NOT NULL CHECK ("brand" IN ('American Express', 'Mastercard', 'Visa')),
    "card_type" TEXT NOT NULL CHECK ("card_type" IN ('debit', 'credit', 'prepaid')),
    "expires_on" TEXT NOT NULL,
    "credit_limit" REAL,
    "status" TEXT NOT NULL CHECK ("status" IN ('active', 'blocked', 'cancelled', 'expired')),
    "issued_at" TEXT NOT NULL,
    FOREIGN KEY ("account_id") REFERENCES "accounts" ("id")
);
CREATE INDEX "idx_cards_account_id" ON "cards" ("account_id");

-- merchants: One row per business that accepts card payments.
CREATE TABLE "merchants" (
    "id" INTEGER PRIMARY KEY,
    "name" TEXT NOT NULL,
    "mcc" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "country" TEXT NOT NULL CHECK ("country" IN ('ES', 'FR', 'PT', 'IT', 'DE', 'GB'))
);

-- transactions: One row per movement on one account.
CREATE TABLE "transactions" (
    "id" INTEGER PRIMARY KEY,
    "account_id" INTEGER NOT NULL,
    "merchant_id" INTEGER,
    "type" TEXT NOT NULL CHECK ("type" IN ('atm_withdrawal', 'card_payment', 'direct_debit', 'fee', 'interest', 'salary', 'transfer_in', 'transfer_out')),
    "amount" REAL NOT NULL,
    "balance_after" REAL NOT NULL,
    "description" TEXT NOT NULL,
    "occurred_at" TEXT NOT NULL,
    "is_foreign" INTEGER NOT NULL,
    FOREIGN KEY ("account_id") REFERENCES "accounts" ("id"),
    FOREIGN KEY ("merchant_id") REFERENCES "merchants" ("id")
);
CREATE INDEX "idx_transactions_account_id" ON "transactions" ("account_id");
CREATE INDEX "idx_transactions_merchant_id" ON "transactions" ("merchant_id");

-- loans: One row per loan granted to one customer.
CREATE TABLE "loans" (
    "id" INTEGER PRIMARY KEY,
    "loan_number" TEXT NOT NULL UNIQUE,
    "customer_id" INTEGER NOT NULL,
    "loan_type" TEXT NOT NULL CHECK ("loan_type" IN ('auto', 'mortgage', 'personal', 'student')),
    "principal" REAL NOT NULL,
    "annual_rate" REAL NOT NULL,
    "term_months" INTEGER NOT NULL,
    "monthly_payment" REAL NOT NULL,
    "started_on" TEXT NOT NULL,
    "status" TEXT NOT NULL CHECK ("status" IN ('active', 'defaulted', 'paid_off')),
    FOREIGN KEY ("customer_id") REFERENCES "customers" ("id")
);
CREATE INDEX "idx_loans_customer_id" ON "loans" ("customer_id");

-- loan_payments: One row per scheduled instalment on one loan.
CREATE TABLE "loan_payments" (
    "id" INTEGER PRIMARY KEY,
    "loan_id" INTEGER NOT NULL,
    "instalment_number" INTEGER NOT NULL,
    "due_date" TEXT NOT NULL,
    "paid_date" TEXT,
    "payment_amount" REAL NOT NULL,
    "interest_amount" REAL NOT NULL,
    "principal_amount" REAL NOT NULL,
    "balance_after" REAL NOT NULL,
    FOREIGN KEY ("loan_id") REFERENCES "loans" ("id")
);
CREATE INDEX "idx_loan_payments_loan_id" ON "loan_payments" ("loan_id");

-- stock_prices: One row per ticker per trading day.
CREATE TABLE "stock_prices" (
    "id" INTEGER PRIMARY KEY,
    "ticker" TEXT NOT NULL,
    "company_name" TEXT NOT NULL,
    "trade_date" TEXT NOT NULL,
    "open_price" REAL NOT NULL,
    "high_price" REAL NOT NULL,
    "low_price" REAL NOT NULL,
    "close_price" REAL NOT NULL,
    "volume" INTEGER NOT NULL
);

-- exchange_rates: One row per currency pair per day.
CREATE TABLE "exchange_rates" (
    "id" INTEGER PRIMARY KEY,
    "base_currency" TEXT NOT NULL CHECK ("base_currency" IN ('EUR')),
    "quote_currency" TEXT NOT NULL CHECK ("quote_currency" IN ('USD', 'GBP', 'CHF', 'JPY', 'MXN')),
    "rate_date" TEXT NOT NULL,
    "rate" REAL NOT NULL
);
