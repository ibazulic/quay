import base64
import json
import logging

from artifacts.plugins.npm import PLUGIN_NAME
from artifacts.utils.plugin_auth import generate_auth_token_for_read
from artifacts.utils.registry_utils import RegistryError, QuayRegistryClient

logger = logging.getLogger(__name__)

quayRegistryClient = QuayRegistryClient(PLUGIN_NAME)


def parse_package_tarball(npm_post_data):
    attachments = npm_post_data.get('_attachments', {})
    # TODO: can there be multiple attachments?
    if not attachments:
        return None
    tarball = list(attachments.values())[0].get('data')
    if not tarball:
        return None
    decoded_bytes = base64.b64decode(tarball)
    return decoded_bytes


def parse_package_metadata(npm_post_data):
    versions = npm_post_data.get('versions', {})
    if not versions:
        return None

    version = list(versions.keys())[0]
    metadata = versions.get(version)
    # update tarball location
    # TODO: catch exception
    download_url = f'{quayRegistryClient.scheme}://{quayRegistryClient.hostname}/artifacts/npm/download/{metadata["name"]}/{version}'
    metadata['dist']['tarball'] = download_url

    return metadata


def get_package_metadata(namespace, package_name, tag, grant_token):
    """"
    package metadata is stored in the config blob
    """
    response = quayRegistryClient.get_oci_manifest_by_tag(namespace, package_name, tag, grant_token)
    if response.status_code != 200:
        raise RegistryError('Error fetching manifest')

    manifest = response.json
    config_digest = manifest.get('config', {}).get('digest')
    if not config_digest:
        raise RegistryError('No config digest found in manifest')

    response = quayRegistryClient.get_oci_blob(namespace, package_name, config_digest, grant_token)
    if response.status_code != 200:
        raise RegistryError('Error fetching config blob')

    return json.loads(response.data)


def get_package_list(auth_result, namespace, package_name):
    # get list of tags for the package
    grant_token = generate_auth_token_for_read(auth_result, namespace, package_name)
    tags = quayRegistryClient.get_all_tags(namespace, package_name, grant_token)
    package_list = {}
    for tag in tags:
        metadata = get_package_metadata(namespace, package_name, tag, grant_token)
        package_list[tag] = metadata

    return package_list


def get_package_tarball(auth_result, namespace, package_name, package_version):
    # get the package manifest
    grant_token = generate_auth_token_for_read(auth_result, namespace, package_name)
    response = quayRegistryClient.get_oci_manifest_by_tag(namespace, package_name, package_version, grant_token)
    if response.status_code != 200:
        return response

    manifest = response.json
    data_digest = manifest.get('layers')[0].get('digest')
    response = quayRegistryClient.get_oci_blob(namespace, package_name, data_digest, grant_token)
    return response


class InvalidPackageNameError(Exception):
    pass


def check_valid_package_name(package_name):
    logger.info(f'💟 💟 💟 💟 💟 package_name {package_name}')
    if not package_name:
        raise InvalidPackageNameError('Invalid package name')

    if "/" not in package_name:
        raise InvalidPackageNameError('Invalid package name')

    if not package_name.startswith('@'):
        raise InvalidPackageNameError('Invalid package name')
