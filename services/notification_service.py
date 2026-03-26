from __future__ import annotations

from datetime import UTC, datetime

from config import get_settings

try:
    from slack_sdk.webhook import WebhookClient
except Exception:  # pragma: no cover
    WebhookClient = None


class NotificationService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.backend_events: list[dict[str, object]] = []

    def send(self, feature_name: str, score: float, platforms: list[str], zip_path: str) -> dict[str, object]:
        if not self.settings.slack_webhook_url:
            return {"ok": False, "message": "SLACK_WEBHOOK_URL not configured"}
        if WebhookClient is None:
            return {"ok": False, "message": "slack_sdk is not installed in the current environment"}
        try:
            response = WebhookClient(self.settings.slack_webhook_url).send(
                text=f"{feature_name} scored {score}/100 for {', '.join(platforms)}. Package: {zip_path}"
            )
            return {"ok": response.status_code == 200, "status_code": response.status_code}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}

    def notify_template_created(self, brand_name: str, mission: str, used_web_context: bool) -> dict[str, object]:
        event = {
            "type": "template_created",
            "brand_name": brand_name,
            "mission": mission,
            "used_web_context": used_web_context,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.backend_events.append(event)
        self.backend_events = self.backend_events[-20:]
        print(
            "[template-created] "
            f"brand={brand_name} "
            f"used_web_context={used_web_context} "
            f"mission={mission or 'n/a'}"
        )
        return event

    def list_backend_events(self) -> list[dict[str, object]]:
        return list(reversed(self.backend_events))
