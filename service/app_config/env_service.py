from database.session import SessionClass
from models.component.models import TeamComponentEnv
from repository.component.env_var_repo import env_var_repo


class AppEnvVarService(object):
    def get_env_by_container_port(self, session: SessionClass, tenant, service, container_port):
        return env_var_repo.get_service_env_by_port(tenant.tenant_id, service.service_id, container_port)

    def get_self_define_env(self, session: SessionClass, service, scopes, is_change, attr_names):
        if service:
            return env_var_repo.get_service_env(session, service.tenant_id, service.service_id,
                                                scopes, is_change, attr_names, 1, "outer")


class AppEnvService(object):

    @staticmethod
    def get_service_default_env_by_language(language):
        """
        根据指定的语言找到默认的环境变量
        :param language:  语言
        :return: 语言对应的默认的环境变量
        """
        checkJson = {}
        if language == "dockerfile":
            checkJson["language"] = 'dockerfile'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Python":
            checkJson["language"] = 'Python'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Ruby":
            checkJson["language"] = 'Ruby'
            checkJson["runtimes"] = "2.0.0"
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "PHP":
            checkJson["language"] = 'PHP'
            checkJson["runtimes"] = "5.6.11"
            checkJson["procfile"] = "apache"
            dependencies = {}
            checkJson["dependencies"] = dependencies
        elif language == "Java-maven":
            checkJson["language"] = 'Java-maven'
            checkJson["runtimes"] = "1.8"
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Java-war":
            checkJson["language"] = 'Java-war'
            checkJson["runtimes"] = "1.8"
            checkJson["procfile"] = "tomcat7"
            checkJson["dependencies"] = {}
        elif language == "Java-jar":
            checkJson["language"] = 'Java-jar'
            checkJson["runtimes"] = "1.8"
            checkJson["procfile"] = "tomcat7"
            checkJson["dependencies"] = {}
        elif language == "Node.js":
            checkJson["language"] = 'Node.js'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "static":
            checkJson["language"] = 'static'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = "apache"
            checkJson["dependencies"] = {}
        elif language == "Clojure":
            checkJson["language"] = 'Clojure'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Go":
            checkJson["language"] = 'Go'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Gradle":
            checkJson["language"] = 'Gradle'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Play":
            checkJson["language"] = 'Play'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Grails":
            checkJson["language"] = 'Grails'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        elif language == "Scala":
            checkJson["language"] = 'Scala'
            checkJson["runtimes"] = ""
            checkJson["procfile"] = ""
            checkJson["dependencies"] = {}
        return checkJson

    def save_compile_env(self, session: SessionClass, service, language, check_dependency, user_dependency):
        params = {
            "service_id": service.service_id,
            "language": language,
            "check_dependency": check_dependency,
            "user_dependency": user_dependency
        }
        add_model: TeamComponentEnv = TeamComponentEnv(**params)
        session.add(add_model)
        
        return add_model


compile_env_service = AppEnvService()
env_var_service = AppEnvVarService()
