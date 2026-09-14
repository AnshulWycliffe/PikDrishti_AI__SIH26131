import json
import urllib.request
import urllib.parse
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from . import db, cache
from .models import Farm, Crop, DiseaseAnalysis, YieldPrediction, Conversation, ChatMessage, User, PestTrap
from .services.disease_service import DiseaseService
from .services.yield_service import YieldPredictionService
from .services.gemini_service import GeminiService
from .services.weather_service import WeatherService
from .services.bhasini_service import BhasiniService
from .services.ipm_service import IPMService

api_bp = Blueprint('api', __name__)



# Pre-populated accurate coordinates for popular Maharashtra agricultural districts and talukas
MAHARASHTRA_LOCATIONS = [
    {"name": "Nashik", "region": "Maharashtra", "lat": 19.9975, "lon": 73.7898},
    {"name": "Pune", "region": "Maharashtra", "lat": 18.5204, "lon": 73.8567},
    {"name": "Chhatrapati Sambhaji Nagar (Aurangabad)", "region": "Maharashtra", "lat": 19.8762, "lon": 75.3433},
    {"name": "Nagpur", "region": "Maharashtra", "lat": 21.1458, "lon": 79.0882},
    {"name": "Kolhapur", "region": "Maharashtra", "lat": 16.7050, "lon": 74.2433},
    {"name": "Solapur", "region": "Maharashtra", "lat": 17.6599, "lon": 75.9064},
    {"name": "Ahmednagar", "region": "Maharashtra", "lat": 19.0952, "lon": 74.7496},
    {"name": "Satara", "region": "Maharashtra", "lat": 17.6805, "lon": 73.9997},
    {"name": "Sangli", "region": "Maharashtra", "lat": 16.8524, "lon": 74.5815},
    {"name": "Amravati", "region": "Maharashtra", "lat": 20.9374, "lon": 77.7796},
    {"name": "Akola", "region": "Maharashtra", "lat": 20.7002, "lon": 77.0082},
    {"name": "Jalgaon", "region": "Maharashtra", "lat": 21.0077, "lon": 75.5626},
    {"name": "Dhule", "region": "Maharashtra", "lat": 20.9042, "lon": 74.7749},
    {"name": "Nanded", "region": "Maharashtra", "lat": 19.1383, "lon": 77.3210},
    {"name": "Latur", "region": "Maharashtra", "lat": 18.4088, "lon": 76.5604},
    {"name": "Parbhani", "region": "Maharashtra", "lat": 19.2610, "lon": 76.7767},
    {"name": "Jalna", "region": "Maharashtra", "lat": 19.8410, "lon": 75.8864},
    {"name": "Beed", "region": "Maharashtra", "lat": 18.9891, "lon": 75.7601},
    {"name": "Buldhana", "region": "Maharashtra", "lat": 20.5293, "lon": 76.1843},
    {"name": "Yavatmal", "region": "Maharashtra", "lat": 20.3888, "lon": 78.1204},
    {"name": "Wardha", "region": "Maharashtra", "lat": 20.7453, "lon": 78.6022},
    {"name": "Chandrapur", "region": "Maharashtra", "lat": 19.9615, "lon": 79.2961},
    {"name": "Gondia", "region": "Maharashtra", "lat": 21.4602, "lon": 80.1961},
    {"name": "Bhandara", "region": "Maharashtra", "lat": 21.1718, "lon": 79.6548},
    {"name": "Gadchiroli", "region": "Maharashtra", "lat": 20.1809, "lon": 79.9934},
    {"name": "Nandurbar", "region": "Maharashtra", "lat": 21.3700, "lon": 74.2400},
    {"name": "Ratnagiri", "region": "Maharashtra", "lat": 16.9902, "lon": 73.3120},
    {"name": "Sindhudurg", "region": "Maharashtra", "lat": 16.1154, "lon": 73.7297},
    {"name": "Raigad (Alibag)", "region": "Maharashtra", "lat": 18.6414, "lon": 72.8722},
    {"name": "Palghar", "region": "Maharashtra", "lat": 19.6967, "lon": 72.7655},
    {"name": "Thane", "region": "Maharashtra", "lat": 19.2183, "lon": 72.9781},
    {"name": "Dharashiv (Osmanabad)", "region": "Maharashtra", "lat": 18.1856, "lon": 76.0419},
    {"name": "Hingoli", "region": "Maharashtra", "lat": 19.7176, "lon": 77.1494},
    {"name": "Baramati", "region": "Pune, Maharashtra", "lat": 18.1517, "lon": 74.5772},
    {"name": "Niphad", "region": "Nashik, Maharashtra", "lat": 20.0768, "lon": 74.1082},
    {"name": "Dindori", "region": "Nashik, Maharashtra", "lat": 20.1994, "lon": 73.8340},
    {"name": "Malegaon", "region": "Nashik, Maharashtra", "lat": 20.5539, "lon": 74.5288},
    {"name": "Yeola", "region": "Nashik, Maharashtra", "lat": 20.0435, "lon": 74.4870},
    {"name": "Shirdi (Rahata)", "region": "Ahmednagar, Maharashtra", "lat": 19.7667, "lon": 74.4762},
    {"name": "Sangamner", "region": "Ahmednagar, Maharashtra", "lat": 19.5761, "lon": 74.2081},
    {"name": "Pandharpur", "region": "Solapur, Maharashtra", "lat": 17.6775, "lon": 75.3262},
    {"name": "Karad", "region": "Satara, Maharashtra", "lat": 17.2885, "lon": 74.1813},
    {"name": "Phaltan", "region": "Satara, Maharashtra", "lat": 17.9863, "lon": 74.4326}
]

