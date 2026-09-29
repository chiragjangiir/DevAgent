# Fix REST Server (devagent serve)

## Problem
`devagent/server/fastapi_app.py` breaks on newer Starlette versions:
`TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`

`test_api.py` is excluded from CI with `--ignore=tests/test_api.py`.

## Fix options
1. Pin Starlette to `<0.41` (short-term, avoids refactor)
2. Move `on_startup` handlers to `@app.on_event("startup")` or `lifespan=` context manager (Starlette >=0.41 style) — preferred long-term fix
3. The server is described as "intentionally minimal stub" — consider whether to invest or defer

## Recommendation
Fix the lifespan pattern (option 2) and re-enable `test_api.py` in CI.
