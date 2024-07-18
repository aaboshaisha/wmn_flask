from flask import Flask, render_template
import os
from instance.config import Config
from flask_cors import CORS

def create_app(test_config=None): # option to pass configurations specific for testing 
    app = Flask(__name__, instance_relative_config=True) # create app instance
    app.config.from_object(Config)
    
    # set configuration for app instance 
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'myapp.sqlite'),
    )


    if test_config is None:
        # if not testing. load instance specific config if exists
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)
    
    # make sure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    from . import notes
    app.register_blueprint(notes.bp)

    from . import payment
    app.register_blueprint(payment.bp)


    # get the email blueprint
    from . import email
    app.register_blueprint(email.bp)
    
    from . import index
    app.register_blueprint(index.bp)

    CORS(app)
    
    return app