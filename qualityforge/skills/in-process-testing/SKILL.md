# QualityForge skill: In-process API testing

**Spec:** review R6 (Praxify QualityForge Specification §7.5, §10)
**Consumed by:** Architecture and Testing agents

## Purpose

Generated API tests run **in-process** against the app object — FastAPI's
`TestClient` (or the framework equivalent) — never against a bound network
port inside the sandbox. Binding ports is slower, burns execution credits,
and adds network flake that eats the 15-minute run budget (spec §10). This
rule is written into the Architecture Agent's test approach and enforced on
every generated test file.

## Workflow steps

1. The Architecture Agent's technical specification names in-process testing
   (`TestClient`) as the API test approach for every `unit_test` /
   `behavior_check` criterion that touches an endpoint.
2. Generated test files import the app object and exercise it through
   `TestClient(app)`; assertions inspect the returned response object.
3. Before finalizing a test file, check it mechanically:
   `qualityforge.agents.rules.in_process_test_violations(source)` must return
   an empty list. A non-empty result blocks finalization.
4. Sandbox execution limits stay at the strictest settings (spec §7.5);
   in-process tests keep them that way — no listener, no outbound call.

## Forbidden patterns (flagged by the check)

- `uvicorn.run(`, `.run(host=`, `app.run(` — starts a real server
- `socket.socket(`, `.bind(`, `.listen(` — binds a socket
- `HTTPServer`, `WSGIServer`, `http.server` — hand-rolled servers
- `requests.`, `httpx.` pointed at `localhost`/`127.0.0.1` — network loopback
  where an in-process call belongs

## Non-negotiable rules

- No generated test binds a port or opens a network connection.
- Coverage does not drop to accommodate the rule: criteria coverage is 100%
  (spec §12.2); the call mechanism changes, the assertions do not.
