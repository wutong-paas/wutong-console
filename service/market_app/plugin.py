# -*- coding: utf-8 -*-
from models.application.plugin import TeamPlugin, PluginBuildVersion


class Plugin(object):
    def __init__(self,
                 plugin: TeamPlugin,
                 build_version: PluginBuildVersion,
                 config_groups=None,
                 config_items=None,
                 plugin_image=None):
        self.plugin = plugin
        self.build_version = build_version
        self.config_groups = config_groups
        self.config_items = config_items
        self.plugin_image = plugin_image
