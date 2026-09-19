"""
Real-world identifiers, with real check digits.
===============================================================================

WHAT IS THIS FILE?
------------------
Barcodes, bank account numbers, card numbers and vehicle serial numbers are
not arbitrary strings. Each one carries a **check digit**: an extra character
computed from all the others, so that a typo can be detected instantly
without looking anything up in a database.

This file computes those check digits properly, so that every identifier in
this repository is *structurally valid*. An EAN-13 from `supermarket/products`
will scan. An IBAN from `finance/accounts` will pass your payment library's
validator. A VIN from `automobile/vehicles` will pass a VIN decoder's
checksum test.

WHY BOTHER?
-----------
Because this is the single biggest difference between sample data that is
useful and sample data that wastes your afternoon.

If the fake IBANs in your test fixtures fail validation, you cannot use them
to test the happy path -- you end up disabling the validator in tests, which
means the validator is never tested. Data with correct check digits lets you
test the real code path. And the deliberately *broken* ones, in the
`_edge-cases/` folders, let you test the unhappy path on purpose.

IS THIS SAFE? ARE THESE REAL ACCOUNTS?
--------------------------------------
No, and that is deliberate:

* **Card numbers** come only from the published test ranges (4111 1111 ...)
  that every payment processor recognises as non-live. They pass Luhn, they
  will never move money.
* **IBANs** use the reserved "TEST" / documentation bank codes, so the
  structure is valid but no such bank exists.
* **VINs** use invented WMI prefixes (the first three characters, which
  identify the manufacturer). No real carmaker has been assigned them.

See docs/synthetic-data-guarantees.md for the full list.
"""

from __future__ import annotations

import string  # noqa: F401  (kept for callers)

# ===========================================================================
# Luhn algorithm -- payment cards
# ===========================================================================
#
# Invented by Hans Peter Luhn at IBM in 1954 and still what validates every
# card number you have ever typed into a checkout form.
#
# HOW IT WORKS, with 4111 1111 1111 111? as the example:
#
#   1. Starting from the RIGHT, double every second digit.
#   2. If doubling gives a number above 9, subtract 9 (so 14 becomes 5).
#      This is the same as adding the two digits of the result together.
#   3. Add everything up.
#   4. The check digit is whatever makes that total a multiple of 10.
#
# So a single mistyped digit always breaks the sum, and the form can tell you
# so before it ever contacts the bank.


def luhn_check_digit(partial_number: str) -> str:
    """Return the check digit that completes ``partial_number``.

    >>> luhn_check_digit("411111111111111")
    '1'
    >>> luhn_check_digit("53510000000000")
    '2'
    """
    digits = [int(character) for character in partial_number]
    total = 0

    # We are about to append one more digit, so the rightmost digit of the
    # number we have now will end up in an "even" position. Counting from the
    # right of the FINAL number, doubling applies to positions 2, 4, 6... --
    # which from the right of the partial number is positions 1, 3, 5...
    for index, digit in enumerate(reversed(digits)):
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return str((10 - total % 10) % 10)


def luhn_is_valid(number: str) -> bool:
    """True if ``number`` (check digit included) passes the Luhn test.

    >>> luhn_is_valid("4111111111111111")
    True
    >>> luhn_is_valid("4111111111111112")
    False
    """
    cleaned = number.replace(" ", "").replace("-", "")
    if not cleaned.isdigit() or len(cleaned) < 2:
        return False
    return luhn_check_digit(cleaned[:-1]) == cleaned[-1]


# ===========================================================================
# EAN-13 -- retail barcodes
# ===========================================================================
#
# The barcode on almost every product in a supermarket. Thirteen digits: the
# first twelve identify the country prefix, the manufacturer and the product,
# and the thirteenth is the check digit.
#
# HOW IT WORKS, with 841234567890? as the example:
#
#   1. Take the first twelve digits.
#   2. Multiply them alternately by 1 and 3, starting with 1 on the left.
#        8*1 + 4*3 + 1*1 + 2*3 + 3*1 + 4*3 + 5*1 + 6*3 + 7*1 + 8*3 + 9*1 + 0*3
#      = 8 + 12 + 1 + 6 + 3 + 12 + 5 + 18 + 7 + 24 + 9 + 0 = 105
#   3. The check digit is whatever brings that total up to a multiple of 10.
#        110 - 105 = 5
#
# So the full barcode is 8412345678905.


