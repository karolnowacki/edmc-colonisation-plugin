import tkinter as tk
from abc import ABC, abstractmethod
from os import path
from functools import partial
from enum import Enum
from typing import Callable, Optional, Self
from collections import deque

from theme import theme

from .config import Config
from .data import Commodity, TableEntry, ptl
from .report import ReportLabel


class SortingMode(Enum):
    MARKET = 0
    CARRIER = 1
    ALPHABET = 2


class ViewMode(Enum):
    FULL = 0
    FILTERED = 1
    LACKS = 2
    NONE = 3


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
    max_rows_conf = Config.ROWS.get()
    categories_conf = Config.CATEGORIES.get()
    collapsable_conf = Config.COLLAPSABLE.get()
    scrollable_conf = Config.SCROLLABLE.get()
    iconDir = path.join(path.dirname(__file__), "../icons")

    def __init__(self) -> None:
        self.frame: Optional[tk.Frame] = None
        self.row = 0
        self.icons = {
            'left_arrow': tk.PhotoImage(file=path.join(self.iconDir, "left_arrow.gif")),
            'right_arrow': tk.PhotoImage(file=path.join(self.iconDir, "right_arrow.gif")),
            'view_open': tk.PhotoImage(file=path.join(self.iconDir, "view_open.gif")),
            'view_close': tk.PhotoImage(file=path.join(self.iconDir, "view_close.gif")),
            'view_sort': tk.PhotoImage(file=path.join(self.iconDir, "view_sort.gif")),
            'resize': tk.PhotoImage(file=path.join(self.iconDir, "resize.gif")),
        }
        self.subscribers: dict[str, Callable[[tk.Event | None], None]] = {}
        self.title: Optional[tk.Label] = None
        self.station: Optional[tk.Label] = None
        self.total_label: Optional[tk.Label] = None
        self.track_btn: Optional[tk.Button] = None
        self.sorting_btn: Optional[tk.OptionMenu] = None
        self.prev_btn: Optional[tk.Label] = None
        self.next_btn: Optional[tk.Label] = None
        self.view_btn: Optional[tk.Label] = None
        self.table_frame: Optional[tk.Frame] = None
        self.view_mode: ViewMode = ViewMode.FULL
        self.sorting_mode: SortingMode = SortingMode.MARKET
        self.top_rows: int = 0
        self.bottom_rows: int = 0
        self.categories: dict[str, CommodityCategory] = {}
        self.commodity_table: list[TableEntry] = []
        self.table_view: Optional[TableView] = None
        self.view_mode_var = tk.StringVar()
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

        self.prev_btn = tk.Label(frame, image=self.icons['left_arrow'], cursor="hand2")
        self.prev_btn.bind("<Button-1>", partial(self.event, "prev"))
        self.prev_btn.grid(row=0, column=0, sticky=tk.W)

        self.title = tk.Label(frame, text="", justify=tk.CENTER, anchor=tk.CENTER)
        self.title.grid(row=0, column=1, sticky=tk.EW)

        self.next_btn = tk.Label(frame, image=self.icons['right_arrow'], cursor="hand2")
        self.next_btn.bind("<Button-1>", partial(self.event, "next"))
        self.next_btn.grid(row=0, column=2, sticky=tk.W)

        self.view_mode_var.set(ptl(str(self.view_mode)))
        self.view_btn = tk.Menubutton(frame, direction='below', image=self.icons['view_close'], cursor="hand2")
        self.view_btn.menu = tk.Menu(self.view_btn, tearoff=0)
        self.view_btn["menu"] = self.view_btn.menu
        self.view_btn.menu.add_command(label=ptl("Filter mode"))
        self.view_btn.menu.add_separator()
        for v in list(ViewMode):
            self.view_btn.menu.add_radiobutton(label=ptl(str(v)), variable=self.view_mode_var, command=self.change_view)
        self.view_btn.grid(row=0, column=3, padx=4, sticky=tk.E)

        self.sorting_var.set(ptl(str(self.sorting_mode)))
        self.sorting_btn = tk.Menubutton(frame, direction='below', image=self.icons['view_sort'], cursor="hand2")
        self.sorting_btn.menu = tk.Menu(self.sorting_btn, tearoff=0)
        self.sorting_btn["menu"] = self.sorting_btn.menu
        self.sorting_btn.menu.add_command(label=ptl("Sorting mode"))
        self.sorting_btn.menu.add_separator()
        for v in list(SortingMode):
            self.sorting_btn.menu.add_radiobutton(label=ptl(str(v)), variable=self.sorting_var,
                                                  command=self.change_sorting)
        self.sorting_btn.grid(row=0, column=4, padx=4, sticky=tk.E)

        ReportLabel(frame, text=ptl("Report")).grid(row=0, column=5, padx=(4, 0))

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

        if self.scrollable_conf:
            self.table_view = CanvasTableView(self, self.table_frame)
        else:
            self.table_view = FrameTableView(self, self.table_frame)

        theme.update(self.table_frame)
        theme.update(self.frame)

    def event(self, event: str, tk_event: tk.Event | None) -> None:
        if event in self.subscribers:
            self.subscribers[event](tk_event)

    def on(self, event: str, function: Callable[[tk.Event | None], None]) -> None:
        self.subscribers[event] = function

    def change_view(self) -> None:
        view_mode = self.view_mode_var.get()
        index = [ptl(str(e)) for e in ViewMode].index(view_mode)
        self.view_mode = list(ViewMode)[index]
        if self.view_mode == ViewMode.NONE:
            self.view_btn['image'] = self.icons['view_close']
            self.table_frame.grid_remove()
        else:
            self.view_btn['image'] = self.icons['view_open']
            self.table_frame.grid(row=self.next_row(), column=0, sticky=tk.EW)
        self.event('update', None)

    def change_sorting(self):
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
        if not self.scrollable_conf and row >= self.max_rows_conf:
            row = self.max_rows_conf-1

        fg_color = theme.current['highlight'] if theme.current else 'blue'
        self.table_view.fg(fg_color)

        if cc.collapsed == CollapseMode.LEADING:
            self.table_view.draw_text(row, 'name', '▲ ({}) {}'.format(len(cc.rows), ptl(cc.symbol), crop=True))
            self.table_view.bind_action(row, lambda e,cnt=len(cc.rows): self._decr_top_rows(e,cnt))
        elif cc.collapsed == CollapseMode.TRAILING:
            self.table_view.draw_text(row, 'name', '▼ ({}) {}'.format(len(cc.rows), ptl(cc.symbol)), crop=True)
            self.table_view.bind_action(row, lambda e,cnt=len(cc.rows): self._incr_top_rows(e,cnt))
        elif self.collapsable_conf and not self.scrollable_conf:
            if cc.collapsed:
                self.table_view.draw_text(row, 'name', '▶ ({}) {}'.format(len(cc.rows), ptl(cc.symbol)), crop=True)
            else:
                self.table_view.draw_text(row, 'name', '▽ ' + ptl(cc.symbol))
            self.table_view.bind_action(row, lambda e,category=cc.symbol: self._toggle_category(e,category))
        else:
            self.table_view.draw_text(row, 'name', ptl(cc.symbol))

        self.table_view.draw_text(row, 'cargo', None)
        self.table_view.draw_text(row, 'carrier', None)
        if cc.collapsed != CollapseMode.EXPANDED:
            self.table_view.draw_text(row, 'demand', cc.unload())
            self.table_view.draw_text(row, 'buy', cc.buy())
        else:
            self.table_view.draw_text(row, 'demand', None)
            self.table_view.draw_text(row, 'buy', None)

    def _show_commodity(self, row: int, i: TableEntry):
        c: Commodity = i.commodity

        fg_color = theme.current['foreground'] if theme.current else 'black'
        fg_name_color = fg_color if i.buy() <= 0 or i.available else 'dim gray' #'#FFF'
        self.table_view.fg(fg_color)

        self.table_view.fg(fg_name_color).draw_text(row, 'name', c.name, crop=True)
        self.table_view.fg(fg_color).draw_text(row, 'demand', i.unload())
        self.table_view.fg(fg_color).draw_text(row, 'cargo', i.cargo)
        self.table_view.fg(fg_color).draw_text(row, 'carrier', i.carrier)
        self.table_view.fg(fg_color).draw_text(row, 'buy', i.buy())

    def set_table(self, table: list[TableEntry], docked):
        self.commodity_table = table

        if not self.table_view:
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
            if not i or i.demand <= 0:
                continue
            if self.view_mode == ViewMode.LACKS:
                if i.buy() <= 0:
                    continue
            if self.view_mode == ViewMode.FILTERED:
                if not docked:
                    if not i.available or i.buy() <= 0:
                        continue
                elif docked == "carrier":
                    if i.buy() <= 0:
                        continue
            if show_categories and (not cc or i.category() != cc.symbol):
                if not cc or i.category() != cc.symbol:
                    cc = self.categories.get(i.category())
                    if not cc:
                        cc = CommodityCategory(i.category())
                        self.categories[cc.symbol] = cc
                    display_list.append(cc)
            if self.collapsable_conf and not self.scrollable_conf and cc and cc.collapsed:
                cc.rows.append(i)
            else:
                display_list.append(i)
        if self.view_mode == ViewMode.NONE:
            self.top_rows = 0
            self.bottom_rows = 0
            display_list.clear()
        if self.scrollable_conf:
            self.top_rows = 0
        # collapse first rows into 'others'
        if self.top_rows > 0 and len(display_list) > self.max_rows_conf:
            cc_others = CommodityCategory("Others Commodities", CollapseMode.LEADING)
            while len(cc_others.rows) < self.top_rows and len(display_list) > self.max_rows_conf - 1:
                cc_others.rows.append(display_list.popleft())
            display_list.appendleft(cc_others)
            self.top_rows = len(cc_others.rows)
        # collapse last rows into 'others'
        self.bottom_rows = 0
        if not self.scrollable_conf and len(display_list) > self.max_rows_conf:
            cc_others = CommodityCategory("Others Commodities", CollapseMode.TRAILING)
            while len(display_list) > self.max_rows_conf - 1:
                cc_others.rows.append(display_list.pop())
            display_list.append(cc_others)
            self.bottom_rows = len(cc_others.rows)

        self.table_view.draw_start()
        row = 0
        for i in display_list:
            if isinstance(i, TableEntry):
                self._show_commodity(row, i)
            else:
                self._show_category(row, i)
            row += 1

        self.table_view.draw_finish()

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
        if maxcargo <= 0:
            maxcargo = 784
        if self.total_label and theme.current:
            if Config.SHOW_TOTALS.get():
                flight = float(cargo)/float(maxcargo)
                self.total_label['text'] = ptl("Remaining {0:.1f} flights at {1} tons each, total {2} t").format(flight, maxcargo, cargo)
                if color:
                    self.total_label['fg'] = color
                else:
                    self.total_label['fg'] = theme.current['foreground']
                self.total_label.grid()
            else:
                self.total_label.grid_remove()


