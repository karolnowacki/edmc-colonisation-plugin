import tkinter as tk
from os import path
from functools import partial
from enum import Enum
from typing import Callable, Optional
from collections import deque

from theme import theme

from .config import Config
from .data import Commodity, TableEntry, ptl


class SortingMode(Enum):
    MARKET = 0
    CARRIER = 1
    ALPHABET = 2


class ViewMode(Enum):
    FULL = 0
    FILTERED = 1
    NONE = 2


class CollapseMode(Enum):
    EXPANDED = 0
    COLLAPSED = 1
    LEADING = 2  # always collapsed top row
    TRAILING = 3  # always collapsed bottom row

    def __bool__(self):
        return self != CollapseMode.EXPANDED


class CommodityCategory:
    def __init__(self, symbol: str, mode: CollapseMode = CollapseMode.EXPANDED):
        self.symbol = symbol.strip() if symbol else ''
        self.rows: list[TableEntry | CommodityCategory] = []
        self.collapsed: CollapseMode = mode

    def unload(self) -> int:
        return sum(i.unload() for i in self.rows)

    def buy(self) -> int:
        return sum(i.buy() for i in self.rows)

    def clear(self) -> None:
        self.rows = []


class MainUi:
    rows_conf = 20
    collapsable_conf = True
    iconDir = path.join(path.dirname(__file__), "../icons")

    def __init__(self) -> None:
        self.frame: Optional[tk.Frame] = None
        self.row = 0
        self.icons = {
            'left_arrow': tk.PhotoImage(file=path.join(self.iconDir, "left_arrow.gif")),
            'right_arrow': tk.PhotoImage(file=path.join(self.iconDir, "right_arrow.gif")),
            'view_open': tk.PhotoImage(file=path.join(self.iconDir, "view_open.gif")),
            'view_close': tk.PhotoImage(file=path.join(self.iconDir, "view_close.gif"))
        }
        self.rows_conf: Optional[list] = None
        self.subscribers: dict[str, Callable[[tk.Event | None], None]] = {}
        self.title: Optional[tk.Label] = None
        self.station: Optional[tk.Label] = None
        self.total_label: Optional[tk.Label] = None
        self.track_btn: Optional[tk.Button] = None
        self.prev_btn: Optional[tk.Label] = None
        self.next_btn: Optional[tk.Label] = None
        self.view_btn: Optional[tk.Label] = None
        self.table_frame: Optional[tk.Frame] = None
        self.view_mode: ViewMode = ViewMode.FULL
        self.sorting_mode: SortingMode = SortingMode.MARKET
        self.top_rows: int = 0
        self.bottom_rows: int = 0
        self.categories: dict[str, CommodityCategory] = {}
        self.max_rows_conf = Config.ROWS.get()
        self.categories_conf = Config.CATEGORIES.get()
        self.collapsable_conf = Config.COLLAPSABLE.get()
        self.sorting_var = tk.StringVar()

    def next_row(self) -> int:
        row = self.row
        self.row += 1
        return row

    def plugin_app(self, parent: tk.Widget) -> tk.Widget:
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.grid(sticky=tk.EW)
        self.reset_frame()
        return self.frame

    def reset_frame(self):
        for child in list(self.frame.children.values()):
            child.destroy()
        frame = tk.Frame(self.frame)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=self.next_row(), column=0, sticky=tk.EW)

        self.sorting_var.set(ptl(str(self.sorting_mode)))
        tk.OptionMenu(frame, self.sorting_var, *[ptl(str(e)) for e in SortingMode],
                                        command=self.change_sorting).grid(row=0, column=0, sticky=tk.W)

        self.prev_btn = tk.Label(frame, image=self.icons['left_arrow'], cursor="hand2")
        self.prev_btn.bind("<Button-1>", partial(self.event, "prev"))
        self.prev_btn.grid(row=0, column=0, sticky=tk.W)

        self.title = tk.Label(frame, text="", justify=tk.CENTER, anchor=tk.CENTER)
        self.title.grid(row=0, column=1, sticky=tk.EW)

        self.next_btn = tk.Label(frame, image=self.icons['right_arrow'], cursor="hand2")
        self.next_btn.bind("<Button-1>", partial(self.event, "next"))
        self.next_btn.grid(row=0, column=2, sticky=tk.W)

        self.view_btn = tk.Label(frame, image=self.icons['view_close'], cursor="hand2")
        self.view_btn.bind("<Button-1>", self.change_view)
        self.view_btn.grid(row=0, column=3, sticky=tk.E)

        theme.update(frame)

        self.station = tk.Label(self.frame, text=ptl("Loading..."), justify=tk.CENTER)
        self.station.grid_configure(row=self.next_row(), column=0, sticky=tk.EW)

        self.total_label = tk.Label(self.frame, text=ptl("nothing to deliver"), justify=tk.CENTER)
        self.total_label.grid_configure(row=self.next_row(), column=0, sticky=tk.EW)

        self.track_btn = tk.Button(self.frame, text=ptl("Track this construction"),
                                   command=partial(self.event, "track", None))
        self.track_btn.grid(row=self.next_row(), column=0, sticky=tk.EW, columnspan=5)

        self.table_frame = tk.Frame(self.frame, highlightthickness=1)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.grid(row=self.next_row(), column=0, sticky=tk.EW)

        tk.Label(self.table_frame, text=ptl("Commodity")).grid(row=0, column=0, sticky=tk.W)
        tk.Label(self.table_frame, text=ptl("Buy")).grid(row=0, column=1, sticky=tk.E)
        tk.Label(self.table_frame, text=ptl("Demand")).grid(row=0, column=2, sticky=tk.E)
        tk.Label(self.table_frame, text=ptl("Carrier")).grid(row=0, column=3, sticky=tk.E)
        tk.Label(self.table_frame, text=ptl("Cargo")).grid(row=0, column=4, sticky=tk.E)

        font_default = ("Tahoma", 9, "normal")
        font_mono = ("Tahoma", 9, "normal")

        self.rows_conf = []
        for i in range(self.max_rows_conf):
            self.table_frame.grid_rowconfigure(i + 1, pad=0)
            labels = {
                'name': tk.Label(self.table_frame, anchor=tk.W, font=font_default, justify=tk.LEFT),
                'buy': tk.Label(self.table_frame, anchor=tk.E, font=font_mono),
                'demand': tk.Label(self.table_frame, anchor=tk.E, font=font_mono),
                'cargo': tk.Label(self.table_frame, anchor=tk.E, font=font_mono),
                'carrier': tk.Label(self.table_frame, anchor=tk.E, font=font_mono)
            }
            labels['name'].grid_configure(sticky=tk.W)
            for label in labels.values():
                label.grid_remove()
            self.rows_conf.append(labels)

        theme.update(self.table_frame)
        theme.update(self.frame)

    def event(self, event: str, tk_event: tk.Event | None) -> None:
        if event in self.subscribers:
            self.subscribers[event](tk_event)

    def on(self, event: str, function: Callable[[tk.Event | None], None]) -> None:
        self.subscribers[event] = function

    def change_view(self, event: tk.Event) -> None:
        if self.view_btn:
            if self.view_mode == ViewMode.FULL:
                self.view_btn['image'] = self.icons['view_open']
                self.view_mode = ViewMode.FILTERED
            elif self.view_mode == ViewMode.FILTERED:
                self.view_btn['image'] = self.icons['view_close']
                self.view_mode = ViewMode.FULL
        self.event('update', event)

    def change_sorting(self, event):  # pylint: disable=W0613
        sorting = self.sorting_var.get()
        index = [ptl(str(e)) for e in SortingMode].index(sorting)
        self.sorting_mode = list(SortingMode)[index]
        self.event('update', None)

    def set_title(self, text: str) -> None:
        if self.title:
            self.title['text'] = text

    def _toggle_category(self, event, c: str):  # pylint: disable=W0613
        cc = self.categories[c]
        if cc.collapsed:
            cc.collapsed = CollapseMode.EXPANDED
        else:
            cc.collapsed = CollapseMode.COLLAPSED
        self.event('update', None)

    def _incr_top_rows(self, event, rows: int):  # pylint: disable=W0613
        page_size = self.max_rows_conf - 3
        if self.top_rows == 0:
            page_size += 1
        rows = min(self.bottom_rows, page_size)
        self.top_rows += rows
        self.event('update', None)

    def _decr_top_rows(self, event, rows: int):  # pylint: disable=W0613
        page_size = self.max_rows_conf - 3
        rows = min(self.top_rows, page_size)
        self.top_rows -= rows
        if self.top_rows <= 1:
            self.top_rows = 0
        self.event('update', None)

    def _show_category(self, row: int, cc: CommodityCategory):
        if row >= self.max_rows_conf:
            row = self.max_rows_conf - 1
        if cc.collapsed == CollapseMode.LEADING:
            self.rows_conf[row]['name']['text'] = '▲ ({}) {}'.format(len(cc.rows), ptl(cc.symbol))
            self.rows_conf[row]['name'].bind("<Button-1>", lambda e, cnt=len(cc.rows): self._decr_top_rows(e, cnt))
        elif cc.collapsed == CollapseMode.TRAILING:
            self.rows_conf[row]['name']['text'] = '▼ ({}) {}'.format(len(cc.rows), ptl(cc.symbol))
            self.rows_conf[row]['name'].bind("<Button-1>", lambda e, cnt=len(cc.rows): self._incr_top_rows(e, cnt))
        elif self.collapsable_conf:
            self.rows_conf[row]['name'].bind("<Button-1>",
                                             lambda e, category=cc.symbol: self._toggle_category(e, category))
            if cc.collapsed:
                self.rows_conf[row]['name']['text'] = '▶ ({}) {}'.format(len(cc.rows), ptl(cc.symbol))
            else:
                self.rows_conf[row]['name']['text'] = '▽ ' + ptl(cc.symbol)
        else:
            self.rows_conf[row]['name']['text'] = '▽ ' + ptl(cc.symbol)

        fg_color = theme.current['highlight'] if theme.current else 'blue'
        self.rows_conf[row]['name']['fg'] = fg_color
        self.rows_conf[row]['name'].grid(row=row + 1, column=0)
        self.rows_conf[row]['cargo'].grid_remove()
        self.rows_conf[row]['carrier'].grid_remove()
        self.rows_conf[row]['name'].grid(row=row + 1, column=0)
        if cc.collapsed != CollapseMode.EXPANDED:
            self.rows_conf[row]['demand']['text'] = '{:8,d}'.format(cc.unload())
            self.rows_conf[row]['buy']['text'] = '{:8,d}'.format(cc.buy())
            self.rows_conf[row]['demand']['fg'] = fg_color
            self.rows_conf[row]['demand'].grid(row=row + 1, column=1)
            self.rows_conf[row]['buy']['fg'] = fg_color
            self.rows_conf[row]['buy'].grid(row=row + 1, column=4)
        else:
            self.rows_conf[row]['demand'].grid_remove()
            self.rows_conf[row]['buy'].grid_remove()

    def _show_commodity(self, row: int, i: TableEntry):
        c: Commodity = i.commodity

        self.rows_conf[row]['name']['text'] = c.name
        self.rows_conf[row]['demand']['text'] = '{:8,d}'.format(i.unload())
        self.rows_conf[row]['cargo']['text'] = '{:8,d}'.format(i.cargo)
        self.rows_conf[row]['carrier']['text'] = '{:8,d}'.format(i.carrier)
        self.rows_conf[row]['buy']['text'] = '{:8,d}'.format(i.buy())

        self.rows_conf[row]['name'].grid(row=row + 1, column=0)
        self.rows_conf[row]['buy'].grid(row=row + 1, column=1)
        self.rows_conf[row]['demand'].grid(row=row + 1, column=2)
        self.rows_conf[row]['cargo'].grid(row=row + 1, column=3)
        self.rows_conf[row]['carrier'].grid(row=row + 1, column=4)

        if i.buy() <= 0:
            self.rows_conf[row]['name']['fg'] = 'green'
            self.rows_conf[row]['buy']['fg'] = 'green'
            self.rows_conf[row]['demand']['fg'] = 'green'
            self.rows_conf[row]['cargo']['fg'] = 'green'
            self.rows_conf[row]['carrier']['fg'] = 'green'
        else:
            fg_color = theme.current['foreground'] if theme.current else 'black'
            if i.available:
                self.rows_conf[row]['name']['fg'] = '#FFF'
            else:
                self.rows_conf[row]['name']['fg'] = fg_color
            self.rows_conf[row]['buy']['fg'] = fg_color
            self.rows_conf[row]['demand']['fg'] = fg_color
            self.rows_conf[row]['cargo']['fg'] = fg_color
            self.rows_conf[row]['carrier']['fg'] = fg_color
            self.rows_conf[row]['buy']['fg'] = fg_color

    def set_table(self, table: list[TableEntry], docked, is_total: bool):
        # pylint: disable=W0613,R0912
        if not self.rows_conf:
            return

        if self.view_mode == ViewMode.NONE:
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
        display_list: deque[TableEntry | CommodityCategory] = deque()
        show_categories = self.categories_conf and self.sorting_mode == SortingMode.MARKET
        if show_categories:
            for cc in self.categories.values():
                cc.clear()
        cc: CommodityCategory | None = None
        for i in table:
            if not i or i.demand <= 0 or (is_total and i.buy() <= 0):
                continue
            if show_categories and (not cc or i.category() != cc.symbol):
                if not cc or i.category() != cc.symbol:
                    cc = self.categories.get(i.category())
                    if not cc:
                        cc = CommodityCategory(i.category())
                        self.categories[cc.symbol] = cc
                    display_list.append(cc)
            if self.collapsable_conf and cc and cc.collapsed:
                cc.rows.append(i)
            else:
                display_list.append(i)
        # collapse first rows into 'others'
        if self.top_rows > 0 and len(display_list) > self.max_rows_conf:
            cc_others = CommodityCategory("Others Commodities", CollapseMode.LEADING)
            while len(cc_others.rows) < self.top_rows and len(display_list) > self.max_rows_conf - 1:
                cc_others.rows.append(display_list.popleft())
            display_list.appendleft(cc_others)
            self.top_rows = len(cc_others.rows)
        # collapse last rows into 'others'
        self.bottom_rows = 0
        if len(display_list) > self.max_rows_conf:
            cc_others = CommodityCategory("Others Commodities", CollapseMode.TRAILING)
            while len(display_list) > self.max_rows_conf - 1:
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

        for i in range(row, self.max_rows_conf):
            for r in self.rows_conf[i].values():
                r.grid_remove()

        if row == 0:
            self.table_frame.grid_remove()
        else:
            self.table_frame.grid()

    def set_station(self, value: str | None, color: str | None = None) -> None:
        if self.station and theme.current:
            if Config.SHOW_STATION_NAME.get():
                self.station['text'] = str(value)
                if color:
                    self.station['fg'] = color
                elif theme.current:
                    self.station['fg'] = theme.current['foreground']
                if not value:
                    self.station.grid_remove()
                else:
                    self.station.grid()
            else:
                self.station.grid_remove()

    def set_total(self, cargo: int, maxcargo: int, color: str | None = None) -> None:
        if self.total_label and theme.current:
            if Config.SHOW_TOTALS.get():
                if maxcargo > 0:
                    flight = float(cargo) / float(maxcargo)
                else:
                    flight = 0.0
                self.total_label[
                    'text'] = f"Remaining {flight:.1f} flights at {maxcargo} tons each, total {str(cargo)} t"
                if color:
                    self.total_label['fg'] = color
                else:
                    self.total_label['fg'] = theme.current['foreground']
                self.total_label.grid()
            else:
                self.total_label.grid_remove()
