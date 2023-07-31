import json

from sqlalchemy import select, and_, or_, delete, func, not_, exists

from models.application.models import ApplicationConfigGroup, ConfigGroupService
from models.component.models import TeamComponentPort, ComponentExtendMethod, TeamComponentMountRelation, \
    TeamComponentVolume, TeamComponentConfigurationFile, TeamComponentAuth, TeamComponentEnv, \
    ThirdPartyComponentEndpoints
from models.relate.models import TeamComponentRelation
from models.teams import GatewayCustomConfiguration
from repository.application.config_group_repo import app_config_group_service_repo
from repository.base import BaseRepository


class TenantServicePortRepository(BaseRepository[TeamComponentPort]):

    def list_inner_ports(self, session, tenant_env_id, service_id):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.is_inner_service == True)).scalars().all()

    def get_service_port_by_alias(self, session, service_id, alias):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.port_alias == alias)).scalars().first()

    def overwrite_by_component_ids(self, session, component_ids, ports):
        session.execute(delete(TeamComponentPort).where(
            TeamComponentPort.service_id.in_(component_ids)))
        for port in ports:
            session.merge(port)
        session.flush()

    def list_by_k8s_service_names(self, session, tenant_env_id, k8s_service_names):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.k8s_service_name.in_(k8s_service_names))).scalars().all()

    def list_inner_ports_by_service_ids(self, session, tenant_env_id, service_ids):
        if not service_ids:
            return []
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.service_id.in_(service_ids),
            TeamComponentPort.is_inner_service == 1)).scalars().all()

    def delete_service_port(self, session, tenant_env_id, service_id):
        session.execute(
            delete(TeamComponentPort).where(
                TeamComponentPort.service_id == service_id,
                TeamComponentPort.tenant_env_id == tenant_env_id)
        )

    def bulk_all(self, session, port_list):
        session.add_all(port_list)
        session.flush()

    def get_by_k8s_service_name(self, session, tenant_env_id, k8s_service_name):
        if not k8s_service_name:
            return
        return (session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.k8s_service_name == k8s_service_name))).scalars().all()

    def list_by_service_ids(self, session, tenant_env_id, service_ids):
        return (session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.service_id.in_(service_ids)))).scalars().all()

    def get_service_port_by_port(self, session, tenant_env_id, service_id, container_port):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.container_port == container_port)).scalars().first()

    def get_service_ports(self, session, tenant_env_id, service_id):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.service_id == service_id)).scalars().all()

    def get_service_ports_is_outer_service(self, session, tenant_env_id, service_id):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.service_id == service_id,
            TeamComponentPort.is_outer_service == 1)).scalars().all()

    def get_service_port_by_container_port(self, session, service_id, port):
        return session.execute(select(TeamComponentPort).where(
            TeamComponentPort.container_port == port,
            TeamComponentPort.service_id == service_id)).scalars().first()

    def get_service_ports_by_is_inner_service(self, session, tenant_env_id, service_id):
        return (
            session.execute(select(TeamComponentPort).where(TeamComponentPort.tenant_env_id == tenant_env_id,
                                                            TeamComponentPort.service_id == service_id,
                                                            TeamComponentPort.is_inner_service == 1))
        ).scalars().all()

    def add_service_port(self, session, **tenant_service_port):
        service_port = TeamComponentPort(**tenant_service_port)
        session.add(service_port)
        session.flush()
        return service_port

    def delete_serivce_port_by_port(self, session, tenant_env_id, service_id, container_port):
        session.execute(delete(TeamComponentPort).where(TeamComponentPort.tenant_env_id == tenant_env_id,
                                                        TeamComponentPort.service_id == service_id,
                                                        TeamComponentPort.container_port == container_port))