def ean13_check_digit(first_twelve: str) -> str:
    """Return the 13th digit of an EAN-13 barcode.

    >>> ean13_check_digit("841234567890")
    '5'
    >>> ean13_check_digit("400638133393")
    '1'
    """
    if len(first_twelve) != 12 or not first_twelve.isdigit():
        raise ValueError(
            f"EAN-13 needs exactly 12 digits to compute the 13th, got "
            f"{first_twelve!r} ({len(first_twelve)} characters)."
        )

    total = sum(
        int(digit) * (1 if position % 2 == 0 else 3)
        for position, digit in enumerate(first_twelve)
    )
    return str((10 - total % 10) % 10)


def ean13(first_twelve: str) -> str:
    """Build a complete, scannable EAN-13 barcode.

    >>> ean13("841234567890")
    '8412345678905'
    """
    return first_twelve + ean13_check_digit(first_twelve)


def ean13_is_valid(barcode: str) -> bool:
    """True if a 13-digit barcode's check digit is correct.

    >>> ean13_is_valid("8412345678905")
    True
    >>> ean13_is_valid("8412345678900")
    False
    """
    if len(barcode) != 13 or not barcode.isdigit():
        return False
    return ean13_check_digit(barcode[:12]) == barcode[12]


# ===========================================================================
# IBAN -- international bank account numbers
# ===========================================================================
#
# An IBAN looks like:  GB29 TEST 6016 1331 9268 19
#                      ^^   ^^
#                      |    check digits (positions 3 and 4)
#                      country code
#
# The rest is the BBAN -- the country's own domestic account number format,
# which is why IBAN lengths differ by country (Germany 22, UK 22, Spain 24).
#
# HOW THE CHECK WORKS (the "mod-97" test):
#
#   1. Move the first four characters to the end.
#        GB29TEST60161331926819  ->  TEST60161331926819GB29
#   2. Replace every letter with a number: A=10, B=11, ... Z=35.
#        T=29, E=14, S=28, T=29 ...
#   3. Read the result as one enormous integer and take it modulo 97.
#   4. A valid IBAN always gives exactly 1.
#
# To GENERATE one we run it backwards: put "00" in the check position,
# compute the remainder, and the check digits are 98 minus that.

#: Total IBAN length per country. Only the countries this repository uses.
IBAN_LENGTHS = {
    "GB": 22,  # United Kingdom
    "DE": 22,  # Germany
    "FR": 27,  # France
    "ES": 24,  # Spain
    "IE": 22,  # Ireland
    "NL": 18,  # Netherlands
}


def _iban_to_number(iban: str) -> int:
    """Rearrange an IBAN and convert its letters to digits, per ISO 13616."""
    rearranged = iban[4:] + iban[:4]
    return int(
        "".join(
            str(ord(character) - ord("A") + 10) if character.isalpha() else character
            for character in rearranged
        )
    )


def build_iban(country: str, bban: str) -> str:
    """Build a valid IBAN from a country code and a domestic account number.

    >>> build_iban("GB", "TEST60161331926819")
    'GB14TEST60161331926819'
    >>> iban_is_valid(build_iban("DE", "TEST05320130000000"))
    True
    """
    country = country.upper()
    if country not in IBAN_LENGTHS:
        raise ValueError(
            f"Unknown IBAN country {country!r}. Known: "
            f"{', '.join(sorted(IBAN_LENGTHS))}."
        )

    expected_bban_length = IBAN_LENGTHS[country] - 4
    if len(bban) != expected_bban_length:
        raise ValueError(
            f"{country} IBANs are {IBAN_LENGTHS[country]} characters long, so "
            f"the BBAN must be {expected_bban_length}; got {len(bban)} "
            f"({bban!r})."
        )

    # Compute the remainder with "00" standing in for the real check digits.
    remainder = _iban_to_number(f"{country}00{bban}") % 97
    check_digits = f"{98 - remainder:02d}"
    return f"{country}{check_digits}{bban}"


