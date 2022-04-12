from typing import Optional

from pydantic import BaseModel


class CenterAppListQuery(BaseModel):
    """
    本地市场应用列表查询
    """
    scope: Optional[str] = None
    app_name: Optional[str] = None
    # tags: List[str] = []
    page: Optional[int] = 1
    page_size: Optional[int] = 10

    class Config:
        """
        example
        """
        schema_extra = {
            "example": {
                "scope": "all",
                "app_name": "test_app",
                "page": 1,
                "page_size": 10
            }
        }


class CenterAppCreate(BaseModel):
    """
    创建应用市场应用
    """
    ID: Optional[int] = 0
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    create_user: Optional[int] = 0
    create_team: Optional[str] = None
    pic: Optional[str] = None
    source: Optional[str] = None
    dev_status: Optional[str] = None
    scope: Optional[str] = None
    describe: Optional[str] = None
    is_ingerit: Optional[bool] = True
    enterprise_id: Optional[str] = None
    install_number: Optional[int] = 0
    is_official: Optional[bool] = True
    details: Optional[str] = None

    class Config:
        """
        样例数据
        """
        schema_extra = {
            "example": {
                "app_id": "app_id",
                "app_name": "test_ap_name",
                "create_user": 10086,
                "create_team": "talkweb",
                "pic": "pic",
                "source": "team",
                "dev_status": "dev_status",
                "scope": "all",
                "describe": "describe",
                "is_ingerit": True,
                "enterprise_id": "test_enterprise_id",
                "install_number": 10010,
                "is_official": True,
                "details": "details"
            }
        }
