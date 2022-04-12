# -*- coding: utf-8 -*-
from sqlalchemy import select

from exceptions.bcode import ErrAppSnapshotNotFound, ErrAppSnapshotExists
from models.application.models import ApplicationUpgradeSnapshot


class AppSnapshotRepo(object):
    @staticmethod
    def get_by_snapshot_id(session, snapshot_id):
        auss = session.execute(select(ApplicationUpgradeSnapshot).where(
            ApplicationUpgradeSnapshot.snapshot_id == snapshot_id
        )).scalars().all()
        if not auss:
            raise ErrAppSnapshotNotFound
        return auss

    def create(self, session, snapshot: ApplicationUpgradeSnapshot):
        try:
            self.get_by_snapshot_id(session, snapshot.snapshot_id)
            raise ErrAppSnapshotExists
        except ErrAppSnapshotNotFound:
            snapshot.save()
            return snapshot


app_snapshot_repo = AppSnapshotRepo()
