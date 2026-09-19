# Working with the JPEG files

> ⚠️ **SYNTHETIC DATA.** See [synthetic-data-guarantees.md](../synthetic-data-guarantees.md).

JPEG is used here for **photographs and scans** — content with smooth
gradients and no sharp edges, where lossy compression is appropriate and the
file-size saving is worth it.

Diagrams, charts and barcodes go in [`png/`](png.md) instead, because JPEG
would put visible artefacts around every sharp line.

## Status

The JPEG content — product photos, document scans, EXIF-bearing images — is
planned but not yet generated. See the repository
[README](../../README.md) for what has landed.

## What will be here

Images carrying realistic EXIF metadata, which is the part most worth
testing against:

| | |
|---|---|
| Orientation | The flag that makes thumbnails come out sideways if ignored |
| GPS | Coordinates, for testing location extraction — and stripping |
| Camera make/model | Invented, but in the real tag structure |
| Stripped variants | The same image with no EXIF at all |

## Common mistakes to expect

**Ignoring the orientation flag.** A photo can be stored rotated with a tag
saying "display this the other way up". Libraries that ignore it produce
sideways thumbnails. `PIL.ImageOps.exif_transpose()` handles it.

**Assuming EXIF exists.** Many real-world images have none — stripped by an
upload pipeline, or never written. Code should not assume the dictionary has
keys in it.

**Leaking GPS.** If you accept user photo uploads, EXIF GPS is a privacy
problem. The stripped variants exist so you can test that your pipeline
removes it.