class ApplicationConfigGroupRepository(BaseRepository[ConfigGroupService]):

    def is_exists(self, session, region_name, app_id, config_group_name):
        exist = session.execute(
            select(ApplicationConfigGroup).where(
                ApplicationConfigGroup.region_name == region_name,
                ApplicationConfigGroup.app_id == app_id,
                ApplicationConfigGroup.config_group_name == config_group_name)
        ).scalars().first()
        if exist:
            return True
        return False

    @staticmethod
    def bulk_create_or_update(session, config_groups):
        config_group_ids = [cg.config_group_id for cg in config_groups]
        session.execute(delete(ApplicationConfigGroup).where(
            ApplicationConfigGroup.config_group_id.in_(config_group_ids)
        ))
        for config_group in config_groups:
            session.merge(config_group)

    def list_by_service_ids(self, session, region_name, service_ids):
        config_groups = session.execute(
            select(ConfigGroupService).where(ConfigGroupService.service_id.in_(service_ids))
        ).scalars().all()
        config_group_ids = [config_group.config_group_id for config_group in config_groups]

        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.config_group_id.in_(config_group_ids),
                                                 ApplicationConfigGroup.region_name == region_name)
        ).scalars().all()

    def count_by_region_and_app_id(self, session, region_name, app_id):
        # return ApplicationConfigGroup.objects.filter(region_name=region_name, app_id=app_id).count()
        return (session.execute(
            select(func.count(ApplicationConfigGroup.ID)).where(ApplicationConfigGroup.region_name == region_name,
                                                                ApplicationConfigGroup.app_id == app_id)
        )).first()[0]

    def get_config_group_in_use(self, session, region_name, app_id):
        cgroups = session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id,
                                                 ApplicationConfigGroup.enable == 1)
        ).scalars().all()
        cgroup_infos = []
        if cgroups:
            for cgroup in cgroups:
                cgroup_services = app_config_group_service_repo.list(session=session,
                                                                     config_group_id=cgroup.config_group_id)
                if cgroup_services:
                    cgroup_info = {"config_group_id": cgroup.config_group_id,
                                   "config_group_name": cgroup.config_group_name}
                    cgroup_infos.append(cgroup_info)
        return cgroup_infos

    def get(self, session, region_name, app_id, config_group_name):
        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id,
                                                 ApplicationConfigGroup.config_group_name == config_group_name)
        ).scalars().all()

    def list(self, session, region_name, app_id):
        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id).order_by(
                ApplicationConfigGroup.create_time.desc())
        ).scalars().all()

    def list_query(self, session, region_name, app_id, query):
        return session.execute(
            select(ApplicationConfigGroup).where(ApplicationConfigGroup.region_name == region_name,
                                                 ApplicationConfigGroup.app_id == app_id,
                                                 ApplicationConfigGroup.config_group_name.contains(query)).order_by(
                ApplicationConfigGroup.create_time.desc())
        ).scalars().all()

    def create(self, session, **group_req):
        acg = ApplicationConfigGroup(**group_req)
        session.add(acg)
        session.flush()
        return acg

    def delete_by_region_name(self, session, region_name, app_id, config_group_name):
        session.execute(
            delete(ApplicationConfigGroup).where(
                ApplicationConfigGroup.region_name == region_name,
                ApplicationConfigGroup.app_id == app_id,
                ApplicationConfigGroup.config_group_name == config_group_name)
        )

    def update(self, session, **group_req):
        acg = session.execute(
            select(ApplicationConfigGroup).where(
                ApplicationConfigGroup.region_name == group_req["region_name"],
                ApplicationConfigGroup.app_id == group_req["app_id"],
                ApplicationConfigGroup.config_group_name == group_req["config_group_name"])
        ).scalars().first()
        acg.enable = group_req["enable"]
        acg.update_time = group_req["update_time"]


