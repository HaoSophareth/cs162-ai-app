from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    # Profile: empty right after signup, filled in on the onboarding page.
    sex = db.Column(db.String(10))
    age = db.Column(db.Integer)
    weight_kg = db.Column(db.Float)
    height_cm = db.Column(db.Integer)
    plans = db.relationship("Plan", backref="user", cascade="all, delete-orphan")

    @property
    def has_profile(self):
        return None not in (self.sex, self.age, self.weight_kg, self.height_cm)


class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    has_run_before = db.Column(db.Boolean, nullable=False)
    weekly_km = db.Column(db.Float, nullable=False)
    longest_run_km = db.Column(db.Float)  # optional; None for new runners
    run_days = db.Column(db.String(30), nullable=False)
    long_run_day = db.Column(db.String(3), nullable=False)
    race_distance = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    race_date = db.Column(db.Date, nullable=False)
    # Recent race times in whole seconds; None when not given.
    best_5k = db.Column(db.Integer)
    best_10k = db.Column(db.Integer)
    best_half = db.Column(db.Integer)
    best_full = db.Column(db.Integer)
    runs = db.relationship("Run", backref="plan", cascade="all, delete-orphan")


class Run(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    run_type = db.Column(db.String(20), nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    notes = db.Column(db.Text, nullable=False, default="")
    done = db.Column(db.Boolean, nullable=False, default=False)
