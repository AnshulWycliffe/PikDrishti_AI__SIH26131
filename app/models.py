from datetime import datetime
from flask_login import UserMixin
from . import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    phone = db.Column(db.String(20), index=True, unique=True, nullable=True)
    password_hash = db.Column(db.String(128))
    
    # Relationships
    farms = db.relationship('Farm', backref='owner', lazy='dynamic')
    crops = db.relationship('Crop', backref='owner', lazy='dynamic')
    disease_analyses = db.relationship('DiseaseAnalysis', backref='farmer', lazy='dynamic')
    yield_predictions = db.relationship('YieldPrediction', backref='farmer', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

class Farm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200))
    area = db.Column(db.Float) # in acres or hectares
    soil_type = db.Column(db.String(50))
    soil_ph = db.Column(db.Float)
    nitrogen = db.Column(db.Float)
    phosphorus = db.Column(db.Float)
    potassium = db.Column(db.Float)
    irrigation_type = db.Column(db.String(50))
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    crops = db.relationship('Crop', backref='farm_location', lazy='dynamic')

class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    variety = db.Column(db.String(100))
    sowing_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_harvest_date = db.Column(db.DateTime)
    previous_yield = db.Column(db.Float)
    
    farm_id = db.Column(db.Integer, db.ForeignKey('farm.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    analyses = db.relationship('DiseaseAnalysis', backref='crop_info', lazy='dynamic')
    predictions = db.relationship('YieldPrediction', backref='crop_info', lazy='dynamic')
    pest_traps = db.relationship('PestTrap', backref='crop_trap_info', lazy='dynamic')

class DiseaseAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    image_path = db.Column(db.String(255))
    detected_crop = db.Column(db.String(100))
    detected_disease = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    severity = db.Column(db.String(50))
    farmer_observation = db.Column(db.Text)
    gemini_data = db.Column(db.Text)             # JSON: symptoms/recommendations/prevention/explanation

    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    @property
    def crop_display(self):
        """Best available crop name: ML prediction > user-selected crop > dash."""
        return self.detected_crop or (self.crop_info.name if self.crop_info else '—')

    @property
    def gemini_parsed(self):
        """Parsed Gemini structured response, or empty dict."""
        import json
        if self.gemini_data:
            try:
                return json.loads(self.gemini_data)
            except Exception:
                pass
        return {}



class YieldPrediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    predicted_yield_per_acre = db.Column(db.Float)
    total_yield = db.Column(db.Float)
    unit = db.Column(db.String(20))
    
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    disease_analysis_id = db.Column(db.Integer, db.ForeignKey('disease_analysis.id'))

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    messages = db.relationship('ChatMessage', backref='conversation', lazy='dynamic')

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20)) # 'user' or 'ai'
    content = db.Column(db.Text)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'))

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    
    disease_analysis_id = db.Column(db.Integer, db.ForeignKey('disease_analysis.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class PestTrap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    trap_type = db.Column(db.String(100)) # e.g. Pheromone, Sticky
    pest_type = db.Column(db.String(100))
    pest_count = db.Column(db.Integer)
    status = db.Column(db.String(20)) # Safe, Warning, Critical
    
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


class CaseReview(db.Model):
    """Extension-worker decision attached to a disease analysis."""
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('disease_analysis.id'), nullable=False, unique=True)
    status = db.Column(db.String(30), nullable=False, default='under_review')
    decision = db.Column(db.String(30), nullable=False, default='under_review')
    confirmed_disease = db.Column(db.String(100))
    notes = db.Column(db.Text)
    expert_advisory = db.Column(db.Text)
    lab_name = db.Column(db.String(150))
    lab_sample_id = db.Column(db.String(100))
    lab_notes = db.Column(db.Text)
    lab_result = db.Column(db.Text)
    lab_referred_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.String(100))
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    analysis = db.relationship('DiseaseAnalysis', backref=db.backref('case_review', uselist=False))


class CaseFollowUp(db.Model):
    """Current field follow-up plan for an extension-reviewed case."""
    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey('disease_analysis.id'), nullable=False)
    review_id = db.Column(db.Integer, db.ForeignKey('case_review.id'), nullable=False, unique=True)
    assigned_to = db.Column(db.String(100), nullable=False, default='admin')
    priority = db.Column(db.String(20), default='moderate')
    status = db.Column(db.String(20), default='pending')
    action = db.Column(db.Text, nullable=False, default='')
    due_date = db.Column(db.Date)
    next_action = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    review = db.relationship('CaseReview', backref=db.backref('follow_up', uselist=False))
