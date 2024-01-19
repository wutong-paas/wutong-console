from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class NodeCordonParam(BaseModel):
    """
    设置节点调度
    """
    region_code: Annotated[str, Field(title="集群标识")] = None
    cordon: Annotated[bool, Field(title="是否停止调度")] = False
    evict_pods: Annotated[bool, Field(title="是否驱逐节点上已调度的Pod")] = False


class AddNodeLabelParam(BaseModel):
    """
    新增节点标签
    """
    region_code: Annotated[str, Field(title="集群标识")] = None
    label_type: Annotated[str, Field(title="标签类型(common_label/vm_label)")] = "common_label"
    key: Annotated[str, Field(title="标签名")] = None
    value: Annotated[str, Field(title="标签值")] = None


class DeleteNodeLabelParam(BaseModel):
    """
    删除节点标签
    """
    region_code: Annotated[str, Field(title="集群标识")] = None
    label_type: Annotated[str, Field(title="标签类型(common_label/vm_label)")] = "common_label"
    key: Annotated[str, Field(title="标签名")] = None
