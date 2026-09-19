"""
Deterministic randomness.
===============================================================================

WHAT IS THIS FILE?
------------------
Everything in this repository is random, but the *same* random every time.
Run the build today, run it again next year on a different machine, and you
get byte-for-byte identical files.

WHY DOES THAT MATTER?
---------------------
Three reasons, in order of how much they will bite you:

1. **Git diffs.** If rebuilding produced different data, every rebuild would
   show up as "all 231 files changed" and the repository history would be
   useless. With fixed seeds, rebuilding after a code change shows you
   exactly which values your change affected -- which is also the fastest way
   to review your own work.

2. **Stable links.** People hot-link these files into their projects (see
   docs/linking-files.md). A file that silently changes underneath them is
   worse than no file at all.

3. **Reproducibility.** Anyone can re-run the build and confirm they get the
   files that are committed. That is what makes "this data is synthetic" a
   verifiable claim rather than a promise.

WHAT IS A "SEED"?
-----------------
A random number generator is not really random -- it is a machine that turns
one starting number (the *seed*) into a long, unpredictable-looking sequence.
Give it the same seed and you get the same sequence back. So "random but
reproducible" is not a contradiction: it is just a generator whose seed we
wrote down.

    >>> import random
    >>> random.Random(42).randint(1, 100)
    82
    >>> random.Random(42).randint(1, 100)   # same seed, same answer, always
    82

HOW SEEDS ARE DERIVED HERE
--------------------------
There is one MASTER_SEED for the whole repository. Every topic, and every
entity within a topic, derives its own seed from it by hashing:

    MASTER_SEED  ->  seed_for("clinical")  ->  seed_for("clinical", "patients")

This matters more than it looks. If every topic shared one generator, then
adding a single row to `hospitals` would shift the sequence for everything
generated afterwards, and `education` would change too -- for no reason.
Deriving a separate stream per entity keeps changes local: touch the clinical
generator and only clinical files move.
"""

from __future__ import annotations

import hashlib
import random

import numpy as np
from faker import Faker

# ---------------------------------------------------------------------------
# The one number this whole repository hangs from.
# ---------------------------------------------------------------------------
# Changing it regenerates every value in every file. Don't, unless you mean
# to -- and if you do, ship it as a new major version tag, because anyone who
# pinned a URL to the old data will see it change.
MASTER_SEED = 20240614

# Faker ships dozens of locales. This repository generates SPANISH people
# and places -- names, surnames, cities -- while every column name, field
# description and documentation page stays in English.
#
# That split is deliberate. The data is Spanish so that it exercises the
# things Spanish software actually has to handle: two surnames per person,
# accented characters, province-coded postal codes and phone numbers, the
# "ñ" character. The documentation is English so the repository is useful to
# the widest possible audience.
#
# Note that addresses and telephone numbers do NOT come from Faker -- they
# come from generators/common/geography.py, which keeps the city, province,
# postal code and dialling prefix consistent with one another. Faker cannot
# do that, and inconsistent addresses were the single most obvious tell that
# a dataset was generated rather than observed.
LOCALE = "es_ES"


def seed_for(*parts: str) -> int:
    """Derive a stable 32-bit seed from the master seed plus some labels.

    Uses SHA-256 rather than Python's built-in `hash()`, because `hash()` for
    strings is randomised per process (PYTHONHASHSEED) and would therefore
    give different results on every run -- exactly what we are trying to
    avoid.

    >>> seed_for("clinical", "patients") == seed_for("clinical", "patients")
    True
    >>> seed_for("clinical", "patients") == seed_for("clinical", "doctors")
    False
    """
    label = ":".join((str(MASTER_SEED), *parts))
    digest = hashlib.sha256(label.encode("utf-8")).digest()
    # Take the first 4 bytes as an unsigned 32-bit integer. numpy's seeding
    # accepts anything up to 2**32 - 1, so this keeps both generators happy.
    return int.from_bytes(digest[:4], "big")


class Rng:
    """A bundle of every random source an entity generator needs, all seeded
    from the same derived seed.

    Why a bundle? Because the three libraries we use each have their own
    generator, and it is very easy to seed two of them and forget the third --
    at which point the build stops being reproducible in a way that is
    genuinely hard to notice. Handing generators a single `Rng` object makes
    the mistake impossible.

    Usage
    -----
        rng = Rng("clinical", "patients")

        rng.python.choice(["A", "B"])        # stdlib random.Random
        rng.numpy.normal(70, 12, size=100)   # numpy Generator, for statistics
        rng.faker.name()                     # Faker, for names and addresses
    """

    def __init__(self, *parts: str) -> None:
        self.label = ":".join(parts)
        self.seed = seed_for(*parts)

        #: Python's standard library generator. Best for picking from lists,
        #: shuffling, and simple integer ranges.
        self.python = random.Random(self.seed)

        #: numpy's generator. Best for statistical distributions -- normal,
        #: lognormal, poisson -- which is how we make data look naturally
        #: clustered instead of uniformly spread.
        self.numpy = np.random.default_rng(self.seed)

        #: Faker, for realistic names, streets, cities and companies.
        self.faker = Faker(LOCALE)
        self.faker.seed_instance(self.seed)

    def __repr__(self) -> str:
        return f"<Rng {self.label!r} seed={self.seed}>"

    # -- small helpers used all over the topic generators -------------------

    def maybe_null(self, value, probability: float):
        """Return `value`, or None with the given probability.

        Real datasets have gaps: a patient with no recorded phone number, a
        customer who never filled in their email. Code that consumes data has
        to cope with that, so we put a controlled number of holes in the
        optional columns on purpose.

        >>> rng = Rng("demo")
        >>> rng.maybe_null("anything", probability=0.0)
        'anything'
        """
        return None if self.python.random() < probability else value

    def weighted_choice(self, options: dict):
        """Pick one key from ``{value: weight}``.

        Used wherever a real-world distribution is lopsided -- blood types,
        payment methods, appointment statuses. Uniform random choice is the
        single most common thing that makes fake data feel fake.

        >>> rng = Rng("demo")
        >>> rng.weighted_choice({"common": 99, "rare": 1}) in {"common", "rare"}
        True
        """
        keys = list(options.keys())
        weights = list(options.values())
        return self.python.choices(keys, weights=weights, k=1)[0]

    def date_between(self, start, end):
        """A uniformly random date between two ``datetime.date`` values."""
        span_days = (end - start).days
        if span_days <= 0:
            return start
        from datetime import timedelta

        return start + timedelta(days=self.python.randint(0, span_days))
