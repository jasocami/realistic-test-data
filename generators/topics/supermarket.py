"""
Topic: supermarket -- stores, products, customers, till transactions.
===============================================================================

WHAT IS THIS TOPIC FOR?
-----------------------
Retail is the most common shape of business data there is, so this topic is
the one to reach for when you need something that looks like a real
application's database: a product catalogue, a customer list, and a long
table of transactions joining them together.

WHAT MAKES IT REALISTIC
-----------------------
1. **The money adds up.** For every transaction, the sum of its line items
   equals its recorded total, to the cent. This is asserted in the test
   suite. It sounds obvious; it is the first thing that is wrong in most
   generated retail data, and it makes the difference between data you can
   build a report against and data that makes your report look broken.

2. **The barcodes scan.** Every EAN-13 carries a correct check digit, so a
   barcode library will read them rather than rejecting them.

3. **VAT is right.** Spain charges three different rates on groceries --
   21% general, 10% reduced, and 4% "superreducido" on staples like bread,
   milk, eggs, fruit and vegetables. Products carry the rate their category
   actually attracts, which means tax calculations over this data produce
   believable numbers.

4. **The categories form a tree.** `categories.parent_id` points back at the
   same table, so there is a genuine hierarchy to test recursive queries and
   breadcrumb rendering against.

5. **Baskets look like baskets.** Most are small; a few are enormous. Prices
   end in .99 and .49 far more often than chance. Weekends are busier than
   Tuesdays.

READ clinical.py FIRST if you have not already -- it is the fully
commented reference implementation, and this file follows the same
three-part shape.
"""

from __future__ import annotations

import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from ..common.dates import next_weekday
from ..common.geography import PROVINCES, generate_address, phone_number
from ..common.identifiers import business_key, ean13
from ..common.schema import Entity, Field, Topic
from ..common.seeds import Rng

# ===========================================================================
# PART 1 -- REFERENCE DATA
# ===========================================================================

DEFAULT_COUNTS = {
    "stores": 8,
    "categories": 58,
    "suppliers": 50,
    "employees": 110,
    "products": 600,
    "promotions": 90,
    "inventory": 2_400,
    "customers": 900,
    "transactions": 3_000,
    "transaction_items": 8_500,
}

PERIOD_START = date(2023, 1, 1)
PERIOD_END = date(2025, 6, 30)

#: Spanish VAT bands as they apply to groceries.
#:
#: 4% ("superreducido") covers basic staples -- bread, milk, eggs, cheese,
#: fruit, vegetables, pulses. 10% ("reducido") covers most other food. 21%
#: ("general") covers everything that is not food at all, plus a few
#: categories the law treats as non-essential.
VAT_SUPERREDUCED = Decimal("0.04")
VAT_REDUCED = Decimal("0.10")
VAT_GENERAL = Decimal("0.21")

#: The category tree, as ``top level -> [subcategories]``.
#:
#: These are the aisles of an actual Spanish supermarket, in Spanish,
#: because that is what the shelf signs say. Column names and every field
#: description stay in English -- see docs/faq.md on the language split.
CATEGORY_TREE = {
    "Frescos": [
        "Frutas y verduras", "Carnicería", "Pescadería",
        "Charcutería", "Panadería", "Lácteos", "Huevos",
    ],
    "Alimentación": [
        "Pasta y arroz", "Conservas", "Aceites y vinagres",
        "Salsas y especias", "Cereales", "Galletas y bollería",
        "Snacks", "Legumbres", "Azúcar y endulzantes",
    ],
    "Bebidas": [
        "Agua", "Refrescos", "Cerveza", "Vino",
        "Zumos", "Café e infusiones", "Licores",
    ],
    "Congelados": [
        "Verduras congeladas", "Pescado congelado",
        "Helados", "Platos preparados",
    ],
    "Droguería y limpieza": [
        "Detergentes", "Limpieza del hogar", "Papel y celulosa",
        "Lavavajillas", "Insecticidas",
    ],
    "Higiene y belleza": [
        "Higiene bucal", "Cuidado capilar", "Cuidado corporal",
        "Afeitado", "Higiene íntima", "Cosmética",
    ],
    "Bebé": ["Pañales", "Alimentación infantil", "Higiene infantil"],
    "Mascotas": ["Perros", "Gatos", "Otros animales"],
    "Hogar": ["Menaje", "Bazar", "Iluminación"],
}

#: Which VAT band each top-level category attracts.
VAT_BY_TOP_CATEGORY = {
    "Frescos": VAT_SUPERREDUCED,
    "Alimentación": VAT_REDUCED,
    "Bebidas": VAT_GENERAL,       # alcohol and soft drinks are not staples
    "Congelados": VAT_REDUCED,
    "Droguería y limpieza": VAT_GENERAL,
    "Higiene y belleza": VAT_GENERAL,
    "Bebé": VAT_SUPERREDUCED,     # nappies were moved to the lowest band
    "Mascotas": VAT_GENERAL,
    "Hogar": VAT_GENERAL,
}

