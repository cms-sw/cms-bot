# Use cms-bot process_pr version v2 for the followinf github users
from datetime import datetime, timezone

CMSBOT_V2 = {
    "smuzaffar": datetime(2025, 10, 6, 0, 0, 0, tzinfo=timezone.utc),
}


def use_cmsbot_v2(payload):
    obj = None
    if "issue" in payload:
        obj = payload["issue"]
    elif "pull_request" in payload:
        obj = payload["pull_request"]
    else:
        return False
    user = obj.get("user", {}).get("login")
    if not user:
        return False
    created_after = CMSBOT_V2.get(user, None)
    if created_after is None:
        return False
    created_at = obj.get("created_at")
    if not created_at:
        return False
    try:
        created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at >= created_after