@api_bp.route('/farms', methods=['GET', 'POST'])
@login_required
def handle_farms():
    if request.method == 'GET':
        farms = Farm.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            'success': True,
            'farms': [{
                'id': f.id,
                'name': f.name,
                'location': f.location,
                'area': f.area
            } for f in farms]
        })
        
    elif request.method == 'POST':
        data = request.form

        def _float(key):
            v = data.get(key)
            return float(v) if v and v.strip() else None

        farm = Farm(
            name=data.get('name'),
            location=data.get('location'),
            area=_float('area'),
            nitrogen=_float('nitrogen'),
            phosphorus=_float('phosphorus'),
            potassium=_float('potassium'),
            user_id=current_user.id
        )
        db.session.add(farm)
        db.session.commit()
        return jsonify({'success': True, 'farm_id': farm.id})

@api_bp.route('/farms/<int:farm_id>', methods=['PUT'])
@login_required
def update_farm(farm_id):
    farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
    if not farm:
        return jsonify({'success': False, 'error': 'Farm not found'}), 404

    data = request.form

    def _float(key):
        v = data.get(key)
        return float(v) if v and v.strip() else None

    farm.name       = data.get('name', farm.name)
    farm.location   = data.get('location', farm.location)
    farm.area       = _float('area') if data.get('area') else farm.area
    farm.nitrogen   = _float('nitrogen')
    farm.phosphorus = _float('phosphorus')
    farm.potassium  = _float('potassium')

    db.session.commit()
    return jsonify({'success': True})

@api_bp.route('/user/profile', methods=['PUT', 'POST'])
@login_required
def update_user_profile():
    data = request.form
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()

    if not username:
        return jsonify({'success': False, 'error': 'Name cannot be empty'}), 400

    existing_user = User.query.filter(User.username == username, User.id != current_user.id).first()
    if existing_user:
        return jsonify({'success': False, 'error': 'Username already in use'}), 400

    if email:
        existing_email = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing_email:
            return jsonify({'success': False, 'error': 'Email already registered'}), 400
        current_user.email = email

    if phone:
        existing_phone = User.query.filter(User.phone == phone, User.id != current_user.id).first()
        if existing_phone:
            return jsonify({'success': False, 'error': 'Phone number already registered'}), 400
        current_user.phone = phone

    current_user.username = username
    db.session.commit()
    return jsonify({'success': True, 'username': current_user.username, 'email': current_user.email, 'phone': current_user.phone})

