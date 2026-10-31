import os

from flask import Flask
from flask_login import LoginManager

from auth import auth_bp
from main import main_bp
from models import User, db


def create_app():
    app = Flask(__name__)
    # Fine for running locally; set SECRET_KEY in the environment for anything else.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # A relative SQLite path is stored in Flask's instance/ folder.
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///running.db"

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    # Port 5000 is taken by AirPlay Receiver on macOS, so use a less common one.
    app.run(debug=True, port=5050)
