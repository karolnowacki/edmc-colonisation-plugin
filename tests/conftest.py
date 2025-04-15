import sys
import pathlib
import logging

def nop():
    pass

class Config(dict):
    def __getattr__(self, key):
        return self[key]
    def __setattr__(self, key, value):
        self[key] = value

module = type(sys)("EDMCLogging")
module.get_main_logger = logging.getLogger
sys.modules["EDMCLogging"] = module

module = type(sys)("theme")
module.theme = nop
sys.modules["theme"] = module

module = type(sys)("monitor")
module.monitor = nop
sys.modules["monitor"] = module

module = type(sys)("config")
module.config = Config()
module.config.app_dir_path = pathlib.Path('%LocalAppData%\\EDMarketConnector')
sys.modules["config"] = module
sys.modules["config.config"] = module.config
