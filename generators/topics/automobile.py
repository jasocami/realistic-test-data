"""
Topic: automobile -- vehicles, owners, dealerships, service and ITV history.
===============================================================================

WHAT IS THIS TOPIC FOR?
-----------------------
Fleet management, a dealership CRM, a used-car marketplace, a workshop
booking system, or anything that has to parse a VIN or a registration plate.
It is also the topic with the longest per-entity histories: a vehicle
accumulates owners, services and inspections over years, which makes it the
best one for testing timeline and audit-trail features.

WHAT MAKES IT REALISTIC
-----------------------
1. **The VINs pass their checksum.** Seventeen characters with a correct
   check digit at position 9, no I/O/Q, and a model-year letter that matches
   the vehicle's year. A VIN decoder will accept them.

2. **Mileage only ever goes up.** Walk a vehicle's service history in date
   order and the odometer reading never falls. Odometer rollback is fraud,
   and data that does it by accident is useless for detecting it.

3. **Prices depreciate properly.** A car loses roughly a fifth of its value
   in the first year and less each year after, adjusted for how hard it has
   been driven. Plot price against age and you get the familiar curve.

4. **The plates are the modern Spanish format.** Four digits and three
   consonants, with every vowel excluded so a plate can never spell a word.

5. **ITV follows Spanish law.** Cars are first inspected at four years old,
   then every two years until ten, then annually. The inspection history
   reflects that schedule rather than a random interval.

READ clinical.py FIRST -- it is the fully commented reference
implementation, and this file follows the same three-part shape.
"""

from __future__ import annotations

import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from ..common.dates import add_years, age_on
from ..common.geography import PROVINCES, generate_address
from ..common.identifiers import build_vin, dni, licence_plate
from ..common.schema import Entity, Field, Topic
from ..common.seeds import Rng

# ===========================================================================
# PART 1 -- REFERENCE DATA
# ===========================================================================

DEFAULT_COUNTS = {
    "manufacturers": 12,
    "models": 70,
    "dealerships": 30,
    "parts": 400,
    "owners": 1_000,
    "vehicles": 1_500,
    "ownership_history": 2_000,
    "sales": 1_400,
    "inspections": 2_500,
    "service_records": 4_000,
}

PERIOD_START = date(2015, 1, 1)
PERIOD_END = date(2025, 6, 30)

#: Invented manufacturers. Every name here is made up, so no real carmaker
#: is described by this data -- which also means the WMI codes below are
#: safe to invent.
#:
#: Format: (name, country, founded, invented WMI prefix)
MANUFACTURERS = [
    ("Altaria Motors", "Spain", 1962, "ZZA"),
    ("Velmar Automobile", "Germany", 1931, "ZZB"),
    ("Corvera", "Spain", 1978, "ZZC"),
    ("Nordika Bilar", "Sweden", 1947, "ZZD"),
    ("Tessera Auto", "Italy", 1955, "ZZF"),
    ("Aurion Motor Works", "France", 1919, "ZZG"),
    ("Belmonte Vehículos", "Spain", 1984, "ZZH"),
    ("Kestrel Cars", "United Kingdom", 1938, "ZZJ"),
    ("Marova", "Czechia", 1925, "ZZK"),
    ("Ondara Industrial", "Spain", 1991, "ZZL"),
    ("Rivenna", "Italy", 1968, "ZZM"),
    ("Solane Motors", "France", 2004, "ZZN"),
]

#: Model name stems. Combined with a manufacturer they produce names in the
#: style carmakers actually use -- a word, or a letter and a number.
MODEL_STEMS = [
    "Aria", "Vento", "Sierra", "Duna", "Mistral", "Orion", "Lumen",
    "Cielo", "Ribera", "Alba", "Nevada", "Tramonte", "Cobalto", "Zenit",
    "Marea", "Faro", "Lince", "Sendero", "Corso", "Verde", "Astro",
    "Bruma", "Delta", "Espiga", "Fuego", "Grava", "Horizonte",
]

#: Segment -> (body types, typical new price range, typical engine cc,
#: typical power in hp). European segment letters are the standard the
#: industry itself uses, from A for a city car to E for an executive saloon.
SEGMENTS = {
    "A": (["hatchback"], (11_000, 16_000), (900, 1_200), (65, 95)),
    "B": (["hatchback", "estate"], (15_000, 23_000), (1_000, 1_500), (90, 130)),
    "C": (["hatchback", "estate", "saloon"], (21_000, 34_000), (1_200, 2_000), (110, 190)),
    "D": (["saloon", "estate"], (30_000, 52_000), (1_600, 2_400), (150, 265)),
    "E": (["saloon", "coupe"], (48_000, 85_000), (2_000, 3_000), (200, 400)),
    "SUV": (["SUV"], (24_000, 62_000), (1_400, 2_500), (130, 300)),
    "MPV": (["MPV"], (22_000, 38_000), (1_400, 2_000), (110, 180)),
    "Van": (["van"], (18_000, 36_000), (1_500, 2_200), (95, 170)),
}

SEGMENT_WEIGHTS = {"A": 10, "B": 22, "C": 24, "D": 9, "E": 3,
                   "SUV": 22, "MPV": 5, "Van": 5}

#: Fuel mix. Spain ran on diesel for two decades and is still unwinding it,
#: so diesel remains far more common in the used fleet than it is in new
#: sales -- which this distribution reflects.
FUEL_TYPES = {"diesel": 38, "petrol": 36, "hybrid": 14,
              "plug_in_hybrid": 6, "electric": 4, "lpg": 2}

#: Manual gearboxes still dominate in Spain, unlike in North America. Getting
#: this backwards is an instant tell that a dataset was not written for a
#: European market.
TRANSMISSIONS = {"manual": 68, "automatic": 32}

COLOURS = {
    "Blanco": 28, "Negro": 19, "Gris": 18, "Plata": 12, "Azul": 9,
    "Rojo": 7, "Verde": 3, "Marrón": 2, "Amarillo": 1, "Naranja": 1,
}

