import tkinter as tk
from config import config
from os import path
from functools import partial
from enum import Enum
from theme import theme
from collections import deque

from .data import Commodity, TableEntry, ptl

class SortingMode(Enum):
    MARKET = 0
    CARRIER = 1
    ALPHABET = 2

class CollapseMode(Enum):
    EXPANDED = 0
    COLLAPSED = 1
    LEADING = 2     # always collapsed top row
    TRAILING = 3    # always collapsed bottom row
    def __bool__(self):
        return self != CollapseMode.EXPANDED

class CommodityCategory:
    def __init__(self, symbol:str, mode:CollapseMode = CollapseMode.EXPANDED):
        self.symbol = symbol.strip() if symbol else ''
        self.rows: list[TableEntry|CommodityCategory] = []
        self.collapsed: CollapseMode = mode

    def unload(self):
        return sum([i.unload() for i in self.rows])

    def buy(self):
        return sum([i.buy() for i in self.rows])

    def clear(self):
        self.rows = []

class MainUi:
    ROWS = 20
    COLLAPSABLE = True
    iconDir = path.join(path.dirname(__file__), "../icons")
    
    def __init__(self):
        self.row = 0
        self.icons = {}
        self.icons['left_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "left_arrow.gif"))
        self.icons['right_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "right_arrow.gif"))
        self.icons['view_open'] = tk.PhotoImage(file=path.join(self.iconDir, "view_open.gif"))
        self.icons['view_close'] = tk.PhotoImage(file=path.join(self.iconDir, "view_close.gif"))
        self.rows = None
        self.top_rows = 0
        self.bottom_rows = 0
        self.subscribers = {}
        self.title = None
        self.station = None
        self.track_btn = None
        self.prev_btn = None
        self.next_btn = None
        self.view_btn = None
        self.view_table = True
        self.sorting_mode:SortingMode = SortingMode.MARKET
        self.categories: dict[str,CommodityCategory] = {}
        self.ROWS = config.get_int("colonization.Rows", default=25)
        self.CATEGORIES = config.get_bool("colonization.Categories", default=True)
        self.COLLAPSABLE = config.get_bool("colonization.Collapsable", default=True)

    def nextRow(self):
        self.row+=1

    def plugin_app(self, parent:tk.Widget) -> tk.Widget:
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.grid(sticky=tk.EW)
        self.sorting_var = tk.StringVar()
        self.resetFrame()
        return self.frame

    def resetFrame(self):
        for child in list(self.frame.children.values()):
            child.destroy()
        frame = tk.Frame(self.frame)
        frame.columnconfigure(2, weight=1)
        frame.grid(row=0, column=0, sticky=tk.EW)

        #tk.Label(frame, text=ptl("Colonization:"), anchor=tk.W).grid(row=0, column=0, sticky=tk.W)

        self.sorting_var.set(ptl(str(self.sorting_mode)))
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

        self.station = tk.Label(frame, text=ptl("Loading..."), justify=tk.CENTER)
        self.station.grid(row=1, column=0, columnspan=5, sticky=tk.EW)
        
        self.track_btn = tk.Button(frame, text=ptl("Track this construction"), command=partial(self.event, "track", None))
        self.track_btn.grid(row=2, column=0, sticky=tk.EW, columnspan=5)

        self.table_frame = tk.Frame(self.frame, highlightthickness=1)
        #self.table_frame.columnconfigure(0, weight=1)
        #self.table_frame.grid(row=1, column=0, sticky=tk.EW)

        #fontDefault = ("Tahoma", 9, "normal")
        #fontMono = ("Tahoma", 9, "normal")
        tk.Label(self.table_frame, text=ptl("Commodity"), pady=0, width=20, height=1, anchor=tk.W).grid(row=0, column=0)
        tk.Label(self.table_frame, text=ptl("Need"),      pady=0, width=6, height=1, anchor=tk.E).grid(row=0, column=1)
        tk.Label(self.table_frame, text=ptl("Cargo"),     pady=0, width=6, height=1, anchor=tk.E).grid(row=0, column=2)
        tk.Label(self.table_frame, text=ptl("Carrier"),   pady=0, width=6, height=1, anchor=tk.E).grid(row=0, column=3)
        tk.Label(self.table_frame, text=ptl("Buy"),       pady=0, width=6, height=1, anchor=tk.E).grid(row=0, column=4)

        self.rows = list()
        for i in range(self.ROWS):
            self.table_frame.grid_rowconfigure(i+1, pad=0)
            labels = {}
            labels['name'] = tk.Label(self.table_frame, pady=0, width=20, height=1, anchor=tk.W, justify=tk.LEFT)
            labels['name'].grid_configure(sticky=tk.W)
            labels['name'].grid_remove()
            labels['needed'] = tk.Label(self.table_frame, pady=0, width=6, height=1, anchor=tk.E)
            labels['needed'].grid_configure(sticky=tk.SE)
            labels['needed'].grid_remove()
            labels['cargo'] = tk.Label(self.table_frame, pady=0, width=6, height=1, anchor=tk.E)
            labels['cargo'].grid_configure(sticky=tk.SE)
            labels['cargo'].grid_remove()
            labels['carrier'] = tk.Label(self.table_frame, pady=0, width=6, height=1, anchor=tk.E)
            labels['carrier'].grid_configure(sticky=tk.SE)
            labels['carrier'].grid_remove()
            labels['buy'] = tk.Label(self.table_frame, pady=0, width=6, height=1, anchor=tk.E)
            labels['buy'].grid_configure(sticky=tk.SE)
            labels['buy'].grid_remove()
            self.rows.append(labels)

    def event(self, event, tkEvent):
        if event in self.subscribers:
            self.subscribers[event](tkEvent)

    def on(self, event, function):
        self.subscribers[event] = function
        
    def changeView(self, event):
        if self.view_table:
            self.view_btn['image'] = self.icons['view_open']
            self.view_table = False
        else:
            self.view_btn['image'] = self.icons['view_close']
            self.view_table = True
        self.event('update', None)

    def changeSorting(self, event):
        sorting = self.sorting_var.get()
        index = [ptl(str(e)) for e in SortingMode].index(sorting)
        self.sorting_mode = list(SortingMode)[index]
        self.event('update', None)

    def setTitle(self, title):
        if self.title:
            self.title['text'] = title

    def _toggle_category(self, event, c:str):
        cc = self.categories[c]
        if cc.collapsed:
            cc.collapsed = CollapseMode.EXPANDED
        else:
            cc.collapsed = CollapseMode.COLLAPSED
        self.event('update', None)

    def _incr_top_rows(self, event, rows: int):
        rows = self.bottom_rows
        page_size = self.ROWS - 3
        if self.top_rows == 0:
            page_size += 1
        if rows > page_size:
            rows = page_size
        self.top_rows += rows
        self.event('update', None)

    def _decr_top_rows(self, event, rows: int):
        rows = self.top_rows
        page_size = self.ROWS - 3
        if rows > page_size:
            rows = page_size
        self.top_rows -= rows
        if self.top_rows <= 1:
            self.top_rows = 0
        self.event('update', None)

    def _show_category(self, row: int, cc: CommodityCategory):
        if row >= self.ROWS:
            row = self.ROWS-1
        if cc.collapsed == CollapseMode.LEADING:
            self.rows[row]['name']['text'] = '^ ({}) {}'.format(len(cc.rows), ptl(cc.symbol))
            self.rows[row]['name'].bind("<Button-1>", lambda e,cnt=len(cc.rows): self._decr_top_rows(e,cnt))
        elif cc.collapsed == CollapseMode.TRAILING:
            self.rows[row]['name']['text'] = '¡ ({}) {}'.format(len(cc.rows), ptl(cc.symbol))
            self.rows[row]['name'].bind("<Button-1>", lambda e,cnt=len(cc.rows): self._incr_top_rows(e,cnt))
        elif self.COLLAPSABLE:
            self.rows[row]['name'].bind("<Button-1>", lambda e,category=cc.symbol: self._toggle_category(e,category))
            if cc.collapsed:
                self.rows[row]['name']['text'] = '? ({}) {}'.format(len(cc.rows), ptl(cc.symbol))
            else:
                self.rows[row]['name']['text'] = '? ' + ptl(cc.symbol)
        else:
            self.rows[row]['name']['text'] = '? ' + ptl(cc.symbol)

        fg_color = theme.current['highlight'] if theme.current else 'blue'
        self.rows[row]['name']['fg'] = fg_color
        self.rows[row]['name'].grid(row=row+1, column=0)
        self.rows[row]['cargo'].grid_remove()
        self.rows[row]['carrier'].grid_remove()
        self.rows[row]['name'].grid(row=row+1, column=0)
        if cc.collapsed != CollapseMode.EXPANDED:
            self.rows[row]['needed']['text'] = '{:8,d}'.format(cc.unload())
            self.rows[row]['buy']['text'] = '{:8,d}'.format(cc.buy())
            self.rows[row]['needed']['fg'] = fg_color
            self.rows[row]['needed'].grid(row=row+1, column=1)
            self.rows[row]['buy']['fg'] = fg_color
            self.rows[row]['buy'].grid(row=row+1, column=4)
        else:
            self.rows[row]['needed'].grid_remove()
            self.rows[row]['buy'].grid_remove()

    def _show_commodity(self, row: int, i:TableEntry):
        c: Commodity = i.commodity

        self.rows[row]['name']['text'] = c.name
        self.rows[row]['needed']['text'] = '{:8,d}'.format(i.unload())
        self.rows[row]['cargo']['text'] = '{:8,d}'.format(i.cargo)
        self.rows[row]['carrier']['text'] = '{:8,d}'.format(i.carrier)
        self.rows[row]['buy']['text'] = '{:8,d}'.format(i.buy())

        self.rows[row]['name'].grid(row=row+1, column=0)
        self.rows[row]['needed'].grid(row=row+1, column=1)
        self.rows[row]['cargo'].grid(row=row+1, column=2)
        self.rows[row]['carrier'].grid(row=row+1, column=3)
        self.rows[row]['buy'].grid(row=row+1, column=4)

        if i.buy() <= 0:
            self.rows[row]['name']['fg'] = 'green'
            self.rows[row]['needed']['fg'] = 'green'
            self.rows[row]['cargo']['fg'] = 'green'
            self.rows[row]['carrier']['fg'] = 'green'
            self.rows[row]['buy']['fg'] = 'green'
        else:
            fg_color = theme.current['foreground'] if theme.current else 'black'
            if i.available:
                self.rows[row]['name']['fg'] = '#FFF'
            else:
                self.rows[row]['name']['fg'] = fg_color
            self.rows[row]['needed']['fg'] = fg_color
            self.rows[row]['cargo']['fg'] = fg_color
            self.rows[row]['carrier']['fg'] = fg_color
            self.rows[row]['buy']['fg'] = fg_color

    def setTable(self, table: list[TableEntry], docked, isTotal: bool):
        if not self.rows:
            return

        if not self.view_table:
            self.table_frame.grid_remove()
            return

        # sort
        if self.sorting_mode == SortingMode.MARKET:
            table.sort(key=lambda c: c.commodity.market_ord)
        elif self.sorting_mode == SortingMode.CARRIER:
            table.sort(key=lambda c: c.commodity.carrier_ord)
        else:
            table.sort(key=lambda c: c.commodity.name)

        # prepare a list of rows (display_list)
        display_list: deque[TableEntry|CommodityCategory] = deque()
        show_categories = self.CATEGORIES and self.sorting_mode == SortingMode.MARKET
        if show_categories:
            for cc in self.categories.values():
                cc.clear()
        cc: CommodityCategory|None = None
        for i in table:
            if not i or i.needed <= 0 or (isTotal and i.buy() <= 0):
                continue
            if show_categories and (not cc or i.category() != cc.symbol):
                if not cc or i.category() != cc.symbol:
                    cc = self.categories.get(i.category())
                    if not cc:
                        cc = CommodityCategory(i.category())
                        self.categories[cc.symbol] = cc
                    display_list.append(cc)
            if self.COLLAPSABLE and cc and cc.collapsed:
                cc.rows.append(i)
            else:
                display_list.append(i)
        # collapse first rows into 'others'
        if self.top_rows > 0 and len(display_list) > self.ROWS:
            cc_others = CommodityCategory("Others Commodities", CollapseMode.LEADING)
            while len(cc_others.rows) < self.top_rows and len(display_list) > self.ROWS-1:
                cc_others.rows.append(display_list.popleft())
            display_list.appendleft(cc_others)
            self.top_rows = len(cc_others.rows)
        # collapse last rows into 'others'
        self.bottom_rows = 0
        if len(display_list) > self.ROWS:
            cc_others = CommodityCategory("Others Commodities", CollapseMode.TRAILING)
            while len(display_list) > self.ROWS-1:
                cc_others.rows.append(display_list.pop())
            display_list.append(cc_others)
            self.bottom_rows = len(cc_others.rows)

        row = 0
        for i in display_list:
            if isinstance(i, TableEntry):
                self._show_commodity(row, i)
            else:
                self._show_category(row, i)
            row += 1

        for i in range(row, self.ROWS):
            self.rows[i]['name'].grid_remove()
            self.rows[i]['needed'].grid_remove()
            self.rows[i]['cargo'].grid_remove()
            self.rows[i]['carrier'].grid_remove()
            self.rows[i]['buy'].grid_remove()

        if row == 0:
            self.table_frame.grid_remove()
        else:
            self.table_frame.grid()
        

    def setStation(self, station, color=None):
        if self.station and theme.current:
            if self.station['text'] != str(station):
                self.top_rows = 0
                self.station['text'] = str(station)
            if color:
                self.station['fg'] = color
            elif theme.current:
                self.station['fg'] = theme.current['foreground']