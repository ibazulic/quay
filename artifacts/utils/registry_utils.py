import hashlib
import json
import logging
from pprint import pprint

from typing import List

from flask import request

from auth.credentials import validate_credentials
from auth.validateresult import ValidateResult, AuthKind
from data.database import RepositoryKind

from data.model.repository import get_repository

from app import app
from auth.signedgrant import validate_signed_grant_token
from image.oci import OCI_IMAGE_MANIFEST_CONTENT_TYPE, OCI_IMAGE_CONFIG_CONTENT_TYPE
from util.http import abort

logger = logging.getLogger(__name__)

EMPTY_CONFIG_JSON = "{}"
EMPTY_CONFIG_MEDIATYPE = "application/vnd.oci.empty.v1+json"


class RegistryError(Exception):
    pass


# TODO: Eventually these classes can be abosrbed into the OCI module (image.oci)
class OCILayer:
    def __init__(self, media_type, length, digest, annotations=None):
        self.media_type = media_type
        self.length = length
        self.digest = digest
        self.annotations = annotations

    def to_dict(self):
        data = {
            "mediaType": self.media_type,
            "size": self.length,
            "digest": self.digest
        }
        if self.annotations:
            data['annotations'] = self.annotations

        return data

    @classmethod
    def from_dict(cls, data):
        media_type = data.get('mediaType')
        length = data.get('size')
        digest = data.get('digest')
        annotations = data.get('annotations')
        return cls(media_type, length, digest, annotations)


class OCIConfigLayer(OCILayer):
    def __init__(self, media_type, length, digest, annotations=None):
        super().__init__(media_type, length, digest, annotations)


class OCIEmptyConfigLayer(OCIConfigLayer):
    def __init__(self):
        data = EMPTY_CONFIG_JSON.encode('utf-8')
        digest = calculate_sha256_digest(data)
        super().__init__(EMPTY_CONFIG_MEDIATYPE, len(data), digest)


class OCIArtifactManifest:
    def __init__(self, artifact_type, config_layer: OCIConfigLayer, layers: List[OCILayer]):
        self.artifact_type = artifact_type
        self.config_layer = config_layer
        self.layers = layers

    def to_dict(self):
        return {
            "schemaVersion": 2,
            "mediaType": OCI_IMAGE_MANIFEST_CONTENT_TYPE,
            "artifactType": self.artifact_type,
            "config": self.config_layer.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers]
        }

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data):
        artifact_type = data.get('artifactType')
        config_layer = OCIConfigLayer.from_dict(data.get('config'))
        layers = [OCILayer.from_dict(layer) for layer in data.get('layers')]
        return cls(artifact_type, config_layer, layers)

    @classmethod
    def from_json(cls, data):
        data = json.loads(data)
        return cls.from_dict(data)


def calculate_sha256_digest(data):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(data)
    digest = sha256_hash.hexdigest()
    return f'sha256:{digest}'


def is_success(response):
    return response.status_code in [200, 201]


def artifact_plugin_validate_basic_auth():
    """
    Basic auth with username and password
    """
    auth = request.authorization
    if not auth:
        # could be anonymous
        return ValidateResult(AuthKind.credentials, missing=True)
    username = auth.username
    password = auth.password
    auth_result, _auth_kind = validate_credentials(username, password)
    return auth_result.with_kind(AuthKind.credentials)