#: Spanish ITV inspection outcomes. The real Spanish terms are "favorable",
#: "desfavorable" and "negativa"; the English equivalents are used here so
#: that enum values stay in English throughout the repository, as the
#: column names and descriptions do.
INSPECTION_RESULTS = {"favourable": 78, "unfavourable": 18, "negative": 4}

#: Defects an ITV station actually records.
INSPECTION_DEFECTS = [
    "Faulty dipped beam alignment", "Excessive brake imbalance",
    "Worn front tyre below 1.6mm", "Emissions above limit",
    "Corroded exhaust mounting", "Windscreen chip in swept area",
    "Handbrake efficiency below threshold", "Suspension bush play",
    "Number plate light inoperative", "Excessive steering play",
    "Rear shock absorber leaking", "Seat belt retractor faulty",
]

SERVICE_TYPES = {
    "Routine service": 34, "Oil and filter change": 22, "Brake replacement": 11,
    "Tyre replacement": 10, "Clutch repair": 4, "Battery replacement": 6,
    "Air conditioning service": 5, "Timing belt replacement": 3,
    "Suspension repair": 3, "Bodywork repair": 2,
}

PART_CATEGORIES = {
    "Brakes": ["Brake pad set", "Brake disc", "Brake caliper", "Brake fluid"],
    "Filters": ["Oil filter", "Air filter", "Cabin filter", "Fuel filter"],
    "Engine": ["Spark plug", "Timing belt kit", "Water pump", "Turbocharger"],
    "Suspension": ["Shock absorber", "Coil spring", "Control arm", "Wheel bearing"],
    "Electrical": ["Battery", "Alternator", "Starter motor", "Headlight bulb"],
    "Transmission": ["Clutch kit", "Gearbox oil", "Drive shaft"],
    "Body": ["Wing mirror", "Windscreen wiper", "Door handle", "Bumper"],
    "Tyres": ["Summer tyre", "Winter tyre", "All-season tyre"],
}

SALE_TYPES = {"new": 34, "used": 58, "demo": 8}

FINANCING = {"cash": 31, "loan": 48, "leasing": 14, "renting": 7}

#: Average kilometres driven per year in Spain. Used to generate odometer
#: readings that match a vehicle's age.
KM_PER_YEAR_MEAN = 13_500
KM_PER_YEAR_SD = 5_200


# ===========================================================================
# PART 2 -- THE SCHEMA
# ===========================================================================

MANUFACTURERS_ENTITY = Entity(
    name="manufacturers",
    topic="automobile",
    grain="One row per vehicle manufacturer.",
    description=(
        "The carmakers whose vehicles appear in this dataset. All twelve are "
        "invented, which is also why their World Manufacturer Identifier "
        "prefixes can be made up without colliding with a real one."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Models "
                          "and dealerships both join against this."),
        Field("name", "string", unique=True, example="Altaria Motors",
              description="Manufacturer trading name. Entirely invented, so no "
                          "real carmaker is described anywhere in this topic."),
        Field("country", "string", example="Spain",
              description="Country the manufacturer is headquartered in, "
                          "spread across the European motor industry."),
        Field("founded", "integer", unit="year", example=1962,
              description="Year the company was founded, between 1919 and "
                          "2004, following the real shape of European motor "
                          "industry history."),
        Field("wmi", "string", unique=True, pattern=r"^[A-Z]{3}$", example="ZZA",
              description="World Manufacturer Identifier, the first three "
                          "characters of every VIN this maker issues. These "
                          "are deliberately invented codes that no real "
                          "manufacturer has been assigned."),
    ],
)

MODELS = Entity(
    name="models",
    topic="automobile",
    grain="One row per model produced by one manufacturer.",
    description=(
        "The model range. A model defines the segment, body style and engine "
        "envelope; individual cars in the vehicles table inherit those "
        "characteristics and vary within them."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("manufacturer_id", "integer", references="manufacturers.id", example=1,
              description="Who makes this model. Every model belongs to "
                          "exactly one manufacturer."),
        Field("name", "string", example="Altaria Mistral",
              description="Full model name, manufacturer plus model line, as "
                          "it would appear in a brochure or a listing."),
        Field("segment", "enum", values=sorted(SEGMENTS), example="C",
              description="European vehicle segment, the classification the "
                          "industry itself uses: A is a city car, C a family "
                          "hatchback, E an executive saloon, plus SUV, MPV and "
                          "Van as body-led categories."),
        Field("body_type", "enum",
              values=["hatchback", "saloon", "estate", "SUV", "coupe", "MPV", "van"],
              example="hatchback",
              description="Body style, always one that is plausible for the "
                          "segment -- you will not find an A-segment estate "
                          "car, because nobody builds one."),
        Field("year_from", "integer", unit="year", example=2016,
              description="First model year this version was produced. "
                          "Vehicles in this dataset are never older than their "
                          "model's launch."),
        Field("year_to", "integer", unit="year", nullable=True, example=2023,
              description="Last model year produced, or empty if the model is "
                          "still in production -- which is the case for about "
                          "40% of rows."),
        Field("base_price", "decimal", unit="EUR", example=24_900.00,
              description="List price when new, in euros, scaled to the "
                          "segment. This is the figure depreciation is applied "
                          "to when valuing a used example."),
    ],
)

