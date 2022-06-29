from typing import Optional, List

from pydantic import BaseModel, Field


class MarketCreateParam(BaseModel):
    name: Optional[str] = ""
    url: Optional[str] = ""
    domain: Optional[str] = ""
    access_key: Optional[str] = ""
    access_secret: Optional[str] = ""
    type: Optional[str] = "wutong"
    scope: Optional[str] = "enterprise"


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
    store_id: Optional[str] = ""
    share_service_list: List[dict] = []
    share_plugin_list: List[dict] = []


class MarketAppModelParam(BaseModel):
    page: Optional[int] = 1
    page_size: Optional[int] = 100


class MarketAppQueryVO(BaseModel):
    del_flag: Optional[bool] = False
    queryAppVersionFlag: Optional[int] = 1
    # todo
    store_id: Optional[str] = "d50f8f8fb096a39bfb5721d5a3db3f1b"
    name: Optional[str] = ""


class MarketAppQueryParam(BaseModel):
    current: Optional[int] = 1
    size: Optional[int] = 20
    queryVO: Optional[MarketAppQueryVO] = MarketAppQueryVO()


class MarketAppPushParam(BaseModel):
    assembly_info: Optional[str] = ""
    id: Optional[str] = ""
    name: Optional[str] = ""
    version_number: Optional[str] = ""


class MarketAppInstallParam(BaseModel):
    market_app_id: Optional[str] = Field(description="市场应用ID", default="")
    market_app_name: Optional[str] = Field(description="市场应用名称", default="")
    market_app_version_id: Optional[str] = Field(description="市场应用版本ID(ID,非版本号)", default="")
    application_id: Optional[int] = Field(description="本地应用ID(目标应用)", default=0)
    is_deploy: Optional[bool] = Field(description="是否部署", default=False)