class TableView(ABC):
    COLUMNS = ['name', 'buy', 'demand', 'carrier', 'cargo' ]

    def __init__(self, main_ui: MainUi, parent: tk.Widget) -> None:
        self.main_ui = main_ui
        self.parent_frame = parent
        self._fg = None

    @abstractmethod
    def reset(self) -> Self:
        return self

    def fg(self, fg: str) -> Self:
        self._fg = fg
        return self

    @abstractmethod
    def draw_start(self) -> Self:
        return self

    @abstractmethod
    def draw_finish(self) -> Self:
        return self

    @abstractmethod
    def draw_text(self, row: int, col: int|str, text: str|int|None=None, *, crop=False) -> Self:
        return self

    @abstractmethod
    def bind_action(self, row: int, action: Callable) -> Self:
        return self


class FrameTableView(TableView):
    def __init__(self, main_ui: MainUi, parent: tk.Widget) -> None:
        super().__init__(main_ui, parent)
        self.frame = tk.Frame(parent, pady=3, padx=3)
        self.frame.grid(sticky=tk.NSEW)
        self.rows = []
        self.row = 0
        self.reset()

    def reset(self):
        tk.Label(self.parent_frame, text=ptl("Commodity"), width=22).grid(row=0, column=0, sticky=tk.W)
        tk.Label(self.parent_frame, text=ptl("Buy"), width=6).grid(row=0, column=1, sticky=tk.E)
        tk.Label(self.parent_frame, text=ptl("Demand"), width=6).grid(row=0, column=2, sticky=tk.E)
        tk.Label(self.parent_frame, text=ptl("Carrier"), width=6).grid(row=0, column=3, sticky=tk.E)
        tk.Label(self.parent_frame, text=ptl("Cargo"), width=4).grid(row=0, column=4, sticky=tk.E)

        self.rows = []
        for i in range(self.main_ui.max_rows_conf):
            self.parent_frame.grid_rowconfigure(i+1, pad=0)
            labels = {
                'name': tk.Label(self.parent_frame, anchor=tk.W, justify=tk.LEFT, pady=0, width=22),
                'buy': tk.Label(self.parent_frame, anchor=tk.E, pady=0, width=6),
                'demand': tk.Label(self.parent_frame, anchor=tk.E, pady=0, width=6),
                'carrier': tk.Label(self.parent_frame, anchor=tk.E, pady=0, width=6),
                'cargo': tk.Label(self.parent_frame, anchor=tk.E, pady=0, width=4),
            }
            labels['name'].grid_configure(sticky=tk.W)
            for label in labels.values():
                label.grid_remove()
            self.rows.append(labels)

    def draw_start(self):
        self.row = 0

    def draw_finish(self):
        for r in range(self.row+1, len(self.rows)):
            for c in self.COLUMNS:
                self.rows[r][c].grid_remove()
        if self.row == 0:
            self.parent_frame.grid_remove()
        else:
            self.parent_frame.grid()

    def draw_text(self, row: int, col: int|str, text: str|int|None=None, *, crop=False) -> Self:
        if row >= len(self.rows):
            return
        if isinstance(col, str):
            cname = col
            col = self.COLUMNS.index(cname)
        else:
            cname = self.COLUMNS[col]
        if isinstance(text, int):
            text = '{:8,d}'.format(text)
        if not text or len(text) == 0:
            self.rows[row][cname].grid_remove()
            return
        self.rows[row][cname]['text'] = text
        self.rows[row][cname]['fg'] = self._fg
        self.rows[row][cname].grid(row=row+1, column=col)
        self.row = max(self.row, row)

    def bind_action(self, row: int, action: Callable) -> Self:
        if row < len(self.rows):
            self.rows[row]['name'].bind("<Button-1>", action)
        return self


