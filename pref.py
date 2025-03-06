import tkinter as tk
import tkinter.ttk as ttk
import myNotebook as nb
from os import path
from functools import partial

from colonization.colonization import ColonizationPlugin
from colonization.requirements import requirements

class PreferencesUi:

    def __init__(self, config, plugin:ColonizationPlugin):
        self.config = config
        self.plugin = plugin
        self.row = 0
        self.subscribers = {}

    def plugin_prefs(self, parent, cmdr, is_beta):
        self.frame = nb.Frame(parent)

        btn = nb.Button(self.frame, text="Load FC data", command=partial(self.event, 'forceFCload', None))
        btn.grid(row=self.row, column=0)
        self.nextRow()
        
        for c in self.plugin.constructions:
            nb.Label(self.frame, text=c.name).grid(row=self.row, column=0)
            nb.Label(self.frame, text=c.stationName).grid(row=self.row, column=1)
            if c.marketId:
                nb.Button(self.frame, text="Unbind", command=partial(self.plugin.unbindStation, c.marketId)).grid(row=self.row, column=2)
            self.nextRow()
         
        nb.Label(self.frame, text="Add construction").grid(row=self.row, column=0)
        constType = tk.StringVar()
        ttk.Combobox(self.frame, textvariable=constType, width=40, values=requirements.types()).grid(row=self.row, column=1)
        constName = tk.StringVar()
        nb.EntryMenu(self.frame, textvariable=constName).grid(row=self.row, column=2)
        nb.Button(self.frame, text="Add", command=partial(self.addConstruction, constName, constType)).grid(row=self.row, column=3)
        
        return self.frame
    
    def event(self, event, tkEvent):
        if event in self.subscribers:
            self.subscribers[event](tkEvent)

    def on(self, event, function):
        self.subscribers[event] = function
        
    def nextRow(self):
        self.row += 1
        
    def addConstruction(self, constName, constType):
        self.plugin.addConstruction(constName.get(), constType.get())
    