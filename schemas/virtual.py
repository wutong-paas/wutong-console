from typing import Optional
from pydantic import BaseModel


class CreateVirtualParam(BaseModel):
    # 虚拟机名称
    name: Optional[str] = None
    # 虚拟机显示名称
    display_name: Optional[str] = None
    # 描述信息
    desc: Optional[str] = None
    # 支持 http、registry
    os_source_from: Optional[str] = None
    # registry 时 URL 为系统 Docker 镜像
    # http 时 URL 为系统包下载地址
    os_source_url: Optional[str] = None
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
