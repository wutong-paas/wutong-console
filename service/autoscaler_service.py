from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError

from clients.remote_build_client import remote_build_client
from core.utils.crypt import make_uuid
from database.session import SessionClass
from exceptions.exceptions import ErrDuplicateMetrics, ErrAutoscalerRuleNotFound
from models.component.models import AutoscalerRules, AutoscalerRuleMetrics
from repository.component.autoscaler_repo import autoscaler_rules_repo, autoscaler_rule_metrics_repo


class AutoscalerService(object):
    def update_autoscaler_rule(self, session, region_name, tenant_env, service_alias, rule_id, data, user_name=''):
        # create autoscaler rule
        autoscaler_rule = {
            "xpa_type": data["xpa_type"],
            "enable": data["enable"],
            "min_replicas": data["min_replicas"],
            "max_replicas": data["max_replicas"],
        }
        autoscaler_rule = autoscaler_rules_repo.update(session, rule_id, **autoscaler_rule)
        if not autoscaler_rule:
            raise ErrAutoscalerRuleNotFound
        autoscaler_rule = jsonable_encoder(autoscaler_rule)

        # delete old autoscaler rule metrics
        autoscaler_rule_metrics_repo.delete_by_rule_id(session, rule_id)
        # create new ones
        metrics = []
        for metric in data["metrics"]:
            metrics.append({
                "rule_id": autoscaler_rule["rule_id"],
                "metric_type": metric["metric_type"],
                "metric_name": metric["metric_name"],
                "metric_target_type": metric["metric_target_type"],
                "metric_target_value": metric["metric_target_value"],
            })

        try:
            autoscaler_rule_metrics_repo.bulk_create(session, metrics)
        except IntegrityError:
            raise ErrDuplicateMetrics

        autoscaler_rule["metrics"] = metrics
        autoscaler_rule["operator"] = user_name

        remote_build_client.update_xpa_rule(session, region_name, tenant_env, service_alias, data=autoscaler_rule)

        return autoscaler_rule

    def get_by_rule_id(self, session, rule_id):
        rule = autoscaler_rules_repo.get_by_rule_id(session, rule_id)
        metrics = autoscaler_rule_metrics_repo.list_by_rule_ids(session, [rule.rule_id])
        if not metrics:
            raise ErrAutoscalerRuleNotFound
        res = jsonable_encoder(rule)
        res["metrics"] = [jsonable_encoder(m) for m in metrics]
        return res

    def create_autoscaler_rule(self, session, region_name, tenant_env, service_alias, data, user_name):
        # create autoscaler rule
        autoscaler_rule = {
            "rule_id": make_uuid(),
            "service_id": data["service_id"],
            "xpa_type": data["xpa_type"],
            "enable": data["enable"],
            "min_replicas": data["min_replicas"],
            "max_replicas": data["max_replicas"],
        }
        asr = AutoscalerRules(**autoscaler_rule)
        session.add(asr)

        # create autoscaler rule metrics
        metrics = []
        for metric in data["metrics"]:
            metrics.append({
                "rule_id": autoscaler_rule["rule_id"],
                "metric_type": metric["metric_type"],
                "metric_name": metric["metric_name"],
                "metric_target_type": metric["metric_target_type"],
                "metric_target_value": metric["metric_target_value"],
            })

        try:
            metrics_list = []
            for metric in metrics:
                metrics_list.append(AutoscalerRuleMetrics(**metric))
            session.add_all(metrics_list)

        except IntegrityError:
            raise ErrDuplicateMetrics

        autoscaler_rule["metrics"] = metrics
        autoscaler_rule["operator"] = user_name

        remote_build_client.create_xpa_rule(session, region_name, tenant_env, service_alias, data=autoscaler_rule)
        return autoscaler_rule

    def list_autoscaler_rules(self, session: SessionClass, service_id):
        rules = autoscaler_rules_repo.list_by_service_id(session, service_id)
        rule_ids = [rule.rule_id for rule in rules]

        metrics = autoscaler_rule_metrics_repo.list_by_rule_ids(session, rule_ids)
        # rule to metrics
        r2m = {}
        for metric in metrics:
            metric = jsonable_encoder(metric)
            if r2m.get(metric["rule_id"], None) is None:
                r2m[metric["rule_id"]] = [metric]
            else:
                r2m[metric["rule_id"]].append(metric)

        res = []
        for rule in rules:
            r = jsonable_encoder(rule)
            r["metrics"] = []
            if r2m.get(rule.rule_id, None) is not None:
                m = r2m[rule.rule_id]
                r["metrics"] = m
            res.append(r)

        return res


class ScalingRecordsService(object):
    def list_scaling_records(self, session: SessionClass, region_name, tenant_env, service_alias, page=None,
                             page_size=None):
        body = remote_build_client.list_scaling_records(session, region_name, tenant_env, service_alias, page,
                                                        page_size)
        return body["bean"]


autoscaler_service = AutoscalerService()
scaling_records_service = ScalingRecordsService()
