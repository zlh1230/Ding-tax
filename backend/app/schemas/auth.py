from pydantic import BaseModel


class DingTalkAuthCode(BaseModel):
    auth_code: str


class CurrentOperator(BaseModel):
    user_id: str
    name: str
