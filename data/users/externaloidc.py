import json
import logging
from urllib.parse import urlparse

import app
from data.model import InvalidTeamException, UserAlreadyInTeam, team
from data.users import oidc_team_sync
from data.users.federated import FederatedUsers, UserInformation
from oauth.login_utils import get_username_from_userinfo
from oauth.oidc import OIDCLoginService

logger = logging.getLogger(__name__)


class OIDCUsers(FederatedUsers):
    def __init__(
        self,
        client_id,
        client_secret,
        oidc_server,
        service_name,
        login_scopes,
        preferred_group_claim_name,
        requires_email=True,
        oidc_superuser_group=None,
        oidc_global_readonly_superuser_group=None,
    ):
        super(OIDCUsers, self).__init__("oidc", requires_email)
        self._client_id = client_id
        self._client_secret = client_secret
        self._oidc_server = oidc_server
        self._service_name = service_name
        self._login_scopes = login_scopes
        self._preferred_group_claim_name = preferred_group_claim_name
        self._requires_email = requires_email
        self._oidc_superuser_group = oidc_superuser_group
        self._oidc_global_readonly_superuser_group = oidc_global_readonly_superuser_group

    def service_metadata(self):
        for service in app.oauth_login.services:
            if isinstance(service, OIDCLoginService):
                return {"issuer_domain": urlparse(service.get_issuer()).netloc}
        return {}

    def is_superuser(self, username: str):
        """
        Initiated from FederatedUserManager.is_superuser(), falls back to ConfigUserManager.is_superuser()
        """
        return None

    def is_global_readonly_superuser(self, username: str):
        """
        Initiated from FederatedUserManager.is_global_readonly_superuser(), falls back to ConfigUserManager.is_global_readonly_superuser()
        """
        return None

    def is_restricted_user(self, username):
        """
        Checks whether the currently logged in user is restricted.
        """
        return None

    def iterate_group_members(self, group_lookup_args, page_size=None, disable_pagination=False):
        """
        Used by teamSync worker, unsupported for oidc team sync
        """
        return (None, "Not supported")

    def has_password_set(self, username):
        # OIDC users authenticate via token flows; they have no Quay-local password.
        # Returning False lets require_fresh_login bypass the fresh-login check so
        # OIDC browser users are not prompted for a password they cannot provide.
        return False

    def verify_credentials(self, username_or_email, password):
        """
        Unsupported to login via username/email and password
        """
        if not password:
            return (None, "Anonymous binding not allowed.")

        if not username_or_email:
            return (None, "Missing username or email.")

        for service in app.oauth_login.services:
            if isinstance(service, OIDCLoginService):
                try:
                    response = service.password_grant_for_login(username_or_email, password)

                    if response is None:
                        return (None, "External OIDC Group Sync: Got no user info")

                    user_info = service.get_user_info(
                        service._http_client, response["access_token"]
                    )

                    return (
                        UserInformation(
                            username=get_username_from_userinfo(user_info, service.config),
                            email=user_info.get("email"),
                            id=user_info.get("sub"),
                        ),
                        None,
                    )
                except Exception as err:
                    logger.exception(
                        f"External OIDC Group Sync: Exception while verifying credentials: {err}"
                    )
                    return (None, err)

    def check_group_lookup_args(self, group_lookup_args, disable_pagination=False):
        """
        No way to verify if the group is valid, so assuming the group is valid
        """
        return (True, None)

    def get_user(self, username_or_email):
        """
        No way to look up a username or email in OIDC so returning None
        """
        return (None, "Currently user lookup is not supported with OIDC")

    def query_users(self, query, limit):
        """
        No way to query users so returning empty list
        """
        return ([], self._federated_service, "Not supported")

    def sync_oidc_groups(self, user_groups, user_obj):
        """
        Adds user to quay teams that have team sync enabled with an OIDC group
        """
        oidc_team_sync.sync_oidc_groups(user_groups, user_obj, self._federated_service)

    def ping(self):
        """
        TODO: get the OIDC connection here
        """
        return (True, None)

    def resync_quay_teams(self, user_groups, user_obj):
        """
        Fetch quay teams that user is a member of.
        Remove user from teams that are synced with an OIDC group but group does not exist in "user_groups"
        """
        oidc_team_sync.resync_quay_teams(user_groups, user_obj, self._federated_service)

    def sync_superuser_status(self, user_groups, user_obj):
        """
        Syncs superuser and global readonly superuser status based on OIDC group membership.
        Registers or deregisters the user via the shared ConfigUserManager arrays.
        """
        if not user_obj or user_groups is None:
            return

        try:
            if self._oidc_superuser_group:
                if user_groups and self._oidc_superuser_group in user_groups:
                    logger.debug(
                        "OIDC superuser sync: granting superuser to %s (member of %s)",
                        user_obj.username,
                        self._oidc_superuser_group,
                    )
                    app.usermanager.register_superuser(user_obj.username)
                else:
                    logger.debug(
                        "OIDC superuser sync: revoking superuser from %s (not member of %s)",
                        user_obj.username,
                        self._oidc_superuser_group,
                    )
                    app.usermanager.deregister_superuser(user_obj.username)

            if self._oidc_global_readonly_superuser_group:
                if user_groups and self._oidc_global_readonly_superuser_group in user_groups:
                    logger.debug(
                        "OIDC superuser sync: granting global readonly superuser to %s (member of %s)",
                        user_obj.username,
                        self._oidc_global_readonly_superuser_group,
                    )
                    app.usermanager.register_global_readonly_superuser(user_obj.username)
                else:
                    logger.debug(
                        "OIDC superuser sync: revoking global readonly superuser from %s (not member of %s)",
                        user_obj.username,
                        self._oidc_global_readonly_superuser_group,
                    )
                    app.usermanager.deregister_global_readonly_superuser(user_obj.username)
        except Exception:
            logger.exception(
                "OIDC superuser sync: failed to sync superuser status for %s",
                user_obj.username,
            )

    def sync_user_groups(self, user_groups, user_obj, login_service):
        oidc_team_sync.sync_user_groups(user_groups, user_obj, self._federated_service)
