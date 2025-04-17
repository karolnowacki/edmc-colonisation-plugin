import tkinter as tk
from tkinter import ttk
from functools import partial
from typing import Callable, Optional

from companion import session, Session
import myNotebook as nb

from .data import ptl
from .colonization import ColonizationPlugin
from .colonization import Construction
from .colonization import FleetCarrier
from .config import Config


class PreferencesUi:
    PAD_X = 10
    PAD_Y = 10

    def __init__(self, plugin: ColonizationPlugin) -> None:
        self.plugin = plugin
        self.row = 0
        self.subscribers: dict[str, Callable[[tk.Event], None]] = {}
        self.frame: Optional[ttk.Frame] = None
        self.fc_callsign: Optional[tk.Label] = None
        self.fc_last_update: Optional[tk.Label] = None
        self.construction_list: Optional[ttk.Frame] = None
        self.ignore_fc_update: Optional[tk.Variable] = None
        self.show_station_name: Optional[tk.Variable] = None
        self.show_totals: Optional[tk.Variable] = None
        self.var_categories: Optional[tk.Variable] | None = None
        self.var_collapsable: Optional[tk.Variable] | None = None
        self.var_rows: Optional[tk.Variable] | None = None

    def plugin_prefs(self, parent: ttk.Notebook, cmdr: str, is_beta: bool) -> nb.Frame:  # pylint: disable=W0613
        self.frame = nb.Frame(parent)
        self.frame.columnconfigure(1, weight=1)
        self.frame.grid(sticky=tk.EW)

        frame = ttk.Frame(self.frame, style='nb.TFrame')
        frame.grid(row=self.row, sticky=tk.EW, padx=self.PAD_X, pady=self.PAD_Y)
        nb.Label(frame, text=ptl("Fleet carrier call sign:")).grid(row=0, column=0)
        self.fc_callsign = nb.Label(frame, text=self.plugin.carrier.call_sign)
        self.fc_callsign.grid(row=0, column=1)
        nb.Label(frame, text=ptl("Fleet carrier last update:")).grid(row=1, column=0)
        self.fc_last_update = nb.Label(frame, text=self.plugin.carrier.last_sync)
        self.fc_last_update.grid(row=1, column=1)
        btn = nb.Button(frame, text=ptl("Load FC data"), command=self.call_capi_fc)
        btn.grid(row=3, columnspan=2, sticky=tk.EW, pady=5)
        self.ignore_fc_update = Config.IGNORE_FC_UPDATE.tk_var()
        nb.Checkbutton(frame, text=ptl("Ignore event based cAPI Fleet Carrier update"),
                       variable=self.ignore_fc_update).grid(row=4, columnspan=2, sticky=tk.W)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).grid(row=self.next_row(), sticky=tk.EW, padx=self.PAD_X)

        self.show_station_name = Config.SHOW_STATION_NAME.tk_var()
        nb.Checkbutton(self.frame, text=ptl("Show station name line"), variable=self.show_station_name).grid(
            row=self.next_row(), sticky=tk.W, padx=self.PAD_X, pady=(self.PAD_Y, 0))

        self.show_totals = Config.SHOW_TOTALS.tk_var()
        nb.Checkbutton(self.frame, text=ptl("Show totals line"), variable=self.show_totals).grid(
            row=self.next_row(), sticky=tk.W, padx=self.PAD_X)

        self.var_categories = Config.CATEGORIES.tk_var()
        nb.Checkbutton(frame, text=ptl("Show commodity categories"), variable=self.var_categories,
                       command=self._on_categories_change).grid(row=self.next_row(), sticky=tk.W, padx=self.PAD_X)

        self.var_collapsable = Config.COLLAPSABLE.tk_var()
        nb.Checkbutton(frame, text=ptl("Collapsable commodity categories"), variable=self.var_collapsable,
                       command=self._on_collapsable_change).grid(row=self.next_row(), sticky=tk.W, padx=self.PAD_X)

        nb.Label(frame, text=ptl("Commodity rows:")).grid(row=self.row, column=0, sticky=tk.W)
        self.var_rows = Config.ROWS.tk_string_var()
        nb.OptionMenu(frame, self.var_rows, self.var_rows.get(), *['10', '15','20','25','30','35'],
                      command=self._on_rows_change).grid(row=self.next_row(), column=1, padx=1, pady=1, sticky=tk.W)

        ttk.Separator(self.frame, orient=tk.HORIZONTAL).grid(row=self.next_row(),
                                                             sticky=tk.EW, padx=self.PAD_X, pady=(self.PAD_Y, 0))

        self.construction_list = ttk.Frame(self.frame, style='nb.TFrame')
        self.construction_list.grid(row=self.next_row(), column=0, sticky=tk.EW, padx=self.PAD_X, pady=self.PAD_Y)
        self.build_construction_list()

        return self.frame

    def build_construction_list(self) -> None:
        if not self.construction_list:
            return
        for widget in self.construction_list.winfo_children():
            widget.destroy()

        row = 0

        nb.Label(self.construction_list, text=ptl("List of tracked construction sites")).grid(row=row, column=0,
                                                                                         columnspan=2)
        row += 1
        for c in self.plugin.constructions:
            nb.Label(self.construction_list, text=c.system).grid(row=row, column=0, sticky=tk.W)
            nb.Label(self.construction_list, text=c.get_name()).grid(row=row, column=1, sticky=tk.W)
            ttk.Button(self.construction_list, text=ptl("Remove from tracking"),
                       command=partial(self.remove_construction, c)).grid(row=row, column=2, pady=2, padx=5)
            row += 1

    def next_row(self) -> int:
        self.row += 1
        return self.row

    def event(self, event: str, tk_event: tk.Event) -> None:
        if event in self.subscribers:
            self.subscribers[event](tk_event)

    def on(self, event: str, function: Callable[[tk.Event], None]) -> None:
        self.subscribers[event] = function

    def remove_construction(self, construction: Construction) -> None:
        self.plugin.remove_construction(construction)
        self.build_construction_list()

    def update_fc(self, carrier: FleetCarrier) -> None:
        if self.fc_callsign and self.fc_last_update:
            self.fc_callsign['text'] = str(carrier.call_sign)
            self.fc_last_update['text'] = str(carrier.last_sync)

    def call_capi_fc(self) -> None:
        if session.state == Session.STATE_OK:
            if self.fc_last_update:
                self.fc_last_update['text'] = "Updating..."

            carrier = session.requests_session.get(
                session.capi_host_for_galaxy() + session.FRONTIER_CAPI_PATH_FLEETCARRIER)
            data = carrier.json()
            self.plugin.capi_fleetcarrier(data)
            if self.fc_callsign and self.fc_last_update:
                if self.plugin.carrier and self.plugin.carrier.call_sign:
                    self.fc_callsign['text'] = str(self.plugin.carrier.call_sign)
                    self.fc_last_update['text'] = str(self.plugin.carrier.last_sync)
                else:
                    self.fc_callsign['text'] = ""
                    self.fc_last_update['text'] = "Missing Fleet Carrier data"
        elif self.fc_last_update:
            self.fc_last_update['text'] = "cAPI session is not open."

    def prefs_changed(self, cmdr:str, is_beta:bool) -> None:  # pylint: disable=W0613
        if self.ignore_fc_update:
            Config.IGNORE_FC_UPDATE.set(self.ignore_fc_update.get())
        if self.show_totals:
            Config.SHOW_TOTALS.set(self.show_totals.get())
        if self.show_station_name:
            Config.SHOW_STATION_NAME.set(self.show_station_name.get())

        self.plugin.update_language()
        self.plugin.update_display()


    def _on_categories_change(self) -> None:
        value: bool = self.var_categories.get()
        if value != Config.CATEGORIES.get():
            self.plugin.ui.categories_conf = value
            Config.CATEGORIES.set(value)
            self.plugin.update_display()

    def _on_collapsable_change(self) -> None:
        value: bool = self.var_collapsable.get()
        if value != Config.COLLAPSABLE.get():
            self.plugin.ui.collapsable_conf = value
            Config.COLLAPSABLE.set(value)
            self.plugin.update_display()

    def _on_rows_change(self, *_) -> None:
        value: int = int(self.var_rows.get())
        if value != Config.ROWS.get():
            self.plugin.ui.rows_conf = value
            Config.ROWS.set(value)
            self.plugin.ui.reset_frame()
            self.plugin.update_display()