def iban_is_valid(iban: str) -> bool:
    """True if the IBAN's mod-97 check passes.

    >>> iban_is_valid("GB14TEST60161331926819")
    True
    >>> iban_is_valid("GB99TEST60161331926819")
    False
    """
    cleaned = iban.replace(" ", "").upper()
    if len(cleaned) < 5 or not cleaned[:2].isalpha() or not cleaned[2:4].isdigit():
        return False
    if cleaned[:2] in IBAN_LENGTHS and len(cleaned) != IBAN_LENGTHS[cleaned[:2]]:
        return False
    try:
        return _iban_to_number(cleaned) % 97 == 1
    except ValueError:
        return False


# ===========================================================================
# VIN -- vehicle identification numbers
# ===========================================================================
#
# Seventeen characters, standardised worldwide by ISO 3779. Every car built
# since 1981 has one, stamped on the chassis and printed on the windscreen.
#
#   1FADP3K24JL######
#   ^^^            ^
#   |              serial number
#   WMI (positions 1-3): who made it and where
#
#   Position  9 -- check digit
#   Position 10 -- model year
#   Position 11 -- which factory built it
#
# The letters I, O and Q are banned outright, because they are too easy to
# confuse with 1 and 0 when reading a number stamped into metal.
#
# HOW THE CHECK DIGIT WORKS:
#   1. Turn each character into a number (digits stay; letters use the
#      transliteration table below -- note that it is NOT simply A=1..Z=26).
#   2. Multiply each by its positional weight.
#   3. Add them up, take modulo 11.
#   4. The result is the check digit -- except 10, which is written as "X".

VIN_ALPHABET = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O or Q

#: ISO 3779 transliteration. Letters map to 1-9 in a specific, non-obvious
#: pattern that repeats -- A-H is 1-8, J-R is 1-9, S-Z is 2-9.
VIN_VALUES = {
    **{str(digit): digit for digit in range(10)},
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}

#: Positional weights. Position 9 weighs 0 because that IS the check digit --
#: it cannot contribute to computing itself.
VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

#: Model-year codes. The cycle is 30 years long, so "J" means both 1988 and
#: 2018 -- you need position 7 to tell them apart on real vehicles. Every
#: vehicle in this repository is from 2010 onward, so there is no ambiguity.
VIN_YEAR_CODES = {
    2010: "A", 2011: "B", 2012: "C", 2013: "D", 2014: "E", 2015: "F",
    2016: "G", 2017: "H", 2018: "J", 2019: "K", 2020: "L", 2021: "M",
    2022: "N", 2023: "P", 2024: "R", 2025: "S", 2026: "T", 2027: "V",
    2028: "W", 2029: "X", 2030: "Y",
}


