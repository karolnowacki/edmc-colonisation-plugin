import sys
import logging
import tkinter as tk
import myNotebook as nb
from time import time
from os import path 
from EDMCLogging import get_main_logger
from config import config

from colonization.colonization import ColonizationPlugin
from colonization.ui import MainUi
from colonization.preferencesui import PreferencesUi

this = sys.modules[__name__] 

logger = get_main_logger()

def plugin_start3(plugin_dir):
    this.plugin = ColonizationPlugin()
    this.plugin.plugin_start3(plugin_dir)
    return "ColonizationPlugin"

def cmdr_data(data, is_beta):
    this.plugin.cmdr_data(data, is_beta)

def journal_entry(cmdr, is_beta, system, station, entry, state):
    this.plugin.journal_entry(cmdr, is_beta, system, station, entry, state)

def plugin_prefs(parent, cmdr, is_beta):
    this.prefs = PreferencesUi(this.plugin)
    frame = nb.Frame(parent)
    this.prefs.plugin_prefs(frame, cmdr, is_beta).grid(row=0, column=0, sticky=tk.EW)
    return frame

def prefs_changed(cmdr, is_beta):
    config.set("colonization.ignoreFCUpdate", this.prefs.ignoreFCUpdate.get())
    this.plugin.updateDisplay()

def capi_fleetcarrier(data):
    if config.get_bool("colonization.ignoreFCUpdate"):
        return
    this.plugin.capi_fleetcarrier(data)

def plugin_app(parent):
    this.ui = MainUi()
    this.plugin.setupUi(this.ui)
    ui = this.ui.plugin_app(parent)
    this.plugin.updateDisplay()
    return ui