# ═══════════════════════════════════════════════════════════════════════════════
# Real-Time Location Search & Geocoding (Accurate Lat/Lon for Weather API)
# ═══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/location/autocomplete', methods=['GET'])
@login_required
def location_autocomplete():
    """
    Search real locations across Maharashtra & India with exact latitude/longitude.
    Combines instant local index + WeatherAPI + OpenStreetMap Nominatim.
    """
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'success': True, 'results': []})

    results = []
    q_lower = query.lower()

    # 1. Instant match from Maharashtra local index
    for item in MAHARASHTRA_LOCATIONS:
        if q_lower in item['name'].lower() or q_lower in item['region'].lower():
            lat = item['lat']
            lon = item['lon']
            display = f"{item['name']}, {item['region']}"
            results.append({
                'name': item['name'],
                'region': item['region'],
                'country': 'India',
                'lat': lat,
                'lon': lon,
                'display': display,
                'full_val': f"{display} ({lat:.4f}, {lon:.4f})"
            })

    weather_api_key = current_app.config.get('WEATHER_API_KEY')

    # 2. Try WeatherAPI search
    if weather_api_key:
        try:
            encoded_q = urllib.parse.quote(query)
            url = f"http://api.weatherapi.com/v1/search.json?key={weather_api_key}&q={encoded_q}"
            req = urllib.request.Request(url, headers={'User-Agent': 'PikDrishtiAI/1.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode('utf-8'))
                for item in data[:6]:
                    lat = float(item.get('lat', 0.0))
                    lon = float(item.get('lon', 0.0))
                    name = item.get('name', '')
                    region = item.get('region', '')
                    display = f"{name}, {region}" if region else name
                    if not any(abs(r['lat'] - lat) < 0.01 and abs(r['lon'] - lon) < 0.01 for r in results):
                        results.append({
                            'name': name,
                            'region': region or 'Maharashtra',
                            'country': item.get('country', 'India'),
                            'lat': lat,
                            'lon': lon,
                            'display': display,
                            'full_val': f"{display} ({lat:.4f}, {lon:.4f})"
                        })
        except Exception:
            pass

    # 3. OpenStreetMap Nominatim for villages & talukas
    if len(results) < 5:
        try:
            search_str = f"{query}, Maharashtra, India" if "maharashtra" not in query.lower() else f"{query}, India"
            encoded_q = urllib.parse.quote(search_str)
            url = f"https://nominatim.openstreetmap.org/search?format=json&countrycodes=in&q={encoded_q}&limit=6&addressdetails=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'PikDrishtiAI-FarmLocator/1.0', 'Accept-Language': 'en,mr'})
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode('utf-8'))
                for item in data:
                    addr = item.get('address', {})
                    place_name = addr.get('village') or addr.get('town') or addr.get('city') or addr.get('county') or item.get('display_name').split(',')[0]
                    state = addr.get('state', 'Maharashtra')
                    district = addr.get('state_district') or addr.get('county') or ''
                    display = f"{place_name}, {district}, {state}" if district and district != place_name else f"{place_name}, {state}"
                    lat = float(item.get('lat'))
                    lon = float(item.get('lon'))
                    
                    if not any(abs(r['lat'] - lat) < 0.01 and abs(r['lon'] - lon) < 0.01 for r in results):
                        results.append({
                            'name': place_name,
                            'region': district or state,
                            'country': 'India',
                            'lat': lat,
                            'lon': lon,
                            'display': display,
                            'full_val': f"{display} ({lat:.4f}, {lon:.4f})"
                        })
        except Exception:
            pass

    return jsonify({'success': True, 'results': results[:8]})


@api_bp.route('/location/reverse', methods=['GET'])
@login_required
def location_reverse():
    """
    Reverse geocode exact device GPS coordinates (lat, lon) to place name.
    """
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({'success': False, 'error': 'lat and lon are required'}), 400

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=12&addressdetails=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'PikDrishtiAI-FarmLocator/1.0', 'Accept-Language': 'en,mr'})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode('utf-8'))
            addr = data.get('address', {})
            place = addr.get('village') or addr.get('town') or addr.get('city') or addr.get('county') or 'Local Farm'
            district = addr.get('state_district') or addr.get('county') or ''
            state = addr.get('state', 'Maharashtra')
            display = f"{place}, {district}, {state}" if district and district != place else f"{place}, {state}"

            return jsonify({
                'success': True,
                'name': place,
                'district': district,
                'state': state,
                'display': display,
                'lat': float(lat),
                'lon': float(lon),
                'query_val': f"{float(lat):.4f},{float(lon):.4f}"
            })
    except Exception:
        return jsonify({
            'success': True,
            'name': 'Current Location',
            'display': f"GPS: {float(lat):.4f}, {float(lon):.4f}",
            'lat': float(lat),
            'lon': float(lon),
            'query_val': f"{float(lat):.4f},{float(lon):.4f}"
        })

