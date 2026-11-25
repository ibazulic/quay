import json
from types import SimpleNamespace

import pytest
from mock import patch

from data import model
from data.users import (
    DatabaseUsers,
    FederatedUsers,
    OIDCLoginService,
    OIDCUsers,
    UserAuthentication,
)
from endpoints.api import api
from endpoints.api.organization import Organization
from endpoints.api.team import OrganizationTeamSyncing, TeamMemberList
from endpoints.api.test.shared import conduct_api_call
from endpoints.test.shared import client_with_identity
from test.fixtures import *
from test.test_ldap import mock_ldap

SYNCED_TEAM_PARAMS = {"orgname": "sellnsmall", "teamname": "synced"}
UNSYNCED_TEAM_PARAMS = {"orgname": "sellnsmall", "teamname": "owners"}


def _wrap(state):
    ua = UserAuthentication()
    ua.state = state
    return ua


def test_team_syncing(app):
    with mock_ldap() as ldap:
        with patch("endpoints.api.team.authentication", _wrap(ldap)):
            with client_with_identity("devtable", app) as cl:
                config = {
                    "group_dn": "cn=AwesomeFolk",
                }

                conduct_api_call(cl, OrganizationTeamSyncing, "POST", UNSYNCED_TEAM_PARAMS, config)

                # Ensure the team is now synced.
                sync_info = model.team.get_team_sync_information(
                    UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
                )
                assert sync_info is not None
                assert json.loads(sync_info.config) == config

                # Remove the syncing.
                conduct_api_call(cl, OrganizationTeamSyncing, "DELETE", UNSYNCED_TEAM_PARAMS, None)

                # Ensure the team is no longer synced.
                sync_info = model.team.get_team_sync_information(
                    UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
                )
                assert sync_info is None


def test_team_member_sync_info_unsynced_superuser(app):
    with mock_ldap() as ldap:
        with patch("endpoints.api.team.authentication", _wrap(ldap)):
            # Check for an unsynced team, with superuser.
            with client_with_identity("devtable", app) as cl:
                resp = conduct_api_call(cl, TeamMemberList, "GET", UNSYNCED_TEAM_PARAMS)
                assert "can_sync" in resp.json
                assert resp.json["can_sync"]["service"] == "ldap"
                assert "synced" not in resp.json


def test_team_member_sync_info_unsynced_nonsuperuser(app):
    with mock_ldap() as ldap:
        with patch("endpoints.api.team.authentication", _wrap(ldap)):
            # Check for an unsynced team, with non-superuser.
            with client_with_identity("randomuser", app) as cl:
                resp = conduct_api_call(cl, TeamMemberList, "GET", UNSYNCED_TEAM_PARAMS)
                assert "can_sync" not in resp.json
                assert "synced" not in resp.json


def test_team_member_sync_info_synced_superuser(app):
    with mock_ldap() as ldap:
        with patch("endpoints.api.team.authentication", _wrap(ldap)):
            # Check for a synced team, with superuser.
            with client_with_identity("devtable", app) as cl:
                resp = conduct_api_call(cl, TeamMemberList, "GET", SYNCED_TEAM_PARAMS)
                assert "can_sync" in resp.json
                assert resp.json["can_sync"]["service"] == "ldap"

                assert "synced" in resp.json
                assert "last_updated" in resp.json["synced"]
                assert "group_dn" in resp.json["synced"]["config"]


def test_team_member_sync_info_synced_nonsuperuser(app):
    with mock_ldap() as ldap:
        with patch("endpoints.api.team.authentication", _wrap(ldap)):
            # Check for a synced team, with non-superuser.
            with client_with_identity("randomuser", app) as cl:
                resp = conduct_api_call(cl, TeamMemberList, "GET", SYNCED_TEAM_PARAMS)
                assert "can_sync" not in resp.json

                assert "synced" in resp.json
                assert "last_updated" not in resp.json["synced"]
                assert "config" not in resp.json["synced"]


def test_organization_teams_sync_bool(app):
    with mock_ldap() as ldap:
        with patch("endpoints.api.organization.authentication", _wrap(ldap)):
            # Ensure synced teams are marked as such in the organization teams list.
            with client_with_identity("devtable", app) as cl:
                resp = conduct_api_call(cl, Organization, "GET", {"orgname": "sellnsmall"})

                assert not resp.json["teams"]["owners"]["is_synced"]

                assert resp.json["teams"]["synced"]["is_synced"]


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