class TenantServiceEndpoints(BaseRepository[ThirdPartyComponentEndpoints]):

    def update_or_create_endpoints(self, session, tenant_env, service, service_endpoints):
        endpoints = self.get_service_endpoints_by_service_id(session, service.service_id)
        if not service_endpoints:
            session.execute(
                delete(ThirdPartyComponentEndpoints).where(ThirdPartyComponentEndpoints.ID == endpoints.ID)
            )
            session.flush()
        elif endpoints:
            endpoints.endpoints_info = json.dumps(service_endpoints)
        else:
            data = {
                "tenant_env_id": tenant_env.env_id,
                "service_id": service.service_id,
                "service_cname": service.service_cname,
                "endpoints_info": json.dumps(service_endpoints),
                "endpoints_type": "static"
            }
            endpoints = ThirdPartyComponentEndpoints(**data)
            session.add(endpoints)
            session.flush()
        return endpoints

    def list_by_component_ids(self, session, component_ids):
        return (session.execute(select(ThirdPartyComponentEndpoints).where(
            ThirdPartyComponentEndpoints.service_id.in_(component_ids)))).scalars().all()

    def get_service_endpoints_by_service_id(self, session, service_id):
        return (session.execute(select(ThirdPartyComponentEndpoints).where(
            ThirdPartyComponentEndpoints.service_id == service_id))).scalars().first()

    def get_all_service_endpoints_by_service_id(self, session, service_id):
        return (session.execute(select(ThirdPartyComponentEndpoints).where(
            ThirdPartyComponentEndpoints.service_id == service_id))).scalars().all()

    def get_service_ports(self, session, tenant_env_id, service_id):
        return (session.execute(select(TeamComponentPort).where(
            TeamComponentPort.tenant_env_id == tenant_env_id,
            TeamComponentPort.service_id == service_id))).scalars().all()


class ServiceExtendRepository(BaseRepository[ComponentExtendMethod]):

    def bulk_create_or_update(self, session, extend_infos):
        session.execute(delete(ComponentExtendMethod).where(
            ComponentExtendMethod.ID.in_([ei.ID for ei in extend_infos])))
        for extend_info in extend_infos:
            session.merge(extend_info)
        session.flush()

    def get_extend_method_by_service(self, session, service):
        if service.service_source == "market":
            return (session.execute(select(ComponentExtendMethod).where(
                ComponentExtendMethod.service_key == service.service_key,
                ComponentExtendMethod.app_version == service.version))).scalars().first()
        return None


class TenantServiceMntRelationRepository(BaseRepository[TeamComponentMountRelation]):

    def overwrite_by_component_id(self, session, component_ids, volume_deps):
        volume_deps = [dep for dep in volume_deps if dep.service_id in component_ids]
        session.execute(delete(TeamComponentMountRelation).where(
            TeamComponentMountRelation.service_id.in_(component_ids)
        ))
        session.add_all(volume_deps)

    def list_mnt_relations_by_service_ids(self, session, tenant_env_id, service_ids):
        return session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.tenant_env_id == tenant_env_id,
            TeamComponentMountRelation.service_id.in_(service_ids)
        )).scalars().all()

    def delete_mnt_relation(self, session, service_id, dep_service_id, mnt_name):
        session.execute(delete(TeamComponentMountRelation).where(
            TeamComponentMountRelation.service_id == service_id,
            TeamComponentMountRelation.dep_service_id == dep_service_id,
            TeamComponentMountRelation.mnt_name == mnt_name))

    def delete_mnt(self, session, service_id):
        session.execute(delete(TeamComponentMountRelation).where(
            TeamComponentMountRelation.service_id == service_id))

    def get_service_mnts_filter_volume_type(self, session, tenant_env_id, service_id, volume_types=None):
        query = "mnt.tenant_env_id = '%s' and mnt.service_id = '%s'" % (tenant_env_id, service_id)
        # if volume_types:
        #     vol_type_sql = " and volume.volume_type in ({})".format(','.join(["'%s'"] * len(volume_types)))
        #     query += vol_type_sql % tuple(volume_types)

        sql = """
        select mnt.mnt_name,
            mnt.mnt_dir,
            mnt.dep_service_id,
            mnt.service_id,
            mnt.tenant_env_id,
            volume.volume_type,
            volume.ID as volume_id
        from tenant_service_mnt_relation as mnt
                 inner join tenant_service_volume as volume
                            on mnt.dep_service_id = volume.service_id and mnt.mnt_name = volume.volume_name
        where {};
        """.format(query)
        result = session.execute(sql).fetchall()
        dep_mnts = []
        for real_dep_mnt in result:
            mnt = TeamComponentMountRelation(
                tenant_env_id=real_dep_mnt.tenant_env_id,
                service_id=real_dep_mnt.service_id,
                dep_service_id=real_dep_mnt.dep_service_id,
                mnt_name=real_dep_mnt.mnt_name,
                mnt_dir=real_dep_mnt.mnt_dir)
            mnt.volume_type = real_dep_mnt.volume_type
            mnt.volume_id = real_dep_mnt.volume_id
            dep_mnts.append(mnt)
        return dep_mnts

    def get_by_dep_service_id(self, session, tenant_env_id, dep_service_id):
        return (session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.tenant_env_id == tenant_env_id,
            TeamComponentMountRelation.dep_service_id == dep_service_id))).scalars().all()

    def get_mount_current_service(self, session, tenant_env_id, service_id):
        """查询挂载当前组件的信息"""
        return (session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.tenant_env_id == tenant_env_id,
            TeamComponentMountRelation.dep_service_id == service_id))).scalars().all()

    def get_mnt_by_dep_id_and_mntname(self, session, dep_service_id, mnt_name):
        return (session.execute(select(TeamComponentMountRelation).where(
            TeamComponentMountRelation.dep_service_id == dep_service_id,
            TeamComponentMountRelation.mnt_name == mnt_name))).scalars().first()

    def get_service_mnts(self, session, tenant_env_id, service_id):
        return self.get_service_mnts_filter_volume_type(session=session, tenant_env_id=tenant_env_id, service_id=service_id)

    def add_service_mnt_relation(self, session, tenant_env_id, service_id, dep_service_id, mnt_name, mnt_dir):
        tsr = TeamComponentMountRelation(
            tenant_env_id=tenant_env_id,
            service_id=service_id,
            dep_service_id=dep_service_id,
            mnt_name=mnt_name,
            mnt_dir=mnt_dir  # this dir is source app's volume path
        )
        session.add(tsr)
        return tsr


