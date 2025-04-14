import tkinter as tk
import tkinter.ttk as ttk
import myNotebook as nb
from companion import session, Session
from os import path
from functools import partial

from .colonization import ColonizationPlugin

class PreferencesUi:
    
    PADX=10
    PADY=10

    def __init__(self, plugin:ColonizationPlugin):
        self.plugin = plugin
        self.row = 0
        self.subscribers = {}

    def plugin_prefs(self, parent, cmdr, is_beta):
        self.frame = nb.Frame(parent)
        self.frame.columnconfigure(1, weight=1)
        self.frame.grid(sticky=tk.EW)

        frame = nb.Frame(self.frame)
        frame.grid(row=self.row, sticky=tk.EW, padx=self.PADX, pady=self.PADY)
        nb.Label(frame, text="Fleet carrier call sign:").grid(row=0, column=0)
        self.FCcallsign = nb.Label(frame, text=self.plugin.carrier.callSign)
        self.FCcallsign.grid(row=0, column=1)
        nb.Label(frame, text="Fleet carrier last update:").grid(row=1, column=0)
        self.FClastupdate = nb.Label(frame, text=self.plugin.carrier.lastSync)
        self.FClastupdate.grid(row=1, column=1)
        btn = nb.Button(frame, text="Load FC data", command=self.updateFleetCarrier)
        btn.grid(row=3, columnspan = 2, sticky=tk.EW, pady=5)
        self.nextRow()
        
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).grid(row=self.row, sticky=tk.EW, padx=self.PADX)
        self.nextRow()
        
        self.constructionList = nb.Frame(self.frame)
        self.constructionList.grid(row=self.row, column=0, sticky=tk.EW, padx=self.PADX, pady=self.PADY)
        self.buildConstructionList()
        self.nextRow()
        
        return self.frame
    
    def buildConstructionList(self):
        for widget in self.constructionList.winfo_children():
            widget.destroy()
            
        row=0
        
        nb.Label(self.constructionList, text="List of tracked construction sites").grid(row=row, column=0, columnspan=2)
        row+=1
        for c in self.plugin.constructions:
            nb.Label(self.constructionList, text=c.system).grid(row=row, column=0, sticky=tk.W)
            nb.Label(self.constructionList, text=c.getName()).grid(row=row, column=1, sticky=tk.W)
            ttk.Button(self.constructionList, text="Remove from tracking", command=partial(self.removeConstruction, c)).grid(row=row, column=2, pady=2, padx=5)
            row+=1
        
            
    def nextRow(self):
        self.row += 1
        return self.row
    
    def event(self, event, tkEvent):
        if event in self.subscribers:
            self.subscribers[event](tkEvent)

    def on(self, event, function):
        self.subscribers[event] = function
        
    def removeConstruction(self, construction):
        self.plugin.removeConstruction(construction)
        self.buildConstructionList()
        
    def updateFC(self, carrier):
        self.FCcallsign['text'] = str(carrier.callSign)
        self.FClastupdate['text'] = str(carrier.lastSync)
        
    def updateFleetCarrier(self):
        if session.state == Session.STATE_OK:
            self.FClastupdate['text'] = "Updating..."
            carrier = session.requests_session.get(session.capi_host_for_galaxy() + session.FRONTIER_CAPI_PATH_FLEETCARRIER)
            data = carrier.json()
            self.plugin.capi_fleetcarrier(data)
            if self.plugin.carrier and self.plugin.carrier.callSign:
                self.FCcallsign['text'] = str(self.plugin.carrier.callSign)
                self.FClastupdate['text'] = str(self.plugin.carrier.lastSync)
            else:
                self.FClastupdate['text'] = "Missing Fleet Carrier data"
        else:
            self.FClastupdate['text'] = "cAPI session is not open."