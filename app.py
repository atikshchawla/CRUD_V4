from flask import Flask
from extensions import db, login_manager
from routes import routes
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key-123'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db' #Initiation DB
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False #Signal limiting


    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)


    # Configure login manager
    login_manager.login_view = 'routes.login'


    # Register blueprint
    app.register_blueprint(routes)


    # Create tables
    with app.app_context():
        db.create_all()


    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )


    # Apply to login route
    limiter.limit("5 per minute")(app.view_functions['routes.login'])

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=False)