def vin_check_digit(vin_with_placeholder: str) -> str:
    """Compute the 9th character of a VIN.

    ``vin_with_placeholder`` must be 17 characters, with any placeholder you
    like at position 9 -- it is ignored, because its weight is zero.

    >>> vin_check_digit("1M8GDM9A_KP042788")
    'X'
    >>> vin_check_digit("11111111111111111")
    '1'
    """
    if len(vin_with_placeholder) != 17:
        raise ValueError(
            f"A VIN is exactly 17 characters; got {len(vin_with_placeholder)} "
            f"({vin_with_placeholder!r})."
        )

    total = 0
    for position, character in enumerate(vin_with_placeholder.upper()):
        if position == 8:
            continue  # the check-digit slot contributes nothing
        if character not in VIN_VALUES:
            raise ValueError(
                f"{character!r} at position {position + 1} is not valid in a "
                f"VIN. The letters I, O and Q are excluded by ISO 3779 "
                f"because they look too much like 1 and 0."
            )
        total += VIN_VALUES[character] * VIN_WEIGHTS[position]

    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def build_vin(wmi: str, descriptor: str, year: int, plant: str, serial: str) -> str:
    """Assemble a complete, checksum-valid VIN.

    Parameters
    ----------
    wmi
        World Manufacturer Identifier, 3 characters. This repository uses
        INVENTED prefixes so they cannot collide with a real manufacturer.
    descriptor
        5 characters describing model, body and engine (positions 4-8).
    year
        Model year; converted to its ISO letter code for position 10.
    plant
        1 character identifying the assembly plant (position 11).
    serial
        6 characters of production sequence (positions 12-17).

    >>> vin = build_vin("ZZA", "BC4DE", 2021, "F", "004217")
    >>> len(vin), vin_is_valid(vin)
    (17, True)
    """
    if year not in VIN_YEAR_CODES:
        raise ValueError(
            f"No VIN year code for {year}. This repository covers "
            f"{min(VIN_YEAR_CODES)}-{max(VIN_YEAR_CODES)}."
        )

    skeleton = f"{wmi}{descriptor}_{VIN_YEAR_CODES[year]}{plant}{serial}"
    return skeleton[:8] + vin_check_digit(skeleton) + skeleton[9:]


def vin_is_valid(vin: str) -> bool:
    """True if the VIN is 17 valid characters and its check digit matches.

    >>> vin_is_valid("1M8GDM9AXKP042788")
    True
    >>> vin_is_valid("1M8GDM9A0KP042788")
    False
    """
    if len(vin) != 17:
        return False
    if any(character not in VIN_ALPHABET for character in vin.upper()):
        return False
    try:
        return vin_check_digit(vin) == vin.upper()[8]
    except ValueError:
        return False


# ===========================================================================
# Human-readable business keys
# ===========================================================================
#
# Alongside the integer `id` that every table uses for joins, most tables also
# carry a padded, prefixed identifier -- MRN-0000042, SKU-001337, STU-004501.
#
# WHY BOTH? Because that is what real systems do. The integer is what the
# database joins on; the prefixed string is what gets printed on a wristband,
# a shelf label or a student card, where a human has to read it aloud without
# ambiguity. Having both here means you can test either style.


def business_key(prefix: str, number: int, width: int = 7) -> str:
    """Format a padded, prefixed identifier.

    >>> business_key("MRN", 42)
    'MRN-0000042'
    >>> business_key("SKU", 1337, width=6)
    'SKU-001337'
    """
    return f"{prefix}-{number:0{width}d}"


# ===========================================================================
# DNI / NIE -- the Spanish national identity number
# ===========================================================================
#
# Every Spanish citizen has a DNI: eight digits followed by a check letter,
# written "12345678Z". Foreign residents have a NIE, which is the same idea
# with a letter (X, Y or Z) at the front instead of a leading digit.
#
# HOW THE CHECK LETTER WORKS:
#   Take the eight digits as a number, divide by 23, and look up the
#   remainder in this table:
#
#       0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22
#       T  R  W  A  G  M  Y  F  P  D  X  B  N  J  Z  S  Q  V  H  L  C  K  E
#
#   12345678 % 23 = 14, and the 14th letter is Z -- hence 12345678Z, the
#   example everybody uses.
#
# The letters I, O, U and Ñ are absent on purpose: I and O look like 1 and 0,
# U could be confused with V, and Ñ is not on every keyboard.

#: The check-letter lookup table, in remainder order. The order is fixed by
#: Spanish law and is not alphabetical.
DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"

#: NIE numbers begin with a letter that stands in for a leading digit.
NIE_PREFIXES = {"X": "0", "Y": "1", "Z": "2"}


