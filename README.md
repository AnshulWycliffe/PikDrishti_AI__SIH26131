# PikDrishti AI

PikDrishti AI is a Flask-based agricultural assistant for farmers. It combines crop and farm records, leaf-image disease analysis, yield prediction, weather data, agricultural news, multilingual assistance, and pest-trap monitoring in one mobile-friendly web application.

## What It Does

- Manage farms, locations, soil nutrient values, crops, and crop varieties.
- Analyze crop-leaf images with the TensorFlow/Keras disease model.
- Enrich disease predictions with symptoms, recommendations, prevention guidance, and structured IPM plans.
- Predict yield from crop, farm area, and disease severity.
- Show current weather and a three-day crop-risk forecast based on the user's saved farm location.
- Track pest-trap readings and warning or critical trap states.
- Provide an agricultural chat assistant with conversation history.
- Support English, Marathi, and Hindi target-language flows for assistant responses, explanations, speech recognition, and text-to-speech.
- Keep English as the original UI language; Marathi and Hindi UI translation use the Google Translate widget.
- Provide history views for disease scans and yield predictions.

## Current Language Behavior

English is the source language and the default UI language.

- **English:** original page markup and English AI/audio output.
- **Marathi:** Google Translate handles the shared UI; Gemini/Bhashini and browser speech use Marathi where supported.
- **Hindi:** Google Translate handles the shared UI; Gemini/Bhashini and browser speech use Hindi where supported.

The selected language is stored in browser `localStorage` under `pikdrishti_lang`. Disease-result and assistant context links pass the selected language to the server so generated explanations and conversation context stay aligned with the active target language.

## Main User Flows

### Farm and crop management

Users can create farms with a location, area, and optional NPK values, then register crops against those farms. Crop pages also support pest-trap readings and simulated trap data for development or demonstration.

### Disease analysis

The scan flow accepts a camera or gallery image, crop selection, location, and optional farmer observations. The `/api/disease/analyze` endpoint:

1. Saves the uploaded image.
2. Runs the disease model.
3. Requests a structured Gemini response in the selected target language.
4. Builds an integrated pest and disease management plan.
5. Stores the analysis and returns an analysis ID.

The result page includes risk, treatment/advisory, symptoms, AI explanation, target-language audio, and follow-up access to the assistant.

### Yield prediction

The yield page follows the same compact mobile workflow as the scan page. Users select a crop, choose a recent disease scan or severity level, and submit the prediction form. Predictions are stored and displayed in the history page.

### Weather

Dashboard weather uses the first saved farm location. If no farm location exists, the app falls back to Pune. When WeatherAPI credentials are unavailable or a request fails, demo weather retains the requested farm location instead of relabeling it as another city.

### Assistant and voice

The assistant supports text chat, conversation history, speech recognition, Bhashini TTS, and browser speech fallback. Supported target codes are:

- `en` - English
- `mr` - Marathi
- `hi` - Hindi

The backend validates the language for chat, ASR, TTS, and voice-chat requests.

## Technology

- Python 3
- Flask application factory
- Flask-SQLAlchemy and SQLite by default
- Flask-Login and Flask-Bcrypt
- Jinja2 templates and Bootstrap-based responsive UI
- TensorFlow/Keras disease model
- Google Gemini for agricultural assistant responses and disease enrichment
- Bhashini for speech recognition, translation, and text-to-speech
- WeatherAPI for current and forecast weather when configured
- Chart.js for history visualizations
- Requests and feedparser-based agricultural news integration

## Repository Layout

```text
PikDrishti AI/
├── app/
│   ├── __init__.py              Flask app factory and extension setup
│   ├── api.py                   Authenticated API routes
│   ├── auth.py                  Login and registration routes
│   ├── main.py                  Page routes and assistant context flow
│   ├── models.py                SQLAlchemy models
│   ├── services/
│   │   ├── bhasini_service.py   ASR, NMT, and TTS integration
│   │   ├── disease_service.py   Disease model inference
│   │   ├── gemini_service.py    Gemini prompts and language handling
│   │   ├── ipm_service.py       Structured IPM recommendations
│   │   ├── news_service.py      Agricultural news retrieval
│   │   ├── rag_service.py       Knowledge-base retrieval
│   │   ├── weather_service.py   Current weather and risk forecast
│   │   └── yield_service.py     Yield prediction
│   ├── static/                  CSS, icons, uploads, PWA assets
│   └── templates/               Jinja page templates
├── knowledge_base/              Local RAG source documents
├── ml/disease/                  Training and evaluation scripts
├── models/                      Disease model and metadata files
├── config.py                    Environment-backed application configuration
├── requirements.txt             Python dependencies
├── run.py                       Development entry point
└── technical_architecture.md    Additional architecture notes
```