DEALERSHIPS = Entity(
    name="dealerships",
    topic="automobile",
    grain="One row per dealership location.",
    description=(
        "Franchised dealers, each representing one manufacturer. Sales happen "
        "at a dealership, so this is the table to join through for territory "
        "and performance analysis."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("name", "string", example="Altaria Motors Sevilla",
              description="Dealership trading name, the manufacturer plus the "
                          "city it serves. Invented throughout."),
        Field("manufacturer_id", "integer", references="manufacturers.id", example=1,
              description="Which marque this dealer is franchised for. A "
                          "dealership sells one manufacturer's new cars, as "
                          "franchise agreements require."),
        Field("city", "string", example="Sevilla",
              description="Spanish city the dealership operates in, drawn from "
                          "real municipalities weighted by population."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province the dealership sits in, always consistent "
                          "with the leading pair of its postal code."),
        Field("address", "string", example="Polígono Industrial Norte, 14",
              description="Street address in Spanish format. Dealerships "
                          "cluster on industrial estates, as they do in "
                          "reality. Invented."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41007",
              description="Spanish postal code whose first two digits encode "
                          "the province, so the two columns always agree."),
        Field("phone", "string", example="+34 954 31 22 07",
              description="Dealership telephone, carrying the dialling prefix "
                          "of the province it trades in."),
        Field("opened_at", "date", example="2011-04-05",
              description="Date the dealership opened. No sale in this dataset "
                          "predates its own dealership's opening."),
    ],
)

OWNERS = Entity(
    name="owners",
    topic="automobile",
    grain="One row per person who has owned a vehicle.",
    description=(
        "Registered keepers. A person may own several vehicles over time and "
        "a vehicle passes through several owners, so the many-to-many "
        "relationship between them lives in ownership_history."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("full_name", "string", example="Javier Moreno Ortega",
              description="Spanish name carrying both surnames, the father's "
                          "then the mother's, as they appear on a vehicle "
                          "registration document."),
        Field("national_id", "string", unique=True, pattern=r"^\d{8}[A-Z]$",
              example="12345678Z",
              description="Spanish DNI, eight digits plus a check letter "
                          "derived modulo 23. Structurally valid so it passes "
                          "a real validator, and registered to nobody."),
        Field("licence_number", "string", unique=True, pattern=r"^ES-\d{8}$",
              example="ES-00041273",
              description="Driving licence reference in an invented format "
                          "that deliberately does not match the real Spanish "
                          "DGT numbering scheme."),
        Field("birth_date", "date", example="1982-09-14",
              description="Date of birth. Owners are between 18 and 88, since "
                          "nobody younger can hold a licence."),
        Field("city", "string", example="Sevilla",
              description="Spanish city of residence, which determines where "
                          "the vehicle is usually registered."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province of residence, consistent with the postal "
                          "code that follows."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41009",
              description="Spanish postal code whose leading pair is the "
                          "province code, so address validation passes."),
        Field("phone", "string", example="+34 612 34 56 78",
              description="Contact number in Spanish mobile format, which is "
                          "what a dealer or workshop would hold on file."),
    ],
)

VEHICLES = Entity(
    name="vehicles",
    topic="automobile",
    grain="One row per individual physical vehicle.",
    description=(
        "The cars themselves, identified by VIN. This is the anchor table of "
        "the topic: ownership, sales, servicing and inspections all point "
        "back at a vehicle."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Use this "
                          "for joins rather than the VIN or the plate."),
        Field("vin", "string", unique=True, pattern=r"^[A-HJ-NPR-Z0-9]{17}$",
              example="ZZAABC4DEXF004217",
              description="Vehicle Identification Number: 17 characters with a "
                          "correct ISO 3779 check digit at position 9 and a "
                          "model-year letter at position 10 that matches the "
                          "year column. The letters I, O and Q never appear, "
                          "because the standard forbids them."),
        Field("plate", "string", unique=True, pattern=r"^\d{4} [BCDFGHJKLMNPRSTVWXYZ]{3}$",
              example="1087 FPC",
              description="Spanish registration in the post-2000 format: four "
                          "digits then three consonants. Every vowel is "
                          "excluded so a plate can never accidentally spell a "
                          "word."),
        Field("model_id", "integer", references="models.id", example=7,
              description="Which model this car is. Determines its segment, "
                          "body style and the price it depreciates from."),
        Field("year", "integer", unit="year", example=2019,
              description="Model year, always within the production window of "
                          "its model and always between 2010 and 2025."),
        Field("colour", "string", example="Blanco",
              description="Paint colour in Spanish. White, black and grey "
                          "dominate, matching the real European colour mix "
                          "where three quarters of cars are monochrome."),
        Field("fuel_type", "enum", values=sorted(FUEL_TYPES), example="diesel",
              description="What it runs on. Diesel remains the largest share "
                          "of the Spanish used fleet even as new sales shift "
                          "away from it."),
        Field("transmission", "enum", values=sorted(TRANSMISSIONS), example="manual",
              description="Gearbox type. Manual dominates at roughly two "
                          "thirds, which is the European pattern and the "
                          "opposite of the North American one."),
        Field("engine_cc", "integer", unit="cm³", example=1598,
              description="Engine displacement in cubic centimetres, scaled to "
                          "the segment. Always zero for battery electric "
                          "vehicles, which have no displacement at all."),
        Field("power_hp", "integer", unit="hp", example=115,
              description="Maximum power in metric horsepower, the unit "
                          "Spanish registration documents use. Correlates with "
                          "engine size and segment."),
        Field("mileage_km", "integer", unit="km", example=84_300,
              description="Current odometer reading. Consistent with the "
                          "vehicle's age at roughly 13,500 km a year, and "
                          "never lower than the reading on its most recent "
                          "service record."),
        Field("registered_on", "date", example="2019-06-14",
              description="Date the vehicle was first registered in Spain, "
                          "which starts the clock for its ITV schedule."),
    ],
    notes=[
        "Mileage is generated from age at a realistic annual rate with wide "
        "variation, so a scatter plot of mileage against age produces the "
        "fan-shaped cloud a real fleet shows rather than a straight line.",
        "Electric vehicles carry engine_cc of 0. That is correct rather than "
        "missing data, and it is a good reminder to check for it before "
        "computing an average displacement.",
    ],
)