# ═══════════════════════════════════════════════════════════════════════════════
# Weather-Based Disease Risk Forecasting & Geospatial Hotspot Mapping
# ═══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/weather/risk-forecast', methods=['GET'])
@login_required
def weather_risk_forecast():
    """
    Returns 3-day micro-climate weather disease risk forecast for farmer location.
    """
    farm_id = request.args.get('farm_id')
    loc = request.args.get('location')

    if farm_id:
        farm = Farm.query.filter_by(id=farm_id, user_id=current_user.id).first()
        if farm and farm.location:
            loc = farm.location
    elif not loc:
        user_farm = Farm.query.filter_by(user_id=current_user.id).first()
        if user_farm and user_farm.location:
            loc = user_farm.location
        else:
            loc = "Nashik, Maharashtra"

    forecast_data = WeatherService.get_forecast_risk(location=loc, days=3)
    return jsonify(forecast_data)


@api_bp.route('/geospatial/hotspots', methods=['GET'])
@login_required
def geospatial_hotspots():
    """
    Returns Maharashtra regional disease outbreak clusters, risk levels & advisories.
    """
    hotspots_data = WeatherService.get_geospatial_hotspots()
    return jsonify(hotspots_data)

@api_bp.route('/crops', methods=['GET', 'POST'])
@login_required
def handle_crops():
    if request.method == 'GET':
        crops = Crop.query.filter_by(user_id=current_user.id).all()
        return jsonify({
            'success': True,
            'crops': [{
                'id': c.id,
                'name': c.name,
                'variety': c.variety,
                'farm_id': c.farm_id
            } for c in crops]
        })
        
    elif request.method == 'POST':
        data = request.form
        crop = Crop(
            name=data.get('name'),
            variety=data.get('variety'),
            farm_id=int(data.get('farm_id')),
            user_id=current_user.id
        )
        db.session.add(crop)
        db.session.commit()
        return jsonify({'success': True, 'crop_id': crop.id})

