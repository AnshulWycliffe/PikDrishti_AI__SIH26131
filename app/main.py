from flask import Blueprint, render_template, redirect, url_for, request, session, flash, jsonify, current_app
from flask_login import login_required, current_user
from . import db
from .models import Farm, Crop, DiseaseAnalysis,YieldPrediction, PestTrap, Conversation, ChatMessage, User, CaseReview, CaseFollowUp
from .services.weather_service import WeatherService, MAHARASHTRA_HOTSPOT_CLUSTERS
from .services.news_service import NewsService
from .services.ipm_service import IPMService
from datetime import datetime, timedelta
from sqlalchemy import or_
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

@main_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('main.admin_dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['is_admin'] = True
            return redirect(url_for('main.admin_dashboard'))
        error = 'Invalid officer credentials.'

    return render_template('admin/mobile_login.html', error=error)

@main_bp.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('main.admin_login'))


@main_bp.route('/admin/profile')
@admin_required
def admin_profile():
    return render_template('admin/profile.html', officer_name=ADMIN_USER)


@main_bp.route('/government')
@admin_required
def government_dashboard():
    """Demonstration dashboard for government surveillance and planning."""
    government_metrics = {
        'total_reports': '12,486',
        'high_risk_cases': '1,243',
        'farmers_reached': '8,752',
        'active_workers': '326',
        'active_hotspots': 12,
        'open_follow_ups': 37,
        'overdue_follow_ups': 9,
        'coverage': 78,
        'cases_this_month': 248,
        'response_time': '6.4h',
        'crop_loss_avoided': '18.4%',
        'targeted_interventions': 64,
    }
    government_hotspots = [
        {
            'district': 'Nashik', 'cluster': 'Niphad tomato belt',
            'lat': 20.0768, 'lon': 74.1082, 'risk': 'High', 'score': 88,
            'threat': 'Late blight', 'cases': 42, 'trend': '+18%', 'color': '#D94841',
        },
        {
            'district': 'Pune', 'cluster': 'Baramati vegetable zone',
            'lat': 18.1517, 'lon': 74.5772, 'risk': 'High', 'score': 81,
            'threat': 'Bacterial spot', 'cases': 31, 'trend': '+11%', 'color': '#D94841',
        },
        {
            'district': 'Kolhapur', 'cluster': 'Sugarcane fringe farms',
            'lat': 16.7050, 'lon': 74.2433, 'risk': 'Moderate', 'score': 59,
            'threat': 'Leaf blight', 'cases': 24, 'trend': '+4%', 'color': '#E09F3E',
        },
        {
            'district': 'Nagpur', 'cluster': 'Central orange belt',
            'lat': 21.1458, 'lon': 79.0882, 'risk': 'Moderate', 'score': 52,
            'threat': 'Mite pressure', 'cases': 18, 'trend': '-3%', 'color': '#E09F3E',
        },
        {
            'district': 'Satara', 'cluster': 'Karad horticulture zone',
            'lat': 17.2885, 'lon': 74.1813, 'risk': 'Low', 'score': 31,
            'threat': 'Early blight', 'cases': 9, 'trend': '-8%', 'color': '#3B8C6E',
        },
        {
            'district': 'Jalgaon', 'cluster': 'Banana production belt',
            'lat': 21.0077, 'lon': 75.5626, 'risk': 'Low', 'score': 26,
            'threat': 'Nutrient stress', 'cases': 7, 'trend': 'Stable', 'color': '#3B8C6E',
        },
    ]
    government_follow_ups = [
        {'case': 'Nashik-2408', 'district': 'Nashik', 'action': 'Collect lab sample', 'owner': 'A. Patil', 'due': 'Today', 'status': 'Urgent'},
        {'case': 'PUN-1182', 'district': 'Pune', 'action': 'Verify treatment response', 'owner': 'S. Jadhav', 'due': 'Tomorrow', 'status': 'On track'},
        {'case': 'KOL-0934', 'district': 'Kolhapur', 'action': 'Visit affected block', 'owner': 'R. More', 'due': '18 Sep', 'status': 'On track'},
        {'case': 'NAG-0711', 'district': 'Nagpur', 'action': 'Review farmer images', 'owner': 'M. Wagh', 'due': '20 Sep', 'status': 'Waiting'},
    ]
    outcome_series = [
        {'label': 'Jan', 'detections': 42, 'resolved': 29},
        {'label': 'Feb', 'detections': 55, 'resolved': 38},
        {'label': 'Mar', 'detections': 63, 'resolved': 47},
        {'label': 'Apr', 'detections': 71, 'resolved': 58},
        {'label': 'May', 'detections': 84, 'resolved': 70},
        {'label': 'Jun', 'detections': 96, 'resolved': 82},
    ]
    risk_distribution = [
        {'label': 'Nashik', 'score': 88, 'risk': 'High', 'color': '#d94841'},
        {'label': 'Pune', 'score': 81, 'risk': 'High', 'color': '#d94841'},
        {'label': 'Kolhapur', 'score': 59, 'risk': 'Moderate', 'color': '#e09f3e'},
        {'label': 'Nagpur', 'score': 52, 'risk': 'Moderate', 'color': '#e09f3e'},
        {'label': 'Satara', 'score': 31, 'risk': 'Low', 'color': '#3b8c6e'},
    ]
    disease_mix = [
        {'label': 'Late blight', 'value': 34, 'color': '#d94841'},
        {'label': 'Bacterial spot', 'value': 26, 'color': '#e09f3e'},
        {'label': 'Leaf blight', 'value': 18, 'color': '#3b8c6e'},
        {'label': 'Mite pressure', 'value': 13, 'color': '#6c8cba'},
        {'label': 'Other conditions', 'value': 9, 'color': '#b6c3bb'},
    ]
    government_reports = [
        {'crop': 'Tomato', 'disease': 'Early Blight', 'district': 'Nashik District', 'time': '2 hours ago', 'risk': 'High Risk', 'color': '#d94841'},
        {'crop': 'Cotton', 'disease': 'Leaf Spot', 'district': 'Jalgaon District', 'time': '5 hours ago', 'risk': 'Medium', 'color': '#e09f3e'},
        {'crop': 'Maize', 'disease': 'Fall Armyworm', 'district': 'Akola District', 'time': '1 day ago', 'risk': 'High Risk', 'color': '#d94841'},
        {'crop': 'Soybean', 'disease': 'Rust', 'district': 'Latur District', 'time': '1 day ago', 'risk': 'Low Risk', 'color': '#3b8c6e'},
        {'crop': 'Onion', 'disease': 'Thrips', 'district': 'Solapur District', 'time': '2 days ago', 'risk': 'Medium', 'color': '#e09f3e'},
    ]
    government_advisories = [
        {'title': 'Manage Early Blight in Tomato', 'date': 'Issued on 14 Sep 2026', 'tone': 'green'},
        {'title': 'Prevent Fall Armyworm in Maize', 'date': 'Issued on 12 Sep 2026', 'tone': 'amber'},
        {'title': 'Control Sucking Pests in Cotton', 'date': 'Issued on 10 Sep 2026', 'tone': 'green'},
    ]
    government_announcements = [
        {'tag': 'New', 'title': 'Monsoon Disease - Surveillance Drive 2026', 'detail': 'Special campaign from 1st Sep to 30th Oct 2026'},
        {'tag': 'Update', 'title': 'New District Data Integrated', 'detail': 'Wardha and Gadchiroli districts now live'},
        {'tag': 'Notice', 'title': 'Training Program for Extension Workers', 'detail': 'Scheduled from 20th to 25th Sep 2026'},
    ]
    return render_template(
        'government/dashboard.html',
        government_metrics=government_metrics,
        government_hotspots=government_hotspots,
        government_follow_ups=government_follow_ups,
        outcome_series=outcome_series,
        risk_distribution=risk_distribution,
        disease_mix=disease_mix,
        government_reports=government_reports,
        government_advisories=government_advisories,
        government_announcements=government_announcements,
    )


