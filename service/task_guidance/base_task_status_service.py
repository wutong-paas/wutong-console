import abc

from loguru import logger

from repository.component.group_service_repo import service_repo
from repository.component.service_config_repo import dep_relation_repo, domain_repo
from repository.component.service_share_repo import component_share_repo
from repository.plugin.service_plugin_repo import app_plugin_relation_repo
from repository.application.service_group_repo import svc_grop_repo


class BaseTaskStatusStrategy(object, metaclass=abc.ABCMeta):
    """Abstract class: confirm the status of the base task"""

    @abc.abstractmethod
    def confirm_status(self, session, tenants):
        raise NotImplementedError("Doesn't provide a reprØesentation for BaseTaskStatus.")


class DefaultStrategy(BaseTaskStatusStrategy):
    """
    The duty of DefaultStrategy is to avoid the lack of strategy for the instance
    of BaseTaskStatusContext.
    When the BaseTaskStatusContext is initialized, if an unsupported task is entered,
    the above error will be triggered.
    """

    def confirm_status(self, session, tenants):
        return False


class AppCreationStrategy(BaseTaskStatusStrategy):
    """Task: app creation"""

    def confirm_status(self, session, eid):
        return svc_grop_repo.check_non_default_group_by_eid(session, eid)


class SourceCodeServiceCreationStrategy(BaseTaskStatusStrategy):
    """Task: create a service based on source code"""

    def confirm_status(self, session, eid):
        return service_repo.check_sourcecode_svc_by_eid(session, eid)


class InstallMysqlFromMarketStrategy(BaseTaskStatusStrategy):
    """Task: install the database based on the application market"""

    def confirm_status(self, session, eid):
        return service_repo.check_db_from_market_by_eid(session, eid)


class ServiceConnectDBStrategy(BaseTaskStatusStrategy):
    """Task: connect database with service"""

    def confirm_status(self, session, eid):
        return dep_relation_repo.check_db_dep_by_eid(session, eid)


class ShareAppStrategy(BaseTaskStatusStrategy):
    """Task: share application to market"""

    def confirm_status(self, session, eid):
        return component_share_repo.check_app_by_eid(session, eid)


class CustomGatewayRuleStrategy(BaseTaskStatusStrategy):
    """Task: customize application access rules"""

    def confirm_status(self, session, eid):
        return domain_repo.check_custom_rule(session, eid)


class InstallPluginStrategy(BaseTaskStatusStrategy):
    """Task: install the performance analysis plugin"""

    def confirm_status(self, session, eid):
        return app_plugin_relation_repo.check_plugins_by_eid(session, eid)


class ImageServiceCreateStrategy(BaseTaskStatusStrategy):
    """Task: install the performance analysis plugin"""

    def confirm_status(self, session, eid):
        return service_repo.check_image_svc_by_eid(session, eid)


class BaseTaskStatusContext(object):
    def __init__(self, eid, task):
        self.eid = eid
        if task == 'app_create':
            self.strategy = AppCreationStrategy()
        elif task == 'source_code_service_create':
            self.strategy = SourceCodeServiceCreationStrategy()
        elif task == 'install_mysql_from_market':
            self.strategy = InstallMysqlFromMarketStrategy()
        elif task == 'service_connect_db':
            self.strategy = ServiceConnectDBStrategy()
        elif task == 'share_app':
            self.strategy = ShareAppStrategy()
        elif task == 'custom_gw_rule':
            self.strategy = CustomGatewayRuleStrategy()
        elif task == 'install_plugin':
            self.strategy = InstallPluginStrategy()
        elif task == "image_service_create":
            self.strategy = ImageServiceCreateStrategy()
        else:
            logger.warning("Task: {task}; unsupported task".format(task=task))
            self.strategy = DefaultStrategy()

    def confirm_status(self, session):
        return self.strategy.confirm_status(session, self.eid)
