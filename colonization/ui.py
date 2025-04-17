import tkinter as tk
from os import path
from functools import partial
from enum import Enum
from typing import Any, Callable, Optional

from theme import theme

from colonization.config import Config
from .data import Commodity, TableEntry, ptl


class SortingMode(Enum):
    MARKET = 0
    CARRIER = 1
    ALPHABET = 2

class ViewMode(Enum):
    FULL = 0
    FILTERED = 1
    NONE = 2

class MainUi:
    ROWS = 35
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
        self.rows: Optional[list] = None
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

    def next_row(self) -> int:
        row = self.row
        self.row += 1
        return row

    def plugin_app(self, parent: tk.Widget) -> tk.Widget:
        self.frame = tk.Frame(parent)
        self.frame.columnconfigure(0, weight=1)
        self.frame.grid(sticky=tk.EW)

        frame = tk.Frame(self.frame)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=self.next_row(), column=0, sticky=tk.EW)

        self.sorting_var = tk.StringVar(value=ptl(str(self.sorting_mode)))
        self.sorting_cb = tk.OptionMenu(frame, self.sorting_var, *[ptl(str(e)) for e in SortingMode], command=self.change_sorting)
        self.sorting_cb.grid(row=0, column=0, sticky=tk.W)

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

        self.station = tk.Label(self.frame, text=ptl("Loading..."), justify=tk.CENTER)
        self.station.grid_configure(row=self.next_row(), column=0, sticky=tk.EW)

        self.total_label = tk.Label(self.frame, text=ptl("nothing to deliver"), justify=tk.CENTER)
        self.total_label.grid_configure(row=self.next_row(), column=0, sticky=tk.EW)

        self.track_btn = tk.Button(self.frame, text=ptl("Track this construction"), command=partial(self.event, "track", None))
        self.track_btn.grid(row=self.next_row(), column=0, sticky=tk.EW, columnspan=5)

        self.table_frame = tk.Frame(self.frame, highlightthickness=1)
        self.table_frame.columnconfigure(0, weight=1)
        self.table_frame.grid(row=self.next_row(), column=0, sticky=tk.EW)

        tk.Label(self.table_frame, text=ptl("Commodity")).grid(row=0, column=0, sticky=tk.W)
        tk.Label(self.table_frame, text=ptl("Buy")+" |").grid(row=0, column=1, sticky=tk.E)
        tk.Label(self.table_frame, text=ptl("Demand")+" |").grid(row=0, column=2, sticky=tk.E)
        tk.Label(self.table_frame, text=ptl("Carrier")+" |").grid(row=0, column=3, sticky=tk.E)
        tk.Label(self.table_frame, text=ptl("Cargo")).grid(row=0, column=4, sticky=tk.E)

        fontDefault = ("Tahoma", 9, "normal")
        fontMono = ("Tahoma", 9, "normal")

        self.rows = []
        for i in range(self.ROWS):
            self.table_frame.grid_rowconfigure(i+1, pad=0)
            labels = {
                'name': tk.Label(self.table_frame, anchor=tk.W, font=fontDefault, justify=tk.LEFT),
                'needed': tk.Label(self.table_frame, anchor=tk.E, font=fontMono),
                'demand': tk.Label(self.table_frame, anchor=tk.E, font=fontMono),
                'cargo': tk.Label(self.table_frame, anchor=tk.E, font=fontMono),
                'carrier': tk.Label(self.table_frame, anchor=tk.E, font=fontMono)
            }
            labels['name'].grid_configure(sticky=tk.W)
            for label in labels.values():
                label.grid_remove()
            self.rows.append(labels)

        return self.frame

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

    def change_sorting(self, event):
        sorting = self.sorting_var.get()
        index = [ptl(str(e)) for e in SortingMode].index(sorting)
        self.sorting_mode = list(SortingMode)[index]
        self.event('update', None)

    def set_title(self, text: str) -> None:
        if self.title:
            self.title['text'] = text

    def set_table(self, table: list[TableEntry], docked: str | None, is_total: bool) -> None:
        if not self.rows:
            return

        if self.view_mode == ViewMode.NONE:
            self.table_frame.grid_remove()
            return

        row = 0

        if self.sorting_mode == SortingMode.MARKET:
            table.sort(key=lambda c: c.commodity.market_ord)
        elif self.sorting_mode == SortingMode.CARRIER:
            table.sort(key=lambda c: c.commodity.carrier_ord)
        else:
            table.sort(key=lambda c: c.commodity.name)
        category: str|None = None
        for i in table:
            if not i:
                continue
            if i.needed <= 0:
                continue

            to_buy = max(0,i.needed-i.cargo-i.carrier)

            if self.view_mode == ViewMode.FILTERED and not docked:
                if not i.available:
                    continue
                if to_buy <= 0:
                    continue
            if self.view_mode == ViewMode.FILTERED and docked == "carrier":
                if to_buy <= 0:
                    continue

            if row >= self.ROWS:
                break

            if theme.current:
                fg_highlight = theme.current['highlight']
                fg_normal = theme.current['foreground']
            else:
                fg_highlight = 'blue'
                fg_normal = 'black'

            if self.sorting_mode == SortingMode.MARKET and i.commodity.category != category:
                category = i.commodity.category
                self.rows[row]['name']['text'] = ptl(category)
                self.rows[row]['name']['fg'] = fg_highlight
                self.rows[row]['name'].grid(row=row+1, column=0)
                self.rows[row]['needed'].grid_remove()
                self.rows[row]['cargo'].grid_remove()
                self.rows[row]['carrier'].grid_remove()
                self.rows[row]['demand'].grid_remove()
                row += 1
                if row >= self.ROWS:
                    break

            self.rows[row]['name']['text'] = i.commodity.name
            self.rows[row]['needed']['text'] = "{:8,d}".format(to_buy)
            self.rows[row]['demand']['text'] = "{:8,d}".format(i.needed)
            self.rows[row]['carrier']['text'] = "{:8,d}".format(i.carrier)
            self.rows[row]['cargo']['text'] = "{:8,d}".format(i.cargo)

            self.rows[row]['name'].grid(row=row + 1, column=0, sticky="w")
            self.rows[row]['needed'].grid(row=row + 1, column=1, sticky="e")
            self.rows[row]['demand'].grid(row=row + 1, column=2, sticky="e")
            self.rows[row]['carrier'].grid(row=row + 1, column=3, sticky="e")
            self.rows[row]['cargo'].grid(row=row + 1, column=4, sticky="e")

            if to_buy <= 0:
                self.rows[row]['name']['fg'] = 'green'
                self.rows[row]['needed']['fg'] = 'green'
                self.rows[row]['demand']['fg'] = 'green'
                self.rows[row]['cargo']['fg'] = 'green'
                self.rows[row]['carrier']['fg'] = 'green'
            elif theme.current:
                if i.available:
                    self.rows[row]['name']['fg'] = fg_highlight
                else:
                    self.rows[row]['name']['fg'] = fg_normal
                self.rows[row]['needed']['fg'] = fg_normal
                self.rows[row]['demand']['fg'] = fg_normal
                self.rows[row]['cargo']['fg'] = fg_normal
                self.rows[row]['carrier']['fg'] = fg_normal
            row += 1

        for j in range(row, self.ROWS):
            self.rows[j]['name'].grid_remove()
            self.rows[j]['needed'].grid_remove()
            self.rows[j]['demand'].grid_remove()
            self.rows[j]['cargo'].grid_remove()
            self.rows[j]['carrier'].grid_remove()

        if self.table_frame:
            if row == 0:
                self.table_frame.grid_remove()
            else:
                self.table_frame.grid()

    def set_station(self, value: str | None, color: str | None = None) -> None:
        if self.station and theme.current:
            if Config.SHOW_STATION_NAME.get():
                self.station['text'] = value
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

    def set_total(self, cargo:int, maxcargo:int, color:str | None = None) -> None:
        if self.total_label and theme.current:
            if Config.SHOW_TOTALS.get():
                if maxcargo > 0:
                    flight = float(cargo)/float(maxcargo)
                else:
                    flight = 0.0
                self.total_label['text'] = f"Remaining {flight:.1f} flights at {maxcargo} tons each, total {str(cargo)} t"
                if color:
                    self.total_label['fg'] = color
                else:
                    self.total_label['fg'] = theme.current['foreground']
                self.total_label.grid()
            else:
                self.total_label.grid_remove()