#: Product base names per subcategory, with a plausible price range in euros
#: and the unit they are sold in.
#:
#: Format: subcategory -> [(base name, unit, min price, max price)]
PRODUCT_BASES = {
    "Frutas y verduras": [
        ("Manzana Golden", "kg", 1.4, 2.6), ("Plátano de Canarias", "kg", 1.6, 2.9),
        ("Tomate pera", "kg", 1.5, 3.2), ("Patata", "kg", 0.8, 1.6),
        ("Cebolla", "kg", 0.9, 1.7), ("Naranja de mesa", "kg", 1.2, 2.4),
        ("Lechuga romana", "ud", 0.9, 1.6), ("Pimiento rojo", "kg", 2.1, 3.8),
        ("Zanahoria", "kg", 0.9, 1.5), ("Calabacín", "kg", 1.3, 2.4),
    ],
    "Carnicería": [
        ("Pechuga de pollo", "kg", 5.5, 8.9), ("Solomillo de cerdo", "kg", 8.9, 13.5),
        ("Carne picada mixta", "kg", 5.9, 8.5), ("Chuleta de cordero", "kg", 12.9, 19.5),
        ("Filete de ternera", "kg", 11.5, 17.9), ("Muslo de pollo", "kg", 3.2, 5.4),
    ],
    "Pescadería": [
        ("Merluza fresca", "kg", 8.9, 14.5), ("Salmón fresco", "kg", 9.9, 15.9),
        ("Gambas cocidas", "kg", 11.5, 18.9), ("Dorada", "kg", 7.5, 12.5),
        ("Bacalao desalado", "kg", 10.9, 16.5),
    ],
    "Charcutería": [
        ("Jamón serrano lonchas", "ud", 2.5, 5.9), ("Chorizo ibérico", "ud", 3.2, 6.8),
        ("Pavo en lonchas", "ud", 1.8, 3.6), ("Queso curado cuña", "ud", 3.9, 8.5),
        ("Salchichón", "ud", 2.4, 5.2),
    ],
    "Panadería": [
        ("Barra de pan", "ud", 0.6, 1.3), ("Pan de molde integral", "ud", 1.4, 2.6),
        ("Croissant", "ud", 0.8, 1.9), ("Chapata", "ud", 0.9, 1.8),
        ("Magdalenas", "pack", 1.6, 3.2),
    ],
    "Lácteos": [
        ("Leche entera", "L", 0.8, 1.5), ("Leche semidesnatada", "L", 0.8, 1.5),
        ("Yogur natural", "pack", 1.2, 2.6), ("Mantequilla", "ud", 1.9, 3.8),
        ("Queso fresco batido", "ud", 1.4, 2.8), ("Nata para cocinar", "ud", 0.9, 1.9),
    ],
    "Huevos": [("Huevos frescos M", "pack", 1.8, 3.4), ("Huevos camperos L", "pack", 2.6, 4.5)],
    "Pasta y arroz": [
        ("Espaguetis", "ud", 0.8, 1.9), ("Macarrones", "ud", 0.8, 1.9),
        ("Arroz redondo", "kg", 1.1, 2.4), ("Arroz integral", "kg", 1.5, 3.1),
        ("Fideos finos", "ud", 0.7, 1.6),
    ],
    "Conservas": [
        ("Atún claro en aceite", "pack", 1.9, 4.5), ("Tomate triturado", "ud", 0.7, 1.6),
        ("Maíz dulce", "ud", 0.8, 1.7), ("Berberechos", "ud", 2.9, 7.5),
        ("Piña en almíbar", "ud", 1.2, 2.4),
    ],
    "Aceites y vinagres": [
        ("Aceite de oliva virgen extra", "L", 6.5, 11.9), ("Aceite de girasol", "L", 1.6, 3.2),
        ("Vinagre de Jerez", "ud", 1.4, 3.6),
    ],
    "Salsas y especias": [
        ("Tomate frito", "ud", 0.9, 1.9), ("Mayonesa", "ud", 1.4, 2.9),
        ("Pimentón dulce", "ud", 1.1, 2.4), ("Sal marina", "kg", 0.5, 1.2),
        ("Orégano", "ud", 0.9, 1.8),
    ],
    "Cereales": [("Cereales de desayuno", "ud", 2.1, 4.5), ("Avena en copos", "ud", 1.4, 2.9)],
    "Galletas y bollería": [
        ("Galletas María", "ud", 0.9, 2.1), ("Galletas de chocolate", "ud", 1.4, 3.2),
        ("Bizcocho", "ud", 1.8, 3.6),
    ],
    "Snacks": [
        ("Patatas fritas", "ud", 1.1, 2.9), ("Frutos secos mezcla", "ud", 2.4, 5.5),
        ("Aceitunas rellenas", "ud", 0.9, 2.2),
    ],
    "Legumbres": [
        ("Garbanzos cocidos", "ud", 0.8, 1.8), ("Lentejas", "kg", 1.3, 2.8),
        ("Alubias blancas", "ud", 0.9, 1.9),
    ],
    "Azúcar y endulzantes": [("Azúcar blanco", "kg", 0.9, 1.8), ("Miel", "ud", 3.2, 6.9)],
    "Agua": [("Agua mineral", "pack", 1.2, 3.4), ("Agua con gas", "pack", 1.6, 3.9)],
    "Refrescos": [
        ("Refresco de cola", "pack", 2.4, 5.9), ("Refresco de naranja", "pack", 2.2, 5.4),
        ("Tónica", "pack", 2.6, 5.5),
    ],
    "Cerveza": [("Cerveza rubia", "pack", 2.9, 7.5), ("Cerveza sin alcohol", "pack", 2.6, 6.2)],
    "Vino": [
        ("Vino tinto Rioja", "ud", 3.9, 14.5), ("Vino blanco Rueda", "ud", 3.5, 11.9),
        ("Vino rosado Navarra", "ud", 2.9, 8.9),
    ],
    "Zumos": [("Zumo de naranja", "L", 1.2, 2.8), ("Néctar de melocotón", "L", 1.1, 2.4)],
    "Café e infusiones": [
        ("Café molido natural", "ud", 2.6, 6.9), ("Cápsulas de café", "pack", 2.9, 7.5),
        ("Infusión manzanilla", "ud", 1.1, 2.6),
    ],
    "Licores": [("Ginebra", "ud", 9.9, 24.5), ("Ron añejo", "ud", 9.5, 22.9)],
    "Verduras congeladas": [("Guisantes congelados", "ud", 1.2, 2.6), ("Menestra congelada", "ud", 1.4, 3.1)],
    "Pescado congelado": [("Merluza congelada", "ud", 3.4, 7.9), ("Langostinos congelados", "ud", 5.9, 13.5)],
    "Helados": [("Helado de vainilla", "ud", 2.4, 5.5), ("Polos de hielo", "pack", 1.9, 4.2)],
    "Platos preparados": [("Pizza congelada", "ud", 2.1, 5.4), ("Croquetas", "ud", 2.4, 5.2)],
    "Detergentes": [("Detergente líquido", "ud", 3.9, 9.5), ("Suavizante", "ud", 2.1, 5.4)],
    "Limpieza del hogar": [
        ("Lejía", "L", 0.9, 2.1), ("Limpiacristales", "ud", 1.6, 3.4),
        ("Fregasuelos", "ud", 1.8, 3.9),
    ],
    "Papel y celulosa": [
        ("Papel higiénico", "pack", 2.9, 8.5), ("Rollo de cocina", "pack", 1.9, 4.9),
        ("Servilletas", "pack", 0.9, 2.4),
    ],
    "Lavavajillas": [("Pastillas lavavajillas", "pack", 3.9, 9.9), ("Lavavajillas a mano", "ud", 1.2, 2.9)],
    "Insecticidas": [("Insecticida volador", "ud", 3.2, 6.9)],
    "Higiene bucal": [("Pasta de dientes", "ud", 1.6, 4.2), ("Cepillo de dientes", "ud", 1.4, 3.9)],
    "Cuidado capilar": [("Champú", "ud", 1.9, 5.9), ("Acondicionador", "ud", 2.1, 5.5)],
    "Cuidado corporal": [("Gel de ducha", "ud", 1.6, 4.5), ("Crema hidratante", "ud", 2.9, 8.9)],
    "Afeitado": [("Cuchillas de afeitar", "pack", 4.5, 12.9), ("Espuma de afeitar", "ud", 1.9, 4.2)],
    "Higiene íntima": [("Compresas", "pack", 1.9, 4.5), ("Protegeslips", "pack", 1.4, 3.2)],
    "Cosmética": [("Desodorante", "ud", 1.9, 4.9), ("Protector solar", "ud", 6.9, 16.5)],
    "Pañales": [("Pañales talla 3", "pack", 6.9, 14.5), ("Toallitas infantiles", "pack", 1.4, 3.6)],
    "Alimentación infantil": [("Potito de frutas", "ud", 0.9, 2.1), ("Leche de continuación", "ud", 8.9, 17.5)],
    "Higiene infantil": [("Gel infantil", "ud", 2.4, 5.5)],
    "Perros": [("Pienso para perro", "kg", 1.9, 4.9), ("Snacks para perro", "ud", 1.6, 4.2)],
    "Gatos": [("Pienso para gato", "kg", 2.4, 5.9), ("Arena para gato", "ud", 3.2, 7.9)],
    "Otros animales": [("Alimento para pájaros", "ud", 2.1, 4.9)],
    "Menaje": [("Sartén antiadherente", "ud", 8.9, 24.9), ("Vaso de cristal", "ud", 1.2, 3.4)],
    "Bazar": [("Pilas AA", "pack", 2.4, 6.9), ("Bolsas de basura", "pack", 1.4, 3.6)],
    "Iluminación": [("Bombilla LED", "ud", 2.9, 7.9)],
}

