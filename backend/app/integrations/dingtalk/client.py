from datetime import datetime, timezone
from typing import Callable, Protocol

import httpx

from app.core.config import DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET
from app.integrations.dingtalk.schemas import DingTalkApprovalInstance, DingTalkUser


class DingTalkClient(Protocol):
    def exchange_auth_code(self, auth_code: str) -> DingTalkUser: ...
    def list_approval_instances(self, process_code: str, start_at: datetime, end_at: datetime) -> list[DingTalkApprovalInstance]: ...


class DingTalkConfigurationError(RuntimeError):
    pass


class DingTalkAuthenticationError(RuntimeError):
    pass


class OfficialDingTalkClient:
    """Read-only adapter for the verified approval-instance endpoints."""

    MAX_RESULTS = 20
    MAX_PAGES = 100
    READ_RETRIES = 2

    def __init__(self, client_factory: Callable[[], httpx.Client] | None = None):
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=20.0))
        self.last_sync_diagnostics = {"list_page_count": 0, "instance_id_count": 0, "detail_failed_count": 0}

    def exchange_auth_code(self, auth_code: str) -> DingTalkUser:
        if not auth_code:
            raise DingTalkAuthenticationError("DingTalk authorization code is missing")
        with self._client_factory() as client:
            access_token = self._app_access_token(client)
            try:
                response = client.post("https://oapi.dingtalk.com/topapi/v2/user/getuserinfo", params={"access_token": access_token}, json={"code": auth_code})
            except httpx.HTTPError as error:
                raise DingTalkAuthenticationError("DingTalk user identity request failed") from error
            body = response.json() if not response.is_error else {}
            user = body.get("result", {}) if isinstance(body, dict) else {}
            user_id = user.get("userid") if isinstance(user, dict) else None
            if response.is_error or body.get("errcode", 0) != 0 or not user_id:
                raise DingTalkAuthenticationError("DingTalk authorization code was rejected")
            return DingTalkUser(user_id=str(user_id), name=str(user.get("name") or "DingTalk user"))

    def list_approval_instances(self, process_code: str, start_at: datetime, end_at: datetime) -> list[DingTalkApprovalInstance]:
        with self._client_factory() as client:
            access_token = self._app_access_token(client)
            headers = {"x-acs-dingtalk-access-token": access_token}
            instance_ids = self._list_instance_ids(client, headers, process_code, start_at, end_at)
            instances = []
            for instance_id in instance_ids:
                response = self._read_with_retry(client, "get", "https://api.dingtalk.com/v1.0/workflow/processInstances", headers=headers, params={"processInstanceId": instance_id})
                if response is None:
                    self.last_sync_diagnostics["detail_failed_count"] += 1
                    continue
                try:
                    instances.append(self._detail_instance(self._result(response), instance_id, process_code))
                except DingTalkConfigurationError:
                    self.last_sync_diagnostics["detail_failed_count"] += 1
            return instances

    def _list_instance_ids(self, client: httpx.Client, headers: dict[str, str], process_code: str, start_at: datetime, end_at: datetime) -> list[str]:
        self.last_sync_diagnostics = {"list_page_count": 0, "instance_id_count": 0, "detail_failed_count": 0}
        instance_ids: list[str] = []
        seen_ids: set[str] = set()
        seen_tokens: set[str] = set()
        next_token: str | int | None = 0
        while True:
            token_key = str(next_token)
            if token_key in seen_tokens or len(seen_tokens) >= self.MAX_PAGES:
                raise DingTalkConfigurationError("DingTalk approval-instance pagination did not terminate")
            seen_tokens.add(token_key)
            response = self._read_with_retry(
                client,
                "post",
                "https://api.dingtalk.com/v1.0/workflow/processes/instanceIds/query",
                headers=headers,
                json={"processCode": process_code, "startTime": int(start_at.timestamp() * 1000), "endTime": int(end_at.timestamp() * 1000), "nextToken": next_token, "maxResults": self.MAX_RESULTS, "statuses": ["RUNNING", "COMPLETED", "TERMINATED"]},
            )
            if response is None:
                raise DingTalkConfigurationError("DingTalk approval-instance list request failed")
            self.last_sync_diagnostics["list_page_count"] += 1
            for instance_id in self._result(response).get("list", []):
                if isinstance(instance_id, str) and instance_id and instance_id not in seen_ids:
                    seen_ids.add(instance_id)
                    instance_ids.append(instance_id)
            next_token = self._result(response).get("nextToken")
            if next_token in (None, "", 0, "0"):
                break
        self.last_sync_diagnostics["instance_id_count"] = len(instance_ids)
        return instance_ids

    @classmethod
    def _read_with_retry(cls, client: httpx.Client, method: str, url: str, **kwargs) -> httpx.Response | None:
        for _ in range(cls.READ_RETRIES):
            try:
                response = getattr(client, method)(url, **kwargs)
            except httpx.HTTPError:
                continue
            if not response.is_error:
                return response
        return None

    @staticmethod
    def _result(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError as error:
            raise DingTalkConfigurationError("DingTalk response was invalid") from error
        result = body.get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            raise DingTalkConfigurationError("DingTalk response was invalid")
        return result

    @classmethod
    def _detail_instance(cls, result: dict, instance_id: str, requested_process_code: str) -> DingTalkApprovalInstance:
        components = result.get("formComponentValues", [])
        components = components if isinstance(components, list) else []
        form_values = {item["name"]: item.get("value") for item in components if isinstance(item, dict) and isinstance(item.get("name"), str)}
        finished_at = cls._parse_time(result.get("finishTime"))
        return DingTalkApprovalInstance(process_instance_id=instance_id, process_code=str(result.get("processCode") or requested_process_code), status=str(result.get("status", "")), result=str(result.get("result", "")), started_at=cls._parse_time(result.get("startTime")), finished_at=finished_at, approved_at=finished_at, approval_no=str(result.get("businessId")) if result.get("businessId") else None, form_values=form_values, form_components=components, source_payload={"source": "DINGTALK"})

    @staticmethod
    def _parse_time(value: object) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(int(str(value)) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.tzinfo else None

    @staticmethod
    def _app_access_token(client: httpx.Client) -> str:
        if not DINGTALK_CLIENT_ID or not DINGTALK_CLIENT_SECRET:
            raise DingTalkConfigurationError("DingTalk application credentials are not configured")
        try:
            response = client.post("https://api.dingtalk.com/v1.0/oauth2/accessToken", json={"appKey": DINGTALK_CLIENT_ID, "appSecret": DINGTALK_CLIENT_SECRET})
        except httpx.HTTPError as error:
            raise DingTalkConfigurationError("DingTalk access token request failed") from error
        token = response.json().get("accessToken") if not response.is_error else None
        if not token:
            raise DingTalkConfigurationError("DingTalk access token request failed")
        return token


def get_dingtalk_client() -> DingTalkClient:
    return OfficialDingTalkClient()
