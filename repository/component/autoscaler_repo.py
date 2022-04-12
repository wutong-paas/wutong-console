from sqlalchemy import select, update, delete

from database.session import SessionClass
from models.component.models import AutoscalerRules, AutoscalerRuleMetrics
from repository.base import BaseRepository


class AutoscalerRulesRepository(BaseRepository[AutoscalerRules]):
    def update(self, session, rule_id, **data):
        session.execute(update(AutoscalerRules).where(
            AutoscalerRules.rule_id == rule_id
        ).values(**data))
        session.flush()
        return session.execute(select(AutoscalerRules).where(
            AutoscalerRules.rule_id == rule_id
        )).scalars().first()

    def get_by_rule_id(self, session, rule_id):
        return (session.execute(select(AutoscalerRules).where(
            AutoscalerRules.rule_id == rule_id))).scalars().first()

    def list_by_service_id(self, session: SessionClass, service_id):
        return (session.execute(select(AutoscalerRules).where(
            AutoscalerRules.service_id == service_id))).scalars().all()


class AutoscalerRuleMetricsRepository(BaseRepository[AutoscalerRuleMetrics]):
    def bulk_create(self, session, data):
        metrics = []
        for item in data:
            metrics.append(
                AutoscalerRuleMetrics(
                    rule_id=item["rule_id"],
                    metric_type=item["metric_type"],
                    metric_name=item["metric_name"],
                    metric_target_type=item["metric_target_type"],
                    metric_target_value=item["metric_target_value"],
                ))
        return session.add_all(metrics)

    def delete_by_rule_id(self, session, rule_id):
        session.execute(delete(AutoscalerRuleMetrics).where(
            AutoscalerRuleMetrics.rule_id == rule_id
        ))
        session.flush()

    def list_by_rule_ids(self, session: SessionClass, rule_ids):
        return (session.execute(select(AutoscalerRuleMetrics).where(
            AutoscalerRuleMetrics.rule_id.in_(rule_ids)))).scalars().all()


autoscaler_rules_repo = AutoscalerRulesRepository(AutoscalerRules)
autoscaler_rule_metrics_repo = AutoscalerRuleMetricsRepository(AutoscalerRuleMetrics)
