# Controlled Report r2 unit examples

These exact packages were supplied for lotus-report#417 RPT04 and lotus-render#352.
The Report owner emitted authored transport inputs through the local registered Report
API, worker and SQLite store with Render deliberately returning 503. They are
`UNIT_FIXTURE_NOT_SOURCE_CAPTURE`: no Manage runtime capture, workbook, Archive custody,
bank authority or joined runtime qualification is established by their provenance.

The supplier receipt SHA256 is
`5feb23c39bba98d60705bbdcd399a0db7c184d68d706453b1338e14dea837647`.
The consumer tests pin the complete package bytes:

| Package | Bytes | SHA256 |
| --- | ---: | --- |
| evaluated_only-render-package.json | 90763 | 9d55e16a07146fa9f43b46897c849230cb3f4dc9f62b00331015c81ac7b71e31 |
| published-render-package.json | 100234 | 3e84458fca2fedfeabdb4d20caffa8c65a1c7ca33b33096352ee4c260a14b613 |

The frozen r2 dataset schema and current r3 interface matrix live under `contracts/report-data/`.
Consumer tests reconstruct all source populations, pointers, policies and cells independently;
no producer implementation is imported. These packages do not replace legacy goldens.

`actual-published-datasets.json` additionally retains exact gzip/base64 encoded Report-produced
three-month datasets for both CompositeDefinition v1 and v2. Decompression is lossless and tests
pin original byte counts and SHA256. These derive from actual controlled Manage795 native TCP /
PostgreSQL source responses, with synthetic unsigned authority and trusted ingress. The source
manifest is `7ad3f141ac883bf631cffbc4db023e20b48ee2ed160f814464d75bb4fe77993c`.
This is offline dataset/source-projection admission. No custody envelope, Report revision,
source capture, joined runtime, workbook or Archive evidence is invented around these datasets.

`actual-published-worker-packages.json` retains the exact subsequent Report registered API/worker/
SQLite emissions using those captured bodies via controlled offline replay (15 reads per package).
The receipt is `ef92abea6141e09575684b23e2e680922323983da0c95b9405ca8201cee59186`.
Tests pin the full original package bytes after decompression, including the genuine Report
revision and custody envelope. The owning consumer renders and independently parses those
packages. Producer Render503 and offline transport remain explicit; these tests do not establish
an authenticated Report-to-Manage network campaign or actual Archive custody.
