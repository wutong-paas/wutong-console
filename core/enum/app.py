# -*- coding: utf-8 -*-
from enum import IntEnum, Enum

from core.enum.common import AutoNumber


class GovernanceModeEnum(AutoNumber):
    BUILD_IN_SERVICE_MESH = ()
    KUBERNETES_NATIVE_SERVICE = ()
    ISTIO_SERVICE_MESH = ()

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]

    @classmethod
    def names(cls):
        return [key.name for key in cls]

    @classmethod
    def use_k8s_service_name_governance_modes(cls):
        return [cls.KUBERNETES_NATIVE_SERVICE.name, cls.ISTIO_SERVICE_MESH.name]


class AppType(AutoNumber):
    rainbond = ()
    helm = ()


class ApplicationUpgradeStatus(IntEnum):
    """升级状态"""
    NOT = 1  # 未升级
    UPGRADING = 2  # 升级中
    UPGRADED = 3  # 已升级
    ROLLING = 4  # 回滚中
    ROLLBACK = 5  # 已回滚
    PARTIAL_UPGRADED = 6  # 部分升级
    PARTIAL_ROLLBACK = 7  # 部分回滚
    UPGRADE_FAILED = 8  # 升级失败
    ROLLBACK_FAILED = 9  # 回滚失败
    DEPLOY_FAILED = 10


class ApplicationUpgradeRecordType(Enum):
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"
