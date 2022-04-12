# -*- coding: utf8 -*-
from core.utils.constants import PluginImage


# todo 删除
def is_slug(image, lang):
    return image.startswith('goodrain.me/runner') or image.startswith(PluginImage.RUNNER) \
           and lang not in ("dockerfile", "docker")