class TenantServiceVolumnRepository(BaseRepository[TeamComponentVolume]):

    def overwrite_by_component_ids(self, session, component_ids, volumes):
        session.execute(delete(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(component_ids)))
        for volume in volumes:
            session.merge(volume)
        session.flush()

    def delete_service_volumes(self, session, service_id):
        session.execute(
            delete(TeamComponentVolume).where(TeamComponentVolume.service_id == service_id)
        )

    def get_service_volume_by_name(self, session, service_id, volume_name):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_name == volume_name)).scalars().first()

    def get_service_volume_by_name_path(self, session, service_id, volume_name, volume_path):
        return session.execute(select(TeamComponentVolume.ID).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_path == volume_path,
            TeamComponentVolume.volume_name == volume_name)).scalars().first()

    def get_service_volumes_about_config_file(self, session, service_id):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_type == "config-file")).scalars().all()

    def get_service_volume_by_pk(self, session, volume_id):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.ID == volume_id)).scalars().first()

    def get_service_config_file(self, session, volume: TeamComponentVolume):
        return session.execute(select(TeamComponentConfigurationFile).where(
            and_(or_(TeamComponentConfigurationFile.volume_name == volume.volume_name,
                     TeamComponentConfigurationFile.volume_id == volume.ID),
                 TeamComponentConfigurationFile.service_id == volume.service_id))).scalars().first()

    def get_service_volumes(self, session, service_id):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            not_(TeamComponentVolume.volume_type == "config-file"))).scalars().all()

    def get_service_volume_by_path(self, session, service_id, volume_path):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id,
            TeamComponentVolume.volume_path == volume_path)).scalars().first()

    def save_service_volume(self, session, service_volume):
        session.add(service_volume)
        session.flush()

    def delete_volume_by_id(self, session, volume_id):
        session.execute(delete(TeamComponentVolume).where(
            TeamComponentVolume.ID == volume_id))

    def delete_file_by_volume(self, session, volume: TeamComponentVolume):
        session.execute(delete(TeamComponentConfigurationFile).where(
            and_(TeamComponentConfigurationFile.service_id == volume.service_id,
                 or_(TeamComponentConfigurationFile.volume_id == volume.ID,
                     TeamComponentConfigurationFile.volume_name == volume.volume_name))))

    def get_services_volumes_by_config(self, session, service_ids, CONFIG, mounted_ids):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(service_ids),
            TeamComponentVolume.volume_type == CONFIG,
            not_(TeamComponentVolume.ID.in_(mounted_ids)))).scalars().all()

    def get_services_volumes_by_share(self, session, service_ids, SHARE, mounted_ids, state_service_ids):
        return session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(service_ids),
            TeamComponentVolume.volume_type == SHARE,
            not_(TeamComponentVolume.ID.in_(mounted_ids)),
            not_(TeamComponentVolume.service_id.in_(state_service_ids)))).scalars().all()

    def add_service_config_file(self, session, **service_config_file):
        tscf = TeamComponentConfigurationFile(**service_config_file)
        session.add(tscf)
        session.flush()
        return tscf

    def get_service_volumes_with_config_file(self, session, service_id):
        return (session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id == service_id))).scalars().all()

    def list_custom_volumes(self, session, service_ids):
        return (session.execute(select(TeamComponentVolume).where(
            TeamComponentVolume.service_id.in_(service_ids),
            not_(TeamComponentVolume.volume_type.in_(
                ["config-file", TeamComponentVolume.SHARE, TeamComponentVolume.LOCAL,
                 TeamComponentVolume.TMPFS]))))).scalars().all()

    def get_service_config_files(self, session, service_id):
        return (session.execute(select(TeamComponentConfigurationFile).where(
            TeamComponentConfigurationFile.service_id == service_id))).scalars().all()