class QuayRegistryClient:
    def __init__(self, plugin_name):
        self.plugin_name = plugin_name
        self.hostname = app.config.get('SERVER_HOSTNAME')
        self.scheme = app.config.get('PREFERRED_URL_SCHEME', 'http')

    def _do_request(self, method, path, headers=None, query_string=None, data=None):
        with app.test_client() as c:
            response = c.open(
                method=method,
                path=path,
                headers=headers,
                data=data,
                query_string=query_string
            )
            return response

    def check_blob_exists(self, namespace, repo_name, digest, registry_grant_token):
        headers = {
            'Authorization': f'Bearer {registry_grant_token}'
        }
        path = f'/v2/{namespace}/{repo_name}/blobs/{digest}'
        response = self._do_request('HEAD', path, headers=headers)
        if response.status_code == 401:
            abort(401, message=response.data)
        return response

    def start_upload_blob(self, namespace, repo_name, registry_grant_token):
        headers = {
            'Authorization': f'Bearer {registry_grant_token}'
        }
        path = f'/v2/{namespace}/{repo_name}/blobs/uploads/'
        response = self._do_request('POST', path, headers=headers)
        pprint(dict(response.headers))
        if response.status_code == 401:
            abort(401, message=response.data)
        return response

    def upload_artifact_blob(self, namespace, repo_name, data, data_digest, registry_grant_token):
        blob_exists_response = self.check_blob_exists(namespace, repo_name, data_digest, registry_grant_token)
        logger.info(f'🟦 🟦 🟦 🟦  uploading blob {data_digest}, exists? {blob_exists_response.data}')
        if blob_exists_response.status_code == 200:
            return blob_exists_response

        start_response = self.start_upload_blob(namespace, repo_name, registry_grant_token)
        if start_response.status_code != 202:
            return start_response

        location = start_response.headers.get('Location')
        qs = {
            'digest': data_digest,
        }
        headers = {
            'Authorization': f'Bearer {registry_grant_token}'
        }
        response = self._do_request('PUT', location, headers=headers, data=data, query_string=qs)
        logger.info(f'🟦 🟦 🟦 🟦  blob upload response {response} {response.data}')
        return response

    def ensure_empty_blob(self, namespace, repo_name, grant_token):
        empty_blob_digest = calculate_sha256_digest(EMPTY_CONFIG_JSON.encode('utf-8'))
        return self.upload_artifact_blob(namespace, repo_name, EMPTY_CONFIG_JSON.encode('utf-8'), empty_blob_digest,
                                         grant_token)

    def list_tags(self, namespace, repo_name, grant_token):
        path = f'/v2/{namespace}/{repo_name}/tags/list'
        headers = {
            'Authorization': f'Bearer {grant_token}'
        }

        response = self._do_request('GET', path, headers=headers)
        logger.info(f'🟦 🟦 🟦 🟦  list tags response {response} {response.data}')
        if response.status_code == 401:
            abort(401, message=response.data)
        return response

    def create_oci_artifact_manifest(self, media_type, length, digest, config_layer=None, layers=None):
        # Generate the list of layer digests
        if not config_layer:
            config_layer = OCIEmptyConfigLayer()

        # Create the OCI manifest
        manifest = OCIArtifactManifest(media_type, config_layer, layers)
        return manifest

    def upload_oci_artifact_manifest(self, namespace, repo_name, manifest: OCIArtifactManifest, tag,
                                     registry_grant_token):
        result = validate_signed_grant_token(registry_grant_token)
        if not result:
            raise RegistryError("Invalid grant token")

        if manifest.config_layer.media_type == EMPTY_CONFIG_MEDIATYPE:
            self.ensure_empty_blob(namespace, repo_name, registry_grant_token)

        headers = {
            'Authorization': f'Bearer {registry_grant_token}',
            'Content-Type': 'application/vnd.oci.image.manifest.v1+json'
        }

        path = f'/v2/{namespace}/{repo_name}/manifests/{tag}'
        response = self._do_request('PUT', path, headers=headers, data=manifest.to_json())
        logger.info(f'🟦 🟦 🟦 🟦  manifest upload response {response} {response.data}')
        if response.status_code == 401:
            abort(401, message=response.data)
        if response.status_code == 201:
            self.update_repository_kind(namespace, repo_name, self.plugin_name)

        return response

    def get_oci_manifest_by_tag(self, namespace, repo_name, tag, grant_token):
        path = f'/v2/{namespace}/{repo_name}/manifests/{tag}'
        headers = {
            'Authorization': f'Bearer {grant_token}',
            'Accept': 'application/vnd.oci.image.manifest.v1+json'
        }
        response = self._do_request('GET', path, headers=headers)
        pprint(response.headers)
        logger.info(f'🟦 🟦 🟦 🟦  get manifest response {response} {response.data}')
        if response.status_code == 401:
            abort(401, message=response.data)
        return response

    def get_oci_blob(self, namespace, repo_name, digest, grant_token):
        path = f'/v2/{namespace}/{repo_name}/blobs/{digest}'
        headers = {
            "Authorization": f"Bearer {grant_token}"
        }
        response = self._do_request('GET', path, headers=headers)
        if response.status_code == 401:
            abort(401, message=response.data)
        return response

    def update_repository_kind(self, namespace, repo_name, kind):
        # get the repository from the database
        repository = get_repository(namespace, repo_name)
        if not repository:
            raise RegistryError(f"Repository {namespace}/{repo_name} not found")

        kind_model = RepositoryKind.get(name=kind)
        repository.kind = kind_model
        repository.save()

    def get_all_tags(self, namespace, repo_name, grant_token):
        # TODO: handle pagination
        tags_response = self.list_tags(namespace, repo_name, grant_token)
        if tags_response.status_code != 200:
            return []
        return tags_response.get_json().get('tags')

    def get_blob_url(self, namespace, repo_name, blob_digest):
        return f'{self.scheme}://{self.hostname}/v2/{namespace}/{repo_name}/blobs/{blob_digest}'

