"""
Spanish geography: provinces, cities, postal codes and street addresses.
===============================================================================

WHAT IS THIS FILE?
------------------
Every address in this repository is located in Spain, and this file is what
makes those addresses internally consistent: the postal code, the city and
the province always agree with each other.

WHY SPANISH POSTAL CODES ARE NOT JUST "FIVE RANDOM DIGITS"
----------------------------------------------------------
A Spanish postal code is five digits, and the first two are not decorative --
they are the province code, assigned alphabetically in 1950 and unchanged
since:

    28001   ->  28 = Madrid,    001 = the district within it
    08001   ->  08 = Barcelona
    41001   ->  41 = Sevilla
    46001   ->  46 = Valencia

The codes run from 01 (Álava) to 52 (Melilla). There is no province 00 and
no province 53, so `00123` and `53001` are both invalid -- which is exactly
what a validation function should reject, and why generating them at random
would make this data useless for testing one.

So `generate_address()` picks a city first and derives the postal code from
that city's province. A patient living in Sevilla always gets a 41xxx code.
If your code cross-checks a postal code against a city, this data will pass;
if it should reject a mismatch, use the deliberately broken examples in the
`_edge-cases/` folders instead.

WHAT IS AND IS NOT REAL HERE
----------------------------
* Province names, province codes and city names are REAL. They are public
  administrative geography, not personal data, and using the genuine ones is
  what lets you test a real address lookup or a mapping integration.
* Street names are drawn from the genuinely most common street names in
  Spain (Calle Mayor, Avenida de la Constitución...), because almost every
  Spanish town really does have one.
* The combination of a street, a number and a city is INVENTED. No address
  in this repository is a real dwelling or a real building.
"""

from __future__ import annotations

#: The 52 Spanish provinces, keyed by their official two-digit code.
#:
#: The numbering is alphabetical by the province's 1950 name, which is why
#: Álava is 01 and Zaragoza is 50 -- and why the two autonomous cities,
#: Ceuta and Melilla, were appended afterwards as 51 and 52.
PROVINCES = {
    "01": "Álava", "02": "Albacete", "03": "Alicante", "04": "Almería",
    "05": "Ávila", "06": "Badajoz", "07": "Baleares", "08": "Barcelona",
    "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca",
    "17": "Girona", "18": "Granada", "19": "Guadalajara", "20": "Gipuzkoa",
    "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León",
    "25": "Lleida", "26": "La Rioja", "27": "Lugo", "28": "Madrid",
    "29": "Málaga", "30": "Murcia", "31": "Navarra", "32": "Ourense",
    "33": "Asturias", "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra",
    "37": "Salamanca", "38": "Santa Cruz de Tenerife", "39": "Cantabria",
    "40": "Segovia", "41": "Sevilla", "42": "Soria", "43": "Tarragona",
    "44": "Teruel", "45": "Toledo", "46": "Valencia", "47": "Valladolid",
    "48": "Bizkaia", "49": "Zamora", "50": "Zaragoza",
    "51": "Ceuta", "52": "Melilla",
}

#: Cities, as (name, province_code, population_weight).
#:
#: The weight makes big cities common and small ones rare, so a histogram of
#: where patients live looks like Spain rather than a uniform scatter. Madrid
#: and Barcelona between them should dominate, as they do in reality.
CITIES = [
    ("Madrid", "28", 3300), ("Barcelona", "08", 1600),
    ("Valencia", "46", 790), ("Sevilla", "41", 680),
    ("Zaragoza", "50", 670), ("Málaga", "29", 580),
    ("Murcia", "30", 460), ("Palma", "07", 420),
    ("Las Palmas de Gran Canaria", "35", 380), ("Bilbao", "48", 350),
    ("Alicante", "03", 340), ("Córdoba", "14", 320),
    ("Valladolid", "47", 300), ("Vigo", "36", 295),
    ("Gijón", "33", 270), ("L'Hospitalet de Llobregat", "08", 265),
    ("A Coruña", "15", 245), ("Vitoria-Gasteiz", "01", 250),
    ("Granada", "18", 230), ("Elche", "03", 230),
    ("Oviedo", "33", 220), ("Badalona", "08", 220),
    ("Cartagena", "30", 215), ("Terrassa", "08", 220),
    ("Jerez de la Frontera", "11", 212), ("Sabadell", "08", 215),
    ("Santa Cruz de Tenerife", "38", 210), ("Pamplona", "31", 200),
    ("Almería", "04", 200), ("San Sebastián", "20", 188),
    ("Burgos", "09", 175), ("Albacete", "02", 173),
    ("Santander", "39", 172), ("Castellón de la Plana", "12", 172),
    ("Getafe", "28", 183), ("Alcorcón", "28", 170),
    ("Logroño", "26", 152), ("Badajoz", "06", 150),
    ("Salamanca", "37", 144), ("Huelva", "21", 143),
    ("Lleida", "25", 140), ("Tarragona", "43", 135),
    ("León", "24", 125), ("Cádiz", "11", 116),
    ("Jaén", "23", 113), ("Ourense", "32", 105),
    ("Girona", "17", 102), ("Lugo", "27", 98),
    ("Cáceres", "10", 96), ("Toledo", "45", 85),
    ("Ciudad Real", "13", 75), ("Guadalajara", "19", 87),
    ("Zamora", "49", 60), ("Palencia", "34", 78),
    ("Cuenca", "16", 54), ("Segovia", "40", 51),
    ("Ávila", "05", 58), ("Huesca", "22", 53),
    ("Soria", "42", 39), ("Teruel", "44", 36),
    ("Ceuta", "51", 84), ("Melilla", "52", 86),
]

