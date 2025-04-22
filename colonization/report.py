import json
import os
import re
import pathlib
import threading
import tkinter as tk
import queue

from datetime import datetime, timedelta
from os.path import basename, getctime
from tkinter import ttk
from tkinter import font as tk_font
from typing import Any, TextIO, MutableMapping, Optional

from theme import theme as edmc_theme
from config import config as edmc_config
from .data import ptl

_RE_LOGFILE = re.compile(r'^Journal(Alpha|Beta)?\.[0-9]{2,4}(-)?[0-9]{2}(-)?[0-9]{2}(T)?[0-9]{2}[0-9]{2}[0-9]{2}'
                         r'\.[0-9]{2}\.log$')


def full_logs_scan():
    if WindowReport.toplevel:
        return
    WindowReport().show()


class ReportLabel(tk.Label):
    def __init__(self, master: ttk.Frame | tk.Frame | None = None, **kw: Any) -> None:
        fg_color = edmc_theme.current['highlight'] if edmc_theme.current else 'blue'
        self.foreground = kw.get('foreground', fg_color)
        ttk.Label.__init__(self, master, **kw)
        self.font_u: tk_font.Font
        self.font_n = None
        self.bind('<Button-1>', self._click)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        # set up initial appearance
        self.configure(state=kw.get('state', tk.NORMAL),
                       text=kw.get('text'),
                       foreground=self.foreground,
                       font=kw.get('font', ttk.Style().lookup('TLabel', 'font')))

    def configure(self, cnf: dict[str, Any] | None = None, **kw: Any) -> dict[str, tuple[str, str, str, Any, Any]] | None:
        if 'foreground' in kw:
            setattr(self, 'foreground', kw['foreground'])
        if 'font' in kw:
            self.font_n = kw['font']
            self.font_u = tk_font.Font(font=self.font_n)
            self.font_u.configure(underline=True)
            kw['font'] = self.font_n
        return super().configure(cnf, **kw)

    def _enter(self, event: tk.Event) -> None:
        if str(self['state']) != tk.DISABLED:
            super().configure(font=self.font_u)

    def _leave(self, event: tk.Event) -> None:
        super().configure(font=self.font_n)

    def _click(self, event: tk.Event) -> None:
        full_logs_scan()


class Station:
    def __init__(self, marketId: int, name: str, loc_name: Optional[str], st_type: str, system: str):
        self.marketId: int = marketId
        self.stationName: str = name
        self.stationLocName: Optional[str] = loc_name
        self.stationType: str = st_type
        self.starSystem: str = system
        self.complete: bool = False
        self.failed: bool = False
        self.contributed: dict[str, int] = {}

    def name(self):
        nm = self.stationName if self.stationLocName is None else self.stationLocName
        if nm.startswith("Orbital Construction Site: "):
            nm = nm[26:].strip()
        elif nm.startswith("Planetary Construction Site: "):
            nm = nm[28:].strip()
        return nm

    def __str__(self):
        if self.stationLocName:
            return f'{self.stationLocName} in {self.starSystem} ({self.marketId})'
        else:
            return f'{self.stationName} in {self.starSystem} ({self.marketId})'


class ScrolledText(tk.Text):
    def __init__(self, master=None, **kw):
        self.frame = tk.Frame(master)
        self.vbar = tk.Scrollbar(self.frame)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)

        kw.update({'yscrollcommand': self.vbar.set})
        tk.Text.__init__(self, self.frame, **kw)
        self.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar['command'] = self.yview

        # Copy geometry methods of self.frame without overriding Text
        # methods -- hack!
        text_meths = vars(tk.Text).keys()
        methods = vars(tk.Pack).keys() | vars(tk.Grid).keys() | vars(tk.Place).keys()
        methods = methods.difference(text_meths)

        for m in methods:
            if m[0] != '_' and m != 'config' and m != 'configure':
                setattr(self, m, getattr(self.frame, m))

    def __str__(self):
        return str(self.frame)


def _commodity_name(c: dict[str, Any]):
    name: str = c.get("Name_Localised")
    if not name:
        name = c.get("Name")
        if name.startswith("$") and name.endswith("_name;"):
            name = name[1:-6]
    return name


