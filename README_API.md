# eugene_api - pyeugene REST/Swagger gateway

Wraps [pyeugene](./pyeugene) (the Champion OpenAPI Python wrapper) in a FastAPI
server so every TR code and Real ID that Eugene Investment & Securities
documents in `TRAN서비스IO.pdf` / `Real서비스IO.pdf` becomes its own REST
endpoint, fully documented in Swagger UI (`/docs`) - instead of hand-writing
and maintaining ~150 endpoints, they're generated from the PDFs.

## How it's built

```
Champion OpenAPI 개발가이드.pdf   (read for architecture, not parsed)
TRAN서비스IO.pdf  ─┐
Real서비스IO.pdf  ─┴─ tools/parse_catalog.py ─→ catalog/tran_catalog.json
                                                catalog/real_catalog.json
                                                       │
                                          eugene_api/catalog.py (load + sanitize)
                                                       │
                                     eugene_api/dynamic_models.py (Pydantic models)
                                                       │
                          eugene_api/routes/{tran,real}.py (one route per code)
                                                       │
                                              eugene_api/app_factory.py → FastAPI app
```

* `tools/parse_catalog.py` walks every bordered table in both PDFs (they use
  one consistent template per TR-code / Real-ID: 제목/설명/Subject/INPUT
  RECORD/OUTPUT RECORD/.../비고) and reconstructs each entry as JSON. Re-run
  it if Eugene ships an updated guide:

  ```bash
  python tools/parse_catalog.py tran "<path to TRAN서비스IO.pdf>" catalog/tran_catalog.json
  python tools/parse_catalog.py real "<path to Real서비스IO.pdf>" catalog/real_catalog.json
  ```

* `eugene_api/catalog.py` sanitizes the parsed fields (drops anything that
  isn't a clean identifier - a few entries embed multi-line "code = meaning"
  legends inside a Description cell that a naive table walk misreads as
  bogus extra fields). Every TR/Real code still ended up with a usable
  schema; codes that had some fields dropped are listed in the
  `dropped_fields` note in `GET /catalog/tran` / `/catalog/real`, and in the
  server's startup log - double check those against the original PDF if you
  need the exact full field list for one of them.

* `eugene_api/routes/tran.py` and `routes/real.py` register one FastAPI
  route per catalog entry, each with its own Pydantic request/response model
  built from that entry's fields - so Swagger shows real field names and
  descriptions per TR code, not one generic `Dict[str, str]` box.

## Running

