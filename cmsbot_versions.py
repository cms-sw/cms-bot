# Use cms-bot process_pr version v2 for the followinf github users
from datetime import datetime, timezone

# User: [(date_after, bot_version),[(date_after, bot_version)]
CMSBOT_V2 = {
    "smuzaffar": [(datetime(2026, 10, 6, 0, 0, 0, tzinfo=timezone.utc), 2)],
}


def get_cmsbot_version(payload):
    version = "1"
    obj = None
    if "issue" in payload:
        obj = payload["issue"]
    elif "pull_request" in payload:
        obj = payload["pull_request"]
    else:
        return version
    user = obj.get("user", {}).get("login")
    if not user:
        return version
    user_data = CMSBOT_V2.get(user, None)
    if user_data is None:
        return version
    created_at = obj.get("created_at")
    if not created_at:
        return version
    try:
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return version
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    for data in user_data:
        if created_at >= data[0]:
            return str(data[1])
    return version
