import importlib
import logging
import pkgutil
import sys

from flask import Blueprint
from peewee import IntegrityError

from artifacts import plugins
from artifacts.utils.registry_utils import QuayRegistryClient

from data.database import RepositoryKind

logger = logging.getLogger(__name__)

current_module = sys.modules[__name__]
current_package = current_module.__package__

plugins_bp = Blueprint("artifacts", __name__)


def discover_plugins():
    # All plugins go in the `plugins` directory and
    # each plugin exposes the `plugin` variable in its
    # __init__.py file

    return {
        pkg.name: importlib.import_module(f".plugins.{pkg.name}", package=current_package).plugin
        for pkg in pkgutil.iter_modules(plugins.__path__)
    }


def init_plugins(application):
    # TODO: pass plugin specific config
    discovered_plugins = discover_plugins()
    for plugin_obj in discovered_plugins.values():
        plugin_obj.register_routes(plugins_bp)
        try:
            RepositoryKind.get_or_create(name=plugin_obj.name)
        except IntegrityError as ex:
            logger.debug("Plugin %s already registered, continuing.", plugin_obj.name)
            pass
    application.register_blueprint(plugins_bp, url_prefix="/artifacts")


def init_web_routes(application):
    discovered_plugins = discover_plugins()
    for plugin_obj in discovered_plugins.values():
        application.register_blueprint(plugin_obj.bp, url_prefix=plugin_obj.name)
