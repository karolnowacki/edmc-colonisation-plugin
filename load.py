import sys
from colonization.config import Config

from colonization.colonization import ColonizationPlugin
from colonization.ui import MainUi
from colonization.preferencesui import PreferencesUi

this = sys.modules[__name__]


def plugin_start3(plugin_dir):
    this.plugin = ColonizationPlugin()  # type: ignore
    this.plugin.plugin_start3(plugin_dir)
    return "ColonizationPlugin"


def cmdr_data(data, is_beta) -> None:
    this.plugin.cmdr_data(data, is_beta)


def journal_entry(cmdr, is_beta, system, station, entry, state):
    return this.plugin.journal_entry(cmdr, is_beta, system, station, entry, state)


def plugin_prefs(parent, cmdr, is_beta):
    this.prefs = PreferencesUi(this.plugin)
    return this.prefs.plugin_prefs(parent, cmdr, is_beta)  # .grid(row=0, column=0, sticky=tk.EW)


def prefs_changed(cmdr, is_beta):
    this.prefs.prefs_changed(cmdr, is_beta)


def capi_fleetcarrier(data):
    if Config.IGNORE_FC_UPDATE.get():
        return
    this.plugin.capi_fleetcarrier(data)


def plugin_app(parent):
    this.ui = MainUi()
    this.plugin.setup_ui(this.ui)
    ui = this.ui.plugin_app(parent)
    this.plugin.update_display()
    return ui