OWNERSHIP_HISTORY = Entity(
    name="ownership_history",
    topic="automobile",
    grain="One row per period during which one owner held one vehicle.",
    description=(
        "The chain of custody. Each row is one owner's tenure, so a vehicle "
        "with three previous keepers has four rows. Only the most recent has "
        "an empty end date."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("vehicle_id", "integer", references="vehicles.id", example=42,
              description="Which car changed hands. Ordering this table by "
                          "vehicle and start date reconstructs the full "
                          "ownership chain."),
        Field("owner_id", "integer", references="owners.id", example=17,
              description="Who held it during this period. The same person can "
                          "appear against several vehicles."),
        Field("owned_from", "date", example="2021-03-08",
              description="Date this keeper took possession. For the first "
                          "owner this equals the vehicle's registration date."),
        Field("owned_until", "date", nullable=True, example="2024-05-19",
              description="Date they sold it on, or empty for the current "
                          "keeper. Exactly one row per vehicle has this empty, "
                          "which makes it the way to find who owns a car now."),
        Field("purchase_price", "decimal", unit="EUR", nullable=True,
              example=14_200.00,
              description="What this keeper paid, in euros, reflecting the "
                          "vehicle's depreciated value at the time. Empty for "
                          "about 15% of transfers where no price was recorded, "
                          "such as an inheritance or a family transfer."),
    ],
    notes=[
        "Ownership periods for a vehicle never overlap and never leave a gap: "
        "one keeper's owned_until is the next keeper's owned_from. This is "
        "asserted in CI and makes the table usable for testing timeline and "
        "interval logic.",
    ],
)

SALES = Entity(
    name="sales",
    topic="automobile",
    grain="One row per vehicle sold through a dealership.",
    description=(
        "Dealer transactions. Not every ownership change is a dealer sale -- "
        "private sales exist too -- so this table is smaller than "
        "ownership_history and joins to only some of it."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("vehicle_id", "integer", references="vehicles.id", example=42,
              description="Which car was sold. A vehicle can be sold more than "
                          "once, first new and later as a used trade-in."),
        Field("dealership_id", "integer", references="dealerships.id", example=3,
              description="Where the sale took place. For a new-car sale the "
                          "dealership is always franchised for that vehicle's "
                          "manufacturer."),
        Field("buyer_id", "integer", references="owners.id", example=17,
              description="Who bought it. Always the person who appears as the "
                          "next keeper in ownership_history."),
        Field("sale_date", "date", example="2021-03-08",
              description="Date of sale, always on or after the dealership "
                          "opened and on or after the vehicle was registered."),
        Field("sale_type", "enum", values=sorted(SALE_TYPES), example="used",
              description="Whether the car was new, used, or an ex-demonstrator. "
                          "Used sales dominate, as they do in the real Spanish "
                          "market by roughly two to one."),
        Field("sale_price", "decimal", unit="EUR", example=18_400.00,
              description="Transaction price in euros. New sales sit near the "
                          "model's list price; used sales follow the "
                          "depreciation curve for the car's age and mileage."),
        Field("financing", "enum", values=sorted(FINANCING), example="loan",
              description="How the purchase was funded. Loans dominate, with "
                          "leasing and renting -- the Spanish term for a "
                          "long-term all-inclusive rental -- behind them."),
        Field("warranty_months", "integer", unit="months", example=24,
              description="Warranty supplied with the sale. New cars carry the "
                          "statutory three years; used cars carry the one-year "
                          "minimum Spanish law requires of a dealer."),
    ],
)

SERVICE_RECORDS = Entity(
    name="service_records",
    topic="automobile",
    grain="One row per workshop visit by one vehicle.",
    description=(
        "Maintenance history, and the largest table in the topic. Each row "
        "records what was done, at what odometer reading, and what it cost in "
        "parts and labour."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("vehicle_id", "integer", references="vehicles.id", example=42,
              description="Which car was worked on. Ordering by vehicle and "
                          "date gives its maintenance timeline."),
        Field("dealership_id", "integer", nullable=True, references="dealerships.id",
              example=3,
              description="The franchised workshop that did the work, or empty "
                          "for about 35% of visits carried out by an "
                          "independent garage -- which is what happens once a "
                          "car is out of warranty."),
        Field("service_date", "date", example="2023-09-12",
              description="Date of the visit, always after the vehicle was "
                          "registered and in strictly increasing order within "
                          "a vehicle's history."),
        Field("mileage_km", "integer", unit="km", example=62_400,
              description="Odometer reading at the time of the visit. Never "
                          "lower than the previous service for the same "
                          "vehicle, because odometers do not run backwards -- "
                          "a rule CI enforces."),
        Field("service_type", "enum", values=sorted(SERVICE_TYPES),
              example="Routine service",
              description="What was carried out. Routine servicing and oil "
                          "changes dominate, with expensive work like timing "
                          "belts appearing only at the mileages where it is "
                          "actually due."),
        Field("parts_cost", "decimal", unit="EUR", example=142.60,
              description="Cost of parts fitted, in euros. Zero for a purely "
                          "diagnostic visit, and several hundred for a clutch "
                          "or timing belt."),
        Field("labour_cost", "decimal", unit="EUR", example=210.00,
              description="Labour charged, in euros, computed from the hours "
                          "the job takes and a realistic Spanish workshop "
                          "rate."),
        Field("total_cost", "decimal", unit="EUR", example=352.60,
              description="Invoice total, exactly parts_cost plus labour_cost. "
                          "Stored rather than derived because that is what an "
                          "invoice does, and it gives you a sum to verify."),
    ],
)

