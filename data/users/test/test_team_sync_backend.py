from types import SimpleNamespace

import pytest
from mock import patch

import features
from data.users import (
    DatabaseUsers,
    FederatedUsers,
    OIDCLoginService,
    OIDCUsers,
    UserAuthentication,
)
from test.fixtures import *


def _oidc_service(**overrides):
    """
    Instantiates a small OIDC service.
    """
    config = {
        "CLIENT_ID": "quay",
        "CLIENT_SECRET": "supersecret",
        "OIDC_SERVER": "http://fakeoidc",
        "SERVICE_NAME": "Test Service",
        "PREFERRED_GROUP_CLAIM_NAME": "groups",
    }

    config.update(overrides)
    return OIDCLoginService({"TEST_LOGIN_CONFIG": config}, "TEST_LOGIN_CONFIG")


def _auth(state, auth_type, services):
    ua = UserAuthentication()
    ua.state = state
    ua.app = SimpleNamespace(config={"AUTHENTICATION_TYPE": auth_type})
    ua.oauth_login = SimpleNamespace(services=services)
    return ua


@pytest.mark.parametrize(
    "feature_on, auth_type, services",
    [
        pytest.param(False, "Database", [_oidc_service()], id="feature-off"),
        pytest.param(
            True, "Database", [_oidc_service(PREFERRED_GROUP_CLAIM_NAME=None)], id="no-claim-name"
        ),
        pytest.param(True, "Database", [], id="no-oidc-service"),
        # for this test state is irrelevant
        pytest.param(True, "AppToken", [_oidc_service()], id="apptoken-auth"),
    ],
)
def test_team_sync_backend_unavailable(feature_on, auth_type, services):
    """
    Verifies the cases when team sync is not available.
    """
    with patch("features.TEAM_SYNCING", features.FeatureNameValue("TEAM_SYNCING", feature_on)):
        auth_object = _auth(DatabaseUsers(), auth_type, services)
        assert auth_object.team_sync_service is None
        assert auth_object.team_sync_backend is None


def test_team_sync_backend_returns_oidc_for_database_auth():
    """
    Verifies that the team sync service returns "oidc" if syncing is enabled
    and OIDC configuration is provided and auth type is database.
    """
    oidc = _oidc_service()

    db_users = DatabaseUsers()

    with patch("features.TEAM_SYNCING", features.FeatureNameValue("TEAM_SYNCING", True)):
        # construct the auth object
        auth_object = _auth(db_users, "Database", [oidc])
        assert auth_object.team_sync_service == "oidc"
        assert isinstance(auth_object.team_sync_backend, OIDCUsers)


def test_team_sync_backend_returns_ldap_for_ldap_auth():
    """
    Verifies that the team sync service returns "ldap" if syncing is enabled, OIDC
    configuration is provided and the auth type is set to LDAP.
    """
    oidc = _oidc_service()

    ldap_users = FederatedUsers("ldap", False)

    with patch("features.TEAM_SYNCING", features.FeatureNameValue("TEAM_SYNCING", True)):
        auth_object = _auth(ldap_users, "LDAP", [oidc])
        assert auth_object.team_sync_service == "ldap"
        assert auth_object.team_sync_backend is ldap_users
