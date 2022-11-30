from repository.enterprise.enterprise_user_perm_repo import enterprise_user_perm_repo
from service.user_service import user_kind_perm_service


def check_perm(session, user, tenant, operation):
    is_team_owner = False
    if tenant.creater == user.user_id:
        is_team_owner = True
    is_enterprise_admin = enterprise_user_perm_repo.is_admin(session, user.enterprise_id, user.user_id)
    if is_team_owner or is_enterprise_admin:
        return True
    perms = user_kind_perm_service.get_user_perms(session=session,
                                                  kind="team", kind_id=tenant.tenant_id, user=user,
                                                  is_owner=is_team_owner,
                                                  is_ent_admin=is_enterprise_admin)
    operation_list = operation.split("_")
    operation_type = "_".join(operation_list[:-1])
    oper = operation_list[-1:][0]
    sub_models = perms["permissions"]["team"]["sub_models"]
    for sub_model in sub_models:
        for key, value in sub_model.items():
            if key == operation_type:
                perm_list = sub_model[operation_type]["perms"]
                for perm in perm_list:
                    for key1, value1 in perm.items():
                        if key1 == oper:
                            return value1
    return False
