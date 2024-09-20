from abc import ABCMeta, abstractmethod

from six import add_metaclass


@add_metaclass(ABCMeta)
class PluginsInterface(object):
    """
    Implements the full plugin interface for use for all plugins.
    The interface contains methods related to logging in, pushing, pulling, creating manifests based on pushed data and other
    plugin related operations.
    """

    @abstractmethod
    def login(self, username):
        """
        Conducts login for a specific user.
        """

    @abstractmethod
    def logout(self, username):
        """
        Conducts logout for a specific user if required.
        """

    @abstractmethod
    def create_artifact_repository(self, namespace_name, artifact_name):
        """
        Create artifact repository for a specific artifact type.
        """

    @abstractmethod
    def create_artifact_manifest(self):
        """
        Creates OCI compliant artifact manifest based on the pushed object.
        """

    @abstractmethod
    def upload_artifact(self):
        """
        Upload the artifact to the registry.
        """

    @abstractmethod
    def get_artifact_repo(artifact_name):
        """
        Gets the artifact repository name.
        """

    @abstractmethod
    def get_artifact_manifest(artifact_name):
        """
        Returns the artifact manifest for a provided artifact name.
        """

    @abstractmethod
    def get_artifact_blob_url(self, artifact_digest):
        """
        Returns the blob download URL for a given artifact digest.
        """
