import logging

from artifacts import init_plugins

import endpoints.decorated  # Note: We need to import this module to make sure the decorators are registered.
import features
from app import app as application
from endpoints.v1 import v1_bp
from endpoints.v2 import v2_bp

application.register_blueprint(v1_bp, url_prefix="/v1")
application.register_blueprint(v2_bp, url_prefix="/v2")

if features.PLUGIN_SUPPORT:
    from artifacts import init_plugins

    init_plugins(application)
