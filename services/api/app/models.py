from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class BrandDoc(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    source: str = "manual"
    content: str
    tags: str = ""
    embedding_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str
    status: str = "PLANNED"
    plan_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RunLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    ts: datetime = Field(default_factory=datetime.utcnow)
    level: str = "INFO"
    message: str
    data_json: str = "{}"