INSPECTIONS = Entity(
    name="inspections",
    topic="automobile",
    grain="One row per ITV roadworthiness inspection of one vehicle.",
    description=(
        "Spanish ITV history. ITV is the compulsory periodic roadworthiness "
        "test: a car is first inspected at four years old, then every two "
        "years until it turns ten, and annually after that. The inspection "
        "dates in this table follow that schedule."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("vehicle_id", "integer", references="vehicles.id", example=42,
              description="Which car was inspected. Cars under four years old "
                          "have no rows here at all, because the law does not "
                          "require a test yet."),
        Field("inspection_date", "date", example="2023-06-20",
              description="Date of the test, following the statutory interval "
                          "for the vehicle's age rather than a random spacing."),
        Field("result", "enum", values=sorted(INSPECTION_RESULTS), example="favourable",
              description="Outcome. 'favourable' passes; 'unfavourable' means "
                          "defects that must be fixed and retested within two "
                          "months; 'negative' means the car is unsafe and may "
                          "not be driven away."),
        Field("defects", "string", nullable=True,
              example="Worn front tyre below 1.6mm",
              description="What was found, for tests that did not pass "
                          "outright. Empty on a favourable result, which is "
                          "about 78% of rows."),
        Field("mileage_km", "integer", unit="km", example=71_800,
              description="Odometer reading recorded at the station. ITV "
                          "centres log this, which is why a car's ITV history "
                          "is used to detect odometer tampering."),
        Field("next_due", "date", example="2025-06-20",
              description="When the next test falls due, computed from the "
                          "vehicle's age at inspection: two years if under "
                          "ten, one year if over."),
        Field("station_code", "string", pattern=r"^ITV-\d{4}$", example="ITV-0412",
              description="Reference of the testing station. Invented format "
                          "that does not correspond to the real Spanish "
                          "station registry."),
    ],
)

PARTS = Entity(
    name="parts",
    topic="automobile",
    grain="One row per part in the spares catalogue.",
    description=(
        "The parts catalogue a workshop orders from. Not linked to service "
        "records in this dataset -- it is a standalone reference table, which "
        "makes it a useful small catalogue for testing search and filtering."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("oem_code", "string", unique=True, pattern=r"^[A-Z]{2}\d{6}$",
              example="BR004217",
              description="Manufacturer part number in an invented format: two "
                          "letters for the category and six digits. Does not "
                          "match any real catalogue numbering."),
        Field("name", "string", example="Brake pad set",
              description="What the part is, in plain English, as it would "
                          "appear on a workshop invoice line."),
        Field("category", "enum", values=sorted(PART_CATEGORIES), example="Brakes",
              description="Which system the part belongs to, from Brakes and "
                          "Filters through to Tyres. Useful for testing "
                          "faceted search."),
        Field("unit_price", "decimal", unit="EUR", example=48.90,
              description="Trade price per unit in euros, scaled to the "
                          "category -- a filter costs a few euros, a "
                          "turbocharger several hundred."),
        Field("stock_quantity", "integer", unit="units", example=24,
              description="Units currently held. About 6% of lines are out of "
                          "stock at zero, which is a case any ordering screen "
                          "has to handle."),
    ],
)


# ===========================================================================
# PART 3 -- THE GENERATOR
# ===========================================================================

def _strip_accents(text: str) -> str:
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _depreciated_value(base_price: Decimal, age_years: float, mileage_km: int) -> Decimal:
    """What a car of this age and mileage is worth.

    Cars lose value fastest at the start: roughly a fifth in the first year,
    then a smaller proportion each year after. Modelling it as a constant
    percentage of the ORIGINAL price -- straight-line depreciation -- gives a
    curve that is visibly wrong and can even go negative.

    Mileage is applied on top: a car driven much harder than average for its
    age is worth less than one that has barely moved.
    """
    # Exponential decay: 18% of the remaining value per year.
    value = base_price * Decimal(str(0.82 ** max(0.0, age_years)))

    # Penalty or bonus for mileage away from the expected figure.
    expected_km = KM_PER_YEAR_MEAN * max(0.5, age_years)
    if expected_km > 0:
        ratio = mileage_km / expected_km
        adjustment = Decimal(str(max(0.6, min(1.18, 1.0 - (ratio - 1.0) * 0.16))))
        value *= adjustment

    # Nothing roadworthy is worth less than a few hundred euros.
    return max(Decimal("450.00"), value).quantize(Decimal("0.01"))


def _generate_manufacturers(count: int) -> list[dict[str, Any]]:
    rows = []
    for index, (name, country, founded, wmi) in enumerate(MANUFACTURERS[:count], start=1):
        rows.append({
            "id": index, "name": name, "country": country,
            "founded": founded, "wmi": wmi,
        })
    return rows


