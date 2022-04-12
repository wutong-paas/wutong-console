import base64
import pickle
import random
import string

from database.session import SessionClass
from models.component.models import DeployRelation
from repository.base import BaseRepository


class DeployRepo(BaseRepository[DeployRelation]):

    def get_service_key_by_service_id(self, session: SessionClass, service_id):
        return session.query(DeployRelation).filter(
            DeployRelation.service_id == service_id).first()

    def get_deploy_relation_by_service_id(self, session: SessionClass, service_id):
        secret_obj = session.query(DeployRelation).filter(
            DeployRelation.service_id == service_id).all()

        if not secret_obj:
            secretkey = ''.join(random.sample(string.ascii_letters + string.digits, 8))
            pwd = base64.b64encode(pickle.dumps({"secret_key": secretkey}))
            deploy = DeployRelation(service_id=service_id, secret_key=pwd, key_type="")
            session.add(deploy)
            secret_key = deploy.secret_key
            return secret_key
        else:
            return secret_obj[0].secret_key


deploy_repo = DeployRepo(DeployRelation)
