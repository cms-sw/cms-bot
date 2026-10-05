# Use cms-bot process_pr version v2 for the followinf github users
from datetime import datetime, timezone

CMSBOT_V2 = {
    "smuzaffar": {
        "repo": ".+",
        "created_after": datetime(2026, 10, 5, 15, 35, 0, tzinfo=timezone.utc),
    }
}