#: Invented own-brand and supplier names, built the way Spanish grocery
#: brands are -- a place, a family name, or a rural noun.
BRANDS = [
    "Campo Sur", "Doña Elena", "La Almazara", "Vega Real", "Monteclaro",
    "Buenamesa", "Selecta", "Origen", "Casa Robles", "El Molinar",
    "Ribera Alta", "Tierra Nuestra", "Los Almendros", "Valdehermoso",
    "Puente Viejo", "Sabor de Antaño",
]

SUPPLIER_SUFFIXES = ["S.L.", "S.A.", "e Hijos S.L.", "Distribuciones S.L.", "Ibérica S.A."]

STORE_FORMATS = {"Supermercado": 55, "Hipermercado": 15, "Express": 30}

PAYMENT_METHODS = {"card": 62, "cash": 26, "mobile": 9, "voucher": 3}

CUSTOMER_SEGMENTS = {"regular": 46, "occasional": 31, "premium": 15, "new": 8}

EMPLOYEE_ROLES = {
    "Cashier": 40, "Shelf stacker": 22, "Butcher": 8, "Fishmonger": 6,
    "Baker": 6, "Department manager": 10, "Store manager": 3, "Security": 5,
}

PROMOTION_TYPES = {"percentage": 52, "second_unit_half_price": 24,
                   "three_for_two": 14, "fixed_discount": 10}


# ===========================================================================
# PART 2 -- THE SCHEMA
# ===========================================================================

STORES = Entity(
    name="stores",
    topic="supermarket",
    grain="One row per physical store in the chain.",
    description=(
        "The shops themselves. Everything operational hangs off a store: "
        "staff work at one, stock is counted per store, and every till "
        "transaction happens at one."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. This is "
                          "what every other table joins against."),
        Field("code", "string", unique=True, pattern=r"^STO-\d{4}$", example="STO-0001",
              description="Internal store code as it appears on receipts and "
                          "delivery notes. Humans quote this rather than the "
                          "numeric id."),
        Field("name", "string", unique=True, example="Supermercado Vega Real Sevilla",
              description="Trading name, combining the store format with a "
                          "brand and the city it serves. Invented -- no real "
                          "retail chain is named here."),
        Field("format", "enum", values=sorted(STORE_FORMATS), example="Supermercado",
              description="Store size band. Hipermercados carry the full "
                          "range and the most staff; Express shops are small "
                          "city-centre outlets with a reduced assortment."),
        Field("city", "string", example="Sevilla",
              description="Spanish city the store is located in, drawn from "
                          "real municipalities weighted by population."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province the city belongs to. Always agrees with "
                          "the first two digits of the postal code, since both "
                          "derive from the same choice of city."),
        Field("address", "string", example="Avenida de Andalucía, 118",
              description="Street address in Spanish format, with the number "
                          "following the street name. Invented."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41009",
              description="Spanish postal code whose leading pair is the "
                          "province code, so it always matches the province "
                          "column beside it."),
        Field("phone", "string", example="+34 954 21 08 33",
              description="Store telephone. The dialling prefix matches the "
                          "province, exactly as a real Spanish landline does."),
        Field("floor_area_sqm", "integer", unit="m²", example=1450,
              description="Sales floor area in square metres, correlated with "
                          "the store format -- Express shops run about 300 m², "
                          "Hipermercados several thousand."),
        Field("opened_at", "date", example="2014-03-17",
              description="Date the store first opened for trade, spread "
                          "across the twenty years before the dataset period."),
    ],
    notes=[
        "Floor area tracks `format`, so grouping by format and averaging the "
        "area produces a sensible chart rather than noise.",
    ],
)

CATEGORIES = Entity(
    name="categories",
    topic="supermarket",
    grain="One row per product category, at any level of the hierarchy.",
    description=(
        "A two-level product taxonomy stored as a self-referencing tree. Top "
        "level rows are the aisles ('Frescos', 'Bebidas') and have no parent; "
        "the rest are the shelves within them and point back at their aisle. "
        "This is the table to use when testing recursive queries, breadcrumb "
        "rendering or tree-shaped UI components."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Parents "
                          "always have a lower id than their children, so a "
                          "simple ordered insert works."),
        Field("name", "string", example="Frutas y verduras",
              description="Category name in Spanish, as it would appear on the "
                          "aisle sign. Names are unique within a parent but not "
                          "globally, which is realistic and worth testing."),
        Field("parent_id", "integer", nullable=True, references="categories.id",
              example=1,
              description="The aisle this shelf belongs to, or empty for the "
                          "nine top-level aisles. This is the self-reference "
                          "that makes the table a tree."),
        Field("level", "integer", example=2,
              description="Depth in the tree: 1 for an aisle, 2 for a shelf "
                          "within it. Stored so you can filter to one level "
                          "without walking the hierarchy."),
        Field("vat_rate", "decimal", unit="fraction", example=0.04,
              description="The Spanish VAT band products in this category "
                          "attract: 0.04 superreducido for staples, 0.10 "
                          "reducido for most food, 0.21 general for non-food. "
                          "Inherited from the parent aisle."),
    ],
    notes=[
        "Spain charges three different VAT rates on supermarket goods. Bread, "
        "milk, eggs, fruit and vegetables sit in the 4% band; most other food "
        "is 10%; cleaning products, alcohol and household goods are 21%. Tax "
        "calculations over this data therefore produce believable totals.",
    ],
)

SUPPLIERS = Entity(
    name="suppliers",
    topic="supermarket",
    grain="One row per company that supplies products to the chain.",
    description=(
        "Wholesalers and producers. Every product is bought from exactly one "
        "supplier, so this is the table to join through when answering "
        "questions about sourcing or lead times."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("name", "string", unique=True, example="Campo Sur Distribuciones S.L.",
              description="Company name in Spanish commercial form, ending in "
                          "S.L. or S.A. -- the Spanish equivalents of Ltd and "
                          "PLC. All invented."),
        Field("tax_id", "string", unique=True, pattern=r"^[A-Z]\d{8}$", example="B12345678",
              description="Spanish CIF, the company tax identifier. The leading "
                          "letter encodes the company type -- B for S.L., A for "
                          "S.A. Invented and not registered to anybody."),
        Field("city", "string", example="Valencia",
              description="Spanish city the supplier operates from, which is "
                          "often where the produce itself originates."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Valencia",
              description="Province of the supplier's registered address, "
                          "consistent with its postal code."),
        Field("phone", "string", example="+34 963 55 12 04",
              description="Commercial contact number, with a dialling prefix "
                          "matching the supplier's own province."),
        Field("email", "string", example="pedidos@campo-sur.example.com",
              description="Orders inbox on the reserved example.com domain, so "
                          "nothing sent here could reach a real business."),
        Field("lead_time_days", "integer", unit="days", example=3,
              description="Working days between placing an order and receiving "
                          "it, from 1 for local fresh produce to 21 for "
                          "imported goods."),
        Field("active", "boolean", example=True,
              description="Whether the chain still buys from this supplier. "
                          "About 8% are dormant, which gives you rows that "
                          "should be filtered out of an ordering screen."),
    ],
)

