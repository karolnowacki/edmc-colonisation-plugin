import sys
import logging
import tkinter as tk
import myNotebook as nb
from config import config
from companion import CAPIData, session
from time import time
from os import path 
from EDMCLogging import get_main_logger

from colonization.colonization import ColonizationPlugin
from ui import MainUi
from pref import PreferencesUi

this = sys.modules[__name__] 
this.ROWS = 25

logger = get_main_logger()

def plugin_start3(plugin_dir):
    this.plugin = ColonizationPlugin(config)
    this.plugin.plugin_start3(plugin_dir)
    this.ui = None
    return "ColonizationPlugin"

def cmdr_data(data: CAPIData, is_beta: bool):
    this.plugin.cmdr_data(data, is_beta)

def journal_entry(cmdr, is_beta, system, station, entry, state):
    this.plugin.journal_entry(cmdr, is_beta, system, station, entry, state)
    if entry['event'] in ("StartUp", "LoadGame"):
        query_time = int(time())
        session.fleetcarrier(query_time=query_time)

def plugin_prefs(parent, cmdr, is_beta):
    this.pref = PreferencesUi(config, this.plugin)
    frame = nb.Frame(parent)
    this.pref.plugin_prefs(frame, cmdr, is_beta).grid(row=0, column=0, sticky=tk.W)
    this.pref.on('forceFCload', forceFCload)
    return frame

def prefs_changed(cmdr, is_beta):
    this.plugin.updateDisplay()

def capi_fleetcarrier(data):
    this.plugin.capi_fleetcarrier(data)

def forceFCload(event):
    r = session.requests_session.get(session.capi_host_for_galaxy() + session.FRONTIER_CAPI_PATH_FLEETCARRIER)
    this.plugin.capi_fleetcarrier(r.json())
    this.pref.updateFC(this.plugin.carrier)

def plugin_app(parent):
    this.ui = MainUi(config)
    this.plugin.setUi(this.ui)
    ui = this.ui.plugin_app(parent)
    ui.grid(row=1, column=0)
    this.plugin.updateDisplay()
    return ui