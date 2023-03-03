from sqlalchemy import text


class ServiceGroupRepository(object):
    def check_non_default_group_by_eid(self, session):
        sql = """
            SELECT
                group_name
            FROM
                service_group a,
                tenant_info b
            WHERE
                a.tenant_id = b.tenant_id
                AND a.is_default = 0
            LIMIT 1
            """
        sql = text(sql)
        result = session.execute(sql).fetchall()
        return True if len(result) > 0 else False


svc_grop_repo = ServiceGroupRepository()
