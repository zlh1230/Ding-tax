import os

os.environ["DATABASE_URL"] = "sqlite:///./test_invoice_jobs.db"
os.environ["APP_ENV"] = "development"
os.environ["DINGTALK_PROCESS_CODE"] = "invoice-process"
os.environ["DINGTALK_ALLOWED_USER_IDS"] = "allowed-user"

import pytest

from app.core.database import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
