# Location and recording time — issue #33

Both file intake and Edit details use the same location and recording-time fields.
No case schema or existing metadata API changes are required.

A location can remain plain text. Search is explicit, returns up to five places,
and selecting a result stores its name and latitude/longitude in the existing
240-character location field. The selected pin appears in an OpenStreetMap map
with attribution and a full-map link. Editing the text removes the old pin unless
the text still contains valid coordinates. Search failures leave manual text intact.
Only the location search term goes to the geocoder; no footage or other case data
is included. The map is loaded directly from OpenStreetMap after pin selection.

## Provider choice and deployment

[Photon's official documentation](https://github.com/komoot/photon#demo-server)
permits reasonable project usage of its public demo, with throttling and no
availability guarantee. The server uses its documented
[GeoJSON search API](https://github.com/komoot/photon/blob/master/docs/api-v1.md).
Search requires an explicit action rather than requesting on every keystroke.
The proxy identifies Rewind, limits upstream requests to one per second per
process, returns at most five validated places, caps response size and timeout,
and caches up to 256 queries for six hours in memory. Concurrent or burst searches
receive 429 rather than forming an unbounded upstream queue.

Set `PHOTON_BASE_URL` to another compatible instance without a frontend rebuild;
an empty value disables search while keeping manual entry. The public endpoint
is suitable for this single-process local demo. For multiple workers or higher
traffic, use a dedicated instance and deployment-wide rate control. The cache
resets on restart. No API key is required or exposed.

[Public Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/)
prohibits autocomplete and restricts generated generic lookup services; it was
not selected. Maps use OpenStreetMap's own embed endpoint and visible
[OpenStreetMap/ODbL attribution](https://www.openstreetmap.org/copyright).

## Recording time

Native platform date and time controls store local `YYYY-MM-DDTHH:mm[:ss]`, or
just a date. No timezone, UTC offset, EXIF timestamp or analysis clock offset is
inferred. A time requires a date. Clearing the date clears its time.

The optional time-description mode supports approximate times and explicit
reported timezone text. Unsupported legacy values, including timestamp offsets,
remain as written and are editable without implicit parsing or conversion. The
user can explicitly replace them with native controls. Metadata remains reported,
unverified context; it does not establish synchronization.

Automated tests mock the geocoder and map, exercise intake/edit/reload and network
failure, and verify local time/legacy preservation. They do not contact public
providers or establish location accuracy.

A separate manual live-provider smoke test on 2026-10-17 searched the public
example “Market Street, San Francisco” and returned five valid coordinate-bearing
results through the production adapter. This checks connectivity/response parsing,
not the accuracy of a case location. No case metadata was sent.
