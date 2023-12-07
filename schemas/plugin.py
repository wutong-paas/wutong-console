from pydantic.fields import Annotated
from pydantic import BaseModel, Field


class InstallSysPlugin(BaseModel):
    """
    安装并开通系统插件
    """
    plugin_type: Annotated[str, Field(title="插件类型")] = None
    build_version: Annotated[str, Field(title="插件版本")] = None
    config: Annotated[dict, Field(title="插件配置项")] = None
    min_cpu: Annotated[int, Field(title="插件cpu")] = None
    min_memory: Annotated[int, Field(title="插件内存")] = None


class BatchInstallPlugin(BaseModel):
    """
    批量安装插件
    """
    plugin_id: Annotated[str, Field(title="插件类型")] = None
    plugin_type: Annotated[str, Field(title="插件类型")] = None
    origin: Annotated[str, Field(title="插件来源")] = None
    build_version: Annotated[str, Field(title="插件版本")] = None
    service_ids: Annotated[list, Field(title="组件id列表")] = None
