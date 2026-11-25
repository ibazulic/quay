import json
import logging

from data.model import InvalidTeamException, UserAlreadyInTeam, team

logger = logging.getLogger(__name__)


def sync_oidc_groups(user_groups, user_obj, federated_service):
    """
    Adds users to synced teams based on the OIDC group membership.
    """
    if not user_groups:
        if user_groups is None:
            logger.debug(
                "External OIDC Group Sync: No group claim found for user: %s - check PREFERRED_GROUP_CLAIM_NAME",
                user_obj.username,
            )
        else:
            logger.debug(
                "External OIDC Group Sync: Found no oidc groups for user: %s", user_obj.username
            )
        return

    # fetch all TeamSync rows for the oidc_group synced with the login service
    synced_teams = team.get_oidc_teams_from_groupname(user_groups, federated_service)
    if len(synced_teams) == 0:
        logger.debug("External OIDC Group Sync: No teams with OIDC syncing groups found")
        return

    logger.debug(
        "External OIDC Group Sync: Syncing user %s with %s groups: %s",
        user_obj.username,
        len(synced_teams),
        [t.team.name for t in synced_teams],
    )

    # fetch team name and organization name for the Teamsync row
    for team_synced in synced_teams:
        team_name = team_synced.team.name
        org_name = team_synced.team.organization.username
        if not team_name or not org_name:
            continue

        # add user to team
        try:
            team.add_user_to_team(user_obj, team_synced.team)
        except InvalidTeamException as err:
            logger.exception(
                "External OIDC Group Sync: Exception occurred when adding user %s to quay team %s: %s",
                user_obj.username,
                team_synced.team,
                err,
            )
        except UserAlreadyInTeam:
            # Ignore
            pass
    return


def resync_quay_teams(user_groups, user_obj, federated_service):
    """
    Fetches Quay teams the user is a member of. If a user is not a member of a
    specific group(s) based on the group membership attribute in user info, then
    the user is removed from said synced group(s).
    """
    # fetch user's quay teams that have team sync enabled
    existing_user_teams = team.get_federated_user_teams(user_obj, federated_service)
    logger.debug(
        "External OIDC Group Sync: For user %s re-syncing %d quay teams",
        user_obj.username,
        len(existing_user_teams),
    )
    user_groups = user_groups or []
    for user_team in existing_user_teams:
        try:
            sync_group_info = json.loads(user_team.teamsync.config)
            # remove user's membership from teams that were not returned from users OIDC groups
            if (
                sync_group_info.get("group_name", None)
                and sync_group_info["group_name"] not in user_groups
            ):
                org_name = user_team.teamsync.team.organization.username
                team.remove_user_from_team(org_name, user_team.name, user_obj.username, None)
                logger.debug(
                    "External OIDC Group Sync: Successfully removed user: %s from team: %s in organization: %s",
                    user_obj.username,
                    user_team.name,
                    org_name,
                )
        except Exception as err:
            logger.exception(
                "External OIDC Group Sync: Exception occurred for user %s when removing membership from quay team: %s as %s",
                user_obj.username,
                user_team.name,
                err,
            )
    return


def sync_user_groups(user_groups, user_obj, federated_service):
    """
    Syncs user to their respective groups based on group membership and provided
    federated service.
    """
    if not user_obj:
        return

    sync_oidc_groups(user_groups, user_obj, federated_service)
    resync_quay_teams(user_groups, user_obj, federated_service)