class TenantServiceRelationRepository(BaseRepository[TeamComponentRelation]):

    @staticmethod
    def list_by_component_ids(session, tenant_env_id, component_ids):
        return session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_env_id == tenant_env_id,
            TeamComponentRelation.service_id.in_(component_ids)
        )).scalars().all()

    def overwrite_by_component_id(self, session, component_ids, component_deps):
        with session.no_autoflush:
            component_deps = [dep for dep in component_deps if dep.service_id in component_ids]
            session.execute(delete(TeamComponentRelation).where(
                TeamComponentRelation.service_id.in_(component_ids)
            ))
            for dep in component_deps:
                session.merge(dep)

    def check_db_dep_by_eid(self, session):
        """
        check if there is a database installed from the market that is dependent on
        """
        sql = """
            SELECT
                a.service_id, a.dep_service_id
            FROM
                tenant_service_relation a,
                tenant_service b,
                tenant_info c,
                tenant_service d
            WHERE
                b.tenant_env_id = c.tenant_env_id
                AND a.service_id = d.service_id
                AND a.dep_service_id = b.service_id
                AND ( b.image LIKE "%mysql%" OR b.image LIKE "%postgres%" OR b.image LIKE "%mariadb%" )
                AND (b.service_source <> "market" OR d.service_source <> "market")
                limit 1"""
        result = session.execute(sql).fetchall()
        if len(result) > 0:
            return True
        sql2 = """
            SELECT
                a.dep_service_id
            FROM
                tenant_service_relation a,
                tenant_service b,
                tenant_info c,
                tenant_service d,
                service_source e,
                service_source f
            WHERE
                b.tenant_env_id = c.tenant_env_id
                AND a.service_id = d.service_id
                AND a.dep_service_id = b.service_id
                AND ( b.image LIKE "%mysql%" OR b.image LIKE "%postgres%" OR b.image LIKE "%mariadb%" )
                AND ( b.service_source = "market" AND d.service_source = "market" )
                AND e.service_id = b.service_id
                AND f.service_id = d.service_id
                AND e.group_key <> f.group_key
                LIMIT 1"""
        result2 = session.execute(sql2).fetchall()
        return True if len(result2) > 0 else False

    def delete_service_relation(self, session, tenant_env_id, service_id):
        session.execute(delete(TeamComponentRelation).where(
            TeamComponentRelation.service_id == service_id,
            TeamComponentRelation.tenant_env_id == tenant_env_id))

    def get_service_dependencies(self, session, tenant_env_id, service_id):
        return session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_env_id == tenant_env_id,
            TeamComponentRelation.service_id == service_id)).scalars().all()

    def get_dependency_by_dep_id(self, session, env_id, dep_service_id):
        return (session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_env_id == env_id,
            TeamComponentRelation.dep_service_id == dep_service_id))).scalars().all()

    def delete_dependency_by_dep_id(self, session, tenant_env_id, dep_service_id):
        return session.execute(delete(TeamComponentRelation).where(
            TeamComponentRelation.tenant_env_id == tenant_env_id,
            TeamComponentRelation.dep_service_id == dep_service_id))

    def get_dependency_by_dep_service_ids(self, session, tenant_env_id, service_id, dep_service_ids):
        return (session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_env_id == tenant_env_id,
            TeamComponentRelation.service_id == service_id,
            TeamComponentRelation.dep_service_id.in_(dep_service_ids)))).scalars().all()

    def get_depency_by_serivce_id_and_dep_service_id(self, session, tenant_env_id, service_id, dep_service_id):
        return (session.execute(select(TeamComponentRelation).where(
            TeamComponentRelation.tenant_env_id == tenant_env_id,
            TeamComponentRelation.service_id == service_id,
            TeamComponentRelation.dep_service_id == dep_service_id))).scalars().first()

    def add_service_dependency(self, session, **tenant_service_relation):
        tsr = TeamComponentRelation(**tenant_service_relation)
        session.add(tsr)

    def delete(self, session, dependency):
        session.delete(dependency)


