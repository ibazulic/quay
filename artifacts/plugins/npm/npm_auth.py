import logging
import uuid
from functools import wraps
from hashlib import sha512

from auth.auth_context import get_authenticated_user
from util.http import abort

from artifacts.utils.plugin_auth import apply_auth_result

from data.model import DataModelException

from auth.validateresult import ValidateResult, AuthKind

from artifacts.plugins.npm.npm_models import NpmToken
from auth.decorators import authentication_count
from endpoints.v2.v2auth import generate_registry_jwt

from auth.credentials import validate_credentials, CredentialKind
from flask import request, jsonify

logger = logging.getLogger(__name__)


def get_bearer_token():
    return request.headers.get('Authorization').split(' ')[1] if request.headers.get('Authorization') else None


def get_username_password():
    user_data = request.get_json()
    username = user_data.get('name')
    password = user_data.get('password')
    return username, password


def npm_username_auth():
    username, password = get_username_password()
    auth_result, _auth_kind = validate_credentials(username, password)
    return auth_result


def delete_npm_token(token):
    token_key = sha512(token.encode('utf-8')).hexdigest()
    try:
        token = NpmToken.get(token_key=token_key)
        token.delete_instance()
        return None
    except DataModelException as e:
        logger.error('Error deleting token', e)
        return f"Error deleting token: {e}"


def get_token_from_db(token):
    token_key = sha512(token.encode('utf-8')).hexdigest()
    return NpmToken.get(token_key=token_key)


def npm_token_auth():
    # get the token from the DB and validate it
    token = get_bearer_token()
    if not token:
        return ValidateResult(AuthKind.credentials, missing=True)

    try:
        db_token = get_token_from_db(token)
        if not db_token:
            return ValidateResult(AuthKind.credentials, error_message='Invalid token')
        return ValidateResult(AuthKind.credentials, user=db_token.user)
    except Exception as e:
        # TODO: use specific exception
        logger.error("Error validating token: %s", e)
        abort(401, message='Error validating token')
