# import datetime
# import time
# import uuid
#
# from loguru import logger
#
# from database.session import SessionClass
# from models.application.models import Application
# from repository.application.application_repo import application_repo
# from repository.teams.team_repo import team_repo
# from schemas.wutong_message import UpdateResourceEventBody, UpdateResourceEvent
# from service.event import redis_message_service
#

# def send_message(session: SessionClass, component_id: str, operation_time: datetime, operator: str,
#                  delay: int = 0):
#     try:
#         if delay > 0:
#             time.sleep(delay)
#         # 组件创建、组件资源更新、组件实例数变更 事件
#         # 查询组件资源信息
#         sql = """
#             select
#             ts.service_cname,
#             ts.min_node,
#             ts.min_cpu,
#             ts.min_memory,
#             sg.group_name,
#             ti.tenant_alias,
#             ti.tenant_id,
#             sg.ID as application_id,
#             ti.namespace
#             from tenant_service ts
#             join service_group_relation sgr on ts.service_id = sgr.service_id
#             join service_group sg on sg.ID = sgr.group_id
#             join tenant_info ti on sg.tenant_id = ti.tenant_id
#             where ts.service_id = '{component_id}'
#             """.format(component_id=component_id)
#
#         result = session.execute(sql).first()
#         if not result:
#             logger.error("投递组件资源变更消息,找不到组件信息,组件ID:{}", component_id)
#             return
#         detail = result
#
#         body_cpu: UpdateResourceEventBody = UpdateResourceEventBody(enterprise_id='', enterprise_name='',
#                                                                     team_id=detail.tenant_id,
#                                                                     team_name=detail.tenant_alias,
#                                                                     application_id=detail.application_id,
#                                                                     application_name=detail.group_name,
#                                                                     component_id=component_id,
#                                                                     component_name=detail.service_cname,
#                                                                     type='cpu', value=detail.min_cpu,
#                                                                     namespace=detail.namespace, operator=operator,
#                                                                     operate_time=operation_time,
#                                                                     min_node=detail.min_node)
#
#         message_cpu: UpdateResourceEvent = UpdateResourceEvent(message_id=uuid.uuid1().__str__(),
#                                                                timestamp=time.time(),
#                                                                body=body_cpu.__dict__)
#         body_mem: UpdateResourceEventBody = UpdateResourceEventBody(enterprise_id='', enterprise_name='',
#                                                                     team_id=detail.tenant_id,
#                                                                     team_name=detail.tenant_alias,
#                                                                     application_id=detail.application_id,
#                                                                     application_name=detail.group_name,
#                                                                     component_id=component_id,
#                                                                     component_name=detail.service_cname,
#                                                                     type='mem', value=detail.min_memory,
#                                                                     namespace=detail.namespace, operator=operator,
#                                                                     operate_time=operation_time,
#                                                                     min_node=detail.min_node)
#
#         message_mem: UpdateResourceEvent = UpdateResourceEvent(message_id=uuid.uuid1().__str__(),
#                                                                timestamp=time.time(),
#                                                                body=body_mem.__dict__)
#         # 投递消息至redis
#         # redis_message_service.send_message(message_cpu)
#         # redis_message_service.send_message(message_mem)
#         # 查询组件磁盘信息
#
#         # and volume_type in ('sfs','share-file')
#         volume_sql = """
#                         select sum(volume_capacity) from tenant_service_volume tsv
#                         where tsv.service_id = '{service_id}'
#                         """.format(service_id=component_id)
#         result = session.execute(volume_sql).first()
#         if result[0]:
#             volume_capacity = result[0]
#             body_storage: UpdateResourceEventBody = UpdateResourceEventBody(enterprise_id='', enterprise_name='',
#                                                                             team_id=detail.tenant_id,
#                                                                             team_name=detail.tenant_alias,
#                                                                             application_id=detail.application_id,
#                                                                             application_name=detail.group_name,
#                                                                             component_id=component_id,
#                                                                             component_name=detail.service_cname,
#                                                                             type='storage',
#                                                                             value=str(volume_capacity),
#                                                                             namespace='', operator='system',
#                                                                             operate_time=datetime.datetime.now(),
#                                                                             min_node=detail.min_node)
#             message_storage: UpdateResourceEvent = UpdateResourceEvent(message_id=uuid.uuid1().__str__(),
#                                                                        timestamp=time.time(),
#                                                                        body=body_storage.__dict__)
#             # 投递消息至redis
#             # redis_message_service.send_message(message_storage)
#     except Exception as e:
#         logger.error("投递资源变更消息失败,组件ID:{},error:{}", component_id, e)
#

