from typing import Optional, List
from pydantic.fields import Annotated
from pydantic import BaseModel, Field


class EnvVariablesParam(BaseModel):
    key: Optional[str] = None
    value: Optional[str] = None
    desc: Optional[str] = None


class DockerRunParams(BaseModel):
    # 创建方式 docker_run或docker_image
    image_type: Optional[str] = None
    group_id: Optional[int] = -1
    # 组件名称
    service_cname: Optional[str] = None
    # docker运行命令
    docker_cmd: Optional[str] = ""
    password: Optional[str] = None
    user_name: Optional[str] = None
    k8s_component_name: Optional[str] = None
    image_hub: Optional[str] = None


class DeployBusinessParams(BaseModel):
    # 组件名称
    component_name: Optional[str] = None
    # docker运行命令
    docker_image: Optional[str] = ""
    registry_password: Optional[str] = None
    registry_user: Optional[str] = None
    dep_service_ids: Optional[str] = None
    env_variables: List[EnvVariablesParam] = None


class DockerRunCheckParam(BaseModel):
    is_again: Optional[bool] = False


class BuildParam(BaseModel):
    is_deploy: Optional[bool] = True


class BatchActionParam(BaseModel):
    # 操作名称 stop| start|restart|delete|move|upgrade|deploy
    action: Optional[str] = None
    # 批量操作的组件ID 多个以英文逗号分隔
    service_ids: Optional[str] = None
    move_group_id: Optional[str] = None


class ThirdPartyCreateParam(BaseModel):
    group_id: Optional[int] = -1
    service_cname: Optional[str] = None
    static: Optional[list] = None
    endpoints_type: Optional[str] = None
    serviceName: Optional[str] = ""
    namespace: Optional[str] = ""
    k8s_component_name: Optional[str] = ""


class BuildSourceParam(BaseModel):
    env_variables: List[EnvVariablesParam] = None
    update_env_variables: List[EnvVariablesParam] = None
    delete_env_variables: List[EnvVariablesParam] = None
    dep_service_ids: Optional[str] = None
    delete_dep_service_ids: Optional[str] = None
    component_code: Optional[str] = None
    docker_image: Optional[str] = None
    registry_user: Optional[str] = None
    registry_password: Optional[str] = None


class BackupScheduleParam(BaseModel):
    # 备份保留时长
    ttl: Optional[str] = None
    # 计划时间
    sync_time: Optional[str] = None
    sync_week: Optional[str] = "*"
    # 描述信息
    desc: Optional[str] = None


class ServiceBackupParam(BaseModel):
    # 备份保留时长
    ttl: Optional[str] = None
    # 描述信息
    desc: Optional[str] = None


class ServiceVerticalParam(BaseModel):
    """
    组件垂直伸缩参数
    """
    new_memory: Annotated[str, Field(title="最大内存")] = "512"
    new_gpu_type: Annotated[str, Field(title="gpu类型")] = None
    new_gpu: Annotated[str, Field(title="gpu大小")] = None
    new_cpu: Annotated[int, Field(title="最大cpu")] = 500
    request_cpu: Annotated[int, Field(title="最小cpu")] = 0
    request_memory: Annotated[int, Field(title="最小内存")] = 0


class LabelSchedulingParam(BaseModel):
    """
    组件标签调度规则
    """
    label_key: Annotated[str, Field(title="标签键")] = None
    label_value: Annotated[str, Field(title="标签值")] = None


class TaintTolerationsParam(BaseModel):
    """
    组件污点容忍
    """
    taint_key: Annotated[str, Field(title="污点键")] = None
    taint_value: Annotated[str, Field(title="污点值")] = None
    op: Annotated[str, Field(title="操作符(Exists、Equal)")] = None
    effect: Annotated[str, Field(title="效果值")] = None


class AddNodeSchedulingParam(BaseModel):
    """
    新增组件节点调度
    """
    node_names: Annotated[list, Field(title="节点名称")] = None
