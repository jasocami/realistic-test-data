"""
Topic: finance -- bank accounts, cards, transactions, loans, market data.
===============================================================================

WHAT IS THIS TOPIC FOR?
-----------------------
Anything money-shaped: a banking app, an expense tracker, a personal finance
dashboard, a fraud-detection experiment, a charting library. It is also the
topic with the most arithmetic that has to hold up, which makes it the best
test of whether a dataset was generated carefully or carelessly.

WHAT MAKES IT REALISTIC
-----------------------
1. **Running balances actually run.** Order an account's transactions by
   time and each `balance_after` is the previous one plus the amount. The
   account's own `balance` is the last of them. This is verified in CI.

2. **Loans really amortise.** Every loan uses the French system (constant
   monthly payment) that Spanish mortgages actually use. Walk the payment
   schedule and the outstanding balance reaches zero at the final
   instalment -- not approximately, exactly.

3. **The IBANs validate.** Spanish IBANs, 24 characters, passing the mod-97
   check. Your payment library will accept them.

4. **Market data obeys its own rules.** In every OHLC row the high is at
   least the open and the close, and the low is at most both. Prices follow
   a geometric random walk, so a chart of them looks like a chart of a
   stock rather than a chart of noise.

5. **Card numbers are safe AND valid.** They come from the published test
   ranges every payment processor recognises as non-live, and they still
   pass the Luhn check.

READ clinical.py FIRST -- it is the fully commented reference
implementation and this file follows the same three-part shape.
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from ..common.dates import add_months, add_years, age_on
from ..common.geography import PROVINCES, generate_address, phone_number
from ..common.identifiers import build_iban, dni, luhn_check_digit
from ..common.schema import Entity, Field, Topic
from ..common.seeds import Rng

# ===========================================================================
# PART 1 -- REFERENCE DATA
# ===========================================================================

DEFAULT_COUNTS = {
    "branches": 25,
    "customers": 800,
    "accounts": 1_100,
    "cards": 850,
    "merchants": 180,
    "loans": 280,
    "loan_payments": 3_000,
    "transactions": 6_000,
    "stock_prices": 3_000,
    "exchange_rates": 1_500,
}

PERIOD_START = date(2023, 1, 1)
PERIOD_END = date(2025, 6, 30)

#: The invented bank this data belongs to. Spanish retail banks are called
#: "Banco X" or "Caja Y"; both patterns appear here and neither names a real
#: institution.
BANK_NAME = "Banco Meridiano"

#: The four-digit bank code that opens every Spanish IBAN. Invented -- the
#: Bank of Spain has not allocated 9999 to anybody.
BANK_CODE = "9999"

ACCOUNT_TYPES = {"checking": 58, "savings": 28, "payroll": 10, "business": 4}

ACCOUNT_STATUSES = {"active": 88, "dormant": 8, "closed": 4}

CARD_BRANDS = {"Visa": 54, "Mastercard": 42, "American Express": 4}

#: Published test card prefixes. Every payment processor treats these as
#: non-live, so they can never move money -- while still passing Luhn, which
#: is what makes them usable for testing the happy path of a checkout form.
CARD_TEST_PREFIXES = {
    "Visa": ["411111", "400000", "424242"],
    "Mastercard": ["555555", "545454", "222100"],
    "American Express": ["378282", "371449"],
}

CARD_STATUSES = {"active": 84, "blocked": 6, "expired": 8, "cancelled": 2}

KYC_STATUSES = {"verified": 86, "pending": 9, "expired": 5}

#: Real Merchant Category Codes -- the ISO 18245 standard every card network
#: uses to classify what a business sells. Public nomenclature, not data
#: about anybody.
MERCHANT_CATEGORIES = [
    ("5411", "Grocery Stores, Supermarkets", 170),
    ("5812", "Eating Places, Restaurants", 140),
    ("5541", "Service Stations", 85),
    ("5814", "Fast Food Restaurants", 95),
    ("5912", "Drug Stores and Pharmacies", 60),
    ("5691", "Men's and Women's Clothing Stores", 55),
    ("4121", "Taxicabs and Limousines", 40),
    ("7011", "Hotels, Motels, Resorts", 30),
    ("5999", "Miscellaneous and Specialty Retail", 50),
    ("4900", "Utilities: Electric, Gas, Water", 45),
    ("5732", "Electronics Stores", 28),
    ("7832", "Motion Picture Theaters", 22),
    ("5921", "Package Stores, Beer, Wine, Liquor", 26),
    ("4814", "Telecommunication Services", 42),
    ("6011", "Automated Cash Disbursements", 55),
    ("8062", "Hospitals", 12),
    ("5499", "Miscellaneous Food Stores", 38),
    ("4111", "Local Commuter Transport", 35),
    ("7994", "Video Game Arcades", 10),
    ("5661", "Shoe Stores", 20),
    ("5942", "Book Stores", 15),
    ("7230", "Beauty and Barber Shops", 24),
    ("8011", "Doctors and Physicians", 14),
    ("5712", "Furniture and Home Furnishings", 16),
]

#: Invented merchant names, built the way Spanish high-street businesses are.
MERCHANT_STEMS = [
    "Casa", "El Rincón de", "La Tienda de", "Bar", "Restaurante",
    "Supermercado", "Farmacia", "Óptica", "Panadería", "Librería",
    "Cafetería", "Taller", "Peluquería", "Electro", "Muebles",
]
MERCHANT_TAILS = [
    "Central", "del Puerto", "San Marcos", "La Plaza", "del Carmen",
    "Real", "Nuevo", "Moderno", "del Sol", "La Esquina", "Gran Vía",
    "Los Arcos", "El Faro", "La Estrella", "Buenavista",
]

TRANSACTION_TYPES = {
    "card_payment": 47, "direct_debit": 14, "transfer_out": 11,
    "transfer_in": 9, "atm_withdrawal": 8, "salary": 5,
    "fee": 4, "interest": 2,
}

LOAN_TYPES = {"personal": 44, "auto": 26, "mortgage": 18, "student": 12}

LOAN_STATUSES = {"active": 72, "paid_off": 22, "defaulted": 6}

#: Invented ticker symbols for a fictional exchange. Deliberately not real
#: tickers, so nobody can mistake this for market history.
TICKERS = [
    ("MRDN", "Meridiano Industrial", 42.50),
    ("CALDR", "Caldera Energía", 18.20),
    ("VGRE", "Vega Renovables", 64.80),
    ("ARCD", "Arcadia Telecom", 9.75),
    ("PNFD", "Pinefield Logística", 27.40),
    ("STNB", "Stonebridge Seguros", 55.10),
    ("LKVW", "Lakeview Alimentación", 12.60),
    ("NRTH", "Northwind Farmacéutica", 88.30),
    ("BLHB", "Blue Harbour Naval", 31.90),
    ("OKVL", "Oakvale Construcción", 7.45),
]

#: Currency pairs quoted against the euro.
CURRENCY_PAIRS = [
    ("EUR", "USD", 1.085), ("EUR", "GBP", 0.855), ("EUR", "CHF", 0.955),
    ("EUR", "JPY", 163.20), ("EUR", "MXN", 18.65),
]


# ===========================================================================
# PART 2 -- THE SCHEMA
# ===========================================================================

BRANCHES = Entity(
    name="branches",
    topic="finance",
    grain="One row per physical bank branch.",
    description=(
        "The bank's offices. Every account is opened at a branch, so this is "
        "the table to join through for any question about regional "
        "performance or customer distribution."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Every "
                          "other table joins against this."),
        Field("branch_code", "string", unique=True, pattern=r"^\d{4}$", example="0142",
              description="Four-digit office code, the same one that appears "
                          "inside every IBAN opened at this branch. Spanish "
                          "account numbers really do encode the office."),
        Field("name", "string", example="Banco Meridiano Sevilla Centro",
              description="Branch name, combining the bank with the city and "
                          "the district it serves. Entirely invented."),
        Field("city", "string", example="Sevilla",
              description="Spanish city the branch operates in, drawn from "
                          "real municipalities weighted by population."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province the branch sits in, always consistent "
                          "with the first two digits of its postal code."),
        Field("address", "string", example="Avenida de la Constitución, 24",
              description="Street address in Spanish format, with the number "
                          "after the street name. Invented."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41004",
              description="Spanish postal code whose leading pair encodes the "
                          "province, so address validation passes on it."),
        Field("phone", "string", example="+34 954 22 18 90",
              description="Branch telephone, with a dialling prefix that "
                          "matches the province it is in."),
        Field("opened_at", "date", example="1998-06-15",
              description="Date the branch began trading, spread across the "
                          "four decades before the dataset period."),
    ],
)

CUSTOMERS = Entity(
    name="customers",
    topic="finance",
    grain="One row per banking customer.",
    description=(
        "Individuals who hold accounts. Accounts, cards and loans all point "
        "back here, so this is the table to start from when exploring the "
        "topic."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Use this "
                          "for joins rather than the national identifier."),
        Field("customer_number", "string", unique=True, pattern=r"^CLI-\d{7}$",
              example="CLI-0000042",
              description="The bank's own reference for this person, quoted on "
                          "correspondence and in the branch."),
        Field("full_name", "string", example="María Fernández Ruiz",
              description="Spanish name carrying both surnames, the father's "
                          "followed by the mother's. Worth testing any "
                          "name-parsing code against."),
        Field("national_id", "string", unique=True, pattern=r"^\d{8}[A-Z]$",
              example="12345678Z",
              description="Spanish DNI: eight digits and a check letter "
                          "derived modulo 23. Structurally valid, so it passes "
                          "a real DNI validator, but registered to nobody."),
        Field("birth_date", "date", example="1986-04-22",
              description="Date of birth. Customers are between 18 and 92, "
                          "following a realistic adult population shape rather "
                          "than a flat spread."),
        Field("email", "string", nullable=True, example="maria.fernandez@example.com",
              description="Contact address on the reserved example.com domain, "
                          "with accents transliterated. Empty for about 7% of "
                          "customers."),
        Field("phone", "string", example="+34 612 34 56 78",
              description="Mobile number in Spanish format. Banks require a "
                          "contact number for two-factor authentication, so "
                          "unlike email this column is never empty."),
        Field("city", "string", example="Sevilla",
              description="Spanish city of residence, usually but not always "
                          "the city of the branch where the account was "
                          "opened."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province of residence, consistent with the postal "
                          "code that follows it."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41009",
              description="Spanish postal code whose first two digits are the "
                          "province code, so the two columns always agree."),
        Field("kyc_status", "enum", values=sorted(KYC_STATUSES), example="verified",
              description="Know Your Customer verification state. Regulators "
                          "require banks to confirm identity; the 14% who are "
                          "pending or expired are the rows a compliance screen "
                          "should surface."),
        Field("risk_score", "integer", example=23,
              description="Internal credit and fraud risk rating from 1 to 100, "
                          "where higher is riskier. Correlates inversely with "
                          "income, so a scatter plot of the two slopes "
                          "downward."),
        Field("annual_income", "decimal", unit="EUR", nullable=True, example=31400.00,
              description="Declared gross annual income in euros, following a "
                          "lognormal distribution -- most customers cluster "
                          "near the median with a long tail above it, as real "
                          "incomes do. Empty for about 18% who never declared "
                          "one."),
        Field("customer_since", "date", example="2016-11-03",
              description="Date the relationship began, always on or before "
                          "the opening date of their earliest account."),
    ],
    notes=[
        "Income is lognormal rather than normal. Real income distributions "
        "have a long right tail -- a few people earn many times the median -- "
        "and a normal distribution cannot reproduce that shape.",
    ],
)

ACCOUNTS = Entity(
    name="accounts",
    topic="finance",
    grain="One row per bank account.",
    description=(
        "Current, savings, payroll and business accounts. Each belongs to one "
        "customer and was opened at one branch, and the balance shown here is "
        "exactly the closing balance of that account's transaction history."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("iban", "string", unique=True, pattern=r"^ES\d{22}$",
              example="ES9199990142001234567890",
              description="Spanish IBAN, 24 characters, passing the ISO 13616 "
                          "mod-97 check. It encodes the bank code, the branch "
                          "code, two domestic check digits and the account "
                          "number -- exactly as a real one does."),
        Field("customer_id", "integer", references="customers.id", example=42,
              description="Who owns the account. A customer may hold several, "
                          "which is why this column is not unique."),
        Field("branch_id", "integer", references="branches.id", example=7,
              description="Where the account was opened. Matches the office "
                          "code embedded in the IBAN, giving you a consistency "
                          "rule to verify."),
        Field("account_type", "enum", values=sorted(ACCOUNT_TYPES), example="checking",
              description="Product type. Checking accounts dominate and carry "
                          "nearly all the transaction activity; savings "
                          "accounts pay interest and move rarely."),
        Field("currency", "enum", values=["EUR"], example="EUR",
              description="Account currency. All accounts here are euro "
                          "denominated, which is what a Spanish retail bank "
                          "would offer; the exchange_rates table exists "
                          "separately for conversion work."),
        Field("balance", "decimal", unit="EUR", example=2418.77,
              description="Current balance in euros, and exactly the "
                          "balance_after of this account's most recent "
                          "transaction. Verified in CI, so the two can never "
                          "disagree."),
        Field("overdraft_limit", "decimal", unit="EUR", example=500.00,
              description="How far the account may go negative. Zero on "
                          "savings accounts, and a few hundred euros on "
                          "checking accounts depending on the customer's risk "
                          "score."),
        Field("status", "enum", values=sorted(ACCOUNT_STATUSES), example="active",
              description="Whether the account is in use. Dormant accounts "
                          "have had no movement for months and closed ones "
                          "none at all, so both are worth excluding from "
                          "activity reports."),
        Field("opened_at", "date", example="2018-03-12",
              description="Date the account was opened, always on or after the "
                          "customer's relationship start date and on or after "
                          "the branch opened."),
    ],
)

CARDS = Entity(
    name="cards",
    topic="finance",
    grain="One row per payment card issued against one account.",
    description=(
        "Debit and credit cards. Numbers come from the published test ranges "
        "that payment processors treat as non-live, so they cannot move money "
        "while still passing the Luhn check that a checkout form applies."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("account_id", "integer", references="accounts.id", example=42,
              description="The account this card draws on. One account may "
                          "have several cards, for instance a debit card and a "
                          "credit card."),
        Field("card_number_masked", "string", example="4111 11** **** 1111",
              description="The card number as an interface should display it, "
                          "with the middle digits hidden. Never store or show "
                          "a full number -- PCI DSS forbids it, and this "
                          "column is what a compliant UI renders."),
        Field("card_number_last4", "string", pattern=r"^\d{4}$", example="1111",
              description="Final four digits, the standard way to let somebody "
                          "identify which of their cards this is without "
                          "exposing the rest."),
        Field("brand", "enum", values=sorted(CARD_BRANDS), example="Visa",
              description="Card network. The brand determines the leading "
                          "digits: Visa always starts with 4, Mastercard with "
                          "5 or 2, American Express with 37."),
        Field("card_type", "enum", values=["debit", "credit", "prepaid"], example="debit"
              , description="Whether spending draws directly on the account, "
                            "on a credit line, or on a preloaded balance."),
        Field("expires_on", "date", example="2027-08-31",
              description="Expiry date, always the last day of a month because "
                          "that is how card expiry works. Cards whose date has "
                          "passed carry the status 'expired'."),
        Field("credit_limit", "decimal", unit="EUR", nullable=True, example=3000.00,
              description="Spending limit for credit cards, scaled to the "
                          "customer's declared income. Empty for debit cards, "
                          "which have no limit of their own."),
        Field("status", "enum", values=sorted(CARD_STATUSES), example="active",
              description="Current state of the card. Blocked cards were "
                          "reported lost or frozen for fraud; expired ones "
                          "simply ran out of time."),
        Field("issued_at", "date", example="2023-08-14",
              description="Date the card was issued, always on or after the "
                          "account was opened and roughly four years before it "
                          "expires."),
    ],
)

MERCHANTS = Entity(
    name="merchants",
    topic="finance",
    grain="One row per business that accepts card payments.",
    description=(
        "Where cardholders spend. Each merchant carries a real ISO 18245 "
        "Merchant Category Code, which is the standard every card network "
        "uses to classify what a business sells -- and what spending-analysis "
        "features categorise on."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("name", "string", example="Supermercado La Plaza",
              description="Trading name in Spanish, built from the patterns "
                          "real high-street businesses use. Entirely "
                          "invented."),
        Field("mcc", "string", pattern=r"^\d{4}$", example="5411",
              description="Merchant Category Code, a genuine four-digit ISO "
                          "18245 code. You can look any of them up and get the "
                          "same description as the next column."),
        Field("category", "string", example="Grocery Stores, Supermarkets",
              description="The official description of the MCC, stored "
                          "alongside so a reader can interpret a transaction "
                          "without a lookup table."),
        Field("city", "string", example="Sevilla",
              description="Spanish city the business trades in, so spending "
                          "can be mapped geographically."),
        Field("country", "enum", values=["ES", "FR", "PT", "IT", "DE", "GB"],
              example="ES",
              description="Country of the merchant. Most are Spanish, with a "
                          "minority abroad -- which is what makes foreign "
                          "transaction fees appear in the data."),
    ],
)

TRANSACTIONS = Entity(
    name="transactions",
    topic="finance",
    grain="One row per movement on one account.",
    description=(
        "The account ledger, and the largest table in the topic. Every row "
        "carries the balance immediately after it, and those balances form an "
        "unbroken running total per account."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1 and "
                          "ordered by time across the whole table."),
        Field("account_id", "integer", references="accounts.id", example=42,
              description="Which account moved. Ordering this table by account "
                          "and then by timestamp reconstructs a statement."),
        Field("merchant_id", "integer", nullable=True, references="merchants.id",
              example=17,
              description="Where the money went, for card payments. Empty for "
                          "transfers, salary, fees and interest, which have no "
                          "merchant -- about 48% of rows."),
        Field("type", "enum", values=sorted(TRANSACTION_TYPES), example="card_payment",
              description="What kind of movement this is. Card payments "
                          "dominate, as they do on a real current account, "
                          "with direct debits and transfers behind them."),
        Field("amount", "decimal", unit="EUR", example=-42.18,
              description="Value in euros, signed: negative for money leaving "
                          "the account and positive for money arriving. Adding "
                          "this to the previous balance gives balance_after "
                          "exactly."),
        Field("balance_after", "decimal", unit="EUR", example=2418.77,
              description="The account balance immediately after this movement "
                          "settled. Walking an account's transactions in time "
                          "order gives an unbroken running total -- asserted "
                          "in CI rather than assumed."),
        Field("description", "string", example="COMPRA SUPERMERCADO LA PLAZA",
              description="The narrative as it appears on a statement, in the "
                          "upper-case shorthand Spanish banks really print."),
        Field("occurred_at", "datetime", example="2025-03-14T18:42:00",
              description="When the movement was recorded. Card payments "
                          "cluster around lunchtime and the evening; salary "
                          "and direct debits land on predictable days of the "
                          "month."),
        Field("is_foreign", "boolean", example=False,
              description="Whether the merchant was outside Spain, which is "
                          "what triggers a currency-conversion fee in a real "
                          "account. True for about 9% of card payments."),
    ],
    notes=[
        "The running-balance invariant is the most valuable thing in this "
        "table. Order by account_id then occurred_at, and each balance_after "
        "equals the previous one plus the amount. Most generated banking data "
        "fails this, which makes it useless for testing a statement view.",
        "Salary credits land between the 25th and the last working day of the "
        "month, and direct debits in the first week -- the rhythm a real "
        "current account has.",
    ],
)

LOANS = Entity(
    name="loans",
    topic="finance",
    grain="One row per loan granted to one customer.",
    description=(
        "Personal loans, car finance, mortgages and student loans. Every loan "
        "uses the French amortisation system -- a constant monthly payment -- "
        "which is what Spanish lenders actually use."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("loan_number", "string", unique=True, pattern=r"^PRE-\d{7}$",
              example="PRE-0000042",
              description="The lender's reference for this loan, quoted on "
                          "statements and correspondence."),
        Field("customer_id", "integer", references="customers.id", example=42,
              description="Who borrowed the money. A customer may hold more "
                          "than one loan at a time."),
        Field("loan_type", "enum", values=sorted(LOAN_TYPES), example="personal",
              description="What the loan is for. Type drives everything else: "
                          "mortgages are large, long and cheap, personal loans "
                          "small, short and expensive."),
        Field("principal", "decimal", unit="EUR", example=12000.00,
              description="Amount originally borrowed in euros. Ranges from a "
                          "few thousand for a personal loan to several hundred "
                          "thousand for a mortgage."),
        Field("annual_rate", "decimal", unit="percent", example=6.45,
              description="Nominal annual interest rate. Mortgages sit near "
                          "3%, car finance around 7%, and personal loans "
                          "closer to 10% -- the real spread between secured "
                          "and unsecured lending."),
        Field("term_months", "integer", unit="months", example=48,
              description="Length of the loan in monthly instalments, from 12 "
                          "for a small personal loan to 360 for a thirty-year "
                          "mortgage."),
        Field("monthly_payment", "decimal", unit="EUR", example=284.52,
              description="The constant instalment under the French system, "
                          "computed from principal, rate and term. Walk the "
                          "schedule with this figure and the balance reaches "
                          "exactly zero."),
        Field("started_on", "date", example="2023-05-01",
              description="Date of the first instalment. Always on or after "
                          "the customer joined the bank."),
        Field("status", "enum", values=sorted(LOAN_STATUSES), example="active",
              description="Where the loan stands. Paid-off loans have their "
                          "full schedule recorded; defaulted ones stop part "
                          "way through, which is what makes them worth having."),
    ],
)

LOAN_PAYMENTS = Entity(
    name="loan_payments",
    topic="finance",
    grain="One row per scheduled instalment on one loan.",
    description=(
        "The amortisation schedule. Each row splits one payment into the part "
        "that covers interest and the part that reduces the debt, and carries "
        "the balance left afterwards."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("loan_id", "integer", references="loans.id", example=1,
              description="Which loan this instalment belongs to. Grouping by "
                          "this column and ordering by instalment number gives "
                          "the full schedule."),
        Field("instalment_number", "integer", example=1,
              description="Position in the schedule, from 1 up to the loan's "
                          "term_months. Together with loan_id this uniquely "
                          "identifies a payment."),
        Field("due_date", "date", example="2023-06-01",
              description="When the instalment was due, always the first of a "
                          "month and exactly one month after the previous "
                          "one."),
        Field("paid_date", "date", nullable=True, example="2023-06-01",
              description="When it was actually paid. Around 11% are a few "
                          "days late, and instalments that were never paid are "
                          "empty -- which is what a defaulted loan looks like."),
        Field("payment_amount", "decimal", unit="EUR", example=284.52,
              description="Total instalment, the same constant figure every "
                          "month, equal to interest_amount plus "
                          "principal_amount."),
        Field("interest_amount", "decimal", unit="EUR", example=64.50,
              description="Portion covering interest, calculated on the "
                          "outstanding balance. It shrinks every month as the "
                          "debt falls -- the defining shape of amortisation."),
        Field("principal_amount", "decimal", unit="EUR", example=220.02,
              description="Portion reducing the debt. It grows every month, "
                          "mirroring the falling interest, so the two always "
                          "sum to the same payment."),
        Field("balance_after", "decimal", unit="EUR", example=11779.98,
              description="Outstanding debt after this instalment. Reaches "
                          "exactly zero at the final payment of a fully "
                          "amortised loan, which CI verifies."),
    ],
    notes=[
        "This table is a ready-made exercise: recompute the schedule yourself "
        "from the loan's principal, rate and term, and check you get the same "
        "numbers. The final balance should be 0.00, not 0.03.",
    ],
)

STOCK_PRICES = Entity(
    name="stock_prices",
    topic="finance",
    grain="One row per ticker per trading day.",
    description=(
        "Daily open-high-low-close price history for ten fictional listed "
        "companies. Prices follow a geometric random walk, so a chart of them "
        "has the texture of a real price series rather than of noise."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("ticker", "string", example="MRDN",
              description="Exchange symbol for the company. All ten are "
                          "invented, deliberately, so this cannot be mistaken "
                          "for real market history."),
        Field("company_name", "string", example="Meridiano Industrial",
              description="Full company name behind the ticker, stored "
                          "alongside so the series is readable without a "
                          "lookup."),
        Field("trade_date", "date", example="2025-03-14",
              description="The trading day. Weekends are excluded, because "
                          "exchanges do not open on them -- which is exactly "
                          "the gap a naive date axis gets wrong."),
        Field("open_price", "decimal", unit="EUR", example=42.50,
              description="Price at the opening bell, always the previous "
                          "close plus a small overnight gap."),
        Field("high_price", "decimal", unit="EUR", example=43.18,
              description="Highest price traded that day. Always greater than "
                          "or equal to both the open and the close -- a rule "
                          "that holds in every row and is asserted in CI."),
        Field("low_price", "decimal", unit="EUR", example=42.01,
              description="Lowest price traded that day. Always less than or "
                          "equal to both the open and the close."),
        Field("close_price", "decimal", unit="EUR", example=42.94,
              description="Price at the closing bell, and the basis for the "
                          "next day's open. This is the column to chart."),
        Field("volume", "integer", unit="shares", example=482_150,
              description="Shares traded that day. Spikes on days with large "
                          "price moves, because volume and volatility really "
                          "do go together."),
    ],
    notes=[
        "The OHLC relationship holds in every row: high >= max(open, close) "
        "and low <= min(open, close). Charting libraries that draw "
        "candlesticks rely on it, and data that breaks it renders as visual "
        "nonsense.",
    ],
)

EXCHANGE_RATES = Entity(
    name="exchange_rates",
    topic="finance",
    grain="One row per currency pair per day.",
    description=(
        "Daily reference rates quoted against the euro. Useful for testing "
        "currency conversion, and for joining against foreign transactions to "
        "work out what they cost in euros."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("base_currency", "enum", values=["EUR"], example="EUR",
              description="The currency being priced, always the euro here, "
                          "matching how the European Central Bank publishes "
                          "its own reference rates."),
        Field("quote_currency", "enum", values=["USD", "GBP", "CHF", "JPY", "MXN"],
              example="USD",
              description="The currency it is priced in. Five pairs are "
                          "covered, spanning very different orders of "
                          "magnitude so that formatting code gets a proper "
                          "workout."),
        Field("rate_date", "date", example="2025-03-14",
              description="The day the rate applies to. Weekends are excluded, "
                          "since currency markets publish no reference rate "
                          "then."),
        Field("rate", "decimal", unit="quote per base", example=1.0852,
              description="How many units of the quote currency one euro buys. "
                          "Moves as a slow random walk around a realistic "
                          "central value for each pair."),
    ],
)


# ===========================================================================
# PART 3 -- THE GENERATOR
# ===========================================================================

def _strip_accents(text: str) -> str:
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _email_from_name(full_name: str, domain: str, rng: Rng) -> str:
    parts = [part.lower() for part in _strip_accents(full_name).split() if part]
    stem = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
    suffix = "" if rng.python.random() > 0.08 else str(rng.python.randint(2, 9))
    return f"{stem}{suffix}@{domain}"


def _spanish_iban(rng: Rng, branch_code: str, account_number: str) -> str:
    """Build a valid Spanish IBAN.

    A Spanish BBAN is twenty digits:

        9999   0142   21   1234567890
        ^^^^   ^^^^   ^^   ^^^^^^^^^^
        bank   branch  |   account number
                       two domestic check digits

    Spain has its own two-digit check ON TOP of the IBAN's mod-97 check, a
    holdover from the pre-IBAN CCC format. We generate plausible digits for
    it and let the IBAN checksum carry the real validation -- documented
    here so nobody assumes the domestic check is also correct.
    """
    domestic_check = f"{rng.python.randint(0, 99):02d}"
    bban = f"{BANK_CODE}{branch_code}{domestic_check}{account_number}"
    return build_iban("ES", bban)


def _generate_branches(count: int) -> list[dict[str, Any]]:
    rng = Rng("finance", "branches")

    districts = ["Centro", "Norte", "Sur", "Este", "Oeste", "Ensanche",
                 "Casco Antiguo", "Nuevos Ministerios", "La Alameda", "Puerto"]

    rows = []
    used_codes: set[str] = set()
    for index in range(1, count + 1):
        location = generate_address(rng, with_phone=True)

        code = f"{rng.python.randint(1, 9999):04d}"
        while code in used_codes:
            code = f"{rng.python.randint(1, 9999):04d}"
        used_codes.add(code)

        rows.append({
            "id": index,
            "branch_code": code,
            "name": f"{BANK_NAME} {location['city']} {rng.python.choice(districts)}",
            "city": location["city"],
            "province": location["province"],
            "address": location["address"],
            "postal_code": location["postal_code"],
            "phone": location["phone"],
            "opened_at": rng.date_between(date(1985, 1, 1), date(2020, 12, 31)),
        })
    return rows


def _generate_customers(count: int) -> list[dict[str, Any]]:
    rng = Rng("finance", "customers")

    rows = []
    for index in range(1, count + 1):
        is_female = rng.python.random() < 0.51
        full_name = rng.faker.name_female() if is_female else rng.faker.name_male()
        location = generate_address(rng, with_phone=True, mobile=True)

        age = int(min(92, max(18, rng.numpy.normal(46, 16))))
        birth_date = date(PERIOD_END.year - age, 1, 1) + timedelta(
            days=rng.python.randint(0, 364)
        )

        # Income is lognormal: most people near the median, a long tail above.
        # A normal distribution cannot produce that shape and looks wrong the
        # moment anyone plots a histogram.
        income = float(rng.numpy.lognormal(mean=10.15, sigma=0.52))
        income = round(min(320_000.0, max(9_000.0, income)), 2)

        # Risk falls as income rises, with plenty of noise.
        risk = int(min(100, max(1, rng.numpy.normal(
            60 - 30 * (income / 60_000), 18
        ))))

        rows.append({
            "id": index,
            "customer_number": f"CLI-{index:07d}",
            "full_name": full_name,
            "national_id": dni(rng),
            "birth_date": birth_date,
            "email": rng.maybe_null(_email_from_name(full_name, "example.com", rng), 0.07),
            "phone": location["phone"],
            "city": location["city"],
            "province": location["province"],
            "postal_code": location["postal_code"],
            "kyc_status": rng.weighted_choice(KYC_STATUSES),
            "risk_score": risk,
            "annual_income": rng.maybe_null(income, 0.18),
            "customer_since": rng.date_between(date(2005, 1, 1), date(2024, 12, 31)),
        })
    return rows


def _generate_accounts(
    customers: list[dict], branches: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("finance", "accounts")

    rows = []
    used_ibans: set[str] = set()
    for index in range(1, count + 1):
        customer = rng.python.choice(customers)
        branch = rng.python.choice(branches)
        account_type = rng.weighted_choice(ACCOUNT_TYPES)

        while True:
            iban = _spanish_iban(rng, branch["branch_code"],
                                 f"{rng.python.randint(0, 9_999_999_999):010d}")
            if iban not in used_ibans:
                used_ibans.add(iban)
                break

        # An account cannot predate the customer or the branch.
        earliest = max(customer["customer_since"], branch["opened_at"], date(2005, 1, 1))
        opened_at = rng.date_between(earliest, date(2025, 3, 31))

        # Only checking accounts get an overdraft, and only lower-risk
        # customers get a meaningful one.
        if account_type in ("checking", "payroll") and customer["risk_score"] < 60:
            overdraft = Decimal(rng.python.choice([0, 200, 500, 1000, 1500]))
        else:
            overdraft = Decimal(0)

        rows.append({
            "id": index,
            "iban": iban,
            "customer_id": customer["id"],
            "branch_id": branch["id"],
            "account_type": account_type,
            "currency": "EUR",
            # Filled in once the transactions have been generated.
            "balance": Decimal("0.00"),
            "overdraft_limit": overdraft.quantize(Decimal("0.01")),
            "status": rng.weighted_choice(ACCOUNT_STATUSES),
            "opened_at": opened_at,
        })
    return rows


def _generate_cards(
    accounts: list[dict], customers: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("finance", "cards")

    income_by_customer = {row["id"]: row["annual_income"] for row in customers}
    eligible = [row for row in accounts if row["status"] != "closed"] or accounts

    rows = []
    for index in range(1, count + 1):
        account = rng.python.choice(eligible)
        brand = rng.weighted_choice(CARD_BRANDS)
        prefix = rng.python.choice(CARD_TEST_PREFIXES[brand])

        # American Express numbers are 15 digits; the others are 16.
        length = 15 if brand == "American Express" else 16
        body = prefix + "".join(
            str(rng.python.randint(0, 9)) for _ in range(length - len(prefix) - 1)
        )
        full_number = body + luhn_check_digit(body)

        card_type = rng.weighted_choice({"debit": 62, "credit": 34, "prepaid": 4})

        issued_at = rng.date_between(
            max(account["opened_at"], date(2020, 1, 1)), date(2025, 5, 31)
        )
        # Cards expire on the last day of a month, about four years out.
        expiry_month = add_years(issued_at, 4)
        expires_on = add_months(expiry_month.replace(day=1), 1) - timedelta(days=1)

        if card_type == "credit":
            income = income_by_customer.get(account["customer_id"]) or 25_000
            limit = Decimal(str(round(min(20_000, max(600, income * 0.15)), 2)))
        else:
            limit = None

        status = "expired" if expires_on < PERIOD_END else rng.weighted_choice(
            {"active": 90, "blocked": 7, "cancelled": 3}
        )

        rows.append({
            "id": index,
            "account_id": account["id"],
            "card_number_masked": f"{full_number[:6]} {'*' * 2} {'*' * 4} {full_number[-4:]}",
            "card_number_last4": full_number[-4:],
            "brand": brand,
            "card_type": card_type,
            "expires_on": expires_on,
            "credit_limit": limit,
            "status": status,
            "issued_at": issued_at,
        })
    return rows


def _generate_merchants(count: int) -> list[dict[str, Any]]:
    rng = Rng("finance", "merchants")

    codes = [entry[0] for entry in MERCHANT_CATEGORIES]
    descriptions = {entry[0]: entry[1] for entry in MERCHANT_CATEGORIES}
    weights = [entry[2] for entry in MERCHANT_CATEGORIES]

    rows = []
    for index in range(1, count + 1):
        mcc = rng.python.choices(codes, weights=weights, k=1)[0]
        location = generate_address(rng)

        rows.append({
            "id": index,
            "name": f"{rng.python.choice(MERCHANT_STEMS)} {rng.python.choice(MERCHANT_TAILS)}",
            "mcc": mcc,
            "category": descriptions[mcc],
            "city": location["city"],
            "country": rng.weighted_choice(
                {"ES": 88, "FR": 3, "PT": 3, "IT": 2, "DE": 2, "GB": 2}
            ),
        })
    return rows


def _generate_transactions(
    accounts: list[dict], merchants: list[dict], count: int
) -> list[dict[str, Any]]:
    """Generate the ledger, keeping a true running balance per account.

    THE POINT OF THIS FUNCTION: `balance_after` must be the previous balance
    plus the amount, for every row, for every account. That means the
    transactions for an account have to be generated in time order and the
    balance carried forward -- which is why this cannot be a simple
    row-at-a-time loop over random accounts.
    """
    rng = Rng("finance", "transactions")

    active = [row for row in accounts if row["status"] != "closed"] or accounts

    # Share the transaction budget out, weighted so that checking accounts
    # carry most of the activity and savings accounts barely move.
    activity = {"checking": 1.0, "payroll": 0.85, "business": 1.4, "savings": 0.12}
    weights = [activity[row["account_type"]] for row in active]
    total_weight = sum(weights)
    per_account = [max(1, int(count * weight / total_weight)) for weight in weights]

    merchant_ids = [row["id"] for row in merchants]
    foreign_merchants = {row["id"] for row in merchants if row["country"] != "ES"}

    rows: list[dict[str, Any]] = []

    for account, how_many in zip(active, per_account):
        # Opening balance when the account was funded.
        balance = Decimal(str(round(abs(rng.numpy.normal(1800, 1400)) + 120, 2)))

        start = max(account["opened_at"], PERIOD_START)
        if start >= PERIOD_END:
            start = PERIOD_END - timedelta(days=30)

        # Decide WHEN and WHAT first, apply the day-of-month rules, and only
        # then sort. Getting this order wrong is subtle and costly: salary
        # credits are moved to the end of the month, so if the dates were
        # sorted before that adjustment the running balance would be built in
        # a different order than the timestamps imply, and every statement
        # view over this data would disagree with itself.
        planned: list[tuple[datetime, str]] = []
        for _ in range(how_many):
            occurred_on = rng.date_between(start, PERIOD_END)
            transaction_type = rng.weighted_choice(TRANSACTION_TYPES)

            if transaction_type == "salary":
                # Payroll lands between the 25th and the 28th.
                occurred_on = occurred_on.replace(day=rng.python.randint(25, 28))
            elif transaction_type == "direct_debit":
                # Standing orders are collected in the first week.
                occurred_on = occurred_on.replace(day=rng.python.randint(1, 7))

            # The adjustment can push a date outside the account's window.
            if occurred_on < start or occurred_on > PERIOD_END:
                continue

            # The TIME has to be decided here, not inside the balance walk
            # below. Sorting by date alone would leave same-day movements in
            # a random order relative to their timestamps, and the running
            # balance would disagree with any statement sorted by time.
            hour = rng.weighted_choice(
                {8: 4, 9: 7, 10: 8, 11: 9, 12: 11, 13: 12, 14: 8, 15: 6,
                 16: 7, 17: 8, 18: 10, 19: 9, 20: 7, 21: 4}
            )
            planned.append((
                datetime.combine(occurred_on, time(hour, rng.python.randint(0, 59))),
                transaction_type,
            ))

        # Sort by the full timestamp, so the balance walk below follows
        # exactly the order a statement would display.
        planned.sort(key=lambda entry: entry[0])

        for occurred_at, transaction_type in planned:
            occurred_on = occurred_at.date()
            merchant_id = None
            is_foreign = False

            if transaction_type == "card_payment":
                merchant_id = rng.python.choice(merchant_ids)
                is_foreign = merchant_id in foreign_merchants
                # Everyday spending is small; occasional purchases are not.
                amount = -Decimal(str(round(
                    float(rng.numpy.lognormal(mean=2.9, sigma=1.0)), 2
                )))
            elif transaction_type == "atm_withdrawal":
                amount = -Decimal(rng.python.choice([20, 40, 50, 60, 100, 150, 200]))
            elif transaction_type == "direct_debit":
                amount = -Decimal(str(round(
                    float(rng.numpy.lognormal(mean=3.6, sigma=0.7)), 2
                )))
            elif transaction_type == "salary":
                amount = Decimal(str(round(
                    float(rng.numpy.normal(1950, 620)), 2
                )))
                amount = max(Decimal("650.00"), amount)
            elif transaction_type == "transfer_in":
                amount = Decimal(str(round(abs(rng.numpy.normal(420, 380)) + 10, 2)))
            elif transaction_type == "transfer_out":
                amount = -Decimal(str(round(abs(rng.numpy.normal(380, 340)) + 10, 2)))
            elif transaction_type == "fee":
                amount = -Decimal(rng.python.choice(["2.50", "3.00", "4.50", "12.00"]))
            else:  # interest
                amount = Decimal(str(round(abs(rng.numpy.normal(3.2, 2.6)) + 0.05, 2)))

            # Respect the overdraft limit: an account cannot be taken below
            # it, so a payment that would breach it is simply skipped, the
            # way a real bank would decline it.
            if balance + amount < -Decimal(str(account["overdraft_limit"])):
                continue

            balance = (balance + amount).quantize(Decimal("0.01"))

            if merchant_id is not None:
                merchant = merchants[merchant_id - 1]
                description = f"COMPRA {merchant['name'].upper()}"
            else:
                description = {
                    "direct_debit": "RECIBO DOMICILIADO",
                    "transfer_out": "TRANSFERENCIA EMITIDA",
                    "transfer_in": "TRANSFERENCIA RECIBIDA",
                    "atm_withdrawal": "REINTEGRO CAJERO",
                    "salary": "NOMINA",
                    "fee": "COMISION MANTENIMIENTO",
                    "interest": "ABONO INTERESES",
                }[transaction_type]

            rows.append({
                "id": 0,  # assigned after the global sort
                "account_id": account["id"],
                "merchant_id": merchant_id,
                "type": transaction_type,
                "amount": amount,
                "balance_after": balance,
                "description": description,
                "occurred_at": occurred_at,
                "is_foreign": is_foreign,
            })

        # The account's stated balance is its final ledger balance.
        account["balance"] = balance

    # Sort globally by time, but keep each account's internal order intact --
    # which a stable sort on the timestamp alone does not guarantee when two
    # movements share a second, so the account and the original position are
    # part of the key.
    rows.sort(key=lambda row: (row["occurred_at"], row["account_id"]))
    for new_id, row in enumerate(rows, start=1):
        row["id"] = new_id
    return rows


def _generate_loans(customers: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("finance", "loans")

    # (principal range, rate range, term choices) by loan type. These spreads
    # are what make the table informative: a mortgage and a personal loan
    # differ in every dimension, not just in size.
    parameters = {
        "personal": ((2_000, 30_000), (7.5, 12.5), [12, 24, 36, 48, 60]),
        "auto": ((6_000, 45_000), (5.5, 9.0), [36, 48, 60, 72, 84]),
        "mortgage": ((60_000, 420_000), (2.4, 4.6), [180, 240, 300, 360]),
        "student": ((3_000, 25_000), (3.5, 6.5), [36, 60, 84, 120]),
    }

    rows = []
    for index in range(1, count + 1):
        customer = rng.python.choice(customers)
        loan_type = rng.weighted_choice(LOAN_TYPES)
        (low, high), (rate_low, rate_high), terms = parameters[loan_type]

        principal = Decimal(str(round(rng.python.uniform(low, high), -2)))
        annual_rate = Decimal(str(round(rng.python.uniform(rate_low, rate_high), 2)))
        term_months = rng.python.choice(terms)

        # The French amortisation system: a constant monthly payment, which
        # is what Spanish lenders use.
        #
        #              P * i
        #   payment = ---------------
        #             1 - (1 + i)^-n
        #
        # where i is the MONTHLY rate and n the number of instalments.
        monthly_rate = annual_rate / Decimal(1200)
        factor = (Decimal(1) + monthly_rate) ** term_months
        monthly_payment = (
            principal * monthly_rate * factor / (factor - Decimal(1))
        ).quantize(Decimal("0.01"))

        started_on = rng.date_between(
            max(customer["customer_since"], date(2019, 1, 1)), date(2025, 3, 1)
        ).replace(day=1)

        rows.append({
            "id": index,
            "loan_number": f"PRE-{index:07d}",
            "customer_id": customer["id"],
            "loan_type": loan_type,
            "principal": principal,
            "annual_rate": annual_rate,
            "term_months": term_months,
            "monthly_payment": monthly_payment,
            "started_on": started_on,
            "status": rng.weighted_choice(LOAN_STATUSES),
        })
    return rows


def _generate_loan_payments(loans: list[dict], count: int) -> list[dict[str, Any]]:
    """Walk each loan's amortisation schedule.

    The final instalment is adjusted so the balance lands on exactly 0.00.
    Real lenders do this too -- rounding each month to the cent leaves a few
    cents outstanding, and the last payment absorbs them.
    """
    rng = Rng("finance", "loan_payments")

    rows: list[dict[str, Any]] = []

    for loan in loans:
        principal = Decimal(str(loan["principal"]))
        monthly_rate = Decimal(str(loan["annual_rate"])) / Decimal(1200)
        payment = Decimal(str(loan["monthly_payment"]))
        term = int(loan["term_months"])

        # A defaulted loan stops part way through; an active one has only
        # reached the instalments that have fallen due so far.
        if loan["status"] == "defaulted":
            instalments = rng.python.randint(3, max(4, term // 2))
        elif loan["status"] == "active":
            elapsed = (PERIOD_END.year - loan["started_on"].year) * 12 + (
                PERIOD_END.month - loan["started_on"].month
            )
            instalments = max(1, min(term, elapsed))
        else:  # paid_off
            instalments = term

        balance = principal

        for number in range(1, instalments + 1):
            interest = (balance * monthly_rate).quantize(Decimal("0.01"))

            if number == term:
                # Final instalment clears whatever is left, to the cent.
                principal_part = balance
                this_payment = (principal_part + interest).quantize(Decimal("0.01"))
            else:
                principal_part = (payment - interest).quantize(Decimal("0.01"))
                this_payment = payment

            balance = (balance - principal_part).quantize(Decimal("0.01"))
            due_date = add_months(loan["started_on"], number)

            # Most people pay on time; some are a few days late; a defaulted
            # loan's last instalments were never paid at all.
            if loan["status"] == "defaulted" and number > instalments - 3:
                paid_date = None
            elif rng.python.random() < 0.11:
                paid_date = due_date + timedelta(days=rng.python.randint(1, 12))
            else:
                paid_date = due_date

            rows.append({
                "id": len(rows) + 1,
                "loan_id": loan["id"],
                "instalment_number": number,
                "due_date": due_date,
                "paid_date": paid_date,
                "payment_amount": this_payment,
                "interest_amount": interest,
                "principal_amount": principal_part,
                "balance_after": balance,
            })

            if len(rows) >= count:
                return rows

    return rows


def _generate_stock_prices(count: int) -> list[dict[str, Any]]:
    """A geometric random walk per ticker.

    WHY GEOMETRIC: share prices move in percentage terms, not in absolute
    ones -- a 1 euro move matters far more to a 7 euro stock than to an 88
    euro one. Adding a fixed-size random step each day produces a series that
    looks visibly wrong to anyone who has seen a price chart.
    """
    rng = Rng("finance", "stock_prices")

    days_per_ticker = max(1, count // len(TICKERS))

    rows: list[dict[str, Any]] = []
    for ticker, company, start_price in TICKERS:
        price = Decimal(str(start_price))
        # Each company gets its own drift and volatility, so they do not all
        # move in lockstep.
        drift = rng.python.uniform(-0.0004, 0.0007)
        volatility = rng.python.uniform(0.010, 0.026)

        trade_date = PERIOD_END - timedelta(days=int(days_per_ticker * 1.45))

        for _ in range(days_per_ticker):
            # Skip weekends -- exchanges are shut.
            while trade_date.weekday() >= 5:
                trade_date += timedelta(days=1)

            previous_close = price
            daily_return = rng.numpy.normal(drift, volatility)
            close = previous_close * Decimal(str(round(1 + daily_return, 6)))
            close = max(Decimal("0.50"), close).quantize(Decimal("0.01"))

            # Overnight gap, then an intraday range that must CONTAIN both
            # the open and the close -- which is why high and low are derived
            # from them rather than drawn independently.
            open_price = (
                previous_close * Decimal(str(round(1 + rng.numpy.normal(0, volatility / 3), 6)))
            ).quantize(Decimal("0.01"))
            open_price = max(Decimal("0.50"), open_price)

            span = abs(float(close - open_price)) + float(close) * abs(
                rng.numpy.normal(0, volatility / 2)
            )
            high = (max(open_price, close) + Decimal(str(round(span * rng.python.random(), 2)))
                    ).quantize(Decimal("0.01"))
            low = (min(open_price, close) - Decimal(str(round(span * rng.python.random(), 2)))
                   ).quantize(Decimal("0.01"))
            low = max(Decimal("0.01"), low)

            # Volume rises with volatility: big moves bring big turnover.
            base_volume = 180_000 + abs(daily_return) * 9_000_000
            volume = int(max(1_000, rng.numpy.normal(base_volume, base_volume * 0.3)))

            rows.append({
                "id": len(rows) + 1,
                "ticker": ticker,
                "company_name": company,
                "trade_date": trade_date,
                "open_price": open_price,
                "high_price": high,
                "low_price": low,
                "close_price": close,
                "volume": volume,
            })

            price = close
            trade_date += timedelta(days=1)

    rows.sort(key=lambda row: (row["trade_date"], row["ticker"]))
    for new_id, row in enumerate(rows, start=1):
        row["id"] = new_id
    return rows


def _generate_exchange_rates(count: int) -> list[dict[str, Any]]:
    rng = Rng("finance", "exchange_rates")

    days_per_pair = max(1, count // len(CURRENCY_PAIRS))

    rows: list[dict[str, Any]] = []
    for base, quote, central in CURRENCY_PAIRS:
        rate = central
        rate_date = PERIOD_END - timedelta(days=int(days_per_pair * 1.45))

        for _ in range(days_per_pair):
            while rate_date.weekday() >= 5:
                rate_date += timedelta(days=1)

            # Mean-reverting walk: rates wander but are pulled back toward a
            # central value, which is how currency pairs actually behave over
            # a couple of years.
            pull = (central - rate) * 0.02
            rate = rate + pull + rng.numpy.normal(0, central * 0.004)

            # JPY is quoted to two decimals, everything else to four.
            places = Decimal("0.01") if quote == "JPY" else Decimal("0.0001")

            rows.append({
                "id": len(rows) + 1,
                "base_currency": base,
                "quote_currency": quote,
                "rate_date": rate_date,
                "rate": Decimal(str(rate)).quantize(places),
            })
            rate_date += timedelta(days=1)

    rows.sort(key=lambda row: (row["rate_date"], row["quote_currency"]))
    for new_id, row in enumerate(rows, start=1):
        row["id"] = new_id
    return rows


def generate(scale: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    """Produce every table in the finance topic."""
    counts = {name: max(1, int(number * scale)) for name, number in DEFAULT_COUNTS.items()}

    branches = _generate_branches(counts["branches"])
    customers = _generate_customers(counts["customers"])
    accounts = _generate_accounts(customers, branches, counts["accounts"])
    cards = _generate_cards(accounts, customers, counts["cards"])
    merchants = _generate_merchants(counts["merchants"])
    # This step also sets each account's closing balance.
    transactions = _generate_transactions(accounts, merchants, counts["transactions"])
    loans = _generate_loans(customers, counts["loans"])
    loan_payments = _generate_loan_payments(loans, counts["loan_payments"])
    stock_prices = _generate_stock_prices(counts["stock_prices"])
    exchange_rates = _generate_exchange_rates(counts["exchange_rates"])

    return {
        "branches": branches,
        "customers": customers,
        "accounts": accounts,
        "cards": cards,
        "merchants": merchants,
        "transactions": transactions,
        "loans": loans,
        "loan_payments": loan_payments,
        "stock_prices": stock_prices,
        "exchange_rates": exchange_rates,
    }


TOPIC = Topic(
    name="finance",
    title="Finance / Banking",
    summary=(
        "Spanish bank accounts with valid IBANs, cards, a ledger with true "
        "running balances, loans that really amortise, and daily market data."
    ),
    description=(
        "A Spanish retail bank: branches, customers, accounts, cards and two "
        "and a half years of ledger movements, plus loans with full "
        "amortisation schedules and daily price history for ten fictional "
        "listed companies.\n\n"
        "This is the topic where the arithmetic has to hold up, and it does. "
        "Running balances are genuinely running -- order an account's "
        "transactions by time and each balance_after is the previous one plus "
        "the amount. Loan schedules amortise to exactly zero. Every IBAN "
        "passes the mod-97 check and every card number passes Luhn while "
        "coming from a published non-live test range.\n\n"
        "Market data follows a geometric random walk with the open-high-low-"
        "close relationship intact in every row, so candlestick charts render "
        "correctly rather than as visual nonsense."
    ),
    entities=[
        BRANCHES,
        CUSTOMERS,
        ACCOUNTS,
        CARDS,
        MERCHANTS,
        TRANSACTIONS,
        LOANS,
        LOAN_PAYMENTS,
        STOCK_PRICES,
        EXCHANGE_RATES,
    ],
)