EMPLOYEES = Entity(
    name="employees",
    topic="supermarket",
    grain="One row per member of store staff.",
    description=(
        "Shop-floor and management staff, each assigned to one store. "
        "Cashiers appear as the operator on till transactions, which is what "
        "links this table into the sales data."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("store_id", "integer", references="stores.id", example=1,
              description="The store this person works at. Everybody is "
                          "assigned to exactly one store in this dataset."),
        Field("employee_code", "string", unique=True, pattern=r"^EMP-\d{5}$",
              example="EMP-00042",
              description="Payroll reference, the number that appears on a "
                          "rota and on the bottom of a till receipt."),
        Field("full_name", "string", example="Javier Moreno Ortega",
              description="Spanish name with two surnames -- the father's "
                          "followed by the mother's -- which is worth testing "
                          "any name-splitting code against."),
        Field("national_id", "string", unique=True, pattern=r"^\d{8}[A-Z]$",
              example="12345678Z",
              description="Spanish DNI, eight digits plus a check letter "
                          "computed modulo 23. Structurally valid, so it passes "
                          "a real DNI validator."),
        Field("role", "enum", values=sorted(EMPLOYEE_ROLES), example="Cashier",
              description="Job title. Cashiers dominate, as they do in a real "
                          "shop, and only they appear as transaction "
                          "operators."),
        Field("hired_at", "date", example="2021-09-06",
              description="Start date, always on or after the store's own "
                          "opening date -- nobody was hired into a shop that "
                          "did not exist."),
        Field("hourly_rate", "decimal", unit="EUR", example=11.40,
              description="Gross pay per hour in euros, from around the "
                          "Spanish minimum wage for shop-floor roles up to "
                          "about 25 for a store manager."),
        Field("active", "boolean", example=True,
              description="Whether the person still works here. Around 12% "
                          "have left, which is a realistic retail turnover "
                          "rate and gives you inactive rows to exclude."),
    ],
)

PRODUCTS = Entity(
    name="products",
    topic="supermarket",
    grain="One row per distinct product line carried by the chain.",
    description=(
        "The catalogue. Every product has a scannable EAN-13 barcode, a "
        "category, a supplier and a shelf price. This is the anchor table for "
        "anything to do with what the shop sells."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1. Use this "
                          "for joins rather than the SKU or the barcode."),
        Field("sku", "string", unique=True, pattern=r"^SKU-\d{6}$", example="SKU-001337",
              description="Internal stock-keeping unit. The chain's own "
                          "reference, used on shelf labels and in ordering."),
        Field("ean13", "string", unique=True, pattern=r"^\d{13}$",
              example="8412345678905",
              description="The printed barcode, thirteen digits with a correct "
                          "check digit -- so a barcode library will actually "
                          "decode it instead of rejecting it. The leading 84 "
                          "is the GS1 country prefix for Spain."),
        Field("name", "string", example="Aceite de oliva virgen extra Campo Sur 1L",
              description="Shelf name in Spanish: what the product is, the "
                          "brand, and the pack size, exactly as a price label "
                          "would read."),
        Field("category_id", "integer", references="categories.id", example=12,
              description="The shelf this product sits on. Always a level-2 "
                          "category, never a top-level aisle."),
        Field("supplier_id", "integer", references="suppliers.id", example=7,
              description="Who the chain buys this product from. One supplier "
                          "per product line."),
        Field("brand", "string", example="Campo Sur",
              description="Own-brand or supplier brand name. All sixteen are "
                          "invented and none corresponds to a real grocery "
                          "brand."),
        Field("unit", "enum", values=["ud", "kg", "L", "pack"], example="L",
              description="How the product is sold: by the item (ud), by "
                          "weight (kg), by volume (L) or as a multipack. This "
                          "determines whether a quantity can be fractional."),
        Field("unit_price", "decimal", unit="EUR", example=7.99,
              description="Shelf price including VAT, in euros. Prices end in "
                          ".99, .95 or .49 far more often than chance, because "
                          "retailers really do price that way."),
        Field("cost_price", "decimal", unit="EUR", example=5.60,
              description="What the chain pays the supplier per unit. Always "
                          "below unit_price, giving a gross margin between "
                          "about 12% and 45% depending on category."),
        Field("vat_rate", "decimal", unit="fraction", example=0.10,
              description="Spanish VAT band applied at the till, inherited "
                          "from the product's category. One of 0.04, 0.10 or "
                          "0.21."),
        Field("active", "boolean", example=True,
              description="Whether the line is still listed. Roughly 7% are "
                          "discontinued but retained for historical sales, "
                          "which is exactly why old transactions can still "
                          "reference them."),
    ],
    notes=[
        "A product's `vat_rate` always equals its category's `vat_rate`. "
        "Storing it on both is deliberate denormalisation -- it is what a "
        "real till system does so that a historical receipt keeps the rate "
        "that applied on the day -- and it gives you a consistency rule to "
        "verify.",
        "Discontinued products still appear in older transactions. Filtering "
        "products to `active = true` and joining to sales will therefore lose "
        "rows, which is a mistake worth being able to reproduce.",
    ],
)

INVENTORY = Entity(
    name="inventory",
    topic="supermarket",
    grain="One row per product held at one store.",
    description=(
        "Current stock levels, one row per store-and-product combination. "
        "Not every store carries every product -- Express shops carry a "
        "fraction of the range -- so this table is much smaller than stores "
        "multiplied by products."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("store_id", "integer", references="stores.id", example=1,
              description="Which store holds this stock. Stock is counted per "
                          "store, never centrally, so the same product appears "
                          "once for every shop that lists it."),
        Field("product_id", "integer", references="products.id", example=42,
              description="Which product is being counted. Only active product "
                          "lines are stocked, so discontinued items have no "
                          "inventory row anywhere."),
        Field("quantity_on_hand", "integer", unit="units", example=48,
              description="Units currently on the shelf and in the back room. "
                          "Can be zero, and about 4% of rows are -- an "
                          "out-of-stock line you should be able to surface."),
        Field("reorder_level", "integer", unit="units", example=20,
              description="The threshold at which the system should raise a "
                          "replenishment order. Comparing this with "
                          "quantity_on_hand gives you a ready-made 'needs "
                          "reordering' query."),
        Field("last_restocked_at", "date", example="2025-06-12",
              description="Date of the most recent delivery for this line at "
                          "this store. Fast-moving fresh goods are restocked "
                          "far more recently than bazar items."),
    ],
)

