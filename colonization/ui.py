import tkinter as tk
from os import path
from functools import partial
from enum import Enum

from theme import theme

class ViewMode(Enum):
    FULL = 0
    FILTERED = 1

class MainUi:
    ROWS = 35
    iconDir = path.join(path.dirname(__file__), "../icons")
    
    def __init__(self):
        self.row = 0
        self.icons = {}
        self.icons['left_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "left_arrow.gif"))
        self.icons['right_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "right_arrow.gif"))
        self.icons['view_open'] = tk.PhotoImage(file=path.join(self.iconDir, "view_open.gif"))
        self.icons['view_close'] = tk.PhotoImage(file=path.join(self.iconDir, "view_close.gif"))
        self.rows = None
        self.subscribers = {}
        self.title = None
        self.station = None
        self.track_btn = None
        self.prev_btn = None
        self.next_btn = None
        self.view_btn = None
        self.view_mode:ViewMode = ViewMode.FULL
        
    def nextRow(self):
        self.row+=1

    def plugin_app(self, parent:tk.Widget) -> tk.Widget:
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.grid(sticky=tk.EW)
        
        frame = tk.Frame(self.frame)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=0, column=0, sticky=tk.EW)

        tk.Label(frame, text="Colonization:", anchor=tk.W).grid(row=0, column=0, sticky=tk.W)
        
        self.prev_btn = tk.Label(frame, image=self.icons['left_arrow'], cursor="hand2")
        self.prev_btn.bind("<Button-1>", partial(self.event, "prev"))
        self.prev_btn.grid(row=0, column=1, sticky=tk.W)
        
        self.title = tk.Label(frame, text="Total", justify=tk.CENTER, anchor=tk.CENTER)
        self.title.grid(row=0, column=2, sticky=tk.EW)
        
        self.next_btn = tk.Label(frame, image=self.icons['right_arrow'], cursor="hand2")
        self.next_btn.bind("<Button-1>", partial(self.event, "next"))
        self.next_btn.grid(row=0, column=3, sticky=tk.W)
        
        self.view_btn = tk.Label(frame, image=self.icons['view_close'], cursor="hand2")
        self.view_btn.bind("<Button-1>", self.changeView)
        self.view_btn.grid(row=0, column=4, sticky=tk.E)

        self.station = tk.Label(frame, text="Loading...", justify=tk.CENTER)
        self.station.grid(row=1, column=0, columnspan=5, sticky=tk.EW)
        
        self.track_btn = tk.Button(frame, text="Track this construction", command=partial(self.event, "track", None))
        self.track_btn.grid(row=2, column=0, sticky=tk.EW, columnspan=5)

        self.table_frame = tk.Frame(self.frame, highlightthickness=1)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.grid(row=1, column=0, sticky=tk.EW)

        tk.Label(self.table_frame, text="Commodity").grid(row=0, column=0)
        tk.Label(self.table_frame, text="Need").grid(row=0, column=1)
        tk.Label(self.table_frame, text="Cargo").grid(row=0, column=2)
        tk.Label(self.table_frame, text="FleetCarrier").grid(row=0, column=3)

        self.rows = list()
        for i in range(self.ROWS):
            labels = {}
            labels['name'] = tk.Label(self.table_frame, justify=tk.LEFT)
            labels['name'].grid_configure(sticky=tk.W)
            labels['name'].grid_remove()
            labels['needed'] = tk.Label(self.table_frame)
            labels['needed'].grid_remove()
            labels['cargo'] = tk.Label(self.table_frame)
            labels['cargo'].grid_remove()
            labels['carrier'] = tk.Label(self.table_frame)
            labels['carrier'].grid_remove()
            self.rows.append(labels)

        return self.frame
    
    def event(self, event, tkEvent):
        if event in self.subscribers:
            self.subscribers[event](tkEvent)

    def on(self, event, function):
        self.subscribers[event] = function
        
    def changeView(self, event):
        if (self.view_mode == ViewMode.FULL):
            self.view_btn['image'] = self.icons['view_open']
            self.view_mode = ViewMode.FILTERED
        elif (self.view_mode == ViewMode.FILTERED):
            self.view_btn['image'] = self.icons['view_close']
            self.view_mode = ViewMode.FULL
        self.event('update', None)
        

    def setTitle(self, title):
        if self.title:
            self.title['text'] = title

    def setTable(self, table, docked):
        if not self.rows:
            return
        row = 0
        for i in table:
            if i['needed'] <= 0:
                continue
            
            toBuy = i['needed']-i['cargo']-i['carrier']
            
            if (self.view_mode == ViewMode.FILTERED and not docked):
                if (not i['available']):
                    continue
                if (toBuy <= 0):
                    continue
            if (self.view_mode == ViewMode.FILTERED and docked == "carrier"):
                if (toBuy <= 0):
                    continue
                
            if (row >= self.ROWS):
                break

            self.rows[row]['name']['text'] = i['commodityName']            
            if (i['cargo'] > 0 or i['carrier'] > 0):
                self.rows[row]['needed']['text'] = "{} ({})".format(i['needed'], toBuy)
            else:
                self.rows[row]['needed']['text'] = i['needed']
            self.rows[row]['cargo']['text'] = i['cargo']
            self.rows[row]['carrier']['text'] = i['carrier']

            self.rows[row]['name'].grid(row=row+1, column=0)
            self.rows[row]['needed'].grid(row=row+1, column=1)
            self.rows[row]['cargo'].grid(row=row+1, column=2)
            self.rows[row]['carrier'].grid(row=row+1, column=3)
            
            if (toBuy <= 0):
                self.rows[row]['name']['fg'] = 'green'
                self.rows[row]['needed']['fg'] = 'green'
                self.rows[row]['cargo']['fg'] = 'green'
                self.rows[row]['carrier']['fg'] = 'green'
            elif theme.current:
                if i['available']:
                    self.rows[row]['name']['fg'] = theme.current['highlight']
                else:
                    self.rows[row]['name']['fg'] = theme.current['foreground']
                self.rows[row]['needed']['fg'] = theme.current['foreground']
                self.rows[row]['cargo']['fg'] = theme.current['foreground']
                self.rows[row]['carrier']['fg'] = theme.current['foreground']
            row+=1

        for i in range(row, self.ROWS):
            self.rows[i]['name'].grid_remove()
            self.rows[i]['needed'].grid_remove()
            self.rows[i]['cargo'].grid_remove()
            self.rows[i]['carrier'].grid_remove()
        

        if (row == 0):
            self.table_frame.grid_remove()
        else:
            self.table_frame.grid()
        

    def setStation(self, station, color=None):
        if self.station and theme.current:
            self.station['text'] = str(station)
            if color:
                self.station['fg'] = color
            elif theme.current:
                self.station['fg'] = theme.current['foreground']