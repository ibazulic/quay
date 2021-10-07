import argparse
import json
from authlib.jose import JsonWebKey
from cryptography.hazmat.primitives import serialization
import os
import os.path

from data.database import db_for_update, User, ServiceKey, ServiceKeyApproval
from data.model import (
    db_transaction,
    config,
)

def generate_key(kid=None):
    """
    'kid' will default to the jwk thumbprint if not set explicitly.

    Reference: https://tools.ietf.org/html/rfc7638
    """
    options = {}
    if kid:
        options["kid"] = kid

    jwk = JsonWebKey.generate_key("RSA", 2048, is_private=True, options=options)

    return jwk

def write_out(jwk, path):
    print(("Writing public key to %s.jwk" % filename))
    with open("%s.jwk" % filename, mode="w") as f:
        f.truncate(0)
        f.write(jwk.as_json())

    print(("Writing key ID to %s.kid" % filename))
    with open("%s.kid" % filename, mode="w") as f:
        f.truncate(0)
        f.write(jwk.as_dict()["kid"])

    print(("Writing private key to %s.pem" % filename))
    with open("%s.pem" % filename, mode="wb") as f:
        f.truncate(0)
        f.write(
            jwk.get_private_key().private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

def _gc_expired(service):
    ServiceKey.delete().where(
        _stale_expired_keys_service_clause(service) | _stale_unapproved_keys_clause(service)
    ).execute()

def create_service_key(name, kid, service, jwk, metadata, expiration_date, rotation_duration=None):

    _gc_expired(service)

    key = ServiceKey.create(
        name=name,
        kid=kid,
        service=service,
        jwk=jwk,
        metadata=metadata,
        expiration_date=expiration_date,
        rotation_duration=rotation_duration,
    )

def approve_service_key(kid, approval_type, approver=None, notes=""):
    key = db_for_update(ServiceKey.select().where(ServiceKey.kid == kid)).get()
    approval = ServiceKeyApproval.create(approver=approver, approval_type=approval_type, notes=notes)
    key.approval = approval
    key.save()

def main():
    path = os.path.join(os.genenv("QUAYCONFIG"), "quay-readonly")
    jwk = generate_key()
    kid = jwk.as_dict()["kid"]
    write_out(jwk)
    create_service_key(
        name="quay-readonly",
        kid=kid,
        service=quay,
        jwk.as_dict(),
        rotation_duration=rotation_duration,
    )
    approve_service_key(kid, approval_type="Super User API", notes="Quay Read Only setup")

main()