CUSTOMERS = Entity(
    name="customers",
    topic="supermarket",
    grain="One row per loyalty-card holder.",
    description=(
        "Registered customers. Only loyalty-card holders appear here, so many "
        "transactions have no customer at all -- which is realistic and makes "
        "this a natural LEFT JOIN test case."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("loyalty_card", "string", unique=True, pattern=r"^LC-\d{9}$",
              example="LC-000004217",
              description="The number printed on the physical loyalty card, "
                          "which is what a cashier scans at the till."),
        Field("full_name", "string", example="Carmen Ibáñez Soler",
              description="Spanish name with both surnames, as it would be "
                          "captured on a loyalty application form."),
        Field("email", "string", nullable=True, example="carmen.ibanez@example.com",
              description="Contact address on the reserved example.com domain, "
                          "with accents transliterated away. Empty for about "
                          "15% of customers who never supplied one."),
        Field("phone", "string", nullable=True, example="+34 622 41 07 93",
              description="Mostly Spanish mobile numbers, since that is what "
                          "people give a shop. Empty for around 9% of rows."),
        Field("city", "string", example="Sevilla",
              description="Spanish city of residence, which is usually but not "
                          "always the city of the store they shop at."),
        Field("province", "enum", values=sorted(set(PROVINCES.values())), example="Sevilla",
              description="Province of residence, consistent with the postal "
                          "code in the next column."),
        Field("postal_code", "string", pattern=r"^\d{5}$", example="41009",
              description="Spanish postal code whose first two digits are the "
                          "province code, so address validation passes."),
        Field("birth_date", "date", nullable=True, example="1986-04-22",
              description="Date of birth where the customer gave one, used for "
                          "age-band marketing. Empty for about 20% of rows."),
        Field("segment", "enum", values=sorted(CUSTOMER_SEGMENTS), example="regular",
              description="Marketing segment derived from spend and visit "
                          "frequency. Premium customers really do spend more "
                          "per basket in this data, so the segmentation is "
                          "worth plotting."),
        Field("signed_up_at", "date", example="2023-04-18",
              description="Date the loyalty card was issued. Always on or "
                          "before that customer's first transaction."),
    ],
)

PROMOTIONS = Entity(
    name="promotions",
    topic="supermarket",
    grain="One row per promotional offer on one product.",
    description=(
        "Time-limited offers. A promotion covers a single product over a date "
        "range, so checking whether a given sale was discounted means "
        "comparing the transaction date against this table."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("product_id", "integer", references="products.id", example=42,
              description="The product on offer. A product can have several "
                          "promotions over time, but they never overlap."),
        Field("type", "enum", values=sorted(PROMOTION_TYPES), example="percentage",
              description="Mechanic of the offer: a straight percentage off, "
                          "second unit at half price, three for the price of "
                          "two, or a fixed cash reduction."),
        Field("discount_percent", "decimal", unit="percent", example=25.00,
              description="Headline reduction as a percentage, between 5 and "
                          "50. For non-percentage mechanics this records the "
                          "effective equivalent saving."),
        Field("starts_on", "date", example="2025-03-01",
              description="First day the offer is live, inclusive. Compare a "
                          "sale date against this and ends_on to decide "
                          "whether a line was discounted."),
        Field("ends_on", "date", example="2025-03-31",
              description="Last day the offer is live, inclusive. Always after "
                          "starts_on, typically by one to six weeks."),
    ],
)

TRANSACTIONS = Entity(
    name="transactions",
    topic="supermarket",
    grain="One row per completed till transaction.",
    description=(
        "The basket header: who bought, where, when, how they paid and what "
        "it came to. The individual products are in transaction_items, and "
        "the totals here are guaranteed to equal the sum of those lines."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1 and "
                          "ordered by time, so a higher id is always a later "
                          "sale."),
        Field("receipt_number", "string", unique=True, pattern=r"^\d{4}-\d{8}$",
              example="0001-00004217",
              description="The number printed on the receipt: store code, then "
                          "a sequence. This is what a customer quotes when "
                          "returning something."),
        Field("store_id", "integer", references="stores.id", example=1,
              description="Which shop rang up the sale. Always a store that "
                          "had already opened on the transaction date, and the "
                          "store the cashier works at."),
        Field("customer_id", "integer", nullable=True, references="customers.id",
              example=42,
              description="The loyalty-card holder, or empty for an anonymous "
                          "sale. About 45% of transactions have no customer, "
                          "which is realistic and makes this the table's main "
                          "LEFT JOIN case."),
        Field("cashier_id", "integer", references="employees.id", example=7,
              description="The employee who operated the till. Always someone "
                          "whose role is Cashier and who works at this store."),
        Field("occurred_at", "datetime", example="2025-03-14T18:42:00",
              description="Date and time of the sale. Trading hours are 09:00 "
                          "to 21:30, with the familiar lunchtime and early "
                          "evening peaks and a much busier Saturday."),
        Field("payment_method", "enum", values=sorted(PAYMENT_METHODS), example="card",
              description="How the basket was paid for. Card dominates, as it "
                          "now does in Spain, with cash still meaningful and "
                          "mobile payment growing."),
        Field("item_count", "integer", unit="lines", example=7,
              description="Number of distinct product lines in the basket, "
                          "matching the row count in transaction_items. Most "
                          "baskets are small; a weekly shop is much larger."),
        Field("subtotal", "decimal", unit="EUR", example=41.32,
              description="Total before VAT, in euros. Equals the sum of the "
                          "line totals minus the VAT those lines carry."),
        Field("vat_amount", "decimal", unit="EUR", example=4.94,
              description="Total VAT across the basket. Because products "
                          "attract different rates, this is not a fixed "
                          "percentage of the subtotal -- which is precisely "
                          "what makes it worth testing against."),
        Field("total", "decimal", unit="EUR", example=46.26,
              description="What the customer actually paid. Always exactly "
                          "equal to the sum of the line totals in "
                          "transaction_items, verified to the cent in CI."),
    ],
    notes=[
        "The money invariant: for every transaction, the sum of its line "
        "totals equals `total`, and `subtotal` plus `vat_amount` equals "
        "`total`. Both are asserted in the test suite. Totals that do not "
        "reconcile are the single most common flaw in generated retail data.",
        "Transaction volume rises on Fridays and Saturdays and dips on "
        "Mondays. Plot sales by weekday and you get the shape of a real "
        "trading week.",
    ],
)

TRANSACTION_ITEMS = Entity(
    name="transaction_items",
    topic="supermarket",
    grain="One row per product scanned at the till within one transaction.",
    description=(
        "The basket lines -- by far the largest table in this topic and the "
        "one to use when you need volume. Each row is one product, its "
        "quantity, and what it came to after any discount."
    ),
    fields=[
        Field("id", "integer", primary_key=True, example=1,
              description="Surrogate primary key, sequential from 1."),
        Field("transaction_id", "integer", references="transactions.id", example=1,
              description="The basket this line belongs to. Grouping by this "
                          "column reconstructs the receipt."),
        Field("line_number", "integer", example=1,
              description="Position of this line on the printed receipt, "
                          "starting at 1 within each transaction."),
        Field("product_id", "integer", references="products.id", example=42,
              description="What was scanned. The same product can appear only "
                          "once per transaction, as a till would merge "
                          "duplicates into one line."),
        Field("quantity", "decimal", unit="units", example=2.00,
              description="How many were bought. Whole numbers for items sold "
                          "by the unit, and fractional for anything priced by "
                          "the kilo -- 0.84 kg of tomatoes is a real line."),
        Field("unit_price", "decimal", unit="EUR", example=7.99,
              description="Price per unit at the moment of sale, copied from "
                          "the product. Stored rather than looked up, because "
                          "a receipt must keep the price that was charged even "
                          "after the shelf price changes."),
        Field("discount_percent", "decimal", unit="percent", example=0.00,
              description="Reduction applied to this line, from an active "
                          "promotion. Zero on about 88% of lines."),
        Field("vat_rate", "decimal", unit="fraction", example=0.10,
              description="VAT band for this line, copied from the product at "
                          "the time of sale for the same historical-accuracy "
                          "reason as unit_price."),
        Field("line_total", "decimal", unit="EUR", example=15.98,
              description="Quantity times unit price, less the discount, "
                          "rounded to the cent. Summing this column within a "
                          "transaction gives exactly that transaction's total."),
    ],
)


