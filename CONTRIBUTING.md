# Contributing

Contributions are welcome — especially new topics.

## Quick start

```bash
git clone https://github.com/jasocami/realistic-test-data
cd realistic-test-data

pyenv virtualenv 3.12.12 realistic-test-data     # or any Python 3.11+
pyenv local realistic-test-data
pip install -r requirements.txt -r requirements-dev.txt
sudo apt install graphviz               # optional, only to redraw the ERDs

python build.py --all
python -m pytest
```

## Adding a topic

**[docs/generators/adding-a-topic.md](docs/generators/adding-a-topic.md)** is
a full walkthrough, from an empty file to a passing test suite.

The short version: write `generators/topics/<name>.py` with reference data,
a schema and generators, then register it in `build.py` and
`tests/conftest.py`. That second line puts your topic through the entire
existing test suite.

## The rules

**Never hand-edit a generated file.** Everything in `csv/`, `json/`, `db/`,
`png/`, `schemas/` and `docs/topics/` is produced by `build.py`. Fix the
generator instead; your edit would be overwritten on the next build.

**Every column needs a real description.** The build enforces it — at least
40 characters, at least five informative words, plus an `example=` and a
`unit=` where relevant. This is not negotiable and not configurable: the
published documentation is generated from those strings.

**Builds must stay deterministic.** After `python build.py --all`,
`git status` must be clean. If it is not, something is unseeded — usually an
unordered `set`, a call to `hash()`, or a date derived from today.

**Money uses `Decimal`, never `float`.**

**Addresses come from `generate_address()`**, so the city, province, postal
code and phone prefix agree with one another.

**No real people, businesses or accounts.** See
[docs/synthetic-data-guarantees.md](docs/synthetic-data-guarantees.md).

## Before opening a pull request

```bash
python build.py --all       # regenerate
git status                  # must be clean, or show only intended changes
python -m pytest            # must pass
ruff check generators tests # must be clean
```

Add at least one test asserting an invariant specific to whatever you added.
The shared tests cover what is true of every topic; the interesting rules
are the ones only your data has.

## Reporting a problem with the data

If a record resembles a real person or business closely enough to concern
you, open an issue and it will be regenerated. Everything comes from a seed,
so fixing it means changing a constant and rebuilding — no manual editing.

## Licence

Data is [CC BY 4.0](LICENSE); code is [MIT](LICENSE-CODE) — see
[LICENSING.md](LICENSING.md). Contributions are accepted under the same
terms, and contributors are credited in the commit history.

If you add data drawn from a public classification system, add it to
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) in the same pull request.
