from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr("app.main.GENERATED_DIR", tmp_path / "generated")
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session_factory = sessionmaker(
        bind=test_engine, autoflush=False, expire_on_commit=False
    )
    app = create_app(test_engine, test_session_factory)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
