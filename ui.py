import tkinter as tk
import l10n
import csv
from os import path
from functools import partial
from enum import Enum

ptl = partial(l10n.translations.tl, context=__file__)

class ViewMode(Enum):
    FULL = 0
    FILTERED = 1

class SortingMode(Enum):
    MARKET = 0
    CARRIER = 1
    ALPHABET = 2

class Commodity:
    def __init__(self, symbol:str, category:str, name:str):
        self.symbol = symbol.strip() if symbol else ''
        self.category = category
        self.name = name.strip() if name else self.symbol
        self.market_ord: int = 0
        self.carrier_ord: int = 0

class MainUi:
    ROWS = 40
    iconDir = path.join(path.dirname(__file__), "icons")
    
    def __init__(self, config):
        self.row = 0
        self.icons = {}
        self.icons['left_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "left_arrow.gif"))
        self.icons['right_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "right_arrow.gif"))
        self.icons['view_open'] = tk.PhotoImage(file=path.join(self.iconDir, "view_open.gif"))
        self.icons['view_close'] = tk.PhotoImage(file=path.join(self.iconDir, "view_close.gif"))
        self.rows = None
        self.subscribers = {}
        self.config = config
        self.title = None
        self.station = None
        self.track_btn = None
        self.prev_btn = None
        self.next_btn = None
        self.view_btn = None
        self.view_mode:ViewMode = ViewMode.FULL
        self.sorting_mode:SortingMode = SortingMode.MARKET

    def nextRow(self):
        self.row+=1

    def plugin_app(self, parent:tk.Widget) -> tk.Widget:
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.grid(sticky=tk.EW)
        
        frame = tk.Frame(self.frame)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=0, column=0, sticky=tk.EW)

        #tk.Label(frame, text=ptl("Colonization:"), anchor=tk.W).grid(row=0, column=0, sticky=tk.W)

        self.sorting_var = tk.StringVar(value=ptl(str(self.sorting_mode)))
        self.sorting_cb = tk.OptionMenu(frame, self.sorting_var, *[ptl(str(e)) for e in SortingMode], command=self.changeSorting)
        self.sorting_cb.grid(row=0, column=0, sticky=tk.W)

        self.prev_btn = tk.Label(frame, image=self.icons['left_arrow'], cursor="hand2")
        self.prev_btn.bind("<Button-1>", partial(self.event, "prev"))
        self.prev_btn.grid(row=0, column=1, sticky=tk.W)
        
        self.title = tk.Label(frame, text=ptl("Total"), justify=tk.CENTER, anchor=tk.CENTER)
        self.title.grid(row=0, column=2, sticky=tk.EW)
        
        self.next_btn = tk.Label(frame, image=self.icons['right_arrow'], cursor="hand2")
        self.next_btn.bind("<Button-1>", partial(self.event, "next"))
        self.next_btn.grid(row=0, column=3, sticky=tk.W)
        
        self.view_btn = tk.Label(frame, image=self.icons['view_close'], cursor="hand2")
        self.view_btn.bind("<Button-1>", self.changeView)
        self.view_btn.grid(row=0, column=4, sticky=tk.E)

        self.station = tk.Label(frame, text=ptl("Station"), justify=tk.CENTER)
        self.station.grid(row=1, column=0, columnspan=5, sticky=tk.EW)
        
        self.track_btn = tk.Button(frame, text=ptl("Track this construction"), command=partial(self.event, "track", None))
        self.track_btn.grid(row=2, column=0, sticky=tk.EW, columnspan=5)

        self.table_frame = tk.Frame(self.frame, highlightthickness=1)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.grid(row=1, column=0, sticky=tk.EW)

        fontDefault = ("Tahoma", 9, "normal")
        fontMono = ("Tahoma", 9, "normal")
        tk.Label(self.table_frame, text=ptl("Commodity")).grid(row=0, column=0)
        tk.Label(self.table_frame, text=ptl("Need")).grid(row=0, column=1)
        tk.Label(self.table_frame, text=ptl("Cargo")).grid(row=0, column=2)
        tk.Label(self.table_frame, text=ptl("Carrier")).grid(row=0, column=3)
        tk.Label(self.table_frame, text=ptl("Buy")).grid(row=0, column=4)

        self.rows = list()
        for i in range(self.ROWS):
            self.table_frame.grid_rowconfigure(i+1, pad=0)
            labels = {}
            labels['name'] = tk.Label(self.table_frame, pady=0, font=fontDefault)
            labels['name'].grid_configure(sticky=tk.W)
            labels['name'].grid_remove()
            labels['needed'] = tk.Label(self.table_frame, pady=0, font=fontMono)
            labels['needed'].grid_configure(sticky=tk.SE)
            labels['needed'].grid_remove()
            labels['cargo'] = tk.Label(self.table_frame, pady=0, font=fontMono)
            labels['cargo'].grid_configure(sticky=tk.SE)
            labels['cargo'].grid_remove()
            labels['carrier'] = tk.Label(self.table_frame, pady=0, font=fontMono)
            labels['carrier'].grid_configure(sticky=tk.SE)
            labels['carrier'].grid_remove()
            labels['buy'] = tk.Label(self.table_frame, pady=0, font=fontMono)
            labels['buy'].grid_configure(sticky=tk.SE)
            labels['buy'].grid_remove()
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

    def changeSorting(self, event):
        sorting = self.sorting_var.get()
        index = [ptl(str(e)) for e in SortingMode].index(sorting)
        self.sorting_mode = list(SortingMode)[index]
        self.event('update', None)

    def setTitle(self, title):
        if self.title:
            self.title['text'] = title

    def setTable(self, table:list, docked, isTotal):
        if not self.rows:
            return

        self.table_frame.grid_slaves(0,0)[0].config(text=ptl("Commodity"))
        self.table_frame.grid_slaves(0,1)[0].config(text=ptl("Need"))
        self.table_frame.grid_slaves(0,2)[0].config(text=ptl("Cargo"))
        self.table_frame.grid_slaves(0,3)[0].config(text=ptl("Carrier"))
        self.table_frame.grid_slaves(0,4)[0].config(text=ptl("Buy"))

        row = 0
        if self.sorting_mode == SortingMode.MARKET:
            table.sort(key=lambda c: c['commodity'].market_ord)
        elif self.sorting_mode == SortingMode.CARRIER:
            table.sort(key=lambda c: c['commodity'].carrier_ord)
        else:
            table.sort(key=lambda c: ptl(c['commodity'].name))
        category: str|None = None
        for i in table:
            if not i:
                continue
            if i['needed'] <= 0:
                continue

            toBuy = i['needed']-i['cargo']-i['carrier']
            if isTotal and toBuy <= 0:
                continue           
            if self.view_mode == ViewMode.FILTERED and not docked:
                if (not i['available']):
                    continue
                if (toBuy <= 0):
                    continue
            if self.view_mode == ViewMode.FILTERED and docked == "carrier":
                if (toBuy <= 0):
                    continue
                
            if row >= self.ROWS:
                break

            c = i['commodity']
            if self.sorting_mode == SortingMode.MARKET and c.category != category:
                category = c.category
                self.rows[row]['name']['text'] = ptl(category)
                self.rows[row]['name']['fg'] = 'black'
                self.rows[row]['name'].grid(row=row+1, column=0)
                self.rows[row]['needed'].grid_remove()
                self.rows[row]['cargo'].grid_remove()
                self.rows[row]['carrier'].grid_remove()
                self.rows[row]['buy'].grid_remove()
                row += 1
                if row >= self.ROWS:
                    break

            self.rows[row]['name']['text'] = c.name

            self.rows[row]['needed']['text'] = '{:8,d}'.format(i['needed'])
            self.rows[row]['cargo']['text'] = '{:8,d}'.format(i['cargo'])
            self.rows[row]['carrier']['text'] = '{:8,d}'.format(i['carrier'])
            self.rows[row]['buy']['text'] = '{:8,d}'.format(toBuy if toBuy > 0 else 0)

            self.rows[row]['name'].grid(row=row+1, column=0)
            self.rows[row]['needed'].grid(row=row+1, column=1)
            self.rows[row]['cargo'].grid(row=row+1, column=2)
            self.rows[row]['carrier'].grid(row=row+1, column=3)
            self.rows[row]['buy'].grid(row=row+1, column=4)
            
            if (toBuy <= 0):
                self.rows[row]['name']['fg'] = 'green'
                self.rows[row]['needed']['fg'] = 'green'
                self.rows[row]['cargo']['fg'] = 'green'
                self.rows[row]['carrier']['fg'] = 'green'
                self.rows[row]['buy']['fg'] = 'green'
            else:
                if i['available']:
                    self.rows[row]['name']['fg'] = '#FFF'
                else:
                    self.rows[row]['name']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['needed']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['cargo']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['carrier']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['buy']['fg'] = self.config.get_str('dark_text')
            row+=1

        for i in range(row, self.ROWS):
            self.rows[i]['name'].grid_remove()
            self.rows[i]['needed'].grid_remove()
            self.rows[i]['cargo'].grid_remove()
            self.rows[i]['carrier'].grid_remove()
            self.rows[i]['buy'].grid_remove()
        

        if (row == 0):
            self.table_frame.grid_remove()
        else:
            self.table_frame.grid()
        

    def setStation(self, station, color=None):
        if self.station:
            self.station['text'] = str(station)
            if color:
                self.station['fg'] = color
            else:
                self.station['fg'] = self.config.get_str('dark_text')