@api_bp.route('/disease/analyze', methods=['POST'])
@login_required
def analyze_disease():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image part"}), 400

    image_file = request.files['image']
    crop_id = request.form.get('crop_id')
    farmer_observation = request.form.get('farmer_observation', '')
    language = (request.form.get('language') or 'en').lower()

    if language not in {'en', 'mr', 'hi'}:
        return jsonify({"success": False, "error": "Unsupported disease explanation language"}), 400

    # ── Save uploaded image to disk for display on results page ──────────────
    import os, uuid
    from flask import current_app
    from werkzeug.utils import secure_filename

    relative_image_path = None
    if image_file and image_file.filename:
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'leaves')
        os.makedirs(upload_dir, exist_ok=True)
        orig_filename = secure_filename(image_file.filename or 'leaf.jpg')
        ext = os.path.splitext(orig_filename)[1] or '.jpg'
        unique_filename = f"leaf_{uuid.uuid4().hex[:10]}{ext}"
        save_path = os.path.join(upload_dir, unique_filename)
        
        # Read file bytes for saving and reset stream pointer for model inference
        file_bytes = image_file.read()
        image_file.seek(0)
        with open(save_path, 'wb') as f:
            f.write(file_bytes)
        relative_image_path = f"uploads/leaves/{unique_filename}"

    result = DiseaseService.predict(image_file, farmer_observation)
    
    if not result.get("success"):
        return jsonify(result)

    # ── Gemini enrichment ────────────────────────────────────────────────────
    gemini_context = result.pop('gemini_context', None)
    gemini_explanation = None
    gemini_structured = {}

    if gemini_context:
        gemini_prompt = (
            gemini_context
            + "\n\nBased on the above disease model prediction, please provide a JSON response with exactly these keys:\n"
            "{\n"
            "  \"symptoms\": [\"...\", ...],\n"
            "  \"recommendations\": [\"...\", ...],\n"
            "  \"prevention\": [\"...\", ...],\n"
            "  \"explanation\": \"...\"\n"
            "}\n"
            f"All text must be in { {'en': 'English', 'mr': 'Marathi', 'hi': 'Hindi'}[language] }. "
            "Do NOT modify the confidence value. Return ONLY the JSON, no extra text."
        )
        gemini_result = GeminiService.ask_assistant(gemini_prompt, history=[], language=language)
        if gemini_result.get('success'):
            raw = gemini_result.get('response', '')
            # Strip markdown code fences if present
            import re, json as _json
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                try:
                    gemini_structured = _json.loads(match.group(0))
                except Exception:
                    gemini_structured = {}
            gemini_explanation = gemini_structured.get('explanation', raw[:500])

    result['symptoms']        = gemini_structured.get('symptoms', [])
    result['recommendations'] = gemini_structured.get('recommendations', [])
    result['prevention']      = gemini_structured.get('prevention', [])
    result['gemini_explanation'] = gemini_explanation
    result['ipm_plan'] = IPMService.build_plan(
        crop=result.get('crop'),
        disease=result.get('disease'),
        confidence=result.get('confidence'),
        severity=result.get('severity'),
    )
    result['image_path']      = relative_image_path

    # ── Persist to DB ────────────────────────────────────────────────────────
    parsed_crop_id = None
    if crop_id:
        try:
            parsed_crop_id = int(crop_id)
        except (ValueError, TypeError):
            parsed_crop_id = None

    import json as _json_store
    analysis = DiseaseAnalysis(
        user_id=current_user.id,
        image_path=relative_image_path,
        crop_id=parsed_crop_id,
        detected_crop=result.get("crop") or (str(crop_id).title() if crop_id and not parsed_crop_id else None),
        detected_disease=result.get("disease"),
        confidence=result.get("confidence"),
        severity=result.get("severity"),
        farmer_observation=farmer_observation,
        gemini_data=_json_store.dumps({
            **gemini_structured,
            'ipm_plan': result['ipm_plan'],
        }),
    )
    db.session.add(analysis)
    db.session.commit()
    result["analysis_id"] = analysis.id

    return jsonify(result)

@api_bp.route('/yield/predict', methods=['POST'])
@login_required
def predict_yield():
    data = request.form
    crop_id = data.get('crop_id')
    
    if not crop_id:
        return jsonify({"success": False, "error": "Crop ID is required"}), 400
        
    crop = Crop.query.get(crop_id)
    if not crop or crop.user_id != current_user.id:
        return jsonify({"success": False, "error": "Invalid crop"}), 400
        
    farm = Farm.query.get(crop.farm_id)
    if not farm or not farm.area:
        return jsonify({"success": False, "error": "Farm area is required for prediction"}), 400
        
    disease_severity = data.get('disease_severity')
    disease_analysis_id = data.get('disease_analysis_id')
    
    result = YieldPredictionService.predict(farm.area, crop.name, disease_severity)
    
    if result.get("success"):
        # Save prediction history
        prediction = YieldPrediction(
            user_id=current_user.id,
            crop_id=crop.id,
            disease_analysis_id=int(disease_analysis_id) if disease_analysis_id else None,
            predicted_yield_per_acre=result.get("yield_per_acre"),
            total_yield=result.get("total_yield"),
            unit=result.get("unit")
        )
        db.session.add(prediction)
        db.session.commit()
        result["prediction_id"] = prediction.id
        
    return jsonify(result)

