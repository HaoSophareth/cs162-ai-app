# CS162 AI application: running plan generator, built twice

Two versions of the same app. They need no API keys or paid services, and each keeps its own data.

- `feature_build/` was built from prompts describing only what the app does.
- `engineering_build/` was built from prompts that also describe how to build it.

## Run them locally

Needs Python 3.10 or newer. Use a separate terminal for each app, starting in this folder.

**Build 1 (feature-wise)**

```bash
cd feature_build
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --port 5051
```

Open http://127.0.0.1:5051

**Build 2 (engineering-wise)**

```bash
cd engineering_build
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --port 5050
```

Open http://127.0.0.1:5050

Sign up with any username and password, answer the profile questions, then create a plan. To test that users are separate, sign up a second user. The database is created on first run. Stop an app with Ctrl+C.

Page changes fade smoothly in Chrome. Other browsers may show a blink on each click.
