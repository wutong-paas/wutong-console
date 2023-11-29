from typing import Optional, List
from pydantic import BaseModel


class PutTagParam(BaseModel):
    tag_id: Optional[int] = None
    name: Optional[str] = None
    desc: Optional[str] = ""
    sn: Optional[int] = 0


class DeleteTagParam(BaseModel):
    tag_ids: Optional[str] = None


class AddTagParam(BaseModel):
    name: Optional[str] = None
    desc: Optional[str] = ""
    sn: Optional[int] = 0
