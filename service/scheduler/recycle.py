import datetime

from loguru import logger

from database.session import SessionClass
from repository.application.application_repo import application_repo
from repository.component.group_service_repo import service_info_repo
from repository.teams.env_repo import env_repo
from service.app_actions.app_delete import component_delete_service
from service.app_actions.app_manage import app_manage_service
from service.application_service import application_service
from service.tenant_env_service import env_services


def recycle_delete_task(session: SessionClass):
    delete_date = datetime.datetime.now().date() - datetime.timedelta(days=7)
    # 扫描待清理组件信息数据
    component_records = service_info_repo.get_logic_delete_records(session=session, delete_date=delete_date)
    logger.info("扫描到需要清理的组件信息:{}条", len(component_records))
    if component_records:
        for record in component_records:
            logger.info("开始清理组件信息:{},删除操作人:{},删除操作时间:{}", record.service_cname, record.delete_operator,
                        record.delete_time)
            # 查询env
            tenant_env = env_repo.get_all_env_by_env_id(session=session, env_id=record.tenant_env_id)
            if tenant_env:
                try:
                    code, msg = app_manage_service.delete(session=session, user_nickname=record.delete_operator,
                                                          tenant_env=tenant_env,
                                                          service=record)
                    if code == 200:
                        logger.info("{0} 组件清理完成".format(record.service_alias))
                    else:
                        logger.info("{0} 组件清理失败:{1}".format(record.service_alias, msg))
                except Exception as e:
                    logger.exception(e)
                    logger.info("{0} 组件清理失败".format(record.service_alias))
        logger.info("组件清理完成")

    session.flush()
    session.commit()

    # 扫描待清理应用信息数据
    app_records = application_repo.get_logic_delete_records(session=session, delete_date=delete_date)
    logger.info("扫描到需要清理的应用信息:{}条", len(app_records))
    if app_records:
        for record in app_records:
            logger.info("开始清理应用信息:{},团队信息:{},删除操作人:{},删除操作时间:{}", record.env_name, record.tenant_name,
                        record.delete_operator, record.delete_time)
            # 查询env
            tenant_env = env_repo.get_env_by_env_id(session=session, env_id=record.tenant_env_id)
            if tenant_env:
                try:
                    application_service.delete_app(session=session, tenant_env=tenant_env,
                                                   region_name=record.region_name,
                                                   app_id=record.ID,
                                                   app_type=record.app_type)
                    logger.info("{0} 应用清理完成".format(record.group_name))
                except Exception as e:
                    logger.exception(e)
                    logger.info("{0} 应用清理失败".format(record.group_name))
        logger.info("应用清理完成")

    session.flush()
    session.commit()

    # 扫描待清理环境信息数据
    logger.info("定时任务开始执行:清理{}之前删除的数据", delete_date)
    env_records = env_repo.get_logic_delete_records(session=session, delete_date=delete_date)
    logger.info("扫描到需要清理的环境信息:{}条", len(env_records))
    if env_records:
        for record in env_records:
            logger.info("开始清理环境信息:{},团队信息:{},删除操作人:{},删除操作时间:{}", record.env_name, record.tenant_name,
                        record.delete_operator, record.delete_time)
            try:
                env_services.delete_by_env_id(session=session, user_nickname=record.delete_operator, env=record)
                logger.info("{0} 环境清理完成".format(record.env_alias))
            except Exception as e:
                logger.exception(e)
                logger.info("{0} 环境清理失败".format(record.env_alias))
        logger.info("环境清理完成")
