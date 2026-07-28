## Run the demo

**Prerequisites:** Docker Desktop (or any Docker Engine with Compose v2). Nothing else — no local
Python, Node or Postgres.

```bash
docker compose up --build
```

That is the whole setup. It starts PostgreSQL, runs the migrations, projects the lifecycle config
into the database, imports `shipments.csv`, and serves the UI:

| What | Where |
| --- | --- |
| Web UI | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| API | http://localhost:8000/api/v1 |


## Test illegal cases
```
ID=$(curl -s 'localhost:8000/api/v1/shipments?status=created&page_size=1' | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")
curl -s -w '\nHTTP %{http_code}\n' -X POST "localhost:8000/api/v1/shipments/$ID/status" \
  -H 'Content-Type: application/json' \
  -d '{"status":"delivered"}'
```