# def component_update_event(session: SessionClass, component_id: str, operation_time: datetime, operator: str,
#                            delay: int = 0):
#     send_message(session=session, component_id=component_id, operation_time=operation_time, operator=operator,
#                  delay=delay)


# def scheduler_task_event(session: SessionClass):
#     # 扫描运行组件信息
#     teams = team_repo.get_all(session=session)
#     if not teams:
#         return True
#     for team in teams:
#         logger.info("team_info:{}", team)
#         # 查询应用信息
#         applications = application_repo.list_by_model(session=session,
#                                                       query_model=Application(tenant_id=team.tenant_id))
#         if not applications:
#             continue
#         for application in applications:
#             # 查询应用组件信息
#             logger.info("application_info:{}", application)
#             sql = """
#                 SELECT
#                     sgr.service_id,
#                     ts.service_cname,
#                     ts.min_node,
#                     ts.min_cpu,
#                     ts.min_memory,
#                     ts.host_path
#                 FROM
#                     service_group_relation sgr
#                     LEFT JOIN tenant_service ts ON ts.service_id = sgr.service_id
#                 WHERE
#                     sgr.group_id = {application_id}
#                     AND create_status = 'complete'
#             """.format(application_id=application.ID)
#             components = session.execute(sql).fetchall()
#             if not components:
#                 continue
#             for component in components:
#                 body_cpu: UpdateResourceEventBody = UpdateResourceEventBody(enterprise_id='', enterprise_name='',
#                                                                             team_id=team.tenant_id,
#                                                                             team_name=team.tenant_name,
#                                                                             application_id=application.ID,
#                                                                             application_name=application.group_name,
#                                                                             component_id=component.service_id,
#                                                                             component_name=component.service_cname,
#                                                                             type='cpu', value=component.min_cpu,
#                                                                             namespace='', operator='system',
#                                                                             operate_time=datetime.datetime.now(),
#                                                                             min_node=component.min_node)
#                 body_mem: UpdateResourceEventBody = UpdateResourceEventBody(enterprise_id='', enterprise_name='',
#                                                                             team_id=team.tenant_id,
#                                                                             team_name=team.tenant_name,
#                                                                             application_id=application.ID,
#                                                                             application_name=application.group_name,
#                                                                             component_id=component.service_id,
#                                                                             component_name=component.service_cname,
#                                                                             type='mem', value=component.min_memory,
#                                                                             namespace='', operator='system',
#                                                                             operate_time=datetime.datetime.now(),
#                                                                             min_node=component.min_node)
#                 message_cpu: UpdateResourceEvent = UpdateResourceEvent(message_id=uuid.uuid1().__str__(),
#                                                                        timestamp=time.time(),
#                                                                        body=body_cpu.__dict__)
#                 message_mem: UpdateResourceEvent = UpdateResourceEvent(message_id=uuid.uuid1().__str__(),
#                                                                        timestamp=time.time(),
#                                                                        body=body_mem.__dict__)
#                 # 查询磁盘信息 todo
#                 volume_sql = """
#                 select sum(volume_capacity) from tenant_service_volume tsv
#                 where tsv.service_id = '{service_id}' and volume_type in ('sfs','share-file')
#                 """.format(service_id=component.service_id)
#                 result = session.execute(volume_sql).first()
#                 if not result:
#                     continue
#                 if not result[0]:
#                     continue
#                 volume_capacity = result[0]
#                 body_storage: UpdateResourceEventBody = UpdateResourceEventBody(enterprise_id='', enterprise_name='',
#                                                                                 team_id=team.tenant_id,
#                                                                                 team_name=team.tenant_name,
#                                                                                 application_id=application.ID,
#                                                                                 application_name=application.group_name,
#                                                                                 component_id=component.service_id,
#                                                                                 component_name=component.service_cname,
#                                                                                 type='storage',
#                                                                                 value=str(volume_capacity),
#                                                                                 namespace='', operator='system',
#                                                                                 operate_time=datetime.datetime.now(),
#                                                                                 min_node=component.min_node)
#                 message_storage: UpdateResourceEvent = UpdateResourceEvent(message_id=uuid.uuid1().__str__(),
#                                                                            timestamp=time.time(),
#                                                                            body=body_storage.__dict__)
#
#                 # 投递消息至redis
#                 # redis_message_service.send_message(message_cpu)
#                 # redis_message_service.send_message(message_mem)
#                 # redis_message_service.send_message(message_storage)
