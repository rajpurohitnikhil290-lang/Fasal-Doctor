# फसल डॉक्टर (Fasal Doctor)

Farmer uploads/clicks a photo of a sick plant -> website tells the disease and the treatment (Hindi / English / Gujarati).

```
fasal-doctor-app/
  main.py            FastAPI backend (calls Claude with the photo)
  static/index.html  the website
  requirements.txt
  render.yaml        one-click deploy config for Render
```

## 1. Get an API key
Create one at https://console.anthropic.com (API keys). Add a small credit balance.
Never put the key inside index.html or push it to GitHub.

## 2. Run on your laptop
```
pip install -r requirements.txt
set ANTHROPIC_API_KEY=sk-ant-...        (PowerShell:  $env:ANTHROPIC_API_KEY="sk-ant-...")
uvicorn main:app --reload
```
Open http://127.0.0.1:8000

To test from a phone on the same Wi-Fi: `uvicorn main:app --host 0.0.0.0` and open `http://<laptop-ip>:8000`.
(Phone camera capture needs https, so use the deployed version for that.)

## 3. Put it online (free, works for everyone, no login)
1. Push this folder to a GitHub repo (add a `.gitignore` with `.env` and `__pycache__/`).
2. Go to https://render.com -> New -> Blueprint -> pick the repo (it reads render.yaml).
3. Paste `ANTHROPIC_API_KEY` when asked. Deploy.
4. You get a link like `https://fasal-doctor.onrender.com` - share it with farmers.

Free Render apps sleep after inactivity, so the first open can take ~30-50 seconds.

## Notes
- `RATE_LIMIT_PER_HOUR` (default 20 photos per IP) protects your API bill. Raise or lower it.
- Photos are not stored; they are sent to Claude for analysis and discarded.
- The result is an AI estimate, not a lab test. Wrong crop-protection advice can hurt a farm, so consider adding a "confirm with KVK" line back before real launch.
