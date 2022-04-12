from typing import Optional

from pydantic import BaseModel


class TeamAppCreateRequest(BaseModel):
    """
    创建团队应用
    """
    app_name: Optional[str] = None
    note: Optional[str] = None
    logo: Optional[str] = None
    app_store_name: Optional[str] = None
    app_store_url: Optional[str] = None
    app_template_name: Optional[str] = None
    version: Optional[str] = None
    region_name: Optional[str] = None
    k8s_app: Optional[str] = None

    class Config:
        """
        样例数据
        """
        schema_extra = {
            "example": {
                "app_name": "app_name",
                "note": "note",
                "logo": "logo",
                "app_store_name": "app_store_name",
                "app_store_url": "app_store_url",
                "app_template_name": "app_template_name",
                "version": "version",
                "region_name": "region_name"
            }
        }


class DevOpsTeamAppCreateParam(BaseModel):
    """
    DevOps创建团队应用
    """
    application_name: Optional[str] = None
    note: Optional[str] = None
    logo: Optional[str] = None
    region_code: Optional[str] = None
    team_code: Optional[str] = None
