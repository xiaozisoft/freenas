from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str


class BoxRcloneRemote(BaseRcloneRemote):
    name = "BOX"
    title = "Box"

    rclone_type = "box"

    credentials_schema = [
        Str("client_id", verbose="OAuth Client ID", default=""),
        Str("client_secret", verbose="OAuth Client Secret", default=""),
        Str("token", verbose="Access Token", required=True),
    ]
    credentials_oauth = True
