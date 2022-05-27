from typing import Optional, List, Dict

from pydantic import BaseModel


class MarketAppCreateParam(BaseModel):
    group_id: Optional[int] = -1
    app_id: Optional[str] = None
    app_version: Optional[str] = None
    is_deploy: Optional[bool] = True
    install_from_cloud: Optional[bool] = False
    market_name: Optional[str] = None


class DevopsMarketAppCreateParam(BaseModel):
    application_id: Optional[int] = -1
    model_app_id: Optional[str] = None
    model_app_version: Optional[str] = None
    team_code: Optional[str] = None


class MarketAppTemplateUpdateParam(BaseModel):
    name: Optional[str] = None
    describe: Optional[str] = "This is a default description."
    pic: Optional[str] = None
    details: Optional[str] = None
    dev_status: Optional[str] = None
    tag_ids: Optional[list] = None
    scope: Optional[str] = "enterprise"
    create_team: Optional[str] = None


class MarketShareUpdateParam(BaseModel):
    status: Optional[int] = None


class AppVersionInfo(BaseModel):
    app_model_id: Optional[str] = None
    version: Optional[str] = None
    scope_target: Optional[str] = None
    version_alias: Optional[str] = None
    template_type: Optional[str] = None
    describe: Optional[str] = None


class MarketAppShareInfoCreateParam(BaseModel):
    app_version_info: Optional[AppVersionInfo] = None
    share_service_list: List[dict] = []
    share_plugin_list: List[dict] = []


class MarketAppModelParam(BaseModel):
    page: Optional[int] = 1
    page_size: Optional[int] = 100