@main_bp.route('/admin')
@admin_required
def admin_dashboard():
    cases = DiseaseAnalysis.query.order_by(DiseaseAnalysis.date.desc()).limit(50).all()
    total_cases = DiseaseAnalysis.query.count()
    reviewed_cases = CaseReview.query.count()
    confirmed_cases = CaseReview.query.filter_by(decision='confirmed').count()
    lab_referrals = CaseReview.query.filter_by(decision='lab_referral').count()
    active_follow_ups = CaseFollowUp.query.filter(CaseFollowUp.status.in_(['pending', 'in_progress', 'escalated'])).count()
    follow_up_queue = CaseFollowUp.query.filter(
        CaseFollowUp.status.in_(['pending', 'in_progress', 'escalated'])
    ).order_by(CaseFollowUp.due_date.asc().nullslast()).limit(8).all()
    return render_template(
        'admin/dashboard.html',
        cases=cases,
        total_cases=total_cases,
        pending_reviews=max(total_cases - reviewed_cases, 0),
        confirmed_cases=confirmed_cases,
        lab_referrals=lab_referrals,
        active_follow_ups=active_follow_ups,
        follow_up_queue=follow_up_queue,
    )


@main_bp.route('/admin/cases/<int:analysis_id>', methods=['GET', 'POST'])
@admin_required
def admin_case_detail(analysis_id):
    analysis = DiseaseAnalysis.query.get_or_404(analysis_id)
    review = CaseReview.query.filter_by(analysis_id=analysis.id).first()

    if request.method == 'POST':
        decision = request.form.get('decision', 'under_review').strip()
        allowed_decisions = {'under_review', 'confirmed', 'uncertain', 'lab_referral', 'rejected'}
        if decision not in allowed_decisions:
            flash('Invalid review decision.', 'danger')
            return redirect(url_for('main.admin_case_detail', analysis_id=analysis.id))

        if not review:
            review = CaseReview(analysis_id=analysis.id)
            db.session.add(review)
        review.status = decision
        review.decision = decision
        review.confirmed_disease = request.form.get('confirmed_disease', '').strip() or None
        review.notes = request.form.get('notes', '').strip() or None
        review.expert_advisory = request.form.get('expert_advisory', '').strip() or None
        review.lab_name = request.form.get('lab_name', '').strip() or None
        review.lab_sample_id = request.form.get('lab_sample_id', '').strip() or None
        review.lab_notes = request.form.get('lab_notes', '').strip() or None
        review.lab_result = request.form.get('lab_result', '').strip() or None
        if decision == 'lab_referral' and not review.lab_referred_at:
            review.lab_referred_at = datetime.utcnow()
        review.reviewed_by = ADMIN_USER
        db.session.commit()
        flash('Case review saved.', 'success')
        return redirect(url_for('main.admin_case_detail', analysis_id=analysis.id))

    return render_template('admin/case_detail.html', analysis=analysis, review=review)


