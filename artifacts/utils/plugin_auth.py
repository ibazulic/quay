import logging
from functools import wraps

from app import app
from auth.decorators import authentication_count
from flask import jsonify

from endpoints.v2.v2auth import generate_registry_jwt
from util.http import abort

logger = logging.getLogger(__name__)


def validate_plugin_auth(auth_fn):
    """
    The auth_fn should return an AuthResult object
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_result = auth_fn()
            if auth_result:
                # will abort with 401 if bad auth
                apply_auth_result(auth_result)
            return func(auth_result, *args, **kwargs)

        return wrapper

    return decorator


def generate_auth_token_for_write(auth_result, namespace, repo_name):
    aud_params = app.config.get('SERVER_HOSTNAME')
    push_scope = f"repository:{namespace}/{repo_name}:pull,push"
    scope_params = [push_scope]
    return generate_registry_jwt(auth_result, bool(auth_result), aud_params, scope_params)


def generate_auth_token_for_read(auth_result, namespace, repo_name):
    aud_params = app.config.get('SERVER_HOSTNAME')
    pull_scope = f"repository:{namespace}/{repo_name}:pull"
    scope_params = [pull_scope]
    auth_credentials_sent = not auth_result.missing
    return generate_registry_jwt(auth_result, auth_credentials_sent, aud_params, scope_params)


def apply_auth_result(auth_result):
    if not auth_result:
        return abort(401, message=jsonify('Invalid username or password'))

    if auth_result.auth_valid:
        logger.debug("Found valid auth result: %s", auth_result.tuple())

        # Set the various pieces of the auth context.
        auth_result.apply_to_context()

        # Log the metric.
        authentication_count.labels(auth_result.kind, True).inc()

    # Otherwise, report the error.
    if auth_result.error_message is not None:
        # Log the failure.
        authentication_count.labels(auth_result.kind, False).inc()
        # Do we only need to abort for JWT based errors?
        abort(401, message=auth_result.error_message)
