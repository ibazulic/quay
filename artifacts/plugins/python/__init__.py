import logging

from .constants import PLUGIN_NAME
from .python_routes import bp as python_bp
from artifacts.plugins_base import BaseArtifactPlugin

logger = logging.getLogger(__name__)


class PythonPlugin(BaseArtifactPlugin):
    def __init__(self, name):
        super().__init__(name)

    def register_routes(self, app):
        app.register_blueprint(python_bp, url_prefix="/python")

    def register_workers(self):
        pass

    def __str__(self):
        return self.name


plugin = PythonPlugin(PLUGIN_NAME)