# ===========================================================================
# PART 3 -- THE GENERATOR
# ===========================================================================

def _strip_accents(text: str) -> str:
    """Remove Spanish diacritics so a name can become an email address."""
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _email_from_name(full_name: str, domain: str, rng: Rng) -> str:
    """first.surname@domain, accents removed, using the FIRST surname."""
    parts = [part.lower() for part in _strip_accents(full_name).split() if part]
    stem = ".".join(parts[:2]) if len(parts) >= 2 else parts[0]
    suffix = "" if rng.python.random() > 0.08 else str(rng.python.randint(2, 9))
    return f"{stem}{suffix}@{domain}"


def _retail_price(rng: Rng, low: float, high: float) -> Decimal:
    """A price in the given range, ending the way retail prices really do.

    Shops overwhelmingly price at .99, .95 and .49 rather than at round
    numbers -- "psychological pricing". Generating a uniform random price to
    two decimal places is one of the clearest giveaways of synthetic retail
    data, because .37 and .61 almost never appear on a real shelf edge.
    """
    base = rng.python.uniform(low, high)
    ending = rng.weighted_choice({99: 46, 95: 18, 49: 14, 50: 8, 0: 6, 25: 4, 75: 4})
    whole = int(base)
    price = Decimal(whole) + Decimal(ending) / Decimal(100)
    # Keep it inside the intended band even after the ending is applied.
    if float(price) < low:
        price += Decimal(1)
    return price.quantize(Decimal("0.01"))


def _generate_stores(count: int) -> list[dict[str, Any]]:
    rng = Rng("supermarket", "stores")

    area_by_format = {"Express": (300, 90), "Supermercado": (1400, 350),
                      "Hipermercado": (6500, 1800)}

    rows = []
    used_names: set[str] = set()
    for index in range(1, count + 1):
        store_format = rng.weighted_choice(STORE_FORMATS)
        location = generate_address(rng, with_phone=True)

        mean, sd = area_by_format[store_format]
        area = int(max(180, rng.numpy.normal(mean, sd)))

        name = f"{store_format} {rng.python.choice(BRANDS)} {location['city']}"
        while name in used_names:
            name = f"{store_format} {rng.python.choice(BRANDS)} {location['city']}"
        used_names.add(name)

        rows.append({
            "id": index,
            "code": f"STO-{index:04d}",
            "name": name,
            "format": store_format,
            "city": location["city"],
            "province": location["province"],
            "address": location["address"],
            "postal_code": location["postal_code"],
            "phone": location["phone"],
            "floor_area_sqm": area,
            "opened_at": rng.date_between(date(2003, 1, 1), date(2022, 12, 31)),
        })
    return rows


def _generate_categories(count: int) -> list[dict[str, Any]]:
    """Build the two-level category tree.

    Parents are emitted before children so that `parent_id` always points at
    a row that already exists -- which matters because SQLite enforces the
    self-referencing foreign key during insertion.
    """
    rows: list[dict[str, Any]] = []
    next_id = 1
    parent_ids: dict[str, int] = {}

    for top_name in CATEGORY_TREE:
        rows.append({
            "id": next_id,
            "name": top_name,
            "parent_id": None,
            "level": 1,
            "vat_rate": VAT_BY_TOP_CATEGORY[top_name],
        })
        parent_ids[top_name] = next_id
        next_id += 1

    for top_name, children in CATEGORY_TREE.items():
        for child_name in children:
            if len(rows) >= count:
                return rows
            rows.append({
                "id": next_id,
                "name": child_name,
                "parent_id": parent_ids[top_name],
                "level": 2,
                "vat_rate": VAT_BY_TOP_CATEGORY[top_name],
            })
            next_id += 1

    return rows


def _generate_suppliers(count: int) -> list[dict[str, Any]]:
    rng = Rng("supermarket", "suppliers")

    rows = []
    used_names: set[str] = set()
    for index in range(1, count + 1):
        location = generate_address(rng, with_phone=True)

        name = f"{rng.python.choice(BRANDS)} {rng.python.choice(SUPPLIER_SUFFIXES)}"
        while name in used_names:
            name = f"{rng.python.choice(BRANDS)} {rng.python.choice(SUPPLIER_SUFFIXES)}"
        used_names.add(name)

        slug = _strip_accents(name.split()[0]).lower()
        # Spanish CIF: a letter for the company type, then eight digits.
        # B is a sociedad limitada, A a sociedad anónima.
        company_letter = "A" if "S.A." in name else "B"

        rows.append({
            "id": index,
            "name": name,
            "tax_id": f"{company_letter}{rng.python.randint(10_000_000, 99_999_999)}",
            "city": location["city"],
            "province": location["province"],
            "phone": location["phone"],
            # The company goes in the LOCAL part, not as a subdomain: the
            # guarantee this repository makes is that every address is on a
            # domain reserved by RFC 2606, and "x.example.com" is a
            # subdomain rather than the reserved domain itself.
            "email": f"pedidos.{slug}{index}@example.com",
            "lead_time_days": rng.weighted_choice(
                {1: 18, 2: 22, 3: 20, 5: 15, 7: 12, 10: 7, 14: 4, 21: 2}
            ),
            "active": rng.python.random() > 0.08,
        })
    return rows


def _generate_employees(stores: list[dict], count: int) -> list[dict[str, Any]]:
    from ..common.identifiers import dni

    rng = Rng("supermarket", "employees")

    rate_by_role = {
        "Cashier": (10.2, 1.1), "Shelf stacker": (9.8, 0.9),
        "Butcher": (13.5, 1.6), "Fishmonger": (13.1, 1.5),
        "Baker": (12.4, 1.3), "Department manager": (16.8, 2.2),
        "Store manager": (24.5, 3.4), "Security": (11.2, 1.2),
    }

    rows = []
    for index in range(1, count + 1):
        store = rng.python.choice(stores)
        role = rng.weighted_choice(EMPLOYEE_ROLES)

        is_female = rng.python.random() < 0.58  # retail skews female in Spain
        full_name = rng.faker.name_female() if is_female else rng.faker.name_male()

        mean, sd = rate_by_role[role]
        rows.append({
            "id": index,
            "store_id": store["id"],
            "employee_code": f"EMP-{index:05d}",
            "full_name": full_name,
            "national_id": dni(rng),
            "role": role,
            # Nobody can be hired before the shop opened.
            "hired_at": rng.date_between(
                max(store["opened_at"], date(2010, 1, 1)), date(2025, 5, 31)
            ),
            "hourly_rate": round(max(9.0, rng.numpy.normal(mean, sd)), 2),
            "active": rng.python.random() > 0.12,
        })
    return rows


def _generate_products(
    categories: list[dict], suppliers: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("supermarket", "products")

    # Only level-2 categories hold products; an aisle itself does not.
    shelves = [row for row in categories if row["level"] == 2]
    active_suppliers = [row for row in suppliers if row["active"]] or suppliers

    # Gross margin varies sharply by aisle: fresh produce is thin, household
    # goods are fat. This is what makes a margin-by-category chart informative.
    margin_by_shelf_default = (0.18, 0.05)
    margin_overrides = {
        "Frutas y verduras": (0.14, 0.04), "Carnicería": (0.13, 0.03),
        "Pescadería": (0.12, 0.03), "Panadería": (0.35, 0.06),
        "Menaje": (0.42, 0.08), "Bazar": (0.44, 0.09),
        "Cosmética": (0.38, 0.07), "Licores": (0.30, 0.06),
    }

    sizes = {"ud": ["", "", ""], "kg": ["", "500g", "1kg"],
             "L": ["1L", "1.5L", "2L"], "pack": ["pack 6", "pack 12", "pack 4"]}

    rows = []
    used_names: set[str] = set()
    used_eans: set[str] = set()

    for index in range(1, count + 1):
        shelf = rng.python.choice(shelves)
        bases = PRODUCT_BASES.get(shelf["name"])
        if not bases:
            continue

        base_name, unit, low, high = rng.python.choice(bases)
        brand = rng.python.choice(BRANDS)
        size = rng.python.choice(sizes[unit])
        name = " ".join(part for part in (base_name, brand, size) if part)

        if name in used_names:
            name = f"{name} {rng.python.randint(2, 99)}"
        used_names.add(name)

        unit_price = _retail_price(rng, low, high)

        mean_margin, sd_margin = margin_overrides.get(
            shelf["name"], margin_by_shelf_default
        )
        margin = min(0.6, max(0.05, rng.numpy.normal(mean_margin, sd_margin)))
        cost_price = (unit_price * Decimal(str(1 - margin))).quantize(Decimal("0.01"))

        # EAN-13 beginning 84, the GS1 country prefix for Spain.
        while True:
            body = f"84{rng.python.randint(0, 9_999_999_999):010d}"
            barcode = ean13(body)
            if barcode not in used_eans:
                used_eans.add(barcode)
                break

        rows.append({
            "id": index,
            "sku": f"SKU-{index:06d}",
            "ean13": barcode,
            "name": name,
            "category_id": shelf["id"],
            "supplier_id": rng.python.choice(active_suppliers)["id"],
            "brand": brand,
            "unit": unit,
            "unit_price": unit_price,
            "cost_price": cost_price,
            "vat_rate": shelf["vat_rate"],
            "active": rng.python.random() > 0.07,
        })
    return rows


def _generate_inventory(
    stores: list[dict], products: list[dict], count: int
) -> list[dict[str, Any]]:
    rng = Rng("supermarket", "inventory")

    # How much of the range each store format carries. An Express shop
    # stocks a fraction of what a Hipermercado does, which is why this table
    # is far smaller than stores x products.
    coverage = {"Express": 0.22, "Supermercado": 0.62, "Hipermercado": 0.95}

    rows: list[dict[str, Any]] = []
    next_id = 1

    for store in stores:
        listed = [
            product for product in products
            if product["active"] and rng.python.random() < coverage[store["format"]]
        ]
        for product in listed:
            if len(rows) >= count:
                return rows

            # Fast-moving fresh lines are restocked constantly; bazar is not.
            fresh = product["vat_rate"] == VAT_SUPERREDUCED
            days_ago = rng.python.randint(0, 3 if fresh else 45)

            reorder = rng.python.choice([8, 10, 12, 15, 20, 25, 30])
            # 4% of lines are out of stock on purpose.
            if rng.python.random() < 0.04:
                quantity = 0
            else:
                quantity = int(max(1, rng.numpy.normal(reorder * 2.4, reorder * 0.8)))

            rows.append({
                "id": next_id,
                "store_id": store["id"],
                "product_id": product["id"],
                "quantity_on_hand": quantity,
                "reorder_level": reorder,
                "last_restocked_at": PERIOD_END - timedelta(days=days_ago),
            })
            next_id += 1

    return rows


def _generate_customers(count: int) -> list[dict[str, Any]]:
    rng = Rng("supermarket", "customers")

    rows = []
    for index in range(1, count + 1):
        is_female = rng.python.random() < 0.54
        full_name = rng.faker.name_female() if is_female else rng.faker.name_male()
        location = generate_address(rng, with_phone=True, mobile=True)

        birth_year = rng.python.randint(1945, 2006)
        birth_date = date(birth_year, 1, 1) + timedelta(days=rng.python.randint(0, 364))

        rows.append({
            "id": index,
            "loyalty_card": f"LC-{index:09d}",
            "full_name": full_name,
            "email": rng.maybe_null(_email_from_name(full_name, "example.com", rng), 0.15),
            "phone": rng.maybe_null(location["phone"], 0.09),
            "city": location["city"],
            "province": location["province"],
            "postal_code": location["postal_code"],
            "birth_date": rng.maybe_null(birth_date, 0.20),
            "segment": rng.weighted_choice(CUSTOMER_SEGMENTS),
            "signed_up_at": rng.date_between(date(2021, 1, 1), date(2025, 3, 31)),
        })
    return rows


def _generate_promotions(products: list[dict], count: int) -> list[dict[str, Any]]:
    rng = Rng("supermarket", "promotions")

    active_products = [row for row in products if row["active"]] or products

    rows = []
    for index in range(1, count + 1):
        product = rng.python.choice(active_products)
        promotion_type = rng.weighted_choice(PROMOTION_TYPES)

        # The effective saving depends on the mechanic: "second unit half
        # price" is a 25% saving across two units, "three for two" is 33%.
        if promotion_type == "second_unit_half_price":
            discount = Decimal("25.00")
        elif promotion_type == "three_for_two":
            discount = Decimal("33.00")
        else:
            discount = Decimal(rng.python.choice([5, 10, 15, 20, 25, 30, 40, 50]))

        starts_on = rng.date_between(PERIOD_START, PERIOD_END - timedelta(days=14))
        rows.append({
            "id": index,
            "product_id": product["id"],
            "type": promotion_type,
            "discount_percent": discount.quantize(Decimal("0.01")),
            "starts_on": starts_on,
            "ends_on": starts_on + timedelta(days=rng.python.choice([7, 14, 21, 28, 42])),
        })
    return rows


def _generate_transactions_and_items(
    stores: list[dict],
    employees: list[dict],
    customers: list[dict],
    products: list[dict],
    promotions: list[dict],
    transaction_count: int,
    item_target: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate baskets and their lines together.

    They have to be generated in one pass, because a transaction's totals
    are DERIVED from its lines. Producing them separately and hoping the
    numbers agree is exactly how retail sample data ends up with receipts
    that do not add up.

    All money arithmetic is done in Decimal rather than float. 0.1 + 0.2 is
    not 0.3 in binary floating point, and over eight thousand line items
    those errors accumulate into totals that are visibly wrong.
    """
    rng = Rng("supermarket", "transactions")

    cashiers_by_store: dict[int, list[dict]] = {}
    for employee in employees:
        if employee["role"] == "Cashier" and employee["active"]:
            cashiers_by_store.setdefault(employee["store_id"], []).append(employee)
    # Any store with no active cashier falls back to its whole staff list.
    for store in stores:
        if store["id"] not in cashiers_by_store:
            cashiers_by_store[store["id"]] = [
                e for e in employees if e["store_id"] == store["id"]
            ] or employees

    sellable = [product for product in products] or products

    # Promotions indexed by product, so looking up "was this on offer that
    # day?" is a dictionary hit rather than a scan of the whole table.
    promotions_by_product: dict[int, list[dict]] = {}
    for promotion in promotions:
        promotions_by_product.setdefault(promotion["product_id"], []).append(promotion)

    # Basket sizes follow a long tail: a great many two- or three-item
    # top-up shops, a few enormous weekly ones.
    average_lines = max(1.5, item_target / max(1, transaction_count))

    # Trading is busiest on Friday and Saturday, quietest on Monday.
    weekday_weights = {0: 11, 1: 12, 2: 13, 3: 14, 4: 19, 5: 23, 6: 8}

    # Opening hours, weighted so that lunchtime and early evening are peaks.
    hour_weights = {9: 6, 10: 9, 11: 11, 12: 13, 13: 12, 14: 7, 15: 5,
                    16: 7, 17: 10, 18: 13, 19: 14, 20: 10, 21: 4}

    transactions: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []

    for index in range(1, transaction_count + 1):
        store = rng.python.choice(stores)
        cashier = rng.python.choice(cashiers_by_store[store["id"]])

        # Pick a date, then nudge it toward the busier weekdays.
        occurred_on = rng.date_between(max(PERIOD_START, store["opened_at"]), PERIOD_END)
        for _ in range(3):
            if rng.python.random() < weekday_weights[occurred_on.weekday()] / 23:
                break
            occurred_on = rng.date_between(
                max(PERIOD_START, store["opened_at"]), PERIOD_END
            )

        hour = rng.weighted_choice(hour_weights)
        occurred_at = datetime.combine(
            occurred_on, time(hour, rng.python.randint(0, 59))
        )

        # A loyalty card is presented a little over half the time, and only
        # by a customer who had already signed up.
        customer = None
        if rng.python.random() < 0.55:
            candidate = rng.python.choice(customers)
            if candidate["signed_up_at"] <= occurred_on:
                customer = candidate

        # Premium customers buy more per visit -- a correlation worth having.
        multiplier = {"premium": 1.6, "regular": 1.1, "occasional": 0.7,
                      "new": 0.6}.get(customer["segment"], 1.0) if customer else 0.9
        line_count = max(
            1, int(rng.numpy.lognormal(mean=0.0, sigma=0.75) * average_lines * multiplier)
        )
        line_count = min(line_count, 40)

        chosen = rng.python.sample(sellable, min(line_count, len(sellable)))

        transaction_total = Decimal("0.00")
        transaction_vat = Decimal("0.00")

        for line_number, product in enumerate(chosen, start=1):
            unit_price = Decimal(str(product["unit_price"]))
            vat_rate = Decimal(str(product["vat_rate"]))

            # Weighed goods come in fractional quantities; everything else
            # is bought in whole units.
            if product["unit"] == "kg":
                quantity = Decimal(str(round(rng.python.uniform(0.15, 2.5), 2)))
            else:
                quantity = Decimal(
                    rng.weighted_choice({1: 64, 2: 22, 3: 8, 4: 4, 6: 2})
                )

            # Was this product on promotion on the day?
            discount = Decimal("0.00")
            for promotion in promotions_by_product.get(product["id"], []):
                if promotion["starts_on"] <= occurred_on <= promotion["ends_on"]:
                    discount = Decimal(str(promotion["discount_percent"]))
                    break

            gross = (quantity * unit_price).quantize(Decimal("0.01"))
            line_total = (
                gross * (Decimal("1") - discount / Decimal("100"))
            ).quantize(Decimal("0.01"))

            # VAT in Spain is included in the shelf price, so it is extracted
            # from the line total rather than added on top.
            line_vat = (
                line_total - (line_total / (Decimal("1") + vat_rate))
            ).quantize(Decimal("0.01"))

            items.append({
                "id": len(items) + 1,
                "transaction_id": index,
                "line_number": line_number,
                "product_id": product["id"],
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_percent": discount,
                "vat_rate": vat_rate,
                "line_total": line_total,
            })

            transaction_total += line_total
            transaction_vat += line_vat

        transactions.append({
            "id": index,
            "receipt_number": f"{store['id']:04d}-{index:08d}",
            "store_id": store["id"],
            "customer_id": customer["id"] if customer else None,
            "cashier_id": cashier["id"],
            "occurred_at": occurred_at,
            "payment_method": rng.weighted_choice(PAYMENT_METHODS),
            "item_count": len(chosen),
            # subtotal + vat == total, exactly, because subtotal is derived
            # by subtraction rather than computed independently.
            "subtotal": (transaction_total - transaction_vat).quantize(Decimal("0.01")),
            "vat_amount": transaction_vat.quantize(Decimal("0.01")),
            "total": transaction_total.quantize(Decimal("0.01")),
        })

    # Order by time and renumber, so a higher id is always a later sale.
    order = sorted(range(len(transactions)), key=lambda i: transactions[i]["occurred_at"])
    remap = {transactions[old]["id"]: new for new, old in enumerate(order, start=1)}

    transactions = [transactions[i] for i in order]
    for new_id, transaction in enumerate(transactions, start=1):
        transaction["id"] = new_id

    for item in items:
        item["transaction_id"] = remap[item["transaction_id"]]
    items.sort(key=lambda row: (row["transaction_id"], row["line_number"]))
    for new_id, item in enumerate(items, start=1):
        item["id"] = new_id

    return transactions, items


def generate(scale: float = 1.0) -> dict[str, list[dict[str, Any]]]:
    """Produce every table in the supermarket topic."""
    counts = {name: max(1, int(number * scale)) for name, number in DEFAULT_COUNTS.items()}

    stores = _generate_stores(counts["stores"])
    categories = _generate_categories(counts["categories"])
    suppliers = _generate_suppliers(counts["suppliers"])
    employees = _generate_employees(stores, counts["employees"])
    products = _generate_products(categories, suppliers, counts["products"])
    inventory = _generate_inventory(stores, products, counts["inventory"])
    customers = _generate_customers(counts["customers"])
    promotions = _generate_promotions(products, counts["promotions"])
    transactions, transaction_items = _generate_transactions_and_items(
        stores, employees, customers, products, promotions,
        counts["transactions"], counts["transaction_items"],
    )

    return {
        "stores": stores,
        "categories": categories,
        "suppliers": suppliers,
        "employees": employees,
        "products": products,
        "inventory": inventory,
        "customers": customers,
        "promotions": promotions,
        "transactions": transactions,
        "transaction_items": transaction_items,
    }


TOPIC = Topic(
    name="supermarket",
    title="Supermarket / Retail",
    summary=(
        "Stores, a Spanish grocery catalogue with scannable EAN-13 barcodes, "
        "loyalty customers, and till transactions whose totals reconcile to "
        "the cent."
    ),
    description=(
        "A Spanish supermarket chain: a handful of stores, a full grocery "
        "catalogue organised into a category tree, loyalty-card customers, "
        "and two and a half years of till transactions.\n\n"
        "This is the most conventional business-shaped data in the "
        "repository, which is what makes it the best starting point for "
        "testing an application: a catalogue, a customer list, and a large "
        "transactions table joining them.\n\n"
        "The money reconciles. For every basket, the line totals sum exactly "
        "to the recorded total and the VAT breakdown adds up, using the three "
        "real Spanish VAT bands -- 4% on staples, 10% on most food, 21% on "
        "everything else. Barcodes carry valid check digits and will scan."
    ),
    entities=[
        STORES,
        CATEGORIES,
        SUPPLIERS,
        EMPLOYEES,
        PRODUCTS,
        INVENTORY,
        CUSTOMERS,
        PROMOTIONS,
        TRANSACTIONS,
        TRANSACTION_ITEMS,
    ],
)