def dni_check_letter(digits: str) -> str:
    """Return the check letter for an eight-digit DNI number.

    >>> dni_check_letter("12345678")
    'Z'
    >>> dni_check_letter("00000000")
    'T'
    """
    if len(digits) != 8 or not digits.isdigit():
        raise ValueError(
            f"A DNI number is exactly 8 digits before the letter; got "
            f"{digits!r} ({len(digits)} characters)."
        )
    return DNI_LETTERS[int(digits) % 23]


def dni(rng) -> str:
    """Generate a complete, checksum-valid DNI.

    >>> from generators.common.seeds import Rng
    >>> identifier = dni(Rng("demo"))
    >>> len(identifier), dni_is_valid(identifier)
    (9, True)
    """
    digits = f"{rng.python.randint(0, 99_999_999):08d}"
    return f"{digits}{dni_check_letter(digits)}"


def nie(rng) -> str:
    """Generate a complete, checksum-valid NIE (foreign resident number).

    The leading letter is converted to a digit before the modulo, so an NIE
    beginning "X" is checked as though it began "0".

    >>> from generators.common.seeds import Rng
    >>> identifier = nie(Rng("demo"))
    >>> identifier[0] in "XYZ", dni_is_valid(identifier)
    (True, True)
    """
    prefix = rng.python.choice(list(NIE_PREFIXES))
    digits = f"{rng.python.randint(0, 9_999_999):07d}"
    numeric = NIE_PREFIXES[prefix] + digits
    return f"{prefix}{digits}{dni_check_letter(numeric)}"


def dni_is_valid(identifier: str) -> bool:
    """True if this is a valid DNI or NIE.

    >>> dni_is_valid("12345678Z")
    True
    >>> dni_is_valid("12345678A")
    False
    >>> dni_is_valid("X1234567L")
    True
    """
    cleaned = identifier.replace("-", "").replace(" ", "").upper()
    if len(cleaned) != 9:
        return False

    body, letter = cleaned[:-1], cleaned[-1]

    if body[0] in NIE_PREFIXES:
        body = NIE_PREFIXES[body[0]] + body[1:]
    if not body.isdigit():
        return False

    try:
        return dni_check_letter(body) == letter
    except ValueError:
        return False


# ===========================================================================
# Spanish vehicle registration plates
# ===========================================================================
#
# Spain switched to its current format in September 2000: four digits, then
# three letters, written "1234 BCD".
#
# The letters exclude every vowel (A, E, I, O, U), plus Ñ and Q. Vowels are
# dropped so that no plate can accidentally spell a word -- an elegant fix
# that several countries arrived at independently -- and Q is dropped because
# it looks too much like O.
#
# Plates are issued in strict sequence nationally, so unlike the old
# province-coded format a modern Spanish plate tells you nothing about where
# the car is from. Only roughly when it was registered.

#: The twenty consonants Spanish plates are allowed to use.
PLATE_LETTERS = "BCDFGHJKLMNPRSTVWXYZ"


def licence_plate(rng) -> str:
    """A Spanish registration plate in the post-2000 format.

    >>> from generators.common.seeds import Rng
    >>> plate = licence_plate(Rng("demo"))
    >>> len(plate), plate[4]
    (8, ' ')
    >>> all(character in PLATE_LETTERS for character in plate[5:])
    True
    """
    digits = f"{rng.python.randint(0, 9999):04d}"
    letters = "".join(rng.python.choice(PLATE_LETTERS) for _ in range(3))
    return f"{digits} {letters}"


def licence_plate_is_valid(plate: str) -> bool:
    """True if this matches the modern Spanish plate format.

    >>> licence_plate_is_valid("1234 BCD")
    True
    >>> licence_plate_is_valid("1234 ABC")     # A is a vowel -- not allowed
    False
    >>> licence_plate_is_valid("M 1234 AB")    # the pre-2000 province format
    False
    """
    cleaned = plate.replace(" ", "").replace("-", "").upper()
    if len(cleaned) != 7:
        return False
    return (
        cleaned[:4].isdigit()
        and all(character in PLATE_LETTERS for character in cleaned[4:])
    )
