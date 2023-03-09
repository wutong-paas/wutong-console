from core.utils.crypt import make_uuid
from database.session import SessionClass
from models.component.models import TeamApplication


def create_tenant_service_group(session: SessionClass, region_name, tenant_env_id, group_id, app_key,
                                app_version, app_name):
    group_name = '_'.join(["wt", make_uuid()[-4:]])
    params = {
        "tenant_env_id": tenant_env_id,
        "group_name": group_name,
        "group_alias": app_name,
        "group_key": app_key,
        "group_version": app_version,
        "region_name": region_name,
        "service_group_id": 0 if group_id == -1 else group_id
    }
    add_model: TeamApplication = TeamApplication(**params)
    session.add(add_model)
    session.flush()

    return add_model