def test_team_sync_with_db_backend_and_oidc(app):
    """
    Verifies that we can turn on team syncing when the backend is database and config
    contains the proper OIDC setup.
    """
    oidc = _oidc_service()
    db_users = DatabaseUsers()
    auth_object = _auth(db_users, "Database", [oidc])

    payload = {
        "group_name": "some-oidc-group",
    }

    with patch("endpoints.api.team.authentication", auth_object):
        with client_with_identity("devtable", app) as cl:
            conduct_api_call(cl, OrganizationTeamSyncing, "POST", UNSYNCED_TEAM_PARAMS, payload)

            # Ensure the team is now synced.
            sync_info = model.team.get_team_sync_information(
                UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
            )
            assert sync_info is not None
            assert sync_info.service.name == "oidc"
            assert json.loads(sync_info.config) == payload

            # Remove the syncing.
            conduct_api_call(cl, OrganizationTeamSyncing, "DELETE", UNSYNCED_TEAM_PARAMS, None)

            # Ensure the team is no longer synced.
            sync_info = model.team.get_team_sync_information(
                UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
            )
            assert sync_info is None


def test_team_sync_with_db_backend_removes_existing_users_from_team(app):
    """
    Verifies that turning on syncing removes all users from the current team.
    """
    oidc = _oidc_service()
    db_users = DatabaseUsers()
    auth_object = _auth(db_users, "Database", [oidc])

    payload = {
        "group_name": "some-oidc-group",
    }

    # add user to the team "owners" of the org
    user_obj = model.user.create_user_noverify("foobar", "foo@bar.com", False)
    team = model.team.get_organization_team(
        UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
    )
    model.team.add_user_to_team(user_obj, team)

    membership_count = len(model.team.list_team_users(team))
    # team must have some members
    assert membership_count >= 1

    # conduct call
    with patch("endpoints.api.team.authentication", auth_object):
        with client_with_identity("devtable", app) as cl:
            conduct_api_call(cl, OrganizationTeamSyncing, "POST", UNSYNCED_TEAM_PARAMS, payload)

            # Ensure the team is now synced.
            sync_info = model.team.get_team_sync_information(
                UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
            )
            assert sync_info is not None
            assert sync_info.service.name == "oidc"
            assert json.loads(sync_info.config) == payload

            # check if the user was deleted
            members = model.team.list_team_users(team)
            assert len(members) == 0


@pytest.mark.xfail(
    strict=True,
    reason="OIDCUsers.check_group_lookup_args accepts any config so an empty group syncs "
    "the team against nothing and wipes team membership information. This is pre-existing "
    "under {'AUTHENTICATION_TYPE': 'OIDC'}."
    "To be fixed in a follow-up PR.",
)
def test_team_sync_with_db_backend_and_no_payload_returns_400(app):
    """
    If the payload is not sent, verify that the API returns a 400 Bad Request.
    """
    oidc = _oidc_service()
    db_users = DatabaseUsers()
    auth_object = _auth(db_users, "Database", [oidc])

    # add user to the team "owners" of the org
    user_obj = model.user.create_user_noverify("foobar", "foo@bar.com", False)
    team = model.team.get_organization_team(
        UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
    )
    model.team.add_user_to_team(user_obj, team)

    membership_count = len(model.team.list_team_users(team))
    # team must have some members
    assert membership_count >= 1

    # conduct call
    with patch("endpoints.api.team.authentication", auth_object):
        with client_with_identity("devtable", app) as cl:
            conduct_api_call(
                cl, OrganizationTeamSyncing, "POST", UNSYNCED_TEAM_PARAMS, {}, expected_code=400
            )


def test_team_sync_with_db_backend_get_team_members(app):
    """
    Verifies that a successful GET on a team membership list includes can_sync key
    with the service equaling "oidc".
    """
    oidc = _oidc_service()
    db_users = DatabaseUsers()
    auth_object = _auth(db_users, "Database", [oidc])

    payload = {
        "group_name": "some-oidc-group",
    }

    # conduct call
    with patch("endpoints.api.team.authentication", auth_object):
        with client_with_identity("devtable", app) as cl:
            conduct_api_call(cl, OrganizationTeamSyncing, "POST", UNSYNCED_TEAM_PARAMS, payload)
            # Ensure the team is now synced.
            sync_info = model.team.get_team_sync_information(
                UNSYNCED_TEAM_PARAMS["orgname"], UNSYNCED_TEAM_PARAMS["teamname"]
            )
            assert sync_info is not None
            assert sync_info.service.name == "oidc"
            assert json.loads(sync_info.config) == payload

            # conduct team membership call list
            resp = conduct_api_call(cl, TeamMemberList, "GET", UNSYNCED_TEAM_PARAMS)
            assert resp is not None
            print(resp)
