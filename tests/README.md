# Tests

Regression cover for the multi-tenancy and account-security behaviour — the
parts where a quiet failure means one agency sees another's data, or nobody
finds out an email was never sent.

## Running

Use the interpreter that runs the app, so its dependencies are present:

```bash
# on the server
cd /opt/wmd-plotter && /opt/wmd-plotter/.venv/bin/python tests/run_all.py

# locally
python3 tests/run_all.py

# one suite
python3 tests/run_all.py tak
python3 tests/test_password_reset.py
```

No pytest, no test dependencies. The suites are plain scripts, so they run
anywhere the app runs — including on the box that is actually misbehaving.

Each suite runs in its own process. They set module-level state (database path,
patched `smtplib`, in-memory stores) that would otherwise bleed between suites
and make results depend on import order.

## Safety

**The tests never touch `backend/users.db`.** Every suite calls
`helpers.isolated_db()` before importing `main`, which repoints `db.DB_PATH` at
a fresh temporary file. Import order matters: `main` reads `DB_PATH` at import
time, so the call has to come first.

If you add a suite, start it the same way, and verify:

```bash
shasum backend/users.db && python3 tests/run_all.py >/dev/null && shasum backend/users.db
```

The two digests must match.

## What each suite covers

| Suite | Covers |
|---|---|
| `test_tak_scoping.py` | TAK servers resolve per organization. No fallback to the site admin's server, no cross-org listing or modification, `profile_id` overrides cannot escape scope, and an org move takes effect on an already-issued token. |
| `test_user_isolation.py` | Model results are per user. Concurrent users don't overwrite each other, exports contain only your own work, TAK packages and Google Earth feeds use unguessable capability tokens, retired public URLs return 410, and both in-memory stores stay bounded. |
| `test_notifications.py` | Access-request email actually sends. Links use the deployed domain, failures are recorded rather than swallowed, and a hostname pasted into the From field is caught before it reaches Brevo. |
| `test_approval.py` | Approving an account emails the user at their enrollment address, and reports honestly when nobody was contacted. |
| `test_password_reset.py` | The reset flow, plus no account enumeration, hash-only storage, single use, expiry, supersession, and rate limiting. |

Billing has its own suite on the `billing-wip` branch, where the code lives.

## Notes for writing more

- `helpers.FakeSMTP` captures mail instead of delivering it. Sends run on daemon
  threads, so use `smtp.wait()` before asserting and `smtp.settle()` before
  clearing — otherwise a message from the previous step lands after your clear
  and gets attributed to the wrong one.
- `helpers.body_text()` decodes the payload. `MIMEText(..., 'utf-8')`
  base64-encodes the body, so matching strings against the raw wire format finds
  nothing and every assertion passes for the wrong reason.
- `helpers.clear_env()` drops notification env vars after importing `main`.
  `main` calls `load_dotenv(backend/.env)`, and on a developer machine that file
  supplies `NOTIFY_FROM` and friends, which satisfy the environment fallbacks and
  mask what the test configured. A real bug once hid behind exactly this.
- `TestClient` keeps a cookie jar. For genuinely unauthenticated requests use a
  second client (`anon` in the existing suites), or the last login's cookie is
  sent and the assertion passes when it should not.
