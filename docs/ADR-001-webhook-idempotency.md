# ADR-001: Duplicate webhook delivery must be idempotent

## Status

Accepted design direction. Persistence implementation is intentionally deferred.

## Context

Messaging providers can retry webhook delivery when acknowledgements are delayed, connections fail, or a provider does not observe a successful response. A duplicate webhook must not create duplicate repair jobs, repeat technician assignments, or emit duplicate outbound notifications.

## Decision

Use the provider's stable message identifier as the idempotency key.

The production persistence design should:

1. store every inbound provider message ID in a dedicated ingestion table
2. enforce a unique database constraint on provider + message ID
3. process the business workflow in the same transaction when practical
4. return the previously accepted result for an already-seen message
5. distinguish received, processing, completed, and failed states when retries require recovery
6. retain correlation/request IDs for debugging without logging message bodies or credentials

## Why this is not implemented as an in-memory cache

An in-memory set would pass a local demo but fail across restarts, multiple workers, and horizontal scaling. The idempotency key belongs in persistent storage.

## Failure behavior

A message should not be marked completed before the business transaction succeeds. Failed attempts remain retriable.

Outbound notifications should also carry a stable operation key when the provider supports one, or be recorded before dispatch so duplicate sends can be detected.

## Portfolio scope

The current portfolio release implements request correlation, webhook signature verification, persistent repair data, health/readiness semantics, and CI. Persistent provider-message idempotency is documented here as the next production-hardening step rather than simulated with an unreliable local-only mechanism.