@api_bp.route('/assistant/chat', methods=['POST'])
@login_required
def assistant_chat():
    data = request.json
    message = data.get('message')
    conversation_id = data.get('conversation_id')
    language = (data.get('language') or 'en').lower()
    
    if not message:
        return jsonify({"success": False, "error": "Message is required"}), 400
    if language not in {'en', 'mr', 'hi'}:
        return jsonify({"success": False, "error": "Unsupported assistant language"}), 400
        
    # Get or create conversation
    if conversation_id:
        conversation = Conversation.query.get(conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            return jsonify({"success": False, "error": "Invalid conversation"}), 400
    else:
        conversation = Conversation(user_id=current_user.id)
        db.session.add(conversation)
        db.session.commit()
        
    # Save user message
    user_msg = ChatMessage(role='user', content=message, conversation_id=conversation.id)
    db.session.add(user_msg)
    db.session.commit()
    
    # Get recent history
    history = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.timestamp.asc()).all()
    
    # Exclude the very last message from history passed to gemini
    past_history = history[:-1] if len(history) > 1 else []
    
    # Call Gemini service with language support
    result = GeminiService.ask_assistant(message, history=past_history, language=language)
    
    if result.get("success"):
        # Save AI response
        ai_msg = ChatMessage(role='ai', content=result.get("response"), conversation_id=conversation.id)
        db.session.add(ai_msg)
        db.session.commit()
        result['conversation_id'] = conversation.id
        
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════════
# Bhashini AI Speech & Language Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/bhasini/asr', methods=['POST'])
@login_required
def bhasini_asr():
    """
    Automatic Speech Recognition: Audio Base64 -> Transcribed Text.
    """
    data = request.json or {}
    audio_base64 = data.get('audio')
    language = (data.get('language') or 'en').lower()

    if not audio_base64:
        return jsonify({"success": False, "error": "Audio payload missing"}), 400
    if language not in {'en', 'mr', 'hi'}:
        return jsonify({"success": False, "error": "Unsupported ASR language"}), 400

    result = BhasiniService.speech_to_text(audio_base64, source_lang=language)
    return jsonify(result)


@api_bp.route('/bhasini/tts', methods=['POST'])
@login_required
def bhasini_tts():
    """
    Text-to-Speech: Input Text -> Audio Base64.
    """
    data = request.json or {}
    text = data.get('text')
    language = (data.get('language') or 'en').lower()
    gender = data.get('gender', 'female')

    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400
    if language not in {'en', 'mr', 'hi'}:
        return jsonify({"success": False, "error": "Unsupported TTS language"}), 400

    result = BhasiniService.text_to_speech(text, source_lang=language, gender=gender)
    return jsonify(result)


@api_bp.route('/bhasini/translate', methods=['POST'])
@login_required
def bhasini_translate():
    """
    Neural Machine Translation between Indian Languages.
    """
    data = request.json or {}
    text = data.get('text')
    source_lang = data.get('source_lang', 'mr')
    target_lang = data.get('target_lang', 'en')

    if not text:
        return jsonify({"success": False, "error": "Text is required"}), 400

    result = BhasiniService.translate_text(text, source_lang=source_lang, target_lang=target_lang)
    return jsonify(result)


@api_bp.route('/bhasini/voice-chat', methods=['POST'])
@login_required
def bhasini_voice_chat():
    """
    End-to-End Voice Conversation:
    1. ASR (Bhashini) - speech to text
    2. RAG + Gemini - agricultural advice in target language
    3. TTS (Bhashini) - text to speech audio
    """
    data = request.json or {}
    audio_base64 = data.get('audio')
    text_query = data.get('text')
    language = (data.get('language') or 'en').lower()
    conversation_id = data.get('conversation_id')

    if language not in {'en', 'mr', 'hi'}:
        return jsonify({"success": False, "error": "Unsupported voice-chat language"}), 400

    user_text = text_query
    if not user_text and audio_base64:
        asr_res = BhasiniService.speech_to_text(audio_base64, source_lang=language)
        if asr_res.get("success"):
            user_text = asr_res.get("text")
        else:
            return jsonify({
                "success": False,
                "error": asr_res.get("error", "ASR processing failed"),
                "fallback_available": asr_res.get("fallback_available", True)
            }), 400

    if not user_text:
        return jsonify({"success": False, "error": "Could not extract voice or text query"}), 400

    # Get or create conversation
    if conversation_id:
        conversation = Conversation.query.get(conversation_id)
        if not conversation or conversation.user_id != current_user.id:
            conversation = Conversation(user_id=current_user.id)
            db.session.add(conversation)
            db.session.commit()
    else:
        conversation = Conversation(user_id=current_user.id)
        db.session.add(conversation)
        db.session.commit()

    # Save user message
    user_msg = ChatMessage(role='user', content=user_text, conversation_id=conversation.id)
    db.session.add(user_msg)
    db.session.commit()

    # History
    history = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.timestamp.asc()).all()
    past_history = history[:-1] if len(history) > 1 else []

    # Gemini Assistant call
    gemini_res = GeminiService.ask_assistant(user_text, history=past_history, language=language)
    if not gemini_res.get("success"):
        return jsonify(gemini_res)

    ai_text = gemini_res.get("response", "")
    ai_msg = ChatMessage(role='ai', content=ai_text, conversation_id=conversation.id)
    db.session.add(ai_msg)
    db.session.commit()

    # Clean plain text for TTS
    import re
    clean_speech_text = re.sub(r'[#*_`\[\]\(\)]', ' ', ai_text)
    clean_speech_text = re.sub(r'\s+', ' ', clean_speech_text).strip()

    # Generate TTS with Bhashini
    tts_res = BhasiniService.text_to_speech(clean_speech_text[:500], source_lang=language)

    return jsonify({
        "success": True,
        "user_text": user_text,
        "response": ai_text,
        "conversation_id": conversation.id,
        "audio_base64": tts_res.get("audio_base64") if tts_res.get("success") else None,
        "language": language
    })


