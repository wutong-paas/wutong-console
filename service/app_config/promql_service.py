# -*- coding: utf8 -*-
import os
import platform
import subprocess
from loguru import logger
from exceptions.main import AbortRequest
from core.setting import settings

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


class PromQLService(object):
    @staticmethod
    def add_or_update_label(component_id, promql):
        """
        Add service_id label, or replace illegal service_id label
        """
        promql_parser = settings.BASE_DIR + "/bin/" + platform.system().lower() + "/promql-parser"
        c = subprocess.Popen([os.getenv("PROMQL_PARSER", promql_parser), "--component_id", component_id],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             env={'PROMQL': promql})
        new_promql, err = c.communicate()
        if not new_promql:
            logger.warning("ensure service id for promql({}): {}".format(promql, err))
            raise AbortRequest("invalid promql", "非法的 prometheus 查询语句")
        return new_promql.decode('UTF-8')


promql_service = PromQLService()