def _generate_models(manufacturers: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("automobile", "models")

    rows = []
    used_names: set[str] = set()
    for index in range(1, count + 1):
        manufacturer = rng.python.choice(manufacturers)
        segment = rng.weighted_choice(SEGMENT_WEIGHTS)
        body_types, (price_low, price_high), _, _ = SEGMENTS[segment]

        stem = rng.python.choice(MODEL_STEMS)
        marque = manufacturer["name"].split()[0]
        name = f"{marque} {stem}"
        while name in used_names:
            name = f"{marque} {rng.python.choice(MODEL_STEMS)} {rng.python.randint(2, 9)}"
        used_names.add(name)

        year_from = rng.python.randint(2010, 2022)
        # About 40% of models are still in production.
        year_to = None if rng.python.random() < 0.40 else min(
            2025, year_from + rng.python.randint(3, 9)
        )

        rows.append({
            "id": index,
            "manufacturer_id": manufacturer["id"],
            "name": name,
            "segment": segment,
            "body_type": rng.python.choice(body_types),
            "year_from": year_from,
            "year_to": year_to,
            "base_price": Decimal(str(round(
                rng.python.uniform(price_low, price_high), -2
            ))).quantize(Decimal("0.01")),
        })
    return rows


def _generate_dealerships(manufacturers: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("automobile", "dealerships")

    rows = []
    used_names: set[str] = set()
    for index in range(1, count + 1):
        manufacturer = rng.python.choice(manufacturers)
        location = generate_address(rng, with_phone=True)

        marque = manufacturer["name"].split()[0]
        name = f"{marque} {location['city']}"
        while name in used_names:
            name = f"{marque} {location['city']} {rng.python.randint(2, 9)}"
        used_names.add(name)

        # Dealerships sit on industrial estates far more often than on the
        # high street, so half of them get that style of address.
        address = location["address"]
        if rng.python.random() < 0.5:
            address = (f"Polígono Industrial "
                       f"{rng.python.choice(['Norte', 'Sur', 'Este', 'Oeste', 'Los Olivos'])}, "
                       f"{rng.python.randint(1, 60)}")

        rows.append({
            "id": index,
            "name": name,
            "manufacturer_id": manufacturer["id"],
            "city": location["city"],
            "province": location["province"],
            "address": address,
            "postal_code": location["postal_code"],
            "phone": location["phone"],
            "opened_at": rng.date_between(date(1995, 1, 1), date(2021, 12, 31)),
        })
    return rows


def _generate_owners(count: int) -> list[dict[str, Any]]:
    rng = Rng("automobile", "owners")

    rows = []
    for index in range(1, count + 1):
        is_female = rng.python.random() < 0.47
        full_name = rng.faker.name_female() if is_female else rng.faker.name_male()
        location = generate_address(rng, with_phone=True, mobile=True)

        age = int(min(88, max(18, rng.numpy.normal(47, 15))))
        birth_date = date(PERIOD_END.year - age, 1, 1) + timedelta(
            days=rng.python.randint(0, 364)
        )

        rows.append({
            "id": index,
            "full_name": full_name,
            "national_id": dni(rng),
            "licence_number": f"ES-{index:08d}",
            "birth_date": birth_date,
            "city": location["city"],
            "province": location["province"],
            "postal_code": location["postal_code"],
            "phone": location["phone"],
        })
    return rows


def _generate_vehicles(
    models: list[dict], manufacturers: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("automobile", "vehicles")

    wmi_by_manufacturer = {row["id"]: row["wmi"] for row in manufacturers}

    rows = []
    used_vins: set[str] = set()
    used_plates: set[str] = set()

    for index in range(1, count + 1):
        model = rng.python.choice(models)
        _, _, (cc_low, cc_high), (hp_low, hp_high) = SEGMENTS[model["segment"]]

        # The car cannot predate its model's launch or postdate production.
        year_low = max(2010, model["year_from"])
        year_high = min(2025, model["year_to"] or 2025)
        year = rng.python.randint(year_low, max(year_low, year_high))

        registered_on = date(year, 1, 1) + timedelta(days=rng.python.randint(0, 364))
        if registered_on > PERIOD_END:
            registered_on = PERIOD_END - timedelta(days=rng.python.randint(1, 60))

        age_years = max(0.1, (PERIOD_END - registered_on).days / 365.25)

        # Mileage derived from age at a realistic annual rate, with enough
        # spread that a scatter plot against age fans out the way a real
        # fleet does rather than forming a line.
        km_per_year = max(2_000, rng.numpy.normal(KM_PER_YEAR_MEAN, KM_PER_YEAR_SD))
        mileage = int(max(150, km_per_year * age_years))

        fuel = rng.weighted_choice(FUEL_TYPES)
        # A battery electric vehicle has no displacement. Zero is the correct
        # value here, not missing data.
        engine_cc = 0 if fuel == "electric" else rng.python.randint(cc_low, cc_high)

        # VIN: the manufacturer's invented WMI, five descriptor characters,
        # the check digit (computed by build_vin), the model-year letter, a
        # plant code and a six-digit serial.
        wmi = wmi_by_manufacturer[model["manufacturer_id"]]
        while True:
            descriptor = "".join(
                rng.python.choice("ABCDEFGHJKLMNPRSTUVWXYZ0123456789") for _ in range(5)
            )
            plant = rng.python.choice("ABCDEFGHJKLMNPRSTUVWXYZ")
            serial = f"{rng.python.randint(0, 999_999):06d}"
            vin = build_vin(wmi, descriptor, year, plant, serial)
            if vin not in used_vins:
                used_vins.add(vin)
                break

        plate = licence_plate(rng)
        while plate in used_plates:
            plate = licence_plate(rng)
        used_plates.add(plate)

        rows.append({
            "id": index,
            "vin": vin,
            "plate": plate,
            "model_id": model["id"],
            "year": year,
            "colour": rng.weighted_choice(COLOURS),
            "fuel_type": fuel,
            "transmission": rng.weighted_choice(TRANSMISSIONS),
            "engine_cc": engine_cc,
            "power_hp": rng.python.randint(hp_low, hp_high),
            "mileage_km": mileage,
            "registered_on": registered_on,
        })
    return rows


def _generate_ownership_history(
    vehicles: list[dict], owners: list[dict], models: list[dict], count: int
) -> list[dict[str, Any]]:
    """Build each vehicle's chain of keepers.

    The chain must be CONTIGUOUS: one keeper's end date is the next keeper's
    start date, with no gaps and no overlaps, and exactly one open-ended row
    per vehicle. Generating ownership rows independently gives none of that,
    and makes the table useless for testing interval logic.
    """
    rng = Rng("automobile", "ownership_history")

    base_price_by_model = {row["id"]: Decimal(str(row["base_price"])) for row in models}

    rows: list[dict[str, Any]] = []
    for vehicle in vehicles:
        if len(rows) >= count:
            break

        registered_on = vehicle["registered_on"]
        age_years = (PERIOD_END - registered_on).days / 365.25

        # Older cars have passed through more hands.
        expected_owners = 1 + int(age_years / 4.5)
        keeper_count = max(1, min(5, rng.python.randint(1, max(1, expected_owners + 1))))

        # Pick the changeover dates, then walk them in order.
        boundaries = sorted(
            rng.date_between(registered_on, PERIOD_END) for _ in range(keeper_count - 1)
        )
        starts = [registered_on, *boundaries]
        ends = [*boundaries, None]

        for owned_from, owned_until in zip(starts, ends):
            if len(rows) >= count:
                break

            owner = rng.python.choice(owners)
            held_age = max(0.0, (owned_from - registered_on).days / 365.25)
            mileage_at_sale = int(vehicle["mileage_km"] * (held_age / max(0.1, age_years)))

            price = _depreciated_value(
                base_price_by_model[vehicle["model_id"]], held_age, mileage_at_sale
            )

            rows.append({
                "id": len(rows) + 1,
                "vehicle_id": vehicle["id"],
                "owner_id": owner["id"],
                "owned_from": owned_from,
                "owned_until": owned_until,
                # Some transfers record no price -- an inheritance, a gift,
                # a transfer between family members.
                "purchase_price": rng.maybe_null(price, 0.15),
            })

    return rows


def _generate_sales(
    ownership: list[dict],
    vehicles: list[dict],
    models: list[dict],
    dealerships: list[dict],
    count: int,
) -> list[dict[str, Any]]:
    rng = Rng("automobile", "sales")

    vehicles_by_id = {row["id"]: row for row in vehicles}
    models_by_id = {row["id"]: row for row in models}
    dealers_by_manufacturer: dict[int, list[dict]] = {}
    for dealer in dealerships:
        dealers_by_manufacturer.setdefault(dealer["manufacturer_id"], []).append(dealer)

    rows = []
    # Roughly two thirds of ownership changes went through a dealer; the
    # rest were private sales, which is why this table is smaller.
    candidates = [row for row in ownership if rng.python.random() < 0.7]

    for record in candidates:
        if len(rows) >= count:
            break

        vehicle = vehicles_by_id[record["vehicle_id"]]
        model = models_by_id[vehicle["model_id"]]

        # A franchised dealer for this marque, falling back to any dealer if
        # the marque has none -- which is what a used sale looks like anyway.
        dealers = dealers_by_manufacturer.get(model["manufacturer_id"]) or dealerships
        dealer = rng.python.choice(dealers)

        sale_date = max(record["owned_from"], dealer["opened_at"])
        if sale_date > PERIOD_END:
            continue

        is_first_owner = record["owned_from"] == vehicle["registered_on"]
        days_old = (sale_date - vehicle["registered_on"]).days
        if is_first_owner and days_old < 120:
            sale_type = rng.weighted_choice({"new": 88, "demo": 12})
        else:
            sale_type = rng.weighted_choice({"used": 94, "demo": 6})

        age_at_sale = max(0.0, days_old / 365.25)
        mileage_at_sale = int(
            vehicle["mileage_km"]
            * (age_at_sale / max(0.1, (PERIOD_END - vehicle["registered_on"]).days / 365.25))
        )

        if sale_type == "new":
            price = Decimal(str(model["base_price"])) * Decimal(
                str(round(rng.python.uniform(0.92, 1.04), 4))
            )
        else:
            price = _depreciated_value(
                Decimal(str(model["base_price"])), age_at_sale, mileage_at_sale
            )

        rows.append({
            "id": len(rows) + 1,
            "vehicle_id": vehicle["id"],
            "dealership_id": dealer["id"],
            "buyer_id": record["owner_id"],
            "sale_date": sale_date,
            "sale_type": sale_type,
            "sale_price": price.quantize(Decimal("0.01")),
            "financing": rng.weighted_choice(FINANCING),
            # Spain requires three years on a new car and one year minimum
            # when a dealer sells a used one.
            "warranty_months": 36 if sale_type == "new" else rng.python.choice([12, 12, 24]),
        })

    return rows


def _generate_service_records(
    vehicles: list[dict], dealerships: list[dict], count: int
) -> list[dict[str, Any]]:
    """Build each vehicle's maintenance timeline.

    Mileage must increase monotonically within a vehicle. That means the
    visits have to be generated in date order with the odometer carried
    forward -- the same discipline the finance ledger needs for its running
    balance.
    """
    rng = Rng("automobile", "service_records")

    # Typical labour hours and parts cost band per job.
    job_profile = {
        "Routine service": (1.5, 60, 180),
        "Oil and filter change": (0.8, 35, 90),
        "Brake replacement": (2.0, 90, 320),
        "Tyre replacement": (1.0, 160, 620),
        "Clutch repair": (5.5, 280, 780),
        "Battery replacement": (0.5, 85, 210),
        "Air conditioning service": (1.2, 40, 130),
        "Timing belt replacement": (4.5, 210, 560),
        "Suspension repair": (3.0, 140, 470),
        "Bodywork repair": (6.0, 180, 900),
    }
    LABOUR_RATE_PER_HOUR = Decimal("48.00")

    rows: list[dict[str, Any]] = []

    for vehicle in vehicles:
        if len(rows) >= count:
            break

        registered_on = vehicle["registered_on"]
        age_years = max(0.1, (PERIOD_END - registered_on).days / 365.25)
        # Roughly one workshop visit per year, plus noise.
        visits = max(0, int(rng.numpy.normal(age_years * 1.1, 0.8)))

        dates = sorted(rng.date_between(registered_on, PERIOD_END) for _ in range(visits))

        previous_mileage = 0
        for service_date in dates:
            if len(rows) >= count:
                break

            elapsed = max(0.0, (service_date - registered_on).days / 365.25)
            mileage = int(vehicle["mileage_km"] * (elapsed / age_years))
            # The odometer never runs backwards.
            mileage = max(previous_mileage + rng.python.randint(50, 900), mileage)
            mileage = min(mileage, vehicle["mileage_km"])
            previous_mileage = mileage

            service_type = rng.weighted_choice(SERVICE_TYPES)
            hours, parts_low, parts_high = job_profile[service_type]

            parts_cost = Decimal(str(round(
                rng.python.uniform(parts_low, parts_high), 2
            )))
            labour_cost = (
                Decimal(str(round(hours * rng.python.uniform(0.85, 1.25), 2)))
                * LABOUR_RATE_PER_HOUR
            ).quantize(Decimal("0.01"))

            # Once a car is out of warranty most owners move to an
            # independent garage, so the franchised dealer drops out.
            uses_dealer = elapsed < 3.0 or rng.python.random() < 0.35

            rows.append({
                "id": len(rows) + 1,
                "vehicle_id": vehicle["id"],
                "dealership_id": rng.python.choice(dealerships)["id"] if uses_dealer else None,
                "service_date": service_date,
                "mileage_km": mileage,
                "service_type": service_type,
                "parts_cost": parts_cost,
                "labour_cost": labour_cost,
                "total_cost": (parts_cost + labour_cost).quantize(Decimal("0.01")),
            })

    return rows


def _generate_inspections(vehicles: list[dict], count: int) -> list[dict[str, Any]]:
    """Generate ITV history on the statutory Spanish schedule.

    The rule for a private car:
      * no test at all for the first four years
      * then every two years until the car turns ten
      * then every year

    Generating inspections at a random interval would miss the thing that
    makes this table interesting -- that the gap between tests halves at ten
    years old.
    """
    rng = Rng("automobile", "inspections")

    rows: list[dict[str, Any]] = []

    for vehicle in vehicles:
        if len(rows) >= count:
            break

        registered_on = vehicle["registered_on"]
        total_age = (PERIOD_END - registered_on).days / 365.25

        # First test at four years old.
        test_age = 4.0
        previous_mileage = 0

        while test_age <= total_age and len(rows) < count:
            inspection_date = registered_on + timedelta(days=int(test_age * 365.25))
            if inspection_date > PERIOD_END:
                break

            mileage = int(vehicle["mileage_km"] * (test_age / max(0.1, total_age)))
            mileage = max(previous_mileage + 1_000, mileage)
            mileage = min(mileage, vehicle["mileage_km"])
            previous_mileage = mileage

            result = rng.weighted_choice(INSPECTION_RESULTS)
            defects = (
                None if result == "favourable"
                else rng.python.choice(INSPECTION_DEFECTS)
            )

            # The interval halves once a car turns ten.
            interval = 2.0 if test_age < 10.0 else 1.0

            rows.append({
                "id": len(rows) + 1,
                "vehicle_id": vehicle["id"],
                "inspection_date": inspection_date,
                "result": result,
                "defects": defects,
                "mileage_km": mileage,
                "next_due": inspection_date + timedelta(days=int(interval * 365.25)),
                "station_code": f"ITV-{rng.python.randint(1, 9999):04d}",
            })

            test_age += interval

    return rows


def _generate_parts(count: int) -> list[dict[str, Any]]:
    rng = Rng("automobile", "parts")

    # Price band per category -- a filter is cheap, a turbocharger is not.
    price_bands = {
        "Brakes": (18, 190), "Filters": (5, 42), "Engine": (12, 720),
        "Suspension": (35, 260), "Electrical": (9, 340),
        "Transmission": (22, 590), "Body": (11, 280), "Tyres": (48, 210),
    }
    category_prefixes = {
        "Brakes": "BR", "Filters": "FL", "Engine": "EN", "Suspension": "SU",
        "Electrical": "EL", "Transmission": "TR", "Body": "BO", "Tyres": "TY",
    }

    rows = []
    used_codes: set[str] = set()
    for index in range(1, count + 1):
        category = rng.python.choice(sorted(PART_CATEGORIES))
        name = rng.python.choice(PART_CATEGORIES[category])
        low, high = price_bands[category]

        code = f"{category_prefixes[category]}{rng.python.randint(0, 999_999):06d}"
        while code in used_codes:
            code = f"{category_prefixes[category]}{rng.python.randint(0, 999_999):06d}"
        used_codes.add(code)

        rows.append({
            "id": index,
            "oem_code": code,
            "name": name,
            "category": category,
            "unit_price": Decimal(str(round(rng.python.uniform(low, high), 2))),
            "stock_quantity": 0 if rng.python.random() < 0.06 else rng.python.randint(1, 120),
        })
    return rows


def generate(scale: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    """Produce every table in the automobile topic."""
    counts = {name: max(1, int(number * scale)) for name, number in DEFAULT_COUNTS.items()}

    manufacturers = _generate_manufacturers(counts["manufacturers"])
    models = _generate_models(manufacturers, counts["models"])
    dealerships = _generate_dealerships(manufacturers, counts["dealerships"])
    parts = _generate_parts(counts["parts"])
    owners = _generate_owners(counts["owners"])
    vehicles = _generate_vehicles(models, manufacturers, counts["vehicles"])
    ownership_history = _generate_ownership_history(
        vehicles, owners, models, counts["ownership_history"]
    )
    sales = _generate_sales(
        ownership_history, vehicles, models, dealerships, counts["sales"]
    )
    inspections = _generate_inspections(vehicles, counts["inspections"])
    service_records = _generate_service_records(
        vehicles, dealerships, counts["service_records"]
    )

    return {
        "manufacturers": manufacturers,
        "models": models,
        "dealerships": dealerships,
        "parts": parts,
        "owners": owners,
        "vehicles": vehicles,
        "ownership_history": ownership_history,
        "sales": sales,
        "service_records": service_records,
        "inspections": inspections,
    }


TOPIC = Topic(
    name="automobile",
    title="Automobile / Vehicles",
    summary=(
        "Vehicles with checksum-valid VINs and Spanish plates, their owners, "
        "dealership sales, workshop history and ITV inspection records."
    ),
    description=(
        "A Spanish vehicle fleet: twelve invented manufacturers, their model "
        "ranges, and fifteen hundred individual cars with full ownership, "
        "servicing and roadworthiness histories.\n\n"
        "This is the topic with the longest per-entity timelines, which makes "
        "it the best one for testing audit trails and history views. Every "
        "VIN carries a correct ISO 3779 check digit and a model-year letter "
        "that matches the car's year; every registration is in the modern "
        "Spanish format, four digits and three consonants with all vowels "
        "excluded.\n\n"
        "Odometer readings only ever increase within a vehicle, ownership "
        "periods tile the whole life of a car without gaps or overlaps, and "
        "prices follow a realistic depreciation curve rather than a straight "
        "line. ITV inspections follow the statutory Spanish schedule: first "
        "test at four years, then biennial until ten, then annual."
    ),
    entities=[
        MANUFACTURERS_ENTITY,
        MODELS,
        DEALERSHIPS,
        PARTS,
        OWNERS,
        VEHICLES,
        OWNERSHIP_HISTORY,
        SALES,
        SERVICE_RECORDS,
        INSPECTIONS,
    ],
)
