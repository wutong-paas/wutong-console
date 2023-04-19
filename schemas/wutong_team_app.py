from typing import Optional

from pydantic import BaseModel


class TeamAppCreateRequest(BaseModel):
    """
    创建环境应用
    """
    app_alias: Optional[str] = None
    team_alias: Optional[str] = None
    project_alias: Optional[str] = None
    note: Optional[str] = None
    logo: Optional[str] = None
    app_store_name: Optional[str] = None
    app_store_url: Optional[str] = None
    app_template_name: Optional[str] = None
    version: Optional[str] = None
    region_name: Optional[str] = None
    app_code: Optional[str] = None
    k8s_app: Optional[str] = None
    project_id: Optional[str] = None


class DevOpsTeamAppCreateParam(BaseModel):
    """
    DevOps创建团队应用
    """
    application_name: Optional[str] = None
    note: Optional[str] = None
    logo: Optional[str] = None
    region_code: Optional[str] = None
    team_code: Optional[str] = None
