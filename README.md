# protheus
Protheus
========

Integrated experiment-planning app.

Install and run the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the frontend in a second terminal:

```bash
cd ~/Desktop/Projects/hacknation-5/protheus
npm install
npm run dev
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`.

Optional local NLP/vector retrieval dependencies are listed in
`backend/requirements-optional.txt`. They are not required for the default app
run and are best installed with Python 3.10 or 3.11.
