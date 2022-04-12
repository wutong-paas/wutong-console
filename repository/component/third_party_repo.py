from models.component.models import ThirdPartyComponentEndpoints
from repository.base import BaseRepository


class ThirdPartyComponentEndpointsRepository(BaseRepository[ThirdPartyComponentEndpoints]):
    pass


third_party_repo = ThirdPartyComponentEndpointsRepository(ThirdPartyComponentEndpoints)