@main_bp.route('/admin/cases/<int:analysis_id>/follow-up', methods=['POST'])
@admin_required
def admin_case_follow_up(analysis_id):
    analysis = DiseaseAnalysis.query.get_or_404(analysis_id)
    review = CaseReview.query.filter_by(analysis_id=analysis.id).first()
    if not review:
        flash('Save a case review before creating a follow-up.', 'warning')
        return redirect(url_for('main.admin_case_detail', analysis_id=analysis.id))

    follow_up = CaseFollowUp.query.filter_by(review_id=review.id).first()
    if not follow_up:
        follow_up = CaseFollowUp(
            analysis_id=analysis.id,
            review_id=review.id,
            assigned_to=ADMIN_USER,
        )
        db.session.add(follow_up)

    follow_up.analysis_id = analysis.id
    follow_up.assigned_to = ADMIN_USER
    follow_up.priority = request.form.get('priority', 'moderate')
    follow_up.status = request.form.get('status', 'pending')
    follow_up.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None
    follow_up.next_action = request.form.get('next_action', '').strip() or None
    follow_up.action = follow_up.next_action or ''
    follow_up.notes = request.form.get('follow_up_notes', '').strip() or None
    db.session.commit()
    flash('Follow-up plan saved.', 'success')
    return redirect(url_for('main.admin_case_detail', analysis_id=analysis.id))

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
    ipm_plan = gd.get('ipm_plan') or IPMService.build_plan(
        crop=analysis.crop_display,
        disease=analysis.detected_disease,
        confidence=analysis.confidence,
        severity=analysis.severity,
    )

    result = {
        "crop":              analysis.crop_display,
        "disease":           analysis.detected_disease or "Unknown",
        "confidence":        analysis.confidence or 0.0,
        "severity":          analysis.severity,
        "symptoms":          gd.get("symptoms", []),
        "recommendations":   gd.get("recommendations", []),
        "prevention":        gd.get("prevention", []),
        "gemini_explanation": gd.get("explanation", ""),
        "ipm_plan":          ipm_plan,
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
            target_language = (request.args.get('language') or 'en').lower()
            if target_language not in {'en', 'mr', 'hi'}:
                target_language = 'en'

            crop_name = analysis.crop_display
            disease_name = analysis.detected_disease or "Unknown"
            severity = analysis.severity or "Moderate"
            gd = analysis.gemini_parsed

            fallback_text = {
                'en': {
                    'symptoms': 'Disease symptoms were observed on the leaves.',
                    'recommendations': 'Follow the recommended crop protection treatment.'
                },
                'mr': {
                    'symptoms': 'पानांवर रोगाची लक्षणे आढळली आहेत.',
                    'recommendations': 'शिफारस केलेल्या पीक संरक्षण उपचारांचे पालन करा.'
                },
                'hi': {
                    'symptoms': 'पत्तियों पर रोग के लक्षण दिखाई दे रहे हैं।',
                    'recommendations': 'अनुशंसित फसल सुरक्षा उपचार का पालन करें।'
                }
            }[target_language]
            symptoms_str = ", ".join(gd.get("symptoms", [])[:3]) if gd.get("symptoms") else fallback_text['symptoms']
            recomms_str = ", ".join(gd.get("recommendations", [])[:2]) if gd.get("recommendations") else fallback_text['recommendations']

            context_labels = {
                'en': ('Crop Diagnosis Context', 'Crop', 'Detected Disease', 'Severity', 'Symptoms', 'Initial Advice', 'I am ready to help with treatment for **{crop}** and **{disease}**.', 'What would you like to ask about chemical treatments, organic remedies, or preventive care?'),
                'mr': ('पीक निदान संदर्भ', 'पीक', 'आढळलेला रोग', 'तीव्रता', 'लक्षणे', 'प्राथमिक सल्ला', 'या निदानाच्या संदर्भात **{crop}** पिकावरील **{disease}** रोगाच्या उपचारासाठी मी तयार आहे.', 'रासायनिक औषधे, सेंद्रिय उपाय किंवा प्रतिबंधात्मक काळजीबद्दल तुम्हाला काय विचारायचे आहे?'),
                'hi': ('फसल निदान संदर्भ', 'फसल', 'पहचाना गया रोग', 'गंभीरता', 'लक्षण', 'प्रारंभिक सलाह', 'इस निदान के आधार पर **{crop}** फसल के **{disease}** रोग के उपचार में आपकी सहायता के लिए मैं तैयार हूँ।', 'रासायनिक दवाओं, जैविक उपायों या बचाव संबंधी देखभाल के बारे में आप क्या पूछना चाहते हैं?')
            }[target_language]

            conv = Conversation(user_id=current_user.id)
            db.session.add(conv)
            db.session.flush()

            context_msg = (
                f"🌱 **{context_labels[0]}:**\n"
                f"- **{context_labels[1]}:** {crop_name}\n"
                f"- **{context_labels[2]}:** {disease_name}\n"
                f"- **{context_labels[3]}:** {severity}\n"
                f"- **{context_labels[4]}:** {symptoms_str}\n"
                f"- **{context_labels[5]}:** {recomms_str}\n\n"
                f"{context_labels[6].format(crop=crop_name, disease=disease_name)} "
                f"{context_labels[7]}"
            )
            ai_msg = ChatMessage(role='ai', content=context_msg, conversation_id=conv.id)
            db.session.add(ai_msg)
            db.session.commit()

            return redirect(url_for('main.assistant', conv=conv.id, context_disease=analysis.id, language=target_language))

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

