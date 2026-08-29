# Security and Controls

What protects `lotus-render`, what deliberately does not live here, and what a deployment must
therefore provide. Measured against `main`.

## The controlling fact: this service does not authenticate callers

`lotus-render` performs **no authentication and no authorization of its own**. There is no API key,
no bearer-token check, no tenant claim and no per-caller policy anywhere in the request path. The
published OpenAPI description states the assumption directly: *authentication and authorization are
enforced by governed platform ingress and service-to-service policy before this internal API is
reached*.

Two consequences follow, and both are deployment obligations rather than service behaviour:

1. **Anything that can reach the port can submit a render or read any job's status.** The render job
   id is the only thing standing between a caller and another caller's job posture, and it is not a
   secret.
2. **`/metrics` and `/metadata` are equally unauthenticated.** They are support-safe by design — see
   below — but they are still service-internal surfaces that should not be routed to the public
   internet.

Treat network reachability as the access control. `lotus-render` is an internal service and must be
deployed as one.

## What the service does enforce

| control | mechanism | effect |
|---|---|---|
| host boundary | `TrustedHostMiddleware` over `LOTUS_RENDER_ALLOWED_HOSTS` | requests arriving with an unknown `Host` are rejected before routing |
| request size | `RequestBodySizeLimitMiddleware` | every received body is streamed into a bounded buffer before route handling; oversized and under-declared bodies return `413 request_body_too_large`, while malformed or negative lengths return `400 invalid_content_length`, without echoing package content |
| cross-origin | CORS middleware is **only installed when origins are configured** | with the empty default there is no CORS path at all, rather than a permissive one |
| execution capacity | bounded limiter around the compile threadpool | over the limit, `429` rather than an unbounded queue of blocking work |
| compile duration | `LOTUS_RENDER_RENDER_COMPILE_TIMEOUT_SECONDS` | an overrunning compile becomes a `failed` job with category `timeout`, not a held thread |

These are blast-radius controls. None of them establishes who the caller is; they bound what a
reachable caller can consume. Defaults and tuning live in [Configuration](Configuration).

### Bounded request-body enforcement

`RequestBodySizeLimitMiddleware` rejects an invalid declaration or a declared oversize before route
handling, then streams and counts the actual bytes for every request. This second measurement closes
both absent-length and under-declared bypasses. A body within the configured limit is replayed
unchanged to the route; the buffer cannot exceed the service limit. This matches the established
`lotus-report` boundary posture rather than relying on ingress or caller honesty.

## Support-safe responses

Every read surface is constructed so that operating the service does not require handling client
data. Diagnostics, status, artifact metadata and metrics never return:

- raw `report_data` or any part of the render package's content
- raw Typst or Docker engine stderr
- artifact storage locations or archive retention truth
- upstream replay or regenerate commands

`GET /renders/{id}/diagnostics` additionally omits caller identity and the package's own correlation
and trace identifiers, so a support engineer can classify and route a failure without seeing who
requested the document. Metrics carry bounded label values only — never a render job id, report job
id, portfolio, tenant, trace, correlation or storage label — and the recorder falls back to a known
value rather than emitting an unbounded one.

The submit response is the exception, and deliberately so: it returns to the caller that supplied
the package, so it echoes `requested_by`, `package_correlation_id` and `package_trace_id` back for
correlation.

## What is persisted

The render store keeps support-safe evidence — snapshot identity, lineage refs, disclosure refs,
caller identity, and the package's correlation and trace identifiers — so a render can be accounted
for after the fact. It does not store raw report data and it does not hold archive retention truth.
The durable home of a rendered artifact is `lotus-archive`, not this service.

## Data the service does not own

`lotus-render` fetches nothing. It has no client, portfolio, position, performance, risk or advisory
data source, and no path by which it could acquire one. Everything it renders arrives in the
package, and everything it renders is presentation of content another service already approved:

- it does not approve, rewrite, infer or fetch advisory facts
- it does not grant client-publication authority — proof-pack packages carry
  `client_publication_authority_granted=false` and it stays that way
- it does not own archive retrieval, retention, legal hold, replay, rerender, regenerate or document
  distribution

This is why the service can be operated without client-data handling procedures: the sensitive
material is in flight through it, never at rest in it beyond the job evidence above.

## Secrets

Current settings contain no secrets, and no code path reads a credential. Keep it that way: no
build, registry, database or service credentials through Docker `ARG` or persisted `ENV` defaults.
Runtime secrets must come from the deployment platform and stay out of metadata, logs, metrics and
OpenAPI examples.

## Supply chain

`make security-audit` runs `pip-audit` behind a governed exception file at
[`security/pip-audit-exceptions.json`](https://github.com/sgajbi/lotus-render/blob/main/security/pip-audit-exceptions.json).
An exception must be time-bounded, owned and linked to a GitHub issue; the gate fails when one is
expired, unowned or unlinked. The audit runs on every CI lane, so an exception cannot quietly
outlive its window.

## Integrity of what is produced

Two different claims are made about a rendered artifact, and conflating them is the common mistake:

| claim | field | what it means |
|---|---|---|
| artifact identity | `artifact_sha256` | truthful hash of the concrete PDF file produced |
| repeatability | `bounded_determinism_fingerprint` | stable across renders **within the governed Typst 0.14.2 runtime envelope**, computed after normalising volatile PDF metadata |

Raw PDF bytes are **not** claimed to be stable across renders: Typst remints document ids and
creation timestamps per artifact. Any control that needs "the same document twice" must compare the
bounded fingerprint, not the file hash. Pinning `LOTUS_RENDER_RUNTIME_ENGINE_VERSION` is what keeps
that claim meaningful — changing it invalidates prior fingerprint comparisons.

## Read next

1. [Configuration](Configuration) — the boundary settings and their defaults
2. [Operations](Operations) — what the support-safe surfaces actually tell you
3. [Development and Testing](Development-and-Testing) — the gates that keep these properties true
