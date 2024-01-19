from pydantic import BaseModel, Field
from pydantic.fields import Annotated


class NodeCordonParam(BaseModel):
    """
    设置节点调度
    """
    region_code: Annotated[str, Field(title="集群标识")] = None
    node_name: Annotated[str, Field(title="节点名称")] = None
    cordon: Annotated[bool, Field(title="是否开启调度")] = False
    evict_pods: Annotated[bool, Field(title="是否驱逐节点上已调度的Pod")] = False
