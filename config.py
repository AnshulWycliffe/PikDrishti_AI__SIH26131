import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev_fallback_secret_key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'agrivision.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # AI and External APIs
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-2.5-flash'
    WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
    MAPPLS_MAP_API = os.environ.get('MAPPLS_MAP_API') or os.environ.get('MAPPLS_API_KEY')
    
    # Bhashini (NLTM / ULCA) Speech & Language API
    BHASHINI_USER_ID = os.environ.get('BHASHINI_USER_ID') or os.environ.get('BHASINI_USER_ID')
    BHASHINI_API_KEY = os.environ.get('BHASINI_UDYAT_API') or os.environ.get('BHASHINI_API_KEY') or os.environ.get('BHASINI_API_KEY')
    BHASHINI_PIPELINE_ID = os.environ.get('BHASHINI_PIPELINE_ID') or os.environ.get('BHASINI_PIPELINE_ID') or '64392f96daac500b55c543d5'
    BHASHINI_INFERENCE_API_KEY = os.environ.get('BHASINI_INFERENCE_KEY') or os.environ.get('BHASHINI_INFERENCE_API_KEY') or os.environ.get('BHASINI_INFERENCE_API_KEY')
    
    # Models
    DISEASE_MODEL_PATH = os.environ.get('DISEASE_MODEL_PATH') or os.path.join(basedir, 'models', 'disease_model.keras')
    YIELD_MODEL_PATH = os.environ.get('YIELD_MODEL_PATH')
    
    # Flags
    DEMO_MODE = os.environ.get('DEMO_MODE', 'true').lower() == 'true'
    
    # Disease detection thresholds
    DISEASE_CONFIDENCE_THRESHOLD = float(os.environ.get('DISEASE_CONFIDENCE_THRESHOLD', '0.70'))
    DISEASE_BATCH_SIZE = int(os.environ.get('DISEASE_BATCH_SIZE', '32'))
