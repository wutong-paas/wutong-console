import json
from re import split as re_split

from loguru import logger

from clients.remote_build_client import remote_build_client
from clients.remote_component_client import remote_component_client
from core.git.github_http import GitHubApi
from core.git.gitlab_http import GitlabApi
from core.git.regionapi import RegionInvokeApi
from core.setting import settings
from core.utils.custom_config import custom_config
from core.utils.oauth.oauth_types import support_oauth_type
from database.session import SessionClass
from exceptions.main import ServiceHandleException
from models.component.models import TeamComponentInfo
from models.users.users import Users
from repository.application.app_repository import app_repo
from repository.application.application_repo import app_market_repo
from repository.component.component_repo import service_source_repo
from repository.teams.team_repo import team_repo


gitClient = GitlabApi()
gitHubClient = GitHubApi()
region_api = RegionInvokeApi()


class BaseService:

    def get_group_services_list(self, session: SessionClass, team_id, region_name, group_id, query=""):
        parms = {
            "team_id": team_id,
            "region_name": region_name,
            "group_id": group_id,
            "service_cname": query
        }
        query_sql = '''
            SELECT
                t.service_id,
                t.k8s_component_name,
                t.service_alias,
                t.create_status,
                t.service_cname,
                t.service_type,
                t.deploy_version,
                t.version,
                t.update_time,
                t.min_memory * t.min_node AS min_memory,
                g.group_name
            FROM
                tenant_service t
                LEFT JOIN service_group_relation r ON t.service_id = r.service_id
                LEFT JOIN service_group g ON r.group_id = g.ID
            WHERE
                t.tenant_id = :team_id
                AND t.service_region = :region_name
                AND r.group_id = :group_id
                AND t.service_cname like '%' :service_cname '%'
            ORDER BY
                t.update_time DESC;
        '''
        services = session.execute(query_sql, parms).fetchall()
        return services

    def get_fuzzy_services_list(self, session: SessionClass, team_id, region_name, query_key, fields, order):
        if fields != "update_time" and fields != "ID":
            fields = "ID"
        if order != "desc" and order != "asc":
            order = "desc"
        query_sql = '''
            SELECT
                t.create_status,
                t.service_id,
                t.service_cname,
                t.min_memory * t.min_node AS min_memory,
                t.service_alias,
                t.service_type,
                t.deploy_version,
                t.version,
                t.update_time,
                r.group_id,
                g.group_name
            FROM
                tenant_service t
                LEFT JOIN service_group_relation r ON t.service_id = r.service_id
                LEFT JOIN service_group g ON r.group_id = g.ID
            WHERE
                t.tenant_id = "{team_id}"
                AND t.service_region = "{region_name}"
                AND t.service_cname LIKE "%{query_key}%"
            ORDER BY
                t.{fields} {order};
        '''.format(
            team_id=team_id, region_name=region_name, query_key=query_key, fields=fields, order=order)
        services = (session.execute(query_sql)).fetchall()
        session.remove()
        return services

    def status_multi_service(self, session: SessionClass, region, tenant_name, service_ids, enterprise_id):
        try:
            body = remote_component_client.service_status(session, region, tenant_name, {"service_ids": service_ids,
                                                                                         "enterprise_id": enterprise_id})
            return body["list"]
        except Exception as e:
            return []

    def get_no_group_services_list(self, session: SessionClass, team_id, region_name):
        query_sql = '''
            SELECT
                t.service_id,
                t.service_alias,
                t.service_cname,
                t.service_type,
                t.create_status,
                t.deploy_version,
                t.version,
                t.update_time,
                t.min_memory * t.min_node AS min_memory,
                g.group_name
            FROM
                tenant_service t
                LEFT JOIN service_group_relation r ON t.service_id = r.service_id
                LEFT JOIN service_group g ON r.group_id = g.ID
            WHERE
                t.tenant_id = "{team_id}"
                AND t.service_region = "{region_name}"
                AND r.group_id IS NULL
            ORDER BY
                t.update_time DESC;
        '''.format(
            team_id=team_id, region_name=region_name)
        services = (session.execute(query_sql)).fetchall()
        return services

    def get_build_infos(self, session: SessionClass, tenant, service_ids):
        apps = dict()
        markets = dict()
        build_infos = dict()
        services = team_repo.list_by_component_ids(session=session, service_ids=service_ids)
        svc_sources = service_source_repo.get_service_sources(session=session, team_id=tenant.tenant_id,
                                                              service_ids=service_ids)
        service_sources = {svc_ss.service_id: svc_ss for svc_ss in svc_sources}

        for service in services:
            service_source = service_sources.get(service.service_id, None)
            code_from = service.code_from
            oauth_type = list(support_oauth_type.keys())
            if code_from in oauth_type:
                result_url = re_split("[:,@]", service.git_url)
                service.git_url = result_url[0] + '//' + result_url[-1]
            bean = {
                "user_name": "",
                "password": "",
                "service_source": service.service_source,
                "image": service.image,
                "cmd": service.cmd,
                "code_from": service.code_from,
                "version": service.version,
                "docker_cmd": service.docker_cmd,
                "create_time": service.create_time,
                "git_url": service.git_url,
                "code_version": service.code_version,
                "server_type": service.server_type,
                "language": service.language,
                "oauth_service_id": service.oauth_service_id,
                "full_name": service.git_full_name
            }
            if service_source:
                bean["user"] = service_source.user_name
                bean["password"] = service_source.password
            if service.service_source == 'market':
                if not service_source:
                    build_infos[service.service_id] = bean
                    continue

                # get from cloud
                app = None
                if service_source.extend_info:
                    extend_info = json.loads(service_source.extend_info)
                    if extend_info and extend_info.get("install_from_cloud", False):
                        market_name = extend_info.get("market_name")
                        bean["install_from_cloud"] = True
                        try:
                            market = markets.get(market_name, None)
                            if not market:
                                market = app_market_repo.get_app_market_by_name(session, tenant.enterprise_id,
                                                                                market_name,
                                                                                raise_exception=True)
                                markets[market_name] = market

                            # todo
                            app = apps.get(service_source.group_key, None)

                            bean["market_error_code"] = 200
                            bean["market_status"] = 1
                        except ServiceHandleException as e:
                            logger.debug(e)
                            bean["market_status"] = 0
                            bean["market_error_code"] = e.error_code
                            bean["version"] = service_source.version
                            bean["app_version"] = service_source.version
                            build_infos[service.service_id] = bean
                            continue

                        bean["install_from_cloud"] = True
                        bean["app_detail_url"] = app.describe

                if not app:
                    app = app_repo.get_wutong_app_qs_by_key(session, tenant.enterprise_id, service_source.group_key)
                    if not app:
                        logger.warning("not found app {0} version {1} in local market".format(
                            service_source.group_key, service_source.version))

                if app:
                    bean["rain_app_name"] = app.app_name
                    bean["details"] = app.details
                    bean["group_key"] = app.app_id
                    bean["app_version"] = service_source.version
                    bean["version"] = service_source.version
            build_infos[service.service_id] = bean
        return build_infos

    def get_not_run_services_request_memory(self, session: SessionClass, tenant, services):
        if not services or len(services) == 0:
            return 0
        not_run_service_ids = []
        memory = 0
        service_ids = [service.service_id for service in services]
        service_status_list = self.status_multi_service(session=session, region=services[0].service_region,
                                                        tenant_name=tenant.tenant_name,
                                                        service_ids=service_ids,
                                                        enterprise_id=tenant.enterprise_id)
        if service_status_list:
            for status_map in service_status_list:
                if status_map.get("status") in ["undeploy", "closed"]:
                    not_run_service_ids.append(status_map.get("service_id"))
            if not_run_service_ids:
                for service in services:
                    if service.service_id in not_run_service_ids:
                        memory += int(service.min_memory) * int(service.min_node)
        return memory

    def calculate_service_cpu(self, min_memory):
        # The algorithm is obsolete
        min_cpu = int(min_memory) / 128 * 20
        return int(min_cpu)

    def get_apps_deploy_versions(self, session, region, tenant_name, service_ids):
        data = {"service_ids": service_ids}
        try:
            res, body = remote_build_client.get_team_services_deploy_version(session, region, tenant_name, data)
            return body["list"]
        except Exception as e:
            logger.exception(e)
            return []


