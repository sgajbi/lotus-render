#set page(margin: (x: 1.5cm, y: 1.7cm))
#set text(size: 11pt)
#show heading.where(level: 1): set text(size: 18pt, weight: "bold")
#show heading.where(level: 2): set text(size: 13pt, weight: "semibold")

= Portfolio Review

Client: ${CLIENT_NAME}

Portfolio: ${PORTFOLIO_NAME}

As of: ${AS_OF_DATE}

Total Value: ${CURRENCY} ${TOTAL_VALUE}

Timezone: ${TIMEZONE}

== Executive Summary

${SUMMARY_PARAGRAPH}

== Review Observations

${OBSERVATIONS}

== Governance

Template: ${TEMPLATE_ID} ${TEMPLATE_VERSION}

Render Job: ${RENDER_JOB_ID}

Requested By: ${REQUESTED_BY}

Correlation ID: ${CORRELATION_ID}

Trace ID: ${TRACE_ID}

Determinism: ${DETERMINISM_STATEMENT}
