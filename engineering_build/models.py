from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    plan = db.relationship("Plan", backref="user", uselist=False)


class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # unique=True enforces one plan per user at the database level.
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    experience = db.Column(db.String(20), nullable=False)
    run_days = db.Column(db.String(30), nullable=False)
    long_run_day = db.Column(db.String(3), nullable=False)
    race_distance = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    race_date = db.Column(db.Date, nullable=False)
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
