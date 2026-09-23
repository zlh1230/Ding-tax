from datetime import datetime
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DingTalkUser:
    user_id: str
    name: str


@dataclass(frozen=True)
class DingTalkApprovalInstance:
    """Adapter-normalized approval data; raw response mapping awaits verified live payload."""

    process_instance_id: str
    process_code: str
    result: str
    approved_at: datetime | None
    approval_no: str | None
    form_values: dict[str, object]
    source_payload: dict
    form_components: list[dict] = field(default_factory=list)
    status: str = "COMPLETED"
    started_at: datetime | None = None
    finished_at: datetime | None = None
