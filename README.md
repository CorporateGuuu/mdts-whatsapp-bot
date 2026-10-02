# MDTS WhatsApp Repair Operations Bot

A compact Flask backend for WhatsApp-driven repair intake and job tracking. The project demonstrates webhook security, persistence, media integration, and workflow automation around a real operational use case.

## Engineering scope

- **API/runtime:** Flask
- **Messaging:** Twilio WhatsApp
- **Persistence:** PostgreSQL + SQLAlchemy
- **Media:** AWS S3 integration boundary
- **Testing:** pytest
- **Deployment shape:** WSGI-compatible Python service

## Implemented workflow

1. inbound WhatsApp message/photo reaches the webhook
2. request authenticity is validated at the Twilio boundary
3. repair job/intake state is created or updated
4. item/model/quantity/pricing information is tracked
5. jobs can be assigned to technicians
6. totals/status can be queried through the command interface

## Security boundary

The WhatsApp endpoint is expected to reject requests without a valid Twilio signature. The current test suite includes a negative-path webhook test that expects an unsigned/invalid request to return `403`.

A separate security-remediation pull request is cleaning tracked configuration/credential artifacts and adding credential scanning. That work must not be described as fully closed until provider-side credential rotation/cutover and runtime configuration are verified.

## Verified CI target

The portfolio CI introduced here installs the locked Python requirements and runs:

```bash
pytest -q
python tests.py
```

**Verified:** the portfolio CI passes on `main`, including dependency installation, `pytest -q`, and `python tests.py` using deterministic non-secret test configuration.

## Environment contract

Runtime configuration includes:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_NUMBER`
- `DATABASE_URL`
- optional AWS/S3 media configuration
- application secret/timezone/business settings

Only placeholders belong in tracked example files. Runtime secrets should be injected by the deployment environment.

## Database model

The repository includes schema for:

- technicians
- repair jobs
- job items

This keeps technician assignment, intake state, and repair-item economics in persistent storage rather than relying on chat history.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
psql "$DATABASE_URL" -f schema.sql
flask --app app run --host 0.0.0.0 --port 5000
```

## Portfolio role

This is a **supporting backend/integration project**, not a flagship distributed-systems project. Its value is that it is small enough for an interviewer to review the webhook, persistence, and test boundaries quickly.

## Hardening roadmap

- verify CI on every pull request
- add disposable PostgreSQL integration tests
- test Twilio signature success and failure paths with deterministic fixtures
- mock S3 integration and test media failure behavior
- add structured request/job correlation IDs
- document retry/idempotency behavior for duplicate webhook delivery
- add health/readiness semantics and deployment smoke tests
