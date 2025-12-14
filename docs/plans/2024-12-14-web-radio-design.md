# Web Radio - Design Document

Webapp Python per controllo remoto RTX via hamlib/rigctld.

## Architettura

```
┌─────────────┐     WebSocket      ┌─────────────┐     TCP/IP      ┌─────────┐
│   Browser   │◄──────────────────►│   FastAPI   │◄───────────────►│ rigctld │
│  Alpine.js  │    (JSON msgs)     │   (async)   │   (port 4532)   │         │
└─────────────┘                    └─────────────┘                 └─────────┘
                                          │
                                          ▼
                                   ┌─────────────┐
                                   │ config.yaml │
                                   │ (auth, rig) │
                                   └─────────────┘
```

### Componenti

1. **FastAPI server** - Entry point, serve file statici + WebSocket endpoint
2. **RigClient** - Classe async che gestisce la connessione TCP a rigctld
3. **WebSocket handler** - Riceve comandi dal browser, inoltra a RigClient, invia aggiornamenti
4. **Poller** - Task async che interroga rigctld periodicamente e pusha via WebSocket
5. **Config** - File YAML con: host/porta rigctld, credenziali auth, intervallo polling

### Flusso dati

- **Browser → Radio**: Utente cambia frequenza → WebSocket msg → FastAPI → rigctld → radio
- **Radio → Browser**: Poller legge stato → WebSocket broadcast → Alpine.js aggiorna UI

## Protocollo WebSocket

### Browser → Server

```json
// Cambio frequenza
{"cmd": "set_freq", "value": 14074000}

// Cambio modo
{"cmd": "set_mode", "value": "USB"}

// Richiesta stato immediato
{"cmd": "get_state"}

// Comandi Fase 2
{"cmd": "set_filter_width", "value": 2400}
{"cmd": "set_spot", "value": true}
{"cmd": "set_agc", "value": "fast"}
{"cmd": "set_rf_gain", "value": 50}
{"cmd": "set_break_in", "value": true}
{"cmd": "set_power", "value": 5}
{"cmd": "RIT", "value": 0}
```

### Server → Browser

```json
// Aggiornamento stato (polling ~200ms)
{
  "type": "state",
  "freq": 14074000,
  "mode": "USB",
  "smeter": -65,
  "filter_width": 2400,
  "spot": false,
  "agc": "med",
  "rf_gain": 80,
  "break_in": false,
  "power": 10,
  "RIT": 0
}

// Conferma comando
{"type": "ack", "cmd": "set_freq", "success": true}

// Errore
{"type": "error", "message": "rigctld connection lost"}
```

### Note protocollo

- S-meter in dBm (come restituito da rigctld)
- Frequenza in Hz (intero)
- Polling ~200ms per S-meter reattivo, configurabile

## Struttura File

```
web_radio/
├── main.py              # FastAPI app, WebSocket handler
├── rig_client.py        # Classe async per comunicazione rigctld
├── config.yaml          # Configurazione
├── requirements.txt     # fastapi, uvicorn, pyyaml
├── Dockerfile           # Container image
├── docker-compose.yml   # Orchestrazione
└── static/
    ├── index.html       # UI con Alpine.js
    ├── style.css        # Stile ispirato KX3
    └── app.js           # Logica WebSocket + Alpine
```

## UI

```
┌────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────┐  │
│  │            14.074.000                            │  │
│  │               USB                                │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  S ▁▂▃▄▅▆▇█░░░░░░░░░░  -65 dBm                        │
│                                                        │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐          │
│  │  LSB   │ │  USB   │ │  CW    │ │  AM    │  ...     │
│  └────────┘ └────────┘ └────────┘ └────────┘          │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ VFO dial (trascinabile o scroll)                 │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  Step: [100] [1k] [10k] [100k]                         │
└────────────────────────────────────────────────────────┘
```

### Elementi UI

- **Display frequenza** - Font LED molto grande (DSEG o simile), 7 segmenti
- **Display modo** - Sotto la frequenza
- **S-meter** - Barra grafica + valore numerico
- **Bottoni modo** - LSB/USB/CW/AM/FM/DATA
- **Controllo frequenza** - Scroll wheel sul display, o slider/dial trascinabile
- **Step selector** - Per incrementi VFO

### Stile

- Sfondo scuro
- Colori ambra/verde LCD
- Font LED per VFO (stile display a 7 segmenti)
- Minimal, ispirato Elecraft KX3

## Configurazione

```yaml
# config.yaml

# Connessione rigctld
rigctld:
  host: "127.0.0.1"
  port: 4532

# Server web
server:
  host: "0.0.0.0"
  port: 8080

# Autenticazione
auth:
  username: "operator"
  password: "changeme"

# Polling
polling:
  interval_ms: 200

# UI defaults
ui:
  default_step: 1000
```

## Gestione Errori

### Connessione rigctld

- All'avvio: retry 3 tentativi, 2s intervallo
- Durante uso: stato "disconnected", indicatore rosso in UI
- Riconnessione automatica in background ogni 5s
- Comandi durante disconnessione → errore immediato

### WebSocket

- Heartbeat ping/pong ogni 30s
- Client disconnesso → rimuovi dalla lista broadcast
- Supporto multipli client simultanei

### Indicatori stato UI

- Verde: Connected (normale)
- Giallo: Reconnecting (rigctld perso)
- Rosso: Disconnected (server down)

## Roadmap

| Funzionalità | MVP | Fase 2 | Fase 3 |
|--------------|-----|--------|--------|
| Lettura frequenza | ✓ | | |
| Lettura modo | ✓ | | |
| S-meter | ✓ | | |
| Cambio frequenza | ✓ | | |
| Cambio modo | ✓ | | |
| Basic auth | ✓ | | |
| Filtro width | | ✓ | |
| Spot | | ✓ | |
| AGC | | ✓ | |
| RF gain | | ✓ | |
| Break-in | | ✓ | |
| Power | | ✓ | |
| Audio streaming | | | ✓ |

### Note Fase 3 (Audio)

- WebRTC o WebSocket binario
- Cattura audio da pulseaudio/pipewire
- Latenza critica per CW/SSB
- Da approfondire

## Stack Tecnologico

- **Backend**: FastAPI + asyncio
- **Frontend**: Alpine.js + CSS custom
- **Comunicazione**: WebSocket (JSON)
- **Config**: YAML
- **Radio**: rigctld via TCP (porta 4532)

## Dipendenze Python

```
fastapi
uvicorn
pyyaml
```

## Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### docker-compose.yml

```yaml
services:
  web-radio:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    restart: unless-stopped
    # rigctld gira sull'host, usa network_mode o specifica host
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - RIGCTLD_HOST=host.docker.internal
```

### Note Docker

- `config.yaml` montato come volume per configurazione esterna
- `host.docker.internal` per raggiungere rigctld sull'host
- Alternativa: `network_mode: host` (più semplice ma meno isolato)
- Per sviluppo: mount del codice sorgente con `--reload`
