# Frozen pooled producer evidence

`producer-packages.json` retains gzip/base64 encodings of seven exact worker-emitted Report
packages. Tests verify their byte count and SHA256 before decoding. `provenance.json` pins their
immutable source candidate and packet; Report production implementation subsequently merged at
`4af947726dab91adec94b098fa9985d5bd6f15f6`. Historical package provenance remains unchanged.

`contracts/report-data/composite_review.v5.schema.json` retains the committed LF schema with SHA256
`d067fd9b356a882c0ea24b4c9ba2738f7f179883bc0e7afd4c76f950ed0944ce`.
The producer checkout CRLF schema has SHA256
`b9e8033b3637bc8799acfba972346f007aa1c31ff042e8b875b38dfdbcf8974d`;
decoded JSON is equal, raw bytes differ.

These packages came from recorded Performance bodies through Report API/native worker/SQLite and
a declining Render503 boundary. They support offline consumer admission, full workbook
reconciliation and registered HTTP/SQLite tests. They do not establish a live Performance
principal, joined Archive acceptance, institutional authority or monthly financial amendment
closure. Qualification remains EXPLICIT_RETAINED_CALCULATED_REPLAY and NOT_ATTESTED.
