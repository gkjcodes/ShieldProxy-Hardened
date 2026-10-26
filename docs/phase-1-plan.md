# ShieldProxy Phase 1 Implementation Plan
## Security Core and Gateway Integrity

**Directory:** `C:\Users\gopal\ShieldProxy-Hardened`
**Phase:** 1 of 4
**Target:** Address Confirmed Vulnerabilities (SEC-AUTH-01/02/03, SEC-DATA-01/02, SEC-RATE-01/02/03, SEC-ASYNC-01/02, SEC-AI-05, SEC-OPS-01, SEC-CONFIG-01/02, SEC-DEP-01, SEC-BUG-01)
**Baseline Score:** 2.38 / 10.0
**Phase 1 Target:** ~5.20 / 10.0

---

## 1. Task Decomposition

Based on the baseline security audit and source code inspection, Phase 1 is decomposed into 6 discrete, testable workstreams:

1. **Workstream 1.1: Dependency and Configuration Integrity (CP-1.1)**
   - Prune confirmed dead packages (`llama-cpp-python`, `scikit-learn`) from `backend/requirements.txt`.
   - Implement `backend/config.py` using `pydantic_settings.BaseSettings` with strict types:
     - `APP_MODE`: `development`, `test`, `protected` (production).
     - `USE_MOCK_LLM`: boolean flag.
     - `REDIS_URL`, `REDIS_REQUIRED_IN_PROTECTED`: failure policy for Redis in protected mode.
     - `CORS_ALLOWED_ORIGINS`: explicit parsed list, never wildcard `*` with credentials.
     - `MAX_BODY_SIZE_BYTES`: default 65,536 (64 KiB).
     - `MAX_MESSAGE_LENGTH`: default 2,000 characters.
     - `GATEWAY_TIMEOUT_SECONDS`: default 15.0 seconds.
     - `API_KEYS`: mapped dictionary/list of valid hashed API keys with tenant ID and roles.
   - Author `.env.example` with placeholders only (zero secrets).

2. **Workstream 1.2: Authentication & Trusted Tenant Identity (CP-1.2)**
   - Create `backend/middleware/auth.py` with FastAPI dependencies:
     - `get_current_tenant`: Extracts `X-API-Key` or `Authorization: Bearer <key>`, performs constant-time hash comparison, resolves `TenantContext(tenant_id, role, rate_limit_rpm)`.
     - `require_admin_role`: Enforces admin privileges for dashboard/management endpoints.
   - Update `backend/models/schemas.py`: Deprecate unverified body `client_id` for security decisions.
   - Refactor `backend/routers/chat.py` and `backend/routers/dashboard.py` to use `auth.py`.

3. **Workstream 1.3: Atomic Redis Rate Limiting & Outage Failure Policy (CP-1.3)**
   - Rewrite `backend/middleware/rate_limiter.py` to use an atomic Redis Lua script:
     - Calculates continuous token refills, decrements, and sets key expiry in a single atomic transaction.
     - Keys rate limits by verified `tenant.tenant_id`.
   - In-memory degraded fallback: Thread-safe local token bucket guarded by `asyncio.Lock`.
   - Enforce failure policy: In `protected` mode, if `REDIS_REQUIRED_IN_PROTECTED=True` and Redis fails, reject with 503 Service Unavailable rather than failing open.
   - Update `backend/utils/redis_client.py` (`MockRedis`) to support real TTL expiration and time-based eviction.

4. **Workstream 1.4: Request Body Size Limiting & Secure Contracts (CP-1.4)**
   - Create `backend/middleware/body_limit.py`:
     - Inspects `Content-Length` header and enforces streamed byte length tracking (maximum 64 KiB default).
     - Rejects oversized requests immediately with HTTP 413 Payload Too Large without unbounded buffering.
   - Standardize error responses to avoid leaking internal exception stack traces or prompt content.

5. **Workstream 1.5: Zero-PII Audit Logging & Non-Blocking Gateway (CP-1.5)**
   - In `backend/routers/chat.py`, stop passing `req.message` to `audit_logger.log()`.
   - Log safe requests **after** LLM completion, recording true execution `latency_ms` (fixing SEC-BUG-01).
   - In `backend/middleware/audit_logger.py`, store only sanitized previews derived from scrubbed text, or record entity counts and HMACs.
   - In `backend/middleware/threat_classifier.py`, eliminate import-time synchronous HTTP probes.
   - In `backend/middleware/llm_gateway.py`, migrate to `AsyncOpenAI`, reuse a shared client instance, apply strict 15.0s timeouts, replace `time.sleep` with `await asyncio.sleep`, and fail explicitly with 503 instead of silent mock fallbacks in protected mode.

6. **Workstream 1.6: Health Probes, Regression & Checkpoint Verification (CP-1.6)**
   - In `backend/main.py`, split `/health` into:
     - `/health/live`: Process liveness probe (200 OK).
     - `/health/ready`: Deep readiness probe checking Redis ping, LLM reachability, and security control readiness.
   - Update frontend API client `src/services/api.js` to send configured `X-API-Key` and handle 401/413/429/503.
   - Build automated verifiers: `scripts/checkpoints/phase1.py` and `scripts/phase_check.py`.

---

## 2. Checkpoint Verification Matrix

| Checkpoint | Target Security Control | Verification Tooling | Exit Criteria |
| :--- | :--- | :--- | :--- |
| **CP-1.1** | Configuration & Dependency Integrity | `tests/test_config.py` | Invalid protected settings fail; no dead deps; placeholders only in `.env.example`. |
| **CP-1.2** | Authentication & Tenant Isolation | `tests/test_auth.py` | 401 on missing/bad key; role checks work; body `client_id` cannot spoof tenant. |
| **CP-1.3** | Atomic Rate Limiting & Fail Policy | `tests/test_rate_limiter.py` | Concurrent bursts throttled accurately; separate quotas per tenant; fail policy respected. |
| **CP-1.4** | Request Body Limits & Safe Errors | `tests/test_body_limits.py` | Bodies >64KB rejected with 413; chunked streams checked; no stack traces exposed. |
| **CP-1.5** | Privacy Logging & Async Hygiene | `tests/test_privacy_logging.py`, `tests/test_async_gateway.py` | Zero raw prompts in Redis; async non-blocking execution; 15s gateway timeout. |
| **CP-1.6** | Health Probes & Release Gates | `tests/test_health.py`, `npm run build`, `scripts/phase_check.py` | `/health/ready` reflects real state; frontend builds; verifier passes with code 0. |

---