class GatewayCustom(BaseRepository[GatewayCustomConfiguration]):

    def delete_by_rule_ids(self, session, rule_ids):
        session.execute(delete(GatewayCustomConfiguration).where(
            GatewayCustomConfiguration.rule_id.in_(rule_ids)))

    def list_by_rule_ids(self, session, rule_ids):
        return (session.execute(select(GatewayCustomConfiguration).where(
            GatewayCustomConfiguration.rule_id.in_(rule_ids)))).scalars().all()

    def get_configuration_by_rule_id(self, session, rule_id):
        return (session.execute(select(GatewayCustomConfiguration).where(
            GatewayCustomConfiguration.rule_id == rule_id))).scalars().first()

    def add_configuration(self, session, **configuration_info):
        gcc = GatewayCustomConfiguration(**configuration_info)
        session.add(gcc)
        return gcc

    def save(self, session, gcc):
        session.merge(gcc)


class ServiceAuthRepository(BaseRepository[TeamComponentAuth]):

    def delete_service_auth(self, session, service_id):
        session.execute(delete(TeamComponentAuth).where(
            TeamComponentAuth.service_id == service_id))

    def get_service_auth(self, session, service_id):
        return (session.execute(select(TeamComponentAuth).where(
            TeamComponentAuth.service_id == service_id))).scalars().all()


class CompileEnvRepository(BaseRepository[TeamComponentEnv]):

    def list_by_component_ids(self, session, component_ids):
        return (session.execute(select(TeamComponentEnv).where(
            TeamComponentEnv.service_id.in_(component_ids)))).scalars().all()

    def delete_service_compile_env(self, session, service_id):
        session.execute(delete(TeamComponentEnv).where(
            TeamComponentEnv.service_id == service_id))

    def save_service_compile_env(self, session, **params):
        tse = TeamComponentEnv(**params)
        session.add(tse)

    def save(self, session, new_compile_env):
        session.merge(new_compile_env)

    def get_service_compile_env(self, session, service_id):
        return (session.execute(select(TeamComponentEnv).where(
            TeamComponentEnv.service_id == service_id))).scalars().first()

    def update_service_compile_env(self, session, service_id, **update_params):
        tse = TeamComponentEnv(**update_params)
        session.merge(tse)


app_config_group_repo = ApplicationConfigGroupRepository(ConfigGroupService)
port_repo = TenantServicePortRepository(TeamComponentPort)

service_endpoints_repo = TenantServiceEndpoints(ThirdPartyComponentEndpoints)
extend_repo = ServiceExtendRepository(ComponentExtendMethod)
mnt_repo = TenantServiceMntRelationRepository(TeamComponentMountRelation)
volume_repo = TenantServiceVolumnRepository(TeamComponentVolume)
dep_relation_repo = TenantServiceRelationRepository(TeamComponentRelation)
configuration_repo = GatewayCustom(GatewayCustomConfiguration)
auth_repo = ServiceAuthRepository(TeamComponentAuth)
compile_env_repo = CompileEnvRepository(TeamComponentEnv)
