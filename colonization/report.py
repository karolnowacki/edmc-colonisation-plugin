import json
import os
import re
import pathlib
import threading
import tkinter as tk
import queue

from datetime import datetime, timedelta
from os.path import basename, getctime
from tkinter import scrolledtext, ttk
from typing import Any, TextIO, MutableMapping, Optional

from config import config as edmc_config

_RE_LOGFILE = re.compile(r'^Journal(Alpha|Beta)?\.[0-9]{2,4}(-)?[0-9]{2}(-)?[0-9]{2}(T)?[0-9]{2}[0-9]{2}[0-9]{2}'
                         r'\.[0-9]{2}\.log$')


def full_logs_scan():
    if WindowReport.toplevel:
        return
    WindowReport().show()

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
            nm = nm[26:].strip()
        return nm

    def __str__(self):
        if self.stationLocName:
            return f'{self.stationLocName} in {self.starSystem} ({self.marketId})'
        else:
            return f'{self.stationName} in {self.starSystem} ({self.marketId})'


class WindowReport:
    toplevel: Optional[tk.Toplevel] = None

    def __init__(self):
        self.frame: Optional[tk.Frame] = None
        self.spinbox: Optional[tk.Spinbox] = None
        self.progress_lbl: Optional[tk.Label] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.progress_var: Optional[tk.IntVar] = None
        self.logtext: Optional[scrolledtext.ScrolledText] = None
        self.tracefile: Optional[TextIO] = None
        self.cmdr: Optional[str] = None
        self.cmdrFID: Optional[str] = None
        self.marketId: Optional[int] = None
        self.stations: dict[int, Station] = {}
        self.timestamp: str = ''
        self.weeks_var: Optional[tk.StringVar] = None
        self.ui_queue: queue.Queue = queue.Queue()
        self.thread: Optional[threading.Thread] = None

    def show(self):
        if self.toplevel:
            self.toplevel.lift()
            return
        self.toplevel = tk.Toplevel()
        self.toplevel.resizable(tk.TRUE, tk.TRUE)
        self.frame = tk.Frame(self.toplevel, relief=tk.GROOVE)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        tk.Label(self.frame, text="Generate colonization report for last weeks:").grid(
            row=0, column=0, sticky=tk.E
        )
        self.weeks_var = tk.StringVar(value="4")
        self.spinbox = tk.Spinbox(self.frame, from_=0, to=12*4, textvariable=self.weeks_var)
        self.spinbox.grid(row=0, column=1, sticky=tk.W)
        tk.Button(self.frame, text="Generate report", command=self._generate_report).grid(
            row=1, columnspan=2
        )
        self.progress_lbl = tk.Label(self.frame, text='')
        self.progress_lbl.grid(row=2, column=0, sticky=tk.EW)
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(self.frame, orient=tk.HORIZONTAL, maximum=100, variable=self.progress_var)
        self.progress_bar.grid(row=2, column=1, sticky=tk.EW, padx=10)
        self.logtext = scrolledtext.ScrolledText(self.frame, height=10)
        self.logtext.grid(row=3, columnspan=2, sticky=tk.NSEW)
        self.frame.rowconfigure(3, weight=1)
        self.frame.pack(expand=True, fill=tk.BOTH, pady=5, padx=5)

    def _generate_report(self):
        self.thread = threading.Thread(target=self._generate_report_worker, daemon=True)
        self.thread.start()

    def _generate_report_worker(self):
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
                self.progress("Starting...", 0)
                for i in range(num_latest_journal_files):
                    logfile = sorted_latest_journal_files[i]
                    with open(logfile, 'rb') as loghandle:
                        self.progress(basename(logfile), int((1+i*100) / num_latest_journal_files))
                        tracefile.write(f'Opening file {logfile}\n')
                        tracefile.flush()
                        for line in loghandle:
                            self.parse_entry(line)
                self.progress("Done", 100)
                self.ui_queue.put(('clear', None))
                tracefile.write('\nTotal:\n')
                for station in self.stations.values():
                    if len(station.contributed):
                        for cmdr, contr in station.contributed.items():
                            self.log(f'cmdr {cmdr}: contributed {contr:6d} to "{station.name()}" in system {station.starSystem}\n')
            self.tracefile = None

    def log(self, text: str):
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

            elif event_type == 'docked':
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
                # self.log(f'"Docked" event, {self.cmdr} docked at market: {station}\n')

            elif event_type == 'undocked':
                self.marketId = None
                # self.log(f'"Undocked" event\n')

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
                self.log(f'"ColonisationContribution" event, cmdr:{self.cmdr} market: "{station} contributed {contributed} ton"\n')
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
                    self.log(f'ConstructionComplete: {station}\n')
                    station.complete = True
                if entry['ConstructionFailed']:
                    self.log(f'ConstructionFailed: {station}\n')
                    station.failed = True

        except Exception as ex:
            self.log(f'Invalid journal entry:\n{line!r}\nexception: {ex}\n')
            return

