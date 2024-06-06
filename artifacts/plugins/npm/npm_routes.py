import json
import logging

from artifacts.plugins.npm import PLUGIN_NAME
from artifacts.plugins.npm.npm_utils import parse_package_tarball, get_package_list, check_valid_package_name, \
    InvalidPackageNameError, parse_package_metadata, get_package_tarball, quayRegistryClient
from artifacts.utils.plugin_auth import apply_auth_result, validate_plugin_auth, generate_auth_token_for_write
from artifacts.utils.registry_utils import calculate_sha256_digest, is_success

from auth.auth_context import get_authenticated_user, get_authenticated_context
from flask import Blueprint, request, jsonify, make_response, abort

from artifacts.plugins.npm.npm_auth import \
    npm_token_auth, delete_npm_token, npm_username_auth
from artifacts.plugins.npm.npm_models import create_and_save_new_token_for_user

from util.cache import no_cache

bp = Blueprint(PLUGIN_NAME, __name__)
logger = logging.getLogger(__name__)


@bp.route('/ping')
def ping():
    return jsonify({'ok': PLUGIN_NAME}), 200


@bp.route('/-/v1/login', methods=['POST'])
def login_hostname():
    """
        Example request data:
        {"hostname":"syahmed-mac"}
    """
    return jsonify({'error': 'validation method not supported'}), 401


@bp.route('/-/user/org.couchdb.user:<user_id>', methods=['PUT'])
@no_cache
@validate_plugin_auth(npm_username_auth)
def npm_login(auth_result, user_id):
    """
    NPM login user
    ref: https://github.com/npm/registry/blob/master/docs/user/authentication.md#login
    """
    token = create_and_save_new_token_for_user(get_authenticated_user())
    return make_response(jsonify({"token": token}), 201)


@bp.route('/-/user/token/<token>', methods=['DELETE'])
@validate_plugin_auth(npm_token_auth)
def logout(auth_result, token):
    """
    logout a user
    bearer token in the Authorization header identifies the user
    ref: https://docs.npmjs.com/cli/v7/commands/npm-logout
    ref: https://github.com/npm/registry/blob/master/docs/user/authentication.md#token-delete
    """
    error = delete_npm_token(token)
    if not error:
        return jsonify({'ok': 'Logged out'}), 201

    return make_response(jsonify({'error': error}), 500)


@bp.route('/<path:package>', methods=['PUT'])
@validate_plugin_auth(npm_token_auth)
def npm_publish_package(auth_result, package):
    try:
        check_valid_package_name(package)
    except InvalidPackageNameError as e:
        return jsonify({'error': str(e)}), 400

    package_data = request.get_json()
    package_name = package_data.get('name')
    package_versions = package_data.get('versions')

    if not package_name or not package_versions or not package_name.startswith('@'):
        return jsonify({'error': 'Invalid package data'}), 400

    # TODO: can there be multiple versions?
    package_version = list(package_versions.keys())[0]

    namespace, repo_name = package_name.split('/')
    namespace = namespace.replace('@', '')
    repo_tag = package_version

    # scope request to upload package
    grant_token = generate_auth_token_for_write(auth_result, namespace, repo_name)

    # upload config
    data = parse_package_tarball(package_data)
    if not data:
        return jsonify({'error': 'No data found to upload'}), 400

    metadata = parse_package_metadata(package_data)
    if not metadata:
        metadata = {}

    metadata_json = json.dumps(metadata)
    metadata_digest = calculate_sha256_digest(metadata_json.encode('utf-8'))
    response = quayRegistryClient.upload_artifact_blob(namespace, repo_name, metadata_json, metadata_digest, grant_token)
    if not is_success(response):
        return jsonify({'error': 'Error uploading package metadata'}), 500

    data_digest = calculate_sha256_digest(data)
    response = quayRegistryClient.upload_artifact_blob(namespace, repo_name, data, data_digest, grant_token)
    if is_success(response):
        return jsonify({'error': 'Error uploading package'}), 500

    # create manifest
    manifest = quayRegistryClient.create_oci_artifact_manifest(
        media_type='application/vnd.npm.package.v1+json',
        length=len(data),
        digest=data_digest,
        config_media_type='application/vnd.npm.config.v1+json',
        config_digest=metadata_digest,
        config_length=len(metadata),
    )

    return quayRegistryClient.upload_oci_artifact_manifest(namespace, repo_name, manifest, repo_tag, grant_token)


@bp.route('/<path:package>', methods=['GET'])
@validate_plugin_auth(npm_token_auth)
def npm_get_package(auth_result, package):
    try:
        check_valid_package_name(package)
    except InvalidPackageNameError as e:
        return jsonify({'error': str(e)}), 400

    namespace, repo_name = package.split('/')
    if not namespace or not repo_name:
        return jsonify({'error': 'Invalid package name'}), 400

    namespace = namespace.replace('@', '')
    package_list = get_package_list(auth_result, namespace, repo_name)
    package_response =  {
        'name': package,
        'versions': package_list
    }
    return jsonify(package_response), 200


@bp.route('/download/<path:namespace>/<path:package_name>/<path:version>', methods=['GET'])
@validate_plugin_auth(npm_token_auth)
def npm_get_package_tarball(auth_result, namespace, package_name, version):
    # get the package
    namespace = namespace.replace('@', '')
    return get_package_tarball(auth_result, namespace, package_name, version)
