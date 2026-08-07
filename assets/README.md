# Vendored assets

## `india-claimed.geojson`

India's boundary **including the full claimed territory**: Jammu & Kashmir,
Ladakh, Aksai Chin, the Shaksgam Valley, Pakistan-administered Kashmir and
Arunachal Pradesh, in accordance with the official boundary of India as
published by the Survey of India.

**Why it is vendored at all.** Plotly's built-in country geometry comes from
Natural Earth, whose `IND` polygon follows a different convention and stops
around 35.5°N. That geometry ships inside plotly.js and cannot be edited, so the
only way to draw India complete is to supply the shape.

| | |
|---|---|
| Source | [datameet/maps](https://github.com/datameet/maps), `Country/india-composite.geojson` |
| Licence | **CC BY 4.0** (the repository's datasets; its code is MIT) |
| Attribution | Data{Meet}, https://github.com/datameet/maps |
| Retrieved | 2026-08-07 |
| Source size | 10.5 MB, 252,604 coordinate pairs |
| Committed size | 45 KB, 2,598 coordinate pairs |

**It is a derivative, and the derivation is reproducible.**
`tools/simplify_boundary.py` performs Douglas-Peucker at a 0.02° tolerance and
rounds to four decimal places:

    python tools/simplify_boundary.py india-composite.geojson \
        assets/india-claimed.geojson --tolerance 0.02

The tolerance is derived rather than tasted. India spans about 30° of latitude
and the map is drawn roughly 400px tall, so one pixel is 0.075°; a 0.02°
tolerance moves no vertex more than about a quarter of a pixel. Four decimal
places is roughly 11 metres, far below the same threshold.

**The extent is asserted by a test.** `tests/test_map_geometry.py` checks the
northern reach above 36°N and the eastern reach beyond 96°E, so a future
resimplification that quietly clipped a claimed region would fail rather than
render a smaller India.

**Attribution is rendered, not just filed here.** CC BY 4.0 requires credit, and
the Dashboard surface names the source beneath the map.
