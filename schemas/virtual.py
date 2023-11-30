from typing import Optional
from pydantic import BaseModel


class CreateVirtualParam(BaseModel):
    # 虚拟机名称
    name: Optional[str] = None
    # 虚拟机显示名称
    display_name: Optional[str] = None
    # 操作系统名称
    os_name: Optional[str] = None
    # 操作系统版本
    os_version: Optional[str] = None
    # 描述信息
    desc: Optional[str] = None
    # 系统盘大小，单位为 Gi
    os_disk_size: Optional[int] = None
    # CPU 单位为 m
    request_cpu: Optional[int] = None
    # Memory 单位为 Mi
    request_memory: Optional[int] = None
    # 默认登录账号
    user: Optional[str] = "ubuntu"
    # 默认登录密码
    password: Optional[str] = "ubuntu"
    # 调度标签
    node_selector_labels: Optional[list] = []


class UpdateVirtualParam(BaseModel):
    # 虚拟机显示名称
    display_name: Optional[str] = None
    # 描述信息
    desc: Optional[str] = None
    # CPU 单位为 m
    request_cpu: Optional[int] = None
    # Memory 单位为 Mi
    request_memory: Optional[int] = None
    # 默认登录用户
    default_login_user: Optional[str] = "ubuntu"


class VirtualPortsParam(BaseModel):
    # 虚拟机端口
    vm_port: Optional[int] = None
    # 虚拟机端口协议
    protocol: Optional[str] = None


class PortsGatewayParam(BaseModel):
    # 虚拟机端口
    vm_port: Optional[int] = None
    # 虚拟机端口协议
    protocol: Optional[str] = None
    # 网关 ID，创建时为空即可
    gateway_id: Optional[str] = None
    # 网关 IP，协议为 tcp 时生效，可选：0.0.0.0、
    gateway_ip: Optional[str] = None
    # 网关端口，协议为 tcp 时生效，如果不设置值（0）时，将自动生成端口
    gateway_port: Optional[int] = 0
    # 网关域名，协议为 http 时生效，如果不设置值，将自动生成域名
    gateway_host: Optional[str] = None
    # 网关路由，协议为 http 时生效，默认为“/”
    gateway_path: Optional[str] = "/"


class UpdateGatewayParam(BaseModel):
    # 网关 ID，创建时为空即可
    gateway_id: Optional[str] = None
    # 网关 IP，协议为 tcp 时生效，可选：0.0.0.0
    gateway_ip: Optional[str] = None
    # 网关端口，协议为 tcp 时生效，如果不设置值（0）时，将自动生成端口
    gateway_port: Optional[int] = 0
    # 网关域名，协议为 http 时生效，如果不设置值，将自动生成域名
    gateway_host: Optional[str] = None
    # 网关路由，协议为 http 时生效，默认为“/”
    gateway_path: Optional[str] = "/"


class DeleteGatewayParam(BaseModel):
    # 网关 ID，创建时为空即可
    gateway_id: Optional[str] = None


class VirtualConnectSSHParam(BaseModel):
    # 虚拟机登录用户，空值使用 root 账号
    vm_user: Optional[str] = "root"
    # 虚拟机 SSH 端口，空值使用 22 端口
    vm_port: Optional[int] = 22


# 创建虚拟机镜像参数
class CreateVirtualImageParam(BaseModel):
    # 镜像名称
    image_name: Optional[str] = None
    # 镜像类型
    image_type: Optional[str] = None
    # 镜像地址
    image_address: Optional[str] = None
    # 操作系统
    os_name: Optional[str] = None
    # 版本
    version: Optional[str] = None
    # 描述
    desc: Optional[str] = ""


# 更新虚拟机镜像参数
class UpdateVirtualImageParam(BaseModel):
    # 镜像id
    image_id: Optional[int] = None
    # 镜像名称
    image_name: Optional[str] = None
    # 镜像类型
    image_type: Optional[str] = None
    # 镜像地址
    image_address: Optional[str] = None
    # 版本
    version: Optional[str] = None
    # 描述
    desc: Optional[str] = ""
