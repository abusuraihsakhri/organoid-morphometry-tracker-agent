# Organoid Morphometry Tracker Agent

A Python CLI, FastAPI service and standalone browser demonstration for **rule-based screening of user-supplied organoid-associated numeric measurements**.

The current implementation evaluates two numeric metrics, a status descriptor, and a manual escalation flag. It **does not** analyze microscopy images, perform segmentation, reconstruct 3D structures, compute lumen-to-wall ratios, fit growth curves, or calculate drug-response IC50 values. The 25 and 12 cutoffs are repository-defined demonstration thresholds, not validated biological reference ranges. Output is unsuitable for clinical decisions.

## Browser demonstration

Open [docs/index.html](docs/index.html) locally in a modern browser without installing Python. The same screen is served at the Python API root (/).

Enter synthetic task/specimen identifiers and numeric metrics, select **Evaluate**, review the triggered alerts, and optionally **Export JSON**. Browser evaluation runs locally in JavaScript using the primary Python supervisor's rules (primary >25, secondary >12, critical flag, and anomaly keywords). It does **not** create HMAC audit signatures or contact any backend. No persistent browser storage is used.

## Python installation and examples

Requirements: Python 3.10 or newer.

~~~bash
python -m pip install -e '.[test]'
export AUDIT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

python cli.py audit --task-id TASK-001 --target ORG-001 --primary 28.5 --secondary 14.2 --status DISCORDANT
python cli.py batch -i sample.csv -o results.csv
python cli.py verify-audit
python cli.py serve --host 127.0.0.1 --port 8000
~~~

The API serves the browser at http://127.0.0.1:8000/ and interactive API documentation at http://127.0.0.1:8000/docs. The generated OpenAPI source of truth is at /openapi.json. The /metrics endpoint returns JSON; /metrics/prometheus provides text-format metrics. POST /api/audit evaluates input metrics.

The second, older workflow remains supported via python organoid_vision_app.py audit. Its secondary metric threshold is 10 rather than 12. The two pipelines are not interchangeable.

### CSV input

Required columns: task_id, target_identifier, primary_metric. Optional fields: secondary_metric, status_descriptor, is_critical_flag. Invalid rows are skipped and reported to stderr. See [sample.csv](sample.csv).

## Privacy and security

Use **synthetic or adequately de-identified** data only. Identifier-pattern checks do not guarantee de-identification or HIPAA compliance.

AUDIT_SECRET_KEY is required for HMAC-SHA256 signing of **in-memory** audit records. Verification recalculates each entry's signature and chain link. Logs are not persisted and are not a durable regulated audit trail. Do not reuse the legacy signing key exposed in older repository history.

When AUDIT_API_TOKEN is configured, /api/* and metrics endpoints require an Authorization header with the value Bearer followed by that token. Docker Compose requires both AUDIT_SECRET_KEY and AUDIT_API_TOKEN. Do not expose the service publicly without appropriate authentication, network controls and rate limiting.

The browser tool never transmits entered values, but its basic identifier-pattern checks are not a de-identification procedure.

## Testing

~~~bash
pytest -q
python -m compileall -q agents organoid_vision cli.py enrichment.py simulator.py
python -m pip check
~~~

GitHub Actions checks Python 3.10–3.12, package installation, the test suite, audit guards and browser JavaScript syntax.

## Docker

~~~bash
export AUDIT_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export AUDIT_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up --build
~~~

The local application is exposed on port 8000. Container builds exclude local .env files; only run the API on a trusted network unless production security controls are provided.

## Architecture and limitations

The core stack comprises Python, Pydantic v2, FastAPI, Uvicorn and standard-library cryptography. The LLM integration currently supports a deterministic **mock only**; OpenAI, Claude and Ollama providers are not implemented. Additional enrichment classes and the legacy organoid_vision workflow are demonstrations, not validated image-analysis systems.

Licensed under the [MIT License](LICENSE).
