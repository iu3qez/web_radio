# Web Radio

Webapp Python per controllo remoto RTX via hamlib/rigctld.

## Stack

- **Backend**: FastAPI + asyncio
- **Frontend**: Alpine.js + CSS custom (tema LED)
- **Comunicazione**: WebSocket (JSON)
- **Config**: YAML
- **Radio**: rigctld via TCP (porta 4532)

## Struttura

```
web_radio/
├── main.py              # FastAPI app, WebSocket handler
├── rig_client.py        # Classe async per comunicazione rigctld
├── config.yaml          # Configurazione
├── requirements.txt     # Dipendenze Python
├── Dockerfile
├── docker-compose.yml
├── static/
│   ├── index.html       # UI con Alpine.js
│   ├── style.css        # Stile LED/LCD
│   └── app.js           # Logica WebSocket + Alpine
└── tests/
    └── test_*.py        # Test pytest
```

## Comandi

```bash
# Sviluppo
source venv/bin/activate
uvicorn main:app --reload

# Test
pytest tests/ -v

# Docker
docker compose up --build
```

## Architettura

```
Browser ←WebSocket→ FastAPI ←TCP→ rigctld ←→ RTX
```

## Protocollo WebSocket

**Comandi (browser → server):**
- `{"cmd": "set_freq", "value": 14074000}`
- `{"cmd": "set_mode", "value": "USB"}`
- `{"cmd": "get_state"}`

**Risposte (server → browser):**
- `{"type": "state", "freq": ..., "mode": ..., "smeter": ...}`
- `{"type": "ack", "cmd": "...", "success": true}`
- `{"type": "error", "message": "..."}`

## Note

- Auth: HTTP Basic (configurato in config.yaml)
- S-meter polling: 200ms default
- Font VFO: DSEG7 (stile 7 segmenti LED)
