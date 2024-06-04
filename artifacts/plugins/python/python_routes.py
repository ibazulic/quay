import logging

from flask import Blueprint, jsonify, request, redirect, url_for, make_response

from artifacts.plugins.python import PLUGIN_NAME
from artifacts.plugins.python.constants import PYTHON_PACKAGE_MEDIA_TYPE, PYPI_JSON_CONTENT_TYPE
from artifacts.plugins.python.python_utils import get_layer_media_type, quayRegistryClient, \
    get_python_packages_for_repo, update_manifest_with_new_layer
from artifacts.utils.plugin_auth import apply_auth_result, validate_plugin_auth, generate_auth_token_for_write, \
    generate_auth_token_for_read
from artifacts.utils.registry_utils import calculate_sha256_digest, QuayRegistryClient, OCILayer, OCIArtifactManifest, \
    artifact_plugin_validate_basic_auth
from auth.credentials import validate_credentials

bp = Blueprint(PLUGIN_NAME, __name__)
logger = logging.getLogger(__name__)


@bp.route('/ping')
def ping():
    return jsonify({'ok': PLUGIN_NAME}), 200


@bp.route('/+login', methods=['POST'])
def login():
    """
        Example request data:
        {"username":"user", "password":"password"}
    """
    req_data = request.get_json()
    if 'username' not in req_data or 'password' not in req_data:
        return jsonify({'error': 'username password required'}), 401

    username = req_data['username']
    password = req_data['password']

    auth_result, _auth_kind = validate_credentials(username, password)
    if auth_result.error_message is not None:
        return jsonify({'error': 'Invalid credentials'}), 401

    apply_auth_result(auth_result)
    return jsonify({'ok': 'login successful'}), 200


@bp.route('/<index>', methods=['POST'])
@validate_plugin_auth(artifact_plugin_validate_basic_auth)
def upload_package(auth_result, index):
    """
    If we are uploading a package, we add different
    file types as a layer to the existing manifest.
    Attributes are added as annotations to the layer
    """

    package_name = request.form['name']
    package_version = request.form['version']
    filetype = request.form['filetype']

    content = request.files['content']

    # convert to OCI format
    namespace = index
    repo_name = f'{package_name}'
    repo_tag = package_version

    grant_token = generate_auth_token_for_write(auth_result, namespace, repo_name)

    data = content.read()
    data_digest = calculate_sha256_digest(data)
    response = quayRegistryClient.upload_artifact_blob(namespace, repo_name, data, data_digest, grant_token)
    logger.info(f'🟦 🟦 🟦 🟦  upload response {response.data} {response.status_code}')
    if response.status_code not in [200, 201]:
        return jsonify({'error': 'Error uploading package'}), 500

    # TODO: there may be more annotations to add
    layer = OCILayer(
        get_layer_media_type(filetype),
        len(data),
        data_digest,
        annotations={
            'filename': content.filename,
            'requires-python': request.form.get('requires_python'),
            'filetype': filetype,
        }
    )

    manifest_response = quayRegistryClient.get_oci_manifest_by_tag(namespace, repo_name, repo_tag, grant_token)
    logger.info(f'🟦 🟦 🟦 🟦  manifest response {manifest_response.data} {manifest_response.status_code}')

    manifest = None
    if manifest_response.status_code == 200:
        manifest = OCIArtifactManifest.from_json(manifest_response.data)
        update_manifest_with_new_layer(manifest, layer)
    else:
        # create manifest
        manifest = quayRegistryClient.create_oci_artifact_manifest(
            media_type=PYTHON_PACKAGE_MEDIA_TYPE,
            length=len(data),
            digest=data_digest,
            layers=[layer]
        )

    logger.info(f'🔴🟣🔴🟣🔴🟣 manifest {manifest.to_json()}')

    response = quayRegistryClient.upload_oci_artifact_manifest(
        namespace,
        repo_name,
        manifest,
        repo_tag,
        grant_token
    )

    logger.info(f'🔴🟣🔴🟣🔴🟣 manifest response {response} {response.data}')
    # TODO: check if the response is good
    if response.status_code != 201:
        return jsonify({'error': 'Error uploading package'}), 500

    return jsonify({'ok': 'Package published'}), 200


@bp.route('/<index>/<package>', methods=['GET'], strict_slashes=False)
@validate_plugin_auth(artifact_plugin_validate_basic_auth)
def get_package(auth_result, index, package):
    # TODO: handle anonymous read
    namespace = index
    repo_name = package
    grant_token = generate_auth_token_for_read(auth_result, namespace, repo_name)

    logger.info(f'🔴🟣🔴🟣🔴🟣 request for {index} {package}')

    packages = get_python_packages_for_repo(namespace, repo_name, grant_token)

    json_resp = jsonify(packages)
    logger.info(f'🔴🟣🔴🟣🔴🟣 packages for {namespace}/{repo_name} --- {json_resp.data}')
    json_resp.headers['Content-Type'] = PYPI_JSON_CONTENT_TYPE
    return json_resp


@bp.route('/download/<namespace>/<repo_name>/<digest>/<filename>', strict_slashes=False, methods=['GET'])
@validate_plugin_auth(artifact_plugin_validate_basic_auth)
def download_package(auth_result, namespace, repo_name, digest, filename):
    logger.info(f'🔴🟣🔴🟣🔴🟣 request for {namespace} {repo_name} {digest} {filename}')
    grant_token = generate_auth_token_for_read(auth_result, namespace, repo_name)
    return quayRegistryClient.get_oci_blob(namespace, repo_name, digest, grant_token)