class WindowReport:
    toplevel: Optional[tk.Toplevel] = None

    def __init__(self):
        self.frame: Optional[tk.Frame] = None
        self.spinbox: Optional[tk.Spinbox] = None
        self.verbose_var: Optional[tk.BooleanVar] = None
        self.verbose_cb: Optional[tk.Checkbutton] = None
        self.progress_lbl: Optional[tk.Label] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.progress_var: Optional[tk.IntVar] = None
        self.logtext: Optional[ScrolledText] = None
        self.tracefile: Optional[TextIO] = None
        self.cmdr: Optional[str] = None
        self.cmdrFID: Optional[str] = None
        self.marketId: Optional[int] = None
        self.stations: dict[int, Station] = {}
        self.timestamp: str = ''
        self.weeks_var: Optional[tk.StringVar] = None
        self.ui_queue: queue.Queue = queue.Queue()
        self.thread: Optional[threading.Thread] = None
        self.verbose: bool = False

    def show(self):
        if self.toplevel:
            self.toplevel.lift()
            return
        self.toplevel = tk.Toplevel()
        self.toplevel.resizable(tk.TRUE, tk.TRUE)
        self.frame = tk.Frame(self.toplevel, relief=tk.GROOVE)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        tk.Label(self.frame, text=ptl("Generate colonization report for last weeks:")).grid(
            row=0, column=0, sticky=tk.E
        )
        self.weeks_var = tk.StringVar(value="4")
        self.spinbox = tk.Spinbox(self.frame, width=3, from_=0, to=12*4, textvariable=self.weeks_var)
        self.spinbox.grid(row=0, column=1, padx=20, sticky=tk.W)
        self.verbose_var = tk.BooleanVar(value=self.verbose)
        self.verbose_cb = tk.Checkbutton(self.frame, text=ptl("Verbose log"), variable=self.verbose_var)
        self.verbose_cb.grid(row=0, column=2, sticky=tk.E)
        tk.Button(self.frame, text=ptl("Generate report"), command=self._generate_report).grid(
            row=1, columnspan=3
        )
        self.progress_lbl = tk.Label(self.frame, text=ptl('Progress:'))
        self.progress_lbl.grid(row=2, column=0, sticky=tk.EW)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self.frame, orient=tk.HORIZONTAL, maximum=100, variable=self.progress_var, )
        self.progress_bar.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=10)
        self.logtext = ScrolledText(self.frame, height=10)
        self.logtext.grid(row=3, columnspan=3, sticky=tk.NSEW)
        self.frame.rowconfigure(3, weight=1)
        self.frame.pack(expand=True, fill=tk.BOTH, pady=5, padx=5)

    def _generate_report(self):
        self.verbose = self.verbose_var.get()
        self.thread = threading.Thread(target=self._generate_report_worker, daemon=True)
        self.thread.start()

    def _generate_report_worker(self):
        self.ui_queue.put(('clear', None))
        journal_dir: str | None = edmc_config.get_str('journaldir') or edmc_config.default_journal_dir
        journal_dir_path = pathlib.Path.expanduser(pathlib.Path(journal_dir))
        journal_files = (x for x in os.listdir(journal_dir_path) if _RE_LOGFILE.search(x))
        today = datetime.now()
        n_days_ago = (today - timedelta(days=7*int(self.weeks_var.get()))).timestamp()
        if journal_files:
            journal_files = (journal_dir_path / pathlib.Path(x) for x in journal_files)
            latest_journal_files = (x for x in journal_files if os.path.getctime(x) > n_days_ago)
            sorted_latest_journal_files = sorted(latest_journal_files, key=getctime)
            num_latest_journal_files = len(sorted_latest_journal_files)
            tracefile_name = os.path.abspath(os.path.join(edmc_config.plugin_dir_path, "../colonization.log"))
            with open(tracefile_name, "wt", encoding='utf-8') as tracefile:
                self.tracefile = tracefile
                self.toplevel.after(100, self.refresh_data)
                self.progress(ptl("Starting..."), 0)
                for i in range(num_latest_journal_files):
                    logfile = sorted_latest_journal_files[i]
                    with open(logfile, 'rb') as loghandle:
                        self.progress(basename(logfile), int((1+i*100) / num_latest_journal_files))
                        tracefile.write(f'File: {logfile}\n')
                        tracefile.flush()
                        for line in loghandle:
                            self.parse_entry(line)
                self.progress(ptl("Done"), 100)
                self.ui_queue.put(('clear', None))
                tracefile.write('\nTotal:\n')
                for station in self.stations.values():
                    if len(station.contributed):
                        for cmdr, contr in station.contributed.items():
                            self.log(f'{cmdr}:\t{contr:6d} ton to "{station.name()}" ({station.starSystem})\n')
            self.tracefile = None

    def log(self, text: str, *, verbose:bool = False):
        if verbose and not self.verbose:
            return
        self.tracefile.write(self.timestamp + ": " + text)
        # self.tracefile.flush()
        self.ui_queue.put(('log', text))

    def progress(self, text: str, percent: int):
        self.ui_queue.put(('status', text))
        self.ui_queue.put(('progress', percent))

    def refresh_data(self):
        if (not self.thread or not self.thread.is_alive()) and self.ui_queue.empty():
            return
        # refresh the GUI with new data from the queue
        while not self.ui_queue.empty():
            key, data = self.ui_queue.get()
            if key == 'log':
                self.logtext.insert(tk.END, data)
            elif key == 'status':
                self.progress_lbl['text'] = data
            elif key == 'progress':
                self.progress_var.set(int(data))
            elif key == 'clear':
                self.logtext.delete('1.0', tk.END)
        self.toplevel.after(100, self.refresh_data)  # called only once!

    def _set_current_location(self, entry: MutableMapping[str, Any]) -> Station:
        self.marketId = entry['MarketID']
        station = self.stations.get(self.marketId, None)
        if not station:
            station = Station(self.marketId, entry['StationName'], entry.get('StationName_Localised'), entry['StationType'], entry['StarSystem'])
            self.stations[self.marketId] = station
        if entry['StationName'] != station.stationName:
            new_name = entry['StationName']
            self.log(f'Station renamed from "{station.stationName}" to "{new_name}"\n')
            station.stationName = new_name
            station.stationLocName = entry.get('StationName_Localised', None)
        return station

    def parse_entry(self, line: bytes):
        if line is None:
            return
        try:
            # Preserve property order because why not?
            entry: MutableMapping[str, Any] = json.loads(line)
            assert 'timestamp' in entry, "Timestamp does not exist in the entry"

            event_type = entry['event'].lower()
            self.timestamp = entry['timestamp']

            if event_type == 'fileheader':
                self.cmdr = None
                self.cmdrFID = None
                self.marketId = None

            elif event_type == 'commander':
                if self.cmdr != entry['Name'] or self.cmdrFID != entry['FID']:
                    self.cmdr = entry['Name']
                    self.cmdrFID = entry['FID']
                    self.marketId = None
                # self.log(f'"Commander" event, {self.cmdr}, {self.cmdrFID}\n')

            elif event_type == 'location':
                if not entry.get('MarketID', False):
                    return
                station = self._set_current_location(entry)
                self.log(f'Location: {self.cmdr} is at: {station}\n', verbose=True)
            elif event_type == 'docked':
                station = self._set_current_location(entry)
                self.log(f'Docked: {self.cmdr} docked at: {station}\n', verbose=True)
            elif event_type == 'undocked':
                self.marketId = None
                self.log(f'Undocked\n', verbose=True)

            elif event_type == 'colonisationcontribution':
                market_id = entry['MarketID']
                if self.marketId != market_id:
                    self.log(f'Invalid "ColonisationContribution" entry: {market_id} != {self.marketId}\n')
                    return
                if market_id not in self.stations:
                    self.log(f'Invalid "ColonisationContribution" entry: unknown marketId {market_id}\n')
                    return
                station = self.stations[market_id]
                contributed = sum([x["Amount"] for x in entry["Contributions"]])
                self.log(f'cmdr:{self.cmdr} contributed {contributed:3d} ton to "{station}"\n')
                if self.verbose:
                    spaces = ' ' * len(f'cmdr:{self.cmdr} contributed')
                    for x in entry["Contributions"]:
                        self.log(f'{spaces} {x["Amount"]:3d} ton of "{_commodity_name(x)}"\n', verbose=True)
                if self.cmdr in station.contributed:
                    station.contributed[self.cmdr] += contributed
                else:
                    station.contributed[self.cmdr] = contributed

            elif event_type == "colonisationconstructiondepot":
                market_id = entry['MarketID']
                if self.marketId != market_id:
                    self.log(f'Invalid "ColonisationConstructionDepot" entry: {market_id} != {self.marketId}\n')
                    return
                if market_id not in self.stations:
                    self.log(f'Invalid "ColonisationConstructionDepot" entry: unknown marketId {market_id}\n')
                    return
                station = self.stations[market_id]
                if entry['ConstructionComplete']:
                    self.log(f'Construction complete: {station}\n', verbose=station.complete)
                    station.complete = True
                if entry['ConstructionFailed']:
                    self.log(f'Construction failed: {station}\n', verbose=station.failed)
                    station.failed = True

        except Exception as ex:
            self.log(f'Invalid journal entry:\n{line!r}\nexception: {ex}\n')
            return