class BaseTenantService(object):
    def calculate_service_cpu(self, region, min_memory):
        # The algorithm is obsolete
        min_cpu = int(min_memory) / 128 * 20
        return int(min_cpu)


class CodeRepositoriesService(object):
    def __init__(self):
        self.MODULES = settings.MODULES

    def initRepositories(self, tenant, user, service, service_code_from, code_url, code_id, code_version):
        if service_code_from == "gitlab_new":
            if custom_config.GITLAB:
                project_id = 0
                if user.git_user_id > 0:
                    project_id = gitClient.createProject(tenant.tenant_name + "_" + service.service_alias)
                    logger.debug(project_id)
                    ts = TeamComponentInfo.objects.get(service_id=service.service_id)
                    if project_id > 0:
                        gitClient.addProjectMember(project_id, user.git_user_id, 'master')
                        gitClient.addProjectMember(project_id, 2, 'reporter')
                        ts.git_project_id = project_id
                        ts.git_url = "git@code.goodrain.com:app/" + tenant.tenant_name + "_" + service.service_alias + ".git"
                        gitClient.createWebHook(project_id)
                    ts.code_from = service_code_from
                    ts.code_version = "master"
                    ts.save()
                    self.codeCheck(ts)
        elif service_code_from == "gitlab_exit" or service_code_from == "gitlab_manual":
            ts = TeamComponentInfo.objects.get(service_id=service.service_id)
            ts.git_project_id = code_id
            ts.git_url = code_url
            ts.code_from = service_code_from
            ts.code_version = code_version
            ts.save()
            self.codeCheck(ts)
        elif service_code_from == "github":
            ts = TeamComponentInfo.objects.get(service_id=service.service_id)
            ts.git_project_id = code_id
            ts.git_url = code_url
            ts.code_from = service_code_from
            ts.code_version = code_version
            ts.save()
            code_user = code_url.split("/")[3]
            code_project_name = code_url.split("/")[4].split(".")[0]
            gitHubClient.createReposHook(code_user, code_project_name, user.github_token)
            self.codeCheck(ts)

    def codeCheck(self, service, check_type="first_check", event_id=None):
        data = {}
        data["tenant_id"] = service.tenant_id
        data["service_id"] = service.service_id
        data["git_url"] = "--branch " + service.code_version + " --depth 1 " + service.git_url
        data["check_type"] = check_type
        data["url_repos"] = service.git_url
        data['code_version'] = service.code_version
        data['git_project_id'] = int(service.git_project_id)
        data['code_from'] = service.code_from
        if event_id:
            data['event_id'] = event_id
        parsed_git_url = git_url_parse(service.git_url)
        if parsed_git_url.host == "code.goodrain.com" and service.code_from == "gitlab_new":
            gitUrl = "--branch " + service.code_version + " --depth 1 " + parsed_git_url.url2ssh
        elif parsed_git_url.host == 'github.com':
            createUser = Users.objects.get(user_id=service.creater)
            if settings.MODULES.get('Privite_Github', True):
                gitUrl = "--branch " + service.code_version + " --depth 1 " + service.git_url
            else:
                gitUrl = "--branch " + service.code_version + " --depth 1 " + parsed_git_url.url2https_token(
                    createUser.github_token)
        else:
            gitUrl = "--branch " + service.code_version + " --depth 1 " + service.git_url
        data["git_url"] = gitUrl

        task = {}
        task["tube"] = "code_check"
        task["service_id"] = service.service_id
        # task["data"] = data
        task.update(data)
        logger.debug(json.dumps(task))
        tenant = Tenants.objects.get(tenant_id=service.tenant_id)
        task["enterprise_id"] = tenant.enterprise_id
        region_api.code_check(service.service_region, tenant.tenant_name, task)

    def showGitUrl(self, service):
        httpGitUrl = service.git_url
        if service.code_from == "gitlab_new" or service.code_from == "gitlab_exit":
            cur_git_url = service.git_url.split(":")
            httpGitUrl = "http://code.goodrain.com/" + cur_git_url[1]
        elif service.code_from == "gitlab_manual":
            httpGitUrl = service.git_url
        return httpGitUrl

    def deleteProject(self, service):
        if custom_config.GITLAB:
            if service.code_from == "gitlab_new" and service.git_project_id > 0:
                gitClient.deleteProject(service.git_project_id)

    def getProjectBranches(self, project_id):
        if custom_config.GITLAB:
            return gitClient.getProjectBranches(project_id)
        return ""

    def createUser(self, user, email, password, username, name):
        if custom_config.GITLAB:
            if user.git_user_id == 0:
                logger.info("account.login", "user {0} didn't owned a gitlab user_id, will create it".format(user.nick_name))
                git_user_id = gitClient.createUser(email, password, username, name)
                if git_user_id == 0:
                    logger.info("account.gituser",
                                "create gitlab user for {0} failed, reason: got uid 0".format(user.nick_name))
                else:
                    user.git_user_id = git_user_id
                    user.save()
                    logger.info("account.gituser", "user {0} set git_user_id = {1}".format(user.nick_name, git_user_id))

    def modifyUser(self, user, password):
        if custom_config.GITLAB:
            gitClient.modifyUser(user.git_user_id, password=password)

    # def addProjectMember(self, git_project_id, git_user_id, level):
    #     if custom_config.GITLAB:
    #         gitClient.addProjectMember(git_project_id, git_user_id, level)

    def listProjectMembers(self, git_project_id):
        if custom_config.GITLAB:
            return gitClient.listProjectMembers(git_project_id)
        return ""

    def deleteProjectMember(self, project_id, git_user_id):
        if custom_config.GITLAB:
            gitClient.deleteProjectMember(project_id, git_user_id)

    def addProjectMember(self, project_id, git_user_id, gitlab_identity):
        if custom_config.GITLAB:
            gitClient.addProjectMember(project_id, git_user_id, gitlab_identity)

    def editMemberIdentity(self, project_id, git_user_id, gitlab_identity):
        if custom_config.GITLAB:
            gitClient.editMemberIdentity(project_id, git_user_id, gitlab_identity)

    def get_gitHub_access_token(self, code):
        if custom_config.GITHUB:
            return gitHubClient.get_access_token(code)
        return ""

    def getgGitHubAllRepos(self, token):
        if custom_config.GITHUB:
            return gitHubClient.getAllRepos(token)
        return ""

    def gitHub_authorize_url(self, user):
        if custom_config.GITHUB:
            return gitHubClient.authorize_url(user.pk)
        return ""

    def gitHub_ReposRefs(self, session, user, repos, token):
        custom_config.init_session(session)
        if custom_config.GITHUB:
            return gitHubClient.getReposRefs(user, repos, token)
        return ""


base_service = BaseService()
baseService = BaseTenantService()
