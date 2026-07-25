# Backend

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## AI extraction: local Ollama, not a cloud API

Document extraction (`app/extraction.py`) runs against a local Ollama vision
model (`qwen2.5vl:7b`) instead of a cloud API, since uploaded SBC/EOB
documents are health/financial data and the team decided not to send them
to a third party for the hackathon build. Everything runs on-device.

One-time setup:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5vl:7b
```

The `ollama` systemd service must be running (`systemctl status ollama`).
No API key needed.

## Test extraction standalone

```bash
python test_extraction.py "/path/to/sample_eob.pdf"
```

Prints the extracted `IntakeData` as JSON. Use this to iterate on the
extraction prompt without needing the full server running.

## Run the server

(Once session/autosave endpoints are added.)

```bash
uvicorn app.main:app --reload
```