@api_bp.route('/weather', methods=['GET'])
@login_required
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    q = request.args.get('q')

    # If no q or lat/lon provided, try user's first farm location
    first_farm = Farm.query.filter_by(user_id=current_user.id).filter(Farm.location != None).first()
    if first_farm and first_farm.location:
        q = first_farm.location

    weather_data = WeatherService.get_weather(location=q, lat=lat, lon=lon)
    return jsonify(weather_data)





# Pest Trap APIs

@api_bp.route('/trap/log', methods=['POST'])
@login_required
def log_trap_data():
    crop_id = request.form.get('crop_id')
    trap_type = request.form.get('trap_type', 'Pheromone Trap')
    pest_type = request.form.get('pest_type', 'Unknown')
    try:
        pest_count = int(request.form.get('pest_count', 0))
    except ValueError:
        pest_count = 0

    if not crop_id:
        return jsonify({'success': False, 'error': 'Missing crop ID'}), 400

    status = 'Safe'
    if pest_count >= 10:
        status = 'Critical'
    elif pest_count >= 5:
        status = 'Warning'

    trap = PestTrap(
        crop_id=crop_id,
        user_id=current_user.id,
        trap_type=trap_type,
        pest_type=pest_type,
        pest_count=pest_count,
        status=status
    )
    db.session.add(trap)
    db.session.commit()
    return jsonify({'success': True, 'id': trap.id})

@api_bp.route('/trap/history/<int:crop_id>', methods=['GET'])
@login_required
def get_trap_history(crop_id):
    traps = PestTrap.query.filter_by(crop_id=crop_id, user_id=current_user.id).order_by(PestTrap.date.desc()).all()
    data = []
    for t in traps:
        data.append({
            'id': t.id,
            'date': t.date.strftime('%Y-%m-%d %H:%M:%S'),
            'trap_type': t.trap_type,
            'pest_type': t.pest_type,
            'pest_count': t.pest_count,
            'status': t.status
        })
    return jsonify({'success': True, 'history': data})

@api_bp.route('/trap/simulate/<int:crop_id>', methods=['POST'])
@login_required
def simulate_trap_data(crop_id):
    import random
    trap_types = ['Pheromone Trap', 'Yellow Sticky Trap', 'Light Trap']
    pest_types = ['Fall Armyworm', 'Whitefly', 'Aphids', 'Fruit Borer']
    count = random.randint(0, 15)

    status = 'Safe'
    if count >= 10:
        status = 'Critical'
    elif count >= 5:
        status = 'Warning'

    trap = PestTrap(
        crop_id=crop_id,
        user_id=current_user.id,
        trap_type=random.choice(trap_types),
        pest_type=random.choice(pest_types),
        pest_count=count,
        status=status
    )
    db.session.add(trap)
    db.session.commit()
    return jsonify({'success': True, 'count': count, 'status': status})