## Prerequisites

- Python 3.10 or newer is recommended.
- A virtual environment.
- A TensorFlow-compatible environment for disease inference.
- Optional API credentials:
  - Google Gemini for production AI responses.
  - WeatherAPI for live weather.
  - Bhashini credentials for ASR, translation, and TTS.

The application can run in demo mode without the external AI credentials, but external services are required for production-quality responses and live integrations.

## Installation

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

### macOS or Linux

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000/` after the server starts.

The application factory creates the database tables automatically and builds the local RAG index during startup.

## Environment Configuration

Create a `.env` file in the project root when external services are needed:

```env
FLASK_SECRET_KEY=replace_with_a_long_random_secret
DATABASE_URL=sqlite:///agrivision.db

GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
WEATHER_API_KEY=your_weatherapi_key

BHASHINI_USER_ID=your_bhashini_user_id
BHASHINI_API_KEY=your_bhashini_api_key
BHASHINI_PIPELINE_ID=64392f96daac500b55c543d5
BHASHINI_INFERENCE_API_KEY=your_bhashini_inference_key

DISEASE_MODEL_PATH=models/disease_model.keras
YIELD_MODEL_PATH=path/to/your/yield_model.pkl

DEMO_MODE=true
DISEASE_CONFIDENCE_THRESHOLD=0.70
DISEASE_BATCH_SIZE=32
```

Do not commit `.env` or API credentials. The application uses demo mode by default when `DEMO_MODE` is not explicitly set to `false`.

## Important Routes

### Pages

| Route | Purpose |
| --- | --- |
| `/` | Landing page or redirect to dashboard |
| `/dashboard` | Weather, farm summary, activity, news, and forecast |
| `/farms` | Profile, farms, and settings |
| `/crops` | Crop and pest-trap management |
| `/scan` | Crop image upload and disease analysis |
| `/disease-result/<analysis_id>` | Disease result and IPM guidance |
| `/yield` | Yield prediction |
| `/history` | Disease and yield history |
| `/assistant` | Agricultural assistant and conversations |

### API examples

- `POST /api/disease/analyze`
- `POST /api/yield/predict`
- `POST /api/assistant/chat`
- `POST /api/bhasini/asr`
- `POST /api/bhasini/tts`
- `POST /api/bhasini/translate`
- `POST /api/bhasini/voice-chat`
- `GET /api/weather/risk-forecast`
- `GET /api/location/autocomplete`
- `POST /api/trap/log`
- `POST /api/trap/simulate/<crop_id>`

All user-facing data routes require an authenticated Flask-Login session.

## Disease Model

The checked-in model artifacts are:

```text
models/
├── disease_model.keras
├── disease_classes.json
└── disease_metadata.json
```

Training and evaluation utilities are under `ml/disease/`. The inference service is responsible for loading the model, preprocessing uploaded images, mapping class IDs, and returning crop/disease confidence data. Always treat predictions as decision support and seek an agriculture professional when symptoms are unclear or treatment is high-risk.

## Testing and Validation

Useful local checks:

```powershell
python -m compileall -q app
.\venv\Scripts\python.exe -c "from app import create_app; app=create_app(); print(app.name)"
```

Template compilation example:

```powershell
.\venv\Scripts\python.exe -c "from app import create_app; app=create_app(); app.jinja_env.get_template('dashboard.html'); print('template valid')"
```

## Safety Notes

- Disease predictions are advisory and should not replace field or laboratory confirmation.
- Follow registered product labels, crop restrictions, dosage, re-entry periods, and pre-harvest intervals.
- Do not recommend or apply unverified pesticide mixtures.
- Keep uploaded images and API credentials protected in production deployments.
- Replace the development secret key before deploying.

## License and Contributions

This repository does not currently declare a license in its project documentation. Add a license before distributing the project publicly. For changes, keep route contracts stable, preserve the existing service boundaries, and validate affected templates and API paths before opening a pull request.
