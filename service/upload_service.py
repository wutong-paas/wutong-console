import imghdr
import os

from loguru import logger

from core.setting import settings
from core.utils.crypt import make_uuid
from exceptions.exceptions import LogoFormatError, LogoSizeError


class FileUploadService(object):
    async def upload_file(self, upload_file, suffix):
        """
        文件上传

        :param upload_file:
        :param suffix:
        :return:
        """
        file_url = await self.upload_file_to_local(upload_file, suffix)
        return file_url

    @staticmethod
    async def upload_file_to_local(upload_file, suffix):
        """
        上传文件至本地

        :param upload_file:
        :param suffix:
        :return:
        """
        try:
            prefix_file_path = '{0}/uploads'.format(settings.MEDIA_ROOT)
            if not os.path.exists(prefix_file_path):
                os.makedirs(prefix_file_path)
        except Exception as e:
            logger.exception(e)
        filename = 'uploads/{0}.{1}'.format(make_uuid(), suffix)
        save_filename = os.path.join(settings.MEDIA_ROOT, filename)
        query_filename = os.path.join(settings.MEDIA_URL, filename)

        res = await upload_file.read()

        if len(res) > 1048576 * 2:
            raise LogoSizeError

        with open(save_filename, "wb+") as destination:
            destination.write(res)

        image_type = imghdr.what(save_filename)
        if image_type not in {"jpeg", "jpg", "pjpeg", "jfif", "png", "pjp"}:
            os.remove(save_filename)
            raise LogoFormatError
        return query_filename


upload_service = FileUploadService()