class CanvasTableView(TableView):
    PAD_X = 5
    PAD_Y = 5
    TABLE_WIDTH = 350
    COLUMN_WIDTH = [145, 50, 50, 50, 45]
    COLUMN_START = []
    ROW_HEIGHT = 16
    ATTRIBUTES = [
        {'justify': tk.LEFT,  'anchor': tk.NW},
        {'justify': tk.RIGHT, 'anchor': tk.NE},
        {'justify': tk.RIGHT, 'anchor': tk.NE},
        {'justify': tk.RIGHT, 'anchor': tk.NE},
        {'justify': tk.RIGHT, 'anchor': tk.NE},
    ]
    HEADER_ATTRIBUTES = {'justify': tk.LEFT,  'anchor': tk.N}


    def __init__(self, main_ui: MainUi, parent: tk.Widget) -> None:
        super().__init__(main_ui, parent)
        if len(self.COLUMN_START) == 0:
            x = self.PAD_X
            for w in self.COLUMN_WIDTH:
                self.COLUMN_START.append(x)
                x += w
            x += self.PAD_X
            # self.TABLE_WIDTH = x

        self.frame = tk.Frame(parent, pady=3, padx=3)
        self.frame.grid(sticky=tk.NSEW)
        self.canvas: Optional[tk.Canvas] = None
        self.row = 0
        self.resizing = False
        self.resizing_y_start = 0
        self.resizing_h_start = 0
        self.reset()
        theme.update(self.frame)

    def reset(self):
        self.canvas = tk.Canvas(self.frame, width=self.TABLE_WIDTH, height=200, highlightthickness=0,
                                scrollregion=(0, 0, self.TABLE_WIDTH, 1000))
        self.canvas.pack()
        frame = tk.Frame(self.frame)
        frame.pack(side=tk.RIGHT, fill=tk.Y)
        vbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(expand=True,fill=tk.BOTH)
        sizegrip = tk.Label(frame, image=self.main_ui.icons['resize'], cursor="sizing")
        sizegrip.pack(side=tk.BOTTOM, anchor=tk.SE)
        sizegrip.bind("<ButtonPress-1>", self.start_resize)
        sizegrip.bind("<ButtonRelease-1>", self.stop_resize)
        sizegrip.bind("<Motion>", self.resize_frame)
        self.canvas.config(yscrollcommand=vbar.set)
        self.canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        theme.update(frame)
        theme.update(self.canvas)

    def start_resize(self, event: tk.Event):
        self.resizing_y_start = event.y_root
        self.resizing_h_start = self.canvas.winfo_height()
        self.resizing = True

    def stop_resize(self, event: tk.Event):  # pylint: disable=W0613
        self.resizing_y_start = 0
        self.resizing_h_start = 0
        self.resizing = False

    def resize_frame(self, event: tk.Event):
        if self.resizing:
            delta = self.resizing_y_start - event.y_root
            height = self.resizing_h_start - delta
            height = min(max(height, 100), 400)
            self.canvas.config(height=height)

    def draw_start(self):
        self.row = 0
        self.canvas.delete('all')
        self.draw_text(-1, 0, ptl("Commodity"))
        self.draw_text(-1, 1, ptl("Buy"))
        self.draw_text(-1, 2, ptl("Demand"))
        self.draw_text(-1, 3, ptl("Carrier"))
        self.draw_text(-1, 4, ptl("Cargo"))

    def draw_finish(self):
        self.canvas.configure(scrollregion=(0, 0, self.TABLE_WIDTH, self.PAD_Y * 2 + (self.row + 1) * self.ROW_HEIGHT))

    def draw_text(self, row: int, col: int|str, text: str|int|None=None, *, crop=False) -> Self:
        row += 1  # first row is table labels
        if isinstance(text, int):
            text = '{:8,d}'.format(text)
        if not text or len(text) == 0:
            return

        if isinstance(col, str):
            col = self.COLUMNS.index(col)

        if crop:
            font = tk.font.Font()
            w = font.measure(text)
            cropped = w > self.COLUMN_WIDTH[col]+40
            while w > self.COLUMN_WIDTH[col]+40:
                text = text[:-1]
                w = font.measure(text)
            if cropped:
                text += '…'

        x = self.COLUMN_START[col]
        y = row * self.ROW_HEIGHT + self.PAD_Y
        attr = self.ATTRIBUTES[col]
        if row == 0:
            attr = self.HEADER_ATTRIBUTES
            x += 5 + self.COLUMN_WIDTH[col] / 2
        elif col > 0:
            x += self.COLUMN_WIDTH[col]
        self.canvas.create_text(x, y, text=text, fill=self._fg, **attr)
        self.row = max(self.row, row)

    def bind_action(self, row: int, action: Callable) -> Self:   # pylint: disable=W0613
        # not implemented
        return self
