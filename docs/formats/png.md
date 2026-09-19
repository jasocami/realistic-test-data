# Working with the PNG files

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

PNG is used here for **lossless graphics**: diagrams, charts, logos,
barcodes and QR codes — anything with sharp edges, flat colour or
transparency, where JPEG's compression would produce visible artefacts.

Photographs and scans go in [`jpeg/`](jpeg.md) instead.

## What is here

| File | Every topic |
|---|---|
| `erd.png` | The entity-relationship diagram — every table, column and relationship |
| `erd.dot` | The Graphviz source, if you want to re-render at another size |

More PNG content (charts, barcodes, logos) is planned; see the repository
[README](../../README.md) for what has landed.

## The schema diagrams

Each `erd.png` shows every table with every column, `PK` and `FK` markers,
nullable columns greyed with a `?`, crow's-foot cardinality, and live row
counts. Relationship lines are **coloured by parent table**, which is what
makes a dozen crossing foreign keys traceable by eye.

They are generated from the same schema definitions as the data, so they
cannot drift out of date with it.

To re-render — at a different size, or as SVG or PDF:

```bash
sudo apt install graphviz          # or: brew install graphviz

dot -Tsvg png/clinical/erd.dot -o clinical.svg
dot -Tpng -Gdpi=200 png/clinical/erd.dot -o clinical@2x.png
```

## Loading it

```python
from PIL import Image
image = Image.open("png/clinical/erd.png")
print(image.size, image.mode)      # (2147, 1708) RGBA
```

## Common mistakes

**Assuming RGB.** These are RGBA — four channels. Code that indexes colour
channels positionally will be off by one. Use `image.convert("RGB")` if you
need three.

**Re-encoding as JPEG.** Text and sharp diagram lines develop visible
ringing artefacts. Keep diagrams as PNG.

**Transparency on a dark background.** The diagrams carry an opaque white
background deliberately, so they stay readable in GitHub's dark theme. If
you need transparency, re-render from the `.dot` source.
