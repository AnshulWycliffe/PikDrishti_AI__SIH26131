from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify
from flask_login import login_required, current_user
from . import db
from .models import Farm, Crop, DiseaseAnalysis, YieldPrediction, PestTrap, Conversation, ChatMessage, User
from .services.weather_service import WeatherService
from .services.news_service import NewsService
from datetime import datetime, timedelta
import json
main_bp = Blueprint('main', __name__)

# ─── Admin helpers ────────────────────────────────────────────────
ADMIN_USER = 'admin'
ADMIN_PASS = 'admin'

def admin_required(f):
    """Decorator: redirect to admin login if not an admin session."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('main.admin_login'))
        return f(*args, **kwargs)
    return decorated

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/dashboard')
@login_required
def dashboard():
    farms_count = Farm.query.filter_by(user_id=current_user.id).count()
    crops_count = Crop.query.filter_by(user_id=current_user.id).count()
    recent_analyses = DiseaseAnalysis.query.filter_by(user_id=current_user.id).order_by(DiseaseAnalysis.date.desc()).limit(5).all()
    recent_analysis = recent_analyses[0] if recent_analyses else None
    alerts_count = DiseaseAnalysis.query.filter(
        DiseaseAnalysis.user_id == current_user.id,
        DiseaseAnalysis.detected_disease != 'Healthy',
        DiseaseAnalysis.detected_disease.isnot(None)
    ).count()
    recent_yield = YieldPrediction.query.filter_by(user_id=current_user.id).order_by(YieldPrediction.date.desc()).first()
    
    farm = (
        Farm.query
        .filter_by(user_id=current_user.id)
        .first()
    )

    weather = None
    if farm and farm.location:
        weather = WeatherService.get_weather(farm.location)
    else:
        # Default to Maharashtra central location if user hasn't set farm location yet
        weather = WeatherService.get_weather("Pune")

    # Fetch latest Indian agricultural news
    news_items = NewsService.get_agri_news(limit=4)

    # Fetch critical/warning pest traps
    critical_traps = PestTrap.query.filter(PestTrap.user_id == current_user.id, PestTrap.status.in_(['Warning', 'Critical'])).order_by(PestTrap.date.desc()).all()
    alerts_count += len(critical_traps)

    return render_template('dashboard.html', 
                           farms_count=farms_count, 
                           crops_count=crops_count,
                           alerts_count=alerts_count,
                           recent_analysis=recent_analysis,
                           recent_analyses=recent_analyses,
                           recent_yield=recent_yield,
                           farm=farm,
                           weather=weather,
                           news_items=news_items,
                           critical_traps=critical_traps)

@main_bp.route('/farms')
@main_bp.route('/profile')
@login_required
def farms():
    user_farms = Farm.query.filter_by(user_id=current_user.id).all()
    user_crops = Crop.query.filter_by(user_id=current_user.id).all()
    return render_template('farms.html', farms=user_farms, crops=user_crops, user=current_user)

@main_bp.route('/crops')
@login_required
def crops():
    user_crops = Crop.query.filter_by(user_id=current_user.id).all()
    user_farms = Farm.query.filter_by(user_id=current_user.id).all()
    return render_template('crops.html', crops=user_crops, farms=user_farms)

@main_bp.route('/scan')
@login_required
def scan():
    user_crops = Crop.query.filter_by(user_id=current_user.id).all()
    return render_template('scan.html', crops=user_crops)

@main_bp.route('/disease-result/<int:analysis_id>')
@login_required
def disease_result(analysis_id):
    analysis = DiseaseAnalysis.query.get_or_404(analysis_id)
    if analysis.user_id != current_user.id:
        return redirect(url_for('main.dashboard'))

    gd = analysis.gemini_parsed   # {} if not stored

    result = {
        "crop":              analysis.crop_display,
        "disease":           analysis.detected_disease or "Unknown",
        "confidence":        analysis.confidence or 0.0,
        "severity":          analysis.severity,
        "symptoms":          gd.get("symptoms", []),
        "recommendations":   gd.get("recommendations", []),
        "prevention":        gd.get("prevention", []),
        "gemini_explanation": gd.get("explanation", ""),
        "top_predictions":   [],
        "status":            "success",
    }

    return render_template('disease_result.html', analysis=analysis, result=result)


@main_bp.route('/yield')
@login_required
def yield_prediction():
    user_crops = Crop.query.filter_by(user_id=current_user.id).all()
    user_farms = Farm.query.filter_by(user_id=current_user.id).all()
    recent_analyses = DiseaseAnalysis.query.filter_by(user_id=current_user.id).order_by(DiseaseAnalysis.date.desc()).limit(5).all()
    past_predictions = YieldPrediction.query.filter_by(user_id=current_user.id).order_by(YieldPrediction.date.desc()).limit(6).all()
    primary_farm = user_farms[0] if user_farms else None
    return render_template('yield.html', crops=user_crops, farms=user_farms, recent_analyses=recent_analyses, past_predictions=past_predictions, primary_farm=primary_farm)

@main_bp.route('/history')
@login_required
def history():
    disease_history = DiseaseAnalysis.query.filter_by(user_id=current_user.id).order_by(DiseaseAnalysis.date.desc()).all()
    yield_history = YieldPrediction.query.filter_by(user_id=current_user.id).order_by(YieldPrediction.date.desc()).all()
    
    return render_template('history.html', 
                           disease_history=disease_history, 
                           yield_history=yield_history)

@main_bp.route('/assistant')
@login_required
def assistant():
    # If arriving from a disease result page, create a contextual conversation
    analysis_id = request.args.get('analysis_id', type=int)
    if analysis_id:
        analysis = DiseaseAnalysis.query.filter_by(id=analysis_id, user_id=current_user.id).first()
        if analysis:
            crop_name = analysis.crop_display
            disease_name = analysis.detected_disease or "Unknown"
            severity = analysis.severity or "Moderate"
            gd = analysis.gemini_parsed

            symptoms_str = ", ".join(gd.get("symptoms", [])[:3]) if gd.get("symptoms") else "पानांवर रोगाची लक्षणे आढळली आहेत"
            recomms_str = ", ".join(gd.get("recommendations", [])[:2]) if gd.get("recommendations") else "योग्य बुरशीनाशक/कीटकनाशक फवारणी करावी"

            conv = Conversation(user_id=current_user.id)
            db.session.add(conv)
            db.session.flush()

            context_msg = (
                f"🌱 **पीक निदान संदर्भ (Crop Diagnosis Context):**\n"
                f"- **पीक (Crop):** {crop_name}\n"
                f"- **रोग (Detected Disease):** {disease_name}\n"
                f"- **तीव्रता (Severity):** {severity}\n"
                f"- **प्रमुख लक्षणे (Symptoms):** {symptoms_str}\n"
                f"- **प्राथमिक सल्ला (Initial Advice):** {recomms_str}\n\n"
                f"मी या निदानाच्या संदर्भात **{crop_name}** वरील **{disease_name}** उपचारासाठी तयार आहे. "
                f"तुम्हाला रासायनिक औषधे, सेंद्रिय उपाय किंवा प्रतिबंधात्मक काळजीबद्दल काय विचारायचे आहे?"
            )
            ai_msg = ChatMessage(role='ai', content=context_msg, conversation_id=conv.id)
            db.session.add(ai_msg)
            db.session.commit()

            return redirect(url_for('main.assistant', conv=conv.id, context_disease=analysis.id))

    # Support switching to a specific conversation via ?conv=<id>
    conv_id = request.args.get('conv', type=int)
    context_disease_id = request.args.get('context_disease', type=int)
    context_analysis = None
    if context_disease_id:
        context_analysis = DiseaseAnalysis.query.filter_by(id=context_disease_id, user_id=current_user.id).first()

    # All user conversations for sidebar (latest first)
    all_conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.start_time.desc()).all()

    # Active conversation
    if conv_id:
        conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    else:
        conversation = all_conversations[0] if all_conversations else None

    chat_history = []
    if conversation:
        chat_history = ChatMessage.query.filter_by(conversation_id=conversation.id).order_by(ChatMessage.timestamp.asc()).all()

    return render_template('assistant.html',
                           chat_history=chat_history,
                           conversation_id=conversation.id if conversation else '',
                           all_conversations=all_conversations,
                           active_conv_id=conversation.id if conversation else None,
                           context_analysis=context_analysis)


@main_bp.route('/assistant/new')
@login_required
def new_conversation():
    """Create a new blank conversation and redirect to it."""
    conv = Conversation(user_id=current_user.id)
    db.session.add(conv)
    db.session.commit()
    return redirect(url_for('main.assistant', conv=conv.id))


@main_bp.route('/assistant/delete/<int:conv_id>', methods=['POST'])
@login_required
def delete_conversation(conv_id):
    """Delete a conversation and its messages."""
    conv = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first_or_404()
    ChatMessage.query.filter_by(conversation_id=conv.id).delete()
    db.session.delete(conv)
    db.session.commit()
    return redirect(url_for('main.assistant'))


# ═══════════════════════════════════════════════════════════════════
# ADMIN / EXTENSION OFFICER ROUTES
# ═══════════════════════════════════════════════════════════════════

@main_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('main.admin_dashboard'))
    error = None
    if request.method == 'POST':
        if (request.form.get('username') == ADMIN_USER and
                request.form.get('password') == ADMIN_PASS):
            session['is_admin'] = True
            return redirect(url_for('main.admin_dashboard'))
        error = 'Invalid credentials'
    return render_template('admin/login.html', error=error)


@main_bp.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('main.admin_login'))


@main_bp.route('/admin')
@main_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Extension officer overview dashboard with static demo content."""
    total_farmers = 128
    total_scans = 542
    total_farms = 96
    total_traps = 74

    disease_counts = [
        ('Late Blight', 118),
        ('Early Blight', 94),
        ('Bacterial Spot', 63),
        ('Leaf Mold', 49),
        ('Fruit Fly', 41),
        ('Whitefly', 36),
        ('Thrips', 28),
        ('Healthy', 17),
    ]

    severity_counts = [
        ('Critical', 32),
        ('High', 81),
        ('Moderate', 146),
        ('Low', 88),
    ]

    recent_scans = [
        {'id': 1042, 'date': datetime.utcnow() - timedelta(days=1), 'detected_crop': 'Tomato', 'detected_disease': 'Late Blight', 'severity': 'High', 'confidence': 0.94},
        {'id': 1041, 'date': datetime.utcnow() - timedelta(days=2), 'detected_crop': 'Potato', 'detected_disease': 'Early Blight', 'severity': 'Moderate', 'confidence': 0.88},
        {'id': 1040, 'date': datetime.utcnow() - timedelta(days=3), 'detected_crop': 'Bell Pepper', 'detected_disease': 'Bacterial Spot', 'severity': 'Critical', 'confidence': 0.91},
        {'id': 1039, 'date': datetime.utcnow() - timedelta(days=4), 'detected_crop': 'Tomato', 'detected_disease': 'Leaf Mold', 'severity': 'Moderate', 'confidence': 0.79},
        {'id': 1038, 'date': datetime.utcnow() - timedelta(days=5), 'detected_crop': 'Potato', 'detected_disease': 'Healthy', 'severity': 'Low', 'confidence': 0.97},
        {'id': 1037, 'date': datetime.utcnow() - timedelta(days=6), 'detected_crop': 'Tomato', 'detected_disease': 'Late Blight', 'severity': 'High', 'confidence': 0.9},
    ]

    trend_raw = [
        ('2026-09-08', 31),
        ('2026-09-09', 38),
        ('2026-09-10', 53),
        ('2026-09-11', 47),
        ('2026-09-12', 64),
        ('2026-09-13', 71),
    ]

    critical_traps = [
        {'pest_type': 'Fruit Fly', 'pest_count': 46, 'status': 'Critical', 'date': datetime.utcnow() - timedelta(days=2)},
        {'pest_type': 'Whitefly', 'pest_count': 31, 'status': 'Warning', 'date': datetime.utcnow() - timedelta(days=4)},
        {'pest_type': 'Thrips', 'pest_count': 24, 'status': 'Critical', 'date': datetime.utcnow() - timedelta(days=7)},
    ]

    farmer_stats = [
        {'username': 'rajesh_patil', 'email': 'rajesh.patil@gmail.com', 'scans': 21, 'diseases': 9},
        {'username': 'meena_shinde', 'email': 'meena.shinde@gmail.com', 'scans': 18, 'diseases': 8},
        {'username': 'arun_more', 'email': 'arun.more@gmail.com', 'scans': 15, 'diseases': 6},
        {'username': 'sneha_jadhav', 'email': 'sneha.jadhav@gmail.com', 'scans': 14, 'diseases': 5},
        {'username': 'vijay_kadam', 'email': 'vijay.kadam@gmail.com', 'scans': 12, 'diseases': 4},
    ]

    return render_template('admin/dashboard.html',
        total_farmers=total_farmers,
        total_scans=total_scans,
        total_farms=total_farms,
        total_traps=total_traps,
        disease_counts=disease_counts,
        severity_counts=severity_counts,
        recent_scans=recent_scans,
        trend_raw=trend_raw,
        critical_traps=critical_traps,
        farmer_stats=farmer_stats,
    )


@main_bp.route('/admin/gov_portal')
@admin_required
def gov_portal():
        return render_template('admin/portal.html' )

