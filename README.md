# Vera — magicpin Merchant Message Engine

HTTP API for the [magicpin Vera AI Challenge](https://magicpin.com/vera/ai-challenge).

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

- Health: http://localhost:8080/v1/healthz
- Docs: http://localhost:8080/docs

## Tests

```bash
pytest tests/ -q
```

## Docker

```bash
docker compose up --build
```

## Environment variables

| Variable | Description |
|----------|-------------|
| PORT | Server port (set by cloud platform) |
| TEAM_NAME | Your name — shown in `/v1/metadata` |
| TEAM_MEMBERS | Comma-separated team members |
| CONTACT_EMAIL | Contact email for metadata |
| MODEL | Bot model label for metadata |
| APPROACH | Short approach description for metadata |

Copy `.env.example` to `.env` and fill in your details for local runs.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /v1/healthz | Liveness |
| GET | /v1/metadata | Team identity |
| POST | /v1/context | Push context |
| POST | /v1/tick | Proactive messages |
| POST | /v1/reply | Handle replies |
