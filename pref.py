import tkinter as tk
import tkinter.ttk as ttk
import myNotebook as nb
from os import path
from functools import partial

from colonization.colonization import ColonizationPlugin
from colonization.requirements import requirements
from colonization.construction import Construction

class PreferencesUi:

    def __init__(self, config, plugin:ColonizationPlugin):
        self.config = config
        self.plugin = plugin
        self.row = 0
        self.subscribers = {}

    def plugin_prefs(self, parent, cmdr, is_beta):
        self.frame = nb.Frame(parent)
        self.frame.columnconfigure(1, weight=1)
        self.frame.grid(sticky=tk.EW)

        frame = nb.Frame(self.frame)
        frame.grid(row=self.row, sticky=tk.EW)
        nb.Label(frame, text="Fleet carrier call sign:").grid(row=0, column=0)
        self.FCcallsign = nb.Label(frame, text=self.plugin.carrier.callSign)
        self.FCcallsign.grid(row=0, column=1)
        nb.Label(frame, text="Fleet carrier last update:").grid(row=1, column=0)
        self.FClastupdate = nb.Label(frame, text=self.plugin.carrier.lastSync)
        self.FClastupdate.grid(row=1, column=1)
        btn = nb.Button(frame, text="Load FC data", command=partial(self.event, 'forceFCload', None))
        btn.grid(row=3, columnspan = 2, sticky=tk.EW)
        self.nextRow()
        
        self.constructionList = nb.Frame(self.frame)
        self.constructionList.grid(row=self.row, column=0, sticky=tk.EW)
        self.buildConstructionList()
        self.nextRow()
         
        frame = nb.Frame(self.frame)
        frame.grid(row=self.row, sticky=tk.EW)
        nb.Label(frame, text="Add construction:").grid(row=0, column=0)
        constType = tk.StringVar()
        ttk.Combobox(frame, textvariable=constType, width=40, values=requirements.types(), state="readonly").grid(row=0, column=1)
        nb.Label(frame, text="Name:").grid(row=0, column=2)
        constName = tk.StringVar()
        nb.EntryMenu(frame, textvariable=constName).grid(row=0, column=3)
        nb.Button(frame, text="Add", command=partial(self.addConstruction, constName, constType)).grid(row=0, column=4)
        self.nextRow()
        
        ttk.Separator(self.frame, orient=tk.HORIZONTAL).grid(row=self.row, pady=8, sticky=tk.EW)
        self.nextRow()
        
        frame = nb.Frame(self.frame)
        frame.grid(row=self.row, sticky=tk.EW)
        
        self.canvas = tk.Canvas(frame, bg='white', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar = tk.Scrollbar(frame, command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.canvas.configure(yscrollcommand = scrollbar.set, height=300, width=500, border=0)
        self.editFrame = nb.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.editFrame, anchor='nw')
        self.savebtn=nb.Button(frame, text="Save", command=self.saveConstruction, state=tk.DISABLED)
        self.savebtn.grid(row=1, column=0, sticky=tk.E)
        self.nextRow()
        
        return self.frame
    
    def buildConstructionList(self):
        for widget in self.constructionList.winfo_children():
            widget.destroy()
            
        row=0
        
        nb.Label(self.constructionList, text="Name").grid(row=row, column=0)
        nb.Label(self.constructionList, text="Bind Construction Site").grid(row=row, column=1)
        row+=1
        for c in self.plugin.constructions:
            nb.Label(self.constructionList, text=c.name).grid(row=row, column=0, sticky=tk.W)
            nb.Label(self.constructionList, text=c.stationName).grid(row=row, column=1, sticky=tk.W)
            if c.marketId:
                nb.Button(self.constructionList, text="Unbind", command=partial(self.plugin.unbindStation, c.marketId)).grid(row=row, column=2)
            ttk.Button(self.constructionList, text="Edit", command=partial(self.editConstruction, c)).grid(row=row, column=3)
            ttk.Button(self.constructionList, text="Remove", command=partial(self.removeConstruction, c)).grid(row=row, column=4)
            row+=1
        
            
    def nextRow(self):
        self.row += 1
        return self.row
    
    def event(self, event, tkEvent):
        if event in self.subscribers:
            self.subscribers[event](tkEvent)

    def on(self, event, function):
        self.subscribers[event] = function
        

        
    def addConstruction(self, constName, constType):
        self.plugin.addConstruction(constName.get(), constType.get())
        self.buildConstructionList()
        constName.set("")
        constType.set("")
        
    def removeConstruction(self, construction):
        self.plugin.removeConstruction(construction)
        self.buildConstructionList()
        for widget in self.editFrame.winfo_children():
            widget.destroy()
        self.savebtn.configure(state=tk.DISABLED)
        
    def editConstruction(self, construction:Construction):
        for widget in self.editFrame.winfo_children():
            widget.destroy()
            
        self.editedConstruction = construction
        
        row=0
        nb.Label(self.editFrame, text="Name:").grid(row=row, column=0, sticky=tk.E)
        self.editConstructionName = tk.StringVar(value=construction.name)
        nb.EntryMenu(self.editFrame, textvariable=self.editConstructionName, width=40).grid(row=row, column=1, sticky=tk.W)
        row+=1
        nb.Label(self.editFrame, text="Bind station:").grid(row=row, column=0, sticky=tk.E)
        nb.Label(self.editFrame, text=construction.stationName).grid(row=row, column=1, sticky=tk.W)
        row+=1
        nb.Label(self.editFrame, text="System:").grid(row=row, column=0, sticky=tk.E)
        nb.Label(self.editFrame, text=construction.system).grid(row=row, column=1, sticky=tk.W)
        row+=1
        nb.Label(self.editFrame, text="MarketID:").grid(row=row, column=0, sticky=tk.E)
        nb.Label(self.editFrame, text=construction.marketId).grid(row=row, column=1, sticky=tk.W)
        row+=1
        nb.Label(self.editFrame, text="Commodity:").grid(row=row, column=0)
        nb.Label(self.editFrame, text="Required amount:").grid(row=row, column=1)
        row+=1
        self.editCommodities = dict()
        for commodity in requirements.commodities:
            nb.Label(self.editFrame, text=self.plugin.commodityMap.get(commodity, commodity)).grid(row=row, column=0)
            self.editCommodities[commodity] = tk.IntVar(value=construction.needed.get(commodity, 0))
            nb.EntryMenu(self.editFrame, textvariable=self.editCommodities[commodity]).grid(row=row, column=1)
            row+=1
        self.editFrame.update()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self.savebtn.configure(state=tk.ACTIVE)
        
    def saveConstruction(self):
        self.editedConstruction.name = self.editConstructionName.get()
        self.editedConstruction.needed = dict()
        for commodity, qty in self.editCommodities.items():
            qty = int(qty.get())
            if qty > 0:
                self.editedConstruction.needed[commodity] = qty
        self.plugin.save()
        for widget in self.editFrame.winfo_children():
            widget.destroy()
        self.savebtn.configure(state=tk.DISABLED)
        self.buildConstructionList()
        
    def updateFC(self, carrier):
        self.FCcallsign['text'] = str(carrier.callSign)
        self.FClastupdate['text'] = str(carrier.lastSync)