#: The street-name patterns that dominate Spanish towns. "Calle Mayor" is
#: the single most common street name in the country -- almost every
#: municipality has one.
#: NOTE: "Carrer" is deliberately NOT in this list. It is the Catalan and
#: Valencian word for "Calle", so it is correct in Barcelona and Alicante and
#: flatly wrong in Sevilla or Burgos. It is substituted in below, for the
#: provinces where it belongs, rather than being picked at random anywhere.
STREET_TYPES = {
    "Calle": 66, "Avenida": 14, "Plaza": 8, "Paseo": 5,
    "Ronda": 3, "Travesía": 2, "Camino": 2,
}

#: Street names, each carrying its own connector.
#:
#: WHY THE CONNECTOR LIVES WITH THE NAME: Spanish street names split into two
#: grammatical shapes, and the difference is not optional.
#:
#:   "Calle Mayor"          -- an adjective, attached directly
#:   "Calle de Cervantes"   -- a proper noun, needs "de"
#:   "Paseo del Ebro"       -- "de + el" contracts to "del"
#:
#: Putting the "de" in the street TYPE instead produces "Avenida de Real" and
#: "Paseo de Ebro", which are not Spanish. Keeping it with the name means
#: every combination of type and name comes out grammatical.
#: Street types that are grammatically masculine. This matters for the one
#: adjective below that inflects: "Calle Nueva" (feminine) but "Paseo Nuevo"
#: (masculine). "Paseo Nueva" is wrong in a way every Spanish speaker sees
#: instantly, so the agreement is applied rather than ignored.
MASCULINE_STREET_TYPES = {"Paseo", "Camino", "Carrer"}

#: Adjectives that change form with the gender of the street type, as
#: ``{feminine: masculine}``. Most Spanish street adjectives -- Mayor, Real,
#: Grande -- are invariant, so this list is deliberately short.
GENDERED_ADJECTIVES = {"Nueva": "Nuevo", "Vieja": "Viejo", "Alta": "Alto"}

STREET_NAMES = [
    # Bare -- adjectives and place-names used attributively.
    "Mayor", "Real", "Nueva", "Numancia", "Alcalá", "Serrano", "Goya",
    "Velázquez", "Colón",
    # "de" + proper noun.
    "de Cervantes", "de Santa María", "de San Juan", "de San José",
    "de San Antonio", "de San Fernando", "de Andalucía", "de Aragón",
    "de Extremadura", "de Galicia", "de Rosalía de Castro",
    "de Federico García Lorca", "de Antonio Machado", "de Blas de Otero",
    # "de la" + feminine noun.
    "de la Iglesia", "de la Constitución", "de la Paz", "de la Estación",
    "de la Libertad", "de la Fuente", "de la Rosa", "de la Merced",
    # "del" -- the contraction of "de el", before a masculine noun.
    "del Carmen", "del Sol", "del Guadalquivir", "del Ebro", "del Duero",
    # "de las" / "de los" -- plurals.
    "de las Flores", "de las Acacias", "de los Olivos",
]

#: Provinces where Catalan or Valencian is co-official and "Carrer" is the
#: everyday word for a street: the four Catalan provinces (Barcelona, Girona,
#: Lleida, Tarragona), the Balearic Islands, and the three Valencian
#: provinces (Valencia, Alicante, Castellón).
#:
#: Getting this wrong is the kind of detail that makes data read as obviously
#: synthetic to anyone Spanish -- "Carrer Mayor, Sevilla" is a sentence no
#: Spaniard would ever write.
CATALAN_PROVINCES = {"08", "17", "25", "43", "07", "46", "03", "12"}


# ---------------------------------------------------------------------------
# Telephone numbers
# ---------------------------------------------------------------------------
#
# Spanish landline numbers are nine digits beginning with 9, and the opening
# digits identify the province -- exactly like the postal code does. 91 is
# Madrid, 93 is Barcelona, 954 is Sevilla.
#
# The three biggest provinces were allocated short two-digit prefixes (91
# Madrid, 93 Barcelona, 96 Valencia) because they needed more subscriber
# numbers than anywhere else. Everywhere else uses three digits.
#
# Mobile numbers begin with 6 or 7 and carry no geographic meaning at all --
# a Spanish mobile tells you nothing about where its owner lives.
#
# ⚠️ A NOTE ON SAFETY, AND AN HONEST LIMITATION
# ---------------------------------------------
# North America reserves 555-0100 to 555-0199 for fiction, so a US test
# number is provably unable to ring anybody. Spain has no equivalent
# reservation.
#
# That means the numbers generated here are STRUCTURALLY VALID: they will
# pass a Spanish phone validator, which is what makes them useful for
# testing one, but it also means a given number could in principle belong to
# a real subscriber. They are randomly generated, never sampled from any
# real source, and no name in this repository belongs to a real person -- so
# a number here is not linked to anybody. But it is not the same guarantee
# as the 555 range provides, and it would be dishonest to imply otherwise.
#
# If you need provably unreachable numbers, regenerate with
# `RESERVED_PHONES = True` below.

#: Province code -> landline dialling prefix.
PHONE_PREFIXES = {
    "01": "945", "02": "967", "03": "965", "04": "950", "05": "920",
    "06": "924", "07": "971", "08": "93",  "09": "947", "10": "927",
    "11": "956", "12": "964", "13": "926", "14": "957", "15": "981",
    "16": "969", "17": "972", "18": "958", "19": "949", "20": "943",
    "21": "959", "22": "974", "23": "953", "24": "987", "25": "973",
    "26": "941", "27": "982", "28": "91",  "29": "952", "30": "968",
    "31": "948", "32": "988", "33": "985", "34": "979", "35": "928",
    "36": "986", "37": "923", "38": "922", "39": "942", "40": "921",
    "41": "954", "42": "975", "43": "977", "44": "978", "45": "925",
    "46": "96",  "47": "983", "48": "944", "49": "980", "50": "976",
    "51": "956", "52": "952",
}

#: Set True to emit obviously-fake numbers instead of realistic ones.
#: They will not pass validation, which is the point -- use this if you would
#: rather have an absolute guarantee than a usable test fixture.
RESERVED_PHONES = False


def phone_number(rng, province_code: str, *, mobile: bool = False) -> str:
    """A Spanish telephone number, formatted +34 NNN NNN NNN.

    Landlines carry the dialling prefix of the province they belong to, so
    the number agrees with the address it sits next to. Mobiles do not --
    Spanish mobile numbers are not geographic, and pretending otherwise
    would be a realism error in the opposite direction.

    >>> from generators.common.seeds import Rng
    >>> number = phone_number(Rng("demo"), "28")
    >>> number.startswith("+34 91")
    True
    >>> len(number.replace("+34 ", "").replace(" ", ""))
    9
    """
    if RESERVED_PHONES:
        return f"+34 000 {rng.python.randint(0, 999):03d} {rng.python.randint(0, 999):03d}"

    if mobile:
        # 6XX and 7XX are both mobile ranges; 6 is far more common.
        digits = (
            f"{rng.python.choice('667')}"
            f"{rng.python.randint(0, 99_999_999):08d}"
        )
    else:
        prefix = PHONE_PREFIXES[province_code]
        remaining = 9 - len(prefix)
        digits = f"{prefix}{rng.python.randint(0, 10 ** remaining - 1):0{remaining}d}"

    # Spanish numbers are written in groups of three.
    return f"+34 {digits[:3]} {digits[3:6]} {digits[6:]}"


def phone_is_valid(number: str) -> bool:
    """True if this is a structurally valid Spanish subscriber number.

    Spanish numbers are nine digits and must begin with 6 or 7 (mobile) or
    8 or 9 (landline). Nothing else is a valid subscriber number, which is
    why `+34 123 456 789` should be rejected.

    >>> phone_is_valid("+34 913 456 789")
    True
    >>> phone_is_valid("+34 612 345 678")
    True
    >>> phone_is_valid("+34 123 456 789")
    False
    >>> phone_is_valid("+34 91 345 678")
    False
    """
    digits = number.replace("+34", "").replace(" ", "").replace("-", "")
    return len(digits) == 9 and digits.isdigit() and digits[0] in "6789"


def postal_code(rng, province_code: str) -> str:
    """A valid Spanish postal code for the given province.

    The first two digits are the province code; the last three identify the
    district within it and run from 001 upward.

    >>> from generators.common.seeds import Rng
    >>> code = postal_code(Rng("demo"), "28")
    >>> code.startswith("28"), len(code)
    (True, 5)
    """
    if province_code not in PROVINCES:
        raise ValueError(
            f"{province_code!r} is not a Spanish province code. Valid codes "
            f"run from 01 (Álava) to 52 (Melilla)."
        )
    # Real districts are not evenly spread across 001-999; the low numbers
    # are the city centre and the high ones may not exist at all. Capping at
    # 080 keeps the codes inside the range that is actually populated in most
    # provinces.
    return f"{province_code}{rng.python.randint(1, 80):03d}"


def postal_code_is_valid(code: str) -> bool:
    """True if this is a structurally valid Spanish postal code.

    >>> postal_code_is_valid("28001")
    True
    >>> postal_code_is_valid("00123")     # there is no province 00
    False
    >>> postal_code_is_valid("53001")     # there is no province 53
    False
    >>> postal_code_is_valid("2800")      # too short
    False
    """
    return len(code) == 5 and code.isdigit() and code[:2] in PROVINCES


def pick_city(rng) -> tuple[str, str, str]:
    """Choose a city, weighted by population.

    Returns ``(city, province_code, province_name)``.
    """
    names = [city for city, _, _ in CITIES]
    weights = [weight for _, _, weight in CITIES]
    chosen = rng.python.choices(names, weights=weights, k=1)[0]
    province_code = next(code for city, code, _ in CITIES if city == chosen)
    return chosen, province_code, PROVINCES[province_code]


def street_address(rng, province_code: str) -> str:
    """An invented but plausible Spanish street address.

    Spanish addresses put the number AFTER the street name, separated by a
    comma -- "Calle Mayor, 47" -- which is the opposite of the English
    convention and a common thing to get wrong when localising an address
    form.

    Flats add a floor and door: "Calle Mayor, 47, 3º B".

    >>> from generators.common.seeds import Rng
    >>> address = street_address(Rng("demo"), "28")
    >>> "," in address
    True
    """
    street_type = rng.weighted_choice(STREET_TYPES)

    # In Catalan-speaking provinces, "Calle" becomes "Carrer".
    if province_code in CATALAN_PROVINCES and street_type == "Calle":
        if rng.python.random() < 0.45:
            street_type = "Carrer"

    name = rng.python.choice(STREET_NAMES)

    # Make the adjective agree with the street type's gender.
    if street_type in MASCULINE_STREET_TYPES and name in GENDERED_ADJECTIVES:
        name = GENDERED_ADJECTIVES[name]

    number = rng.python.randint(1, 180)
    address = f"{street_type} {name}, {number}"

    # About half of Spanish homes are flats, which carry a floor and a door.
    if rng.python.random() < 0.5:
        floor = rng.python.randint(1, 9)
        door = rng.python.choice(["A", "B", "C", "D", "Izq.", "Dcha."])
        address += f", {floor}º {door}"

    return address


def generate_address(rng, *, with_phone: bool = False, mobile: bool = False) -> dict[str, str]:
    """A complete, internally consistent Spanish address.

    The postal code always belongs to the province the city is in, and -- if
    a phone is requested -- so does the dialling prefix. All four or five
    fields agree with each other, which is the whole point: it lets you test
    address validation against data that is supposed to pass.

    Returns a dict with keys: address, city, province, postal_code, and
    optionally phone.
    """
    city, province_code, province_name = pick_city(rng)
    result = {
        "address": street_address(rng, province_code),
        "city": city,
        "province": province_name,
        "postal_code": postal_code(rng, province_code),
    }
    if with_phone:
        result["phone"] = phone_number(rng, province_code, mobile=mobile)
    return result