### Mock mode (default) - any OS, no account needed

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-api.txt
uvicorn eugene_api.main:app --reload
```

Open http://127.0.0.1:8000/docs. `EUGENE_MOCK_MODE=true` (the default) swaps
in `eugene_api/mock_manager.FakeEugeneManager`, which answers every TR/Real
call with synthetic values shaped like the real response - useful for
exploring the generated API surface, wiring up a client, or writing
integration tests, all without Windows or a live account.

### Real mode - 32-bit Windows + Champion OpenAPI required

pyeugene itself only runs on 32-bit Windows with `pywin32`/`PyQt5` installed
and the Champion OpenAPI OCX registered (see the main [README](./README.md)
and `Champion OpenAPI 개발가이드.pdf` section 2 for the OCX/registry setup).
Once that environment is ready:

```bash
pip install -e .                    # installs pyeugene itself (pyproject.toml)
pip install -r requirements-api.txt
cp .env.example .env                 # fill in EUGENE_USER_ID/PW, EUGENE_CERT_PW, EUGENE_API_KEY
# set EUGENE_MOCK_MODE=false in .env
uvicorn eugene_api.main:app --host 0.0.0.0 --port 8000
```

Every request needs an `X-API-Key: <EUGENE_API_KEY>` header - the server
refuses to start in real mode if `EUGENE_API_KEY` isn't set.

Order/cancel/amend TR codes (Subject ending in `U`, e.g. `OTD1101U` 주식
주문) are **not registered at all** unless `EUGENE_ENABLE_TRADING=true` is
also set - a deliberate extra step before this server can move money on a
real account. `GET /catalog/tran` shows those codes with `"path": null`
when they're disabled.

## Endpoints

* `POST /tran/{code}` - one per TR code, e.g. `POST /tran/OTD3211Q` (주식
  매도 가능 수량). Body = the TR's input fields (all optional strings,
  matching pyeugene's `SetTranInputData`, which takes everything as a
  string). Response = `{"OutRec1": {...}, "OutRec2": [{...}, ...]}` typed
  per-code, mirroring `Eugene.getTranOutputData`.
* `GET /real/{code}/snapshot?key=<realKey>&timeout=5` - subscribes, waits up
  to `timeout` seconds for the next matching real-time update, returns it,
  then unsubscribes. The practical way to see a Real ID's shape from
  Swagger's "Try it out" (WebSocket has no OpenAPI schema).
* `WS /ws/real/{code}?key=<realKey>` - continuous push for as long as the
  socket is open. Authenticate with an `X-API-Key` header if your client can
  set one; otherwise pass `&api_key=<key>` in the query string (browsers
  can't set custom headers on a WebSocket handshake) - prefer the header
  when you can, since a query string can end up in logs/proxies/history.
* `GET /catalog/tran`, `GET /catalog/real` - machine-readable listing of
  every generated route, its fields, and whether it's currently enabled.
* `GET /utils/*` - the small set of code/name lookup and account/login
  Methods from the dev guide (`GetShCode`, `GetNameByCode`,
  `GetLoginState`, `GetAccInfo`, ...).
* `GET /health` - status, mode, and route counts.

## Fixed in pyeugene itself (not just worked around here)

While building this gateway we found and patched several pyeugene bugs/gaps
directly in [pyeugene/](./pyeugene), since fixing them there benefits every
pyeugene user, not just this API:

* **`getAccInfo()` crashed the whole subprocess.** [eugene.py](pyeugene/eugene.py)
  had `.dynamicCall("GetAccInfo()").split[";"]` (indexing the `split` method
  instead of calling it) - `TypeError` on every call. Worse, `eugene_proxy.py`'s
  queue loop had no exception handling at all, so that `TypeError` killed the
  entire subprocess, and every caller's blocking `get_method()`/`get_tr()`/
  `get_real()` would then hang forever. Filed as an upstream issue (see below)
  and fixed here: the `.split[";"]` → `.split(";")` typo, plus try/except
  around all three queue-processing blocks in `eugene_proxy.py` so a bug in
  any single call reports an `{"Error": ...}` payload instead of taking the
  whole manager down.
* **Real-time updates now carry which subscription they belong to.**
  `Eugene.process_event_real_data` receives `realId`/`realKey` straight from
  the `OnGetRealData` callback but used to discard them before queuing the
  data - callers had no way to tell which of several active subscriptions an
  update was for (pyeugene's own README example works around this by
  filtering by symbol client-side). It now stamps every update with
  `_realId`/`_realKey`/`_shCode`, and `RealDispatcher` in this gateway routes
  on those instead of guessing from field shape.
* **No continuation/paging.** `requestTran(rqId, trCode, "", 20)` had the
  next-key and request-count hardcoded. `eugene_proxy.py`'s `tr` handler now
  reads `nextKey`/`requestCnt` from the `tr_cmd` dict (still defaulting to
  `""`/`20` for backward compatibility), and `POST /tran/{code}` exposes them
  as `next_key`/`request_cnt` query params. Note this only wires the
  mechanism through - which response field holds the next key is
  TR-specific and still needs checking against `TRAN서비스IO.pdf` per code.
* **Concurrency.** Two threads calling `put_tr()`+`get_tr()` (or
  `put_method()`+`get_method()`) at the same time could read each other's
  response, since there's one shared queue pair for the whole process.
  `EugeneManager.request_tr()`/`request_method()` now do the put+get pair
  atomically under an internal lock; `eugene_api/service.py` uses these
  instead of rolling its own locking.
* **제휴사(partner) 로그인 연결.** `Eugene.loginPartner()` existed but
  `EugeneProxy` never called it. `EugeneManager(..., partner_code=...)` /
  `EugeneProxy(..., partner_code=...)` now use `CommLoginPartner` when a
  partner code is given (`EUGENE_PARTNER_CODE` in this gateway's `.env`).

`tools/test_pyeugene_fixes.py` exercises all of these against the real
`pyeugene` source (with just enough of `win32gui`/`PyQt5`/`pythoncom`
stubbed out to import it) without needing Windows:

```bash
PYTHONPATH=. python tools/test_pyeugene_fixes.py
```

## Known limitations (still open)

* **FID 조회 (`RequestPortfolioFid`) is not implemented at all** - the
  `FID_API` section in `eugene.py` is empty. The dev guide PDF we have only
  goes up to page 13 (through 5.1.1 로그인); the exact `dynamicCall`
  signatures for `RequestPortfolioFid`/`GetFidOutputRowCnt`/
  `GetFidOutputData` are in section 5.1.4, which isn't in the copy we have.
  Guessing a COM call signature for a brokerage API isn't safe, so this was
  left alone - share pages covering 5.1.2-5.1.7 of `Champion OpenAPI
  개발가이드.pdf` and this can be implemented precisely.
* **주식그룹주문 (`OTD1103U`)** needs `SetTranInputArrayData`/
  `SetTranInputArrayCnt`, which the same missing pages (5.1.3) would document
  the exact signature for. Same caveat as FID - not implemented without it.
  Unlike the other TR codes, `POST /tran/OTD1103U` returns `501 Not
  Implemented` instead of silently calling a broken path (see
  `UNSUPPORTED_CODES` in `eugene_api/routes/tran.py`).
* Real-time routing is now exact per `(realId, realKey)` rather than
  best-effort, but multiple *different* Real IDs still share one queue -
  under heavy multi-symbol load this is a single-threaded fan-in, not a
  fundamental limit but worth knowing about.

## Error handling

A TR/method call that fails inside pyeugene itself (an exception caught by
`eugene_proxy.py`'s own error handling, which reports `{"Error": "..."}`
instead of raising - see the fixes upstream in `pyeugene`) is detected in
`EugeneService._run()` and surfaces as `502 {"detail": "pyeugene 호출 실패: ..."}`,
instead of a `200` response with every field silently `null` (a Pydantic
response model just drops an unrecognized `"Error"` key by default, which
used to hide the failure entirely).

## Regression check

`tools/smoke_test.py` exercises the app end-to-end in mock mode (health,
catalog listing, a TR call, a Real snapshot, a utils lookup, and that
`/openapi.json` builds for all generated routes) without needing Windows:

```bash
PYTHONPATH=. python tools/smoke_test.py
```

`tools/verify_error_handling.py` covers the failure paths found in review:
a simulated pyeugene-side TR failure surfacing as 502 instead of a
null-filled 200, `RealDispatcher.subscribe()` not leaking a subscription
when `put_real()` raises, and the mock's `unRegisterReal` actually removing
its entry (a `str`/`int` type mismatch used to make it never match):

```bash
PYTHONPATH=. python tools/verify_error_handling.py
```
