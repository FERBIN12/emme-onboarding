# Backend

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## AI extraction: Gemini

Document extraction (`app/extraction.py`) calls Gemini vision to read an
uploaded SBC/EOB and fill whatever schema fields are present. Local Ollama
vision models were tried first for privacy (nothing leaves the laptop) but
none were reliable at the extraction task on the available hardware, so
Gemini is the primary path.

Safeguard: identity fields (name, email, zip code) are never sent to or
requested from Gemini -- the prompt excludes them entirely, since the
member already types them into the form directly. See `app/extraction.py`
for details.

Requires `GEMINI_API_KEY` in the environment. Get a free key at
https://aistudio.google.com/apikey.

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
