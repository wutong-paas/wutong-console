from typing import Optional

from pydantic import BaseModel


class CloseTeamAppParam(BaseModel):
    region_name: Optional[str] = None


class CreateTeamParam(BaseModel):
    team_name: Optional[str] = None
    useable_regions: Optional[str] = None
    namespace: Optional[str] = None


class CreateTeamUserParam(BaseModel):
    user_ids: Optional[str] = None
    role_id: Optional[str] = None


class DeleteTeamUserParam(BaseModel):
    user_ids: Optional[list] = None
