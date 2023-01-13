from fastapi import APIRouter

from apis.external import wutong_devops_controller, wutong_hunan_expressway
from apis.manage.application import application_controller, wutong_topological_controller, wutong_temas_controller, \
    domain_controller, app_backup_controller, app_upgrade_controller
from apis.manage.common import common_controller
from apis.manage.components import operation_controller, batch_operation_controller, third_party_controller
from apis.manage.components import wutong_components_controller
from apis.manage.components import wutong_monitor_controller, wutong_log_controller, wutong_version_controller, \
    wutong_xparules_controller, wutong_env_controller, wutong_mnt_controller, wutong_volumes_controller, \
    wutong_dependency_controller, wutong_ports_controller, wutong_domain_controller, wutong_plugin_controller, \
    wutong_webhooks_controller, wutong_probe_controller, wutong_label_controller, wutong_buildsource_controller, \
    wutong_deploy_controller
from apis.manage.enterprise import wutong_enterprise_user_controller, wutong_enterprise_base_controller, \
    wutong_enterprise_controller, enterprise_base_controller
from apis.manage.market import local_market_controller, market_plugin_controller, market_share_controller, \
    helm_market_controller, wutong_market_controller
from apis.manage.obs import wutong_obs_controller
from apis.manage.proxy import wutong_proxy_controller
from apis.manage.team import wutong_team_overview_controller, wutong_team_roles_controller, \
    wutong_team_plugins_controller, wutong_team_users_controller, wutong_team_domain_controller, \
    wutong_team_region_controller, wutong_team_apps_controller, wutong_team_groupapp_controller
from apis.manage.teams import team_manage_controller
from apis.manage.user import access_token_controller, user_config_controller, user_manage_controller, \
    user_oauth_controller

api_router = APIRouter()

# router注册

api_router.include_router(wutong_devops_controller.router, prefix="", tags=["devops"])

api_router.include_router(wutong_hunan_expressway.router, prefix="", tags=["湖南高速大屏"])

# 公共接口部分
api_router.include_router(common_controller.router, tags=["公共部分接口"])

# 用户
api_router.include_router(access_token_controller.router, tags=["访问令牌操作接口"])
api_router.include_router(user_config_controller.router, tags=["用户配置接口"])
api_router.include_router(user_manage_controller.router, tags=["用户管理操作接口"])

# 企业
# todo 移除
api_router.include_router(wutong_enterprise_base_controller.router, tags=["企业基础接口"])
api_router.include_router(enterprise_base_controller.router, tags=["企业基础接口"])
api_router.include_router(wutong_enterprise_controller.router, tags=["企业信息接口"])
api_router.include_router(wutong_enterprise_user_controller.router, tags=["企业信息接口-用户"])

# 团队
api_router.include_router(team_manage_controller.router, tags=["团队管理操作接口"])

# 应用
api_router.include_router(local_market_controller.router, tags=["本地商店接口"])
api_router.include_router(helm_market_controller.router, tags=["Helm商店接口"])
api_router.include_router(market_plugin_controller.router, tags=["商店插件接口"])
api_router.include_router(market_share_controller.router, tags=["商店应用分享接口"])
api_router.include_router(app_backup_controller.router, tags=["应用备份接口"])
api_router.include_router(application_controller.router, tags=["团队应用接口"])
api_router.include_router(wutong_temas_controller.router, tags=["应用接口"])
api_router.include_router(wutong_topological_controller.router, tags=["应用拓扑图接口"])
api_router.include_router(domain_controller.router, tags=["应用网关"])
api_router.include_router(app_upgrade_controller.router, tags=["应用升级"])

# 梧桐应用市场
api_router.include_router(wutong_market_controller.router, tags=["梧桐应用市场"])

# 组件
api_router.include_router(operation_controller.router, tags=["组件操作接口"])
api_router.include_router(batch_operation_controller.router, tags=["组件批量操作接口"])
api_router.include_router(third_party_controller.router, tags=["第三方组件操作接口"])
# todo
api_router.include_router(wutong_components_controller.router, tags=["组件接口"])

api_router.include_router(user_oauth_controller.router, tags=["oauth"])

# # test
# api_router.include_router(test.router, tags=["测试"])

#
api_router.include_router(wutong_version_controller.router, tags=["version"])
api_router.include_router(wutong_monitor_controller.router, tags=["monitor"])
api_router.include_router(wutong_log_controller.router, tags=["log"])
api_router.include_router(wutong_xparules_controller.router, tags=["伸缩"])
api_router.include_router(wutong_env_controller.router, tags=["env"])
api_router.include_router(wutong_mnt_controller.router, tags=["mnt"])
api_router.include_router(wutong_volumes_controller.router, tags=["volumes"])
api_router.include_router(wutong_dependency_controller.router, tags=["dependency"])
api_router.include_router(wutong_ports_controller.router, tags=["ports"])
api_router.include_router(wutong_domain_controller.router, tags=["domain"])
api_router.include_router(wutong_plugin_controller.router, tags=["插件"])
api_router.include_router(wutong_webhooks_controller.router, tags=["webhooks"])
api_router.include_router(wutong_probe_controller.router, tags=["probe"])
api_router.include_router(wutong_label_controller.router, tags=["labels"])
api_router.include_router(wutong_buildsource_controller.router, tags=["buildsource"])
api_router.include_router(wutong_deploy_controller.router, tags=["deploy"])

# team
api_router.include_router(wutong_team_plugins_controller.router, tags=["plugins"])
api_router.include_router(wutong_team_roles_controller.router, tags=["roles"])
api_router.include_router(wutong_team_overview_controller.router, tags=["overview"])
api_router.include_router(wutong_team_users_controller.router, tags=["users"])
api_router.include_router(wutong_team_domain_controller.router, tags=["domain"])
api_router.include_router(wutong_team_region_controller.router, tags=["region"])
api_router.include_router(wutong_team_apps_controller.router, tags=["apps"])
api_router.include_router(wutong_team_groupapp_controller.router, tags=["groupapp"])

# proxy
api_router.include_router(wutong_proxy_controller.router, tags=["proxy"])


# obs
api_router.include_router(wutong_obs_controller.router, tags=["obs"])
