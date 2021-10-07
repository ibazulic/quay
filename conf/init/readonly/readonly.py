from app import app
import argparse
import json
from authlib.jose import JsonWebKey
from cryptography.hazmat.primitives import serialization
import os
import os.path

from data.database import db_for_update, ServiceKey, ServiceKeyApproval, UseThenDisconnect
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
    print(("Writing public key to %s.jwk" % path))
    with open("%s.jwk" % path, mode="w") as f:
        f.truncate(0)
        f.write(jwk.as_json())

    print(("Writing key ID to %s.kid" % path))
    with open("%s.kid" % path, mode="w") as f:
        f.truncate(0)
        f.write(jwk.as_dict()["kid"])

    print(("Writing private key to %s.pem" % path))
    with open("%s.pem" % path, mode="wb") as f:
        f.truncate(0)
        f.write(
            jwk.get_private_key().private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )


def _gc_expired(name):
    ServiceKey.delete().where(ServiceKey.name == name).execute()


def create_service_key(name, kid, service, jwk, metadata, expiration_date, rotation_duration=None):
    _gc_expired(name)

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
    approval = ServiceKeyApproval.create(
        approver=approver, approval_type=approval_type, notes=notes
    )
    key.approval = approval
    key.save()


def main():
    path = "/conf/stack/quay-readonly"
    jwk = generate_key()
    kid = jwk.as_dict()["kid"]
    write_out(jwk, path)
    name = "quay-readonly"
    service = "quay"
    metadata = "{}"
    with UseThenDisconnect(app.config):
        create_service_key(
            name,
            kid,
            service,
            jwk.as_dict(),
            metadata,
            expiration_date=None,
            rotation_duration=None,
        )
        approve_service_key(kid, approval_type="Super User API", notes="Quay Read Only setup")


main()
