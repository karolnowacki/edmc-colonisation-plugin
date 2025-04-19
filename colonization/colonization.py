import csv
import json
import re
import os
from os import path
from typing import Any, Optional, Mapping

from EDMCLogging import get_main_logger
from monitor import monitor
from config import config
from companion import CAPIData

from .construction import Construction, ConstructionResource, ConstructionEncoder
from .fleetcarrier import FleetCarrier
from .ui import MainUi
from .config import Config
from .data import Commodity, TableEntry, ptl

logger = get_main_logger()

class ColonizationPlugin:

    def __init__(self) -> None:
        self.commodity_map: dict[str, Commodity] = {}
        self.constructions: list[Construction] = []
        self.carrier: FleetCarrier = FleetCarrier()
        self.cargo: dict[str, int] = {}
        self.maxcargo: int = 0
        self.current_construction: Construction | None = None
        self.current_construction_id: int | None = -1
        self.plugin_dir: str | None = None
        self.save_dir: str | None = None
        self.ui: MainUi | None = None
        self.docked_construction = False
        self.markets: dict[str, list[str]] = {}
        self.current_market_id = None
        logger.debug("initialized")

    def plugin_start3(self, plugin_dir: str) -> None:
        self.plugin_dir = plugin_dir
        self.save_dir = path.abspath(path.join(plugin_dir, "../../colonization"))
        if not path.exists(self.save_dir):
            os.makedirs(self.save_dir)
        self._load_commodity_map()
        self._load_commodity_sorting()
        self._load_market_json()
        self.load()

    def cmdr_data(self, data: CAPIData, is_beta: bool) -> None:  # pylint: disable=W0613
        local_commodities: list[str] = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if commodity['stock'] > 0:
                local_commodities.append(commodity['name'].lower())
        self.markets[data['lastStarport'].get('id')] = local_commodities
        self.update_display()

    def journal_entry(self, cmdr: str, is_beta: bool, system: str, station: str, entry: dict[str, Any],
                      state: dict[str, Any]) -> str:
        # pylint: disable=W0613,R0912

        if entry['event'] == 'MarketBuy':
            self.add_cargo(entry['Type'], entry['Count'])
            if self.carrier.call_sign and state['StationName'] == self.carrier.call_sign:
                self.carrier.remove(entry['Type'], entry['Count'])
            self.update_display()

        if entry['event'] == "MarketSell":
            self.remove_cargo(entry['Type'], entry['Count'])
            if self.carrier.call_sign and state['StationName'] == self.carrier.call_sign:
                self.carrier.add(entry['Type'], entry['Count'])
            self.update_display()

        if entry['event'] == "CargoTransfer":
            for t in entry['Transfers']:
                if t['Direction'] == "toship":
                    self.add_cargo(t['Type'], t['Count'])
                    self.carrier.remove(t['Type'], t['Count'])
                if t['Direction'] == "tocarrier":
                    self.remove_cargo(t['Type'], t['Count'])
                    self.carrier.add(t['Type'], t['Count'])
            self.update_display()

        if entry['event'] == "Loadout" and entry["Ship"] and entry["CargoCapacity"]:
            self.maxcargo = int(entry["CargoCapacity"])

        if entry['event'] == "ColonisationContribution":
            delivery = {}
            for c in entry['Contributions']:
                delivery[self.commodity_from_name(c['Name'])] = c['Amount']
            self._colonisation_contribution(entry['MarketID'], delivery)
            self.update_display()
            self.save()

        if entry['event'] == "ColonisationConstructionDepot":
            if not state['StationName']:
                return ''
            required = {}
            for r in entry['ResourcesRequired']:
                required[self.commodity_from_name(r['Name'])] = ConstructionResource(
                    commodity=self.commodity_from_name(r['Name']),
                    required=r['RequiredAmount'],
                    provided=r['ProvidedAmount'],
                    payment=r['Payment'])
            self.colonisation_construction_depot(
                system_name=state['SystemName'],
                station_name=state['StationName'],
                market_id=entry['MarketID'],
                construction_progress=entry['ConstructionProgress'],
                construction_complete=entry['ConstructionComplete'],
                construction_failed=entry['ConstructionFailed'],
                required=required)
            self.update_display()
            self.save()

        if entry['event'] == "Cargo":
            self.cargo = state['Cargo'].copy()
            self.maxcargo = max(int(entry.get("Count", 0)), self.maxcargo)
            self.update_display()
            self.save()

        if entry['event'] == "Market":
            self._load_market_json()
            self.update_display()
            self.save()

        if entry['event'] == 'StartUp':
            self.cargo = state['Cargo'].copy()
            self.maxcargo = max(int(entry.get("Count", 0)), self.maxcargo)
            self._set_docked(state)

        if entry['event'] == 'Docked':
            self._set_docked(state)

        if entry['event'] == "Undocked":
            self.docked_construction = False
            self.current_market_id = None
            self.update_display()
        return ''

    def capi_fleetcarrier(self, data: CAPIData) -> str:
        self.carrier.sync_data(data)
        self.update_display()
        return ''

    def _load_market_json(self) -> None:
        journal_dir = config.get_str('journaldir')
        if journal_dir is None or journal_dir == '':
            journal_dir = config.default_journal_dir
        file_path = os.path.join(journal_dir, 'Market.json')
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
            items: list[Mapping[str, Any]] = content.get('Items') or []
            market: list[str] = []
            for i in items:
                if int(i["Stock"]) <= 0:
                    continue
                comm = Commodity.ID_TO_COMMODITY_MAP.get(int(i["id"]))
                if comm:
                    market.append(comm.symbol.lower())
            self.markets[content["MarketID"]] = market

    def update_display(self, event: Any = None) -> None:
        # pylint: disable=W0613,R0912
        if self.ui:
            if self.current_construction:
                short_name = self.current_construction.get_short_name()
                self.ui.set_title(short_name)
                if self.current_construction_id is None:
                    self.ui.set_station(ptl("{} (not tracked)").format(short_name), color="#f00")
                elif self.docked_construction:
                    self.ui.set_station(ptl("{} (docked)").format(short_name), 'green')
                else:
                    self.ui.set_station(short_name)
            else:
                if len(self.constructions) == 0:
                    self.ui.set_title("")
                    self.ui.set_station(ptl("Dock to construction site to start tracking progress"))
                else:
                    self.ui.set_title(ptl("Total"))
                    self.ui.set_station("")

            self.ui.set_total(self.get_total_shopping_value(), self.maxcargo)
            docked_to: Optional[str] = None
            if self.docked_construction:
                docked_to = "construction"
            if self.carrier.call_sign and monitor.state['StationName'] == self.carrier.call_sign:
                docked_to = "carrier"
            self.ui.set_table(self.get_table(), docked_to)
            if self.ui.track_btn and self.ui.total_label:
                if self.docked_construction and self.current_construction_id is None:
                    self.ui.track_btn.grid()
                    if Config.SHOW_TOTALS.get():
                        self.ui.total_label.grid_remove()
                else:
                    self.ui.track_btn.grid_remove()
                    if Config.SHOW_TOTALS.get():
                        self.ui.total_label.grid()
            if self.ui.prev_btn and self.ui.next_btn:
                if self.docked_construction or len(self.constructions) == 0:
                    self.ui.prev_btn.grid_remove()
                    self.ui.next_btn.grid_remove()
                else:
                    self.ui.prev_btn.grid()
                    self.ui.next_btn.grid()

    def get_table(self) -> list[TableEntry]:
        needed = self.current_construction.required if self.current_construction else self._get_total_shopping_list()
        table: list[TableEntry] = []
        local_commodities: list[str] = self.markets.get(self.current_market_id, []) if self.current_market_id else []
        for commodity, required in needed.items():
            table.append(TableEntry(
                commodity=self.commodity_map[commodity],
                demand=required.needed() if isinstance(required, ConstructionResource) else required,
                cargo=self.cargo.get(commodity, 0),
                carrier=self.carrier.get(commodity),
                available=commodity in local_commodities
            ))
        return table

    def get_total_shopping_value(self) -> int:
        needed = self.current_construction.required if self.current_construction else self._get_total_shopping_list()
        value = 0
        for required in needed.values():
            value += required.needed() if isinstance(required, ConstructionResource) else required
        return value

    def _load_commodity_map(self) -> None:
        for f in ('commodity.csv', 'rare_commodity.csv'):
            if not (config.app_dir_path / 'FDevIDs' / f).is_file():
                continue
            with open(config.app_dir_path / 'FDevIDs' / f, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    symbol = row['symbol']
                    comm_id = int(row['id'])
                    comm = Commodity(symbol, row['category'], row['name'])
                    Commodity.ID_TO_COMMODITY_MAP[comm_id] = comm
                    self.commodity_map[symbol.lower()] = comm
        if not Commodity.ID_TO_COMMODITY_MAP.get(129031238):
            comm = Commodity('Steel', 'Metals', 'Steel')
            Commodity.ID_TO_COMMODITY_MAP[129031238] = comm
            self.commodity_map['steel'] = comm

    def _load_commodity_sorting(self) -> None:
        language = config.get_str('language', default='en')
        file_path = path.join(self.plugin_dir, 'L10n', f"sorting-{language}.csv")
        if not path.isfile(file_path):
            file_path = path.join(self.plugin_dir, 'L10n', "sorting-en.csv")
        if path.isfile(file_path):
            with open(file_path, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                category = ''
                for row in reader:
                    symbol = row['symbol'].strip()
                    if symbol == '*':
                        category = row['name'].strip()
                    else:
                        commodity = self.commodity_map.get(symbol.lower())
                        if not commodity:
                            commodity = Commodity(symbol, category, row['name'].strip())
                            self.commodity_map[symbol.lower()] = commodity
                        commodity.name = row['name'].strip()
                        commodity.market_ord = int(row['market'].strip())
                        commodity.carrier_ord = int(row['carrier'].strip())

    def update_language(self):
        self._load_commodity_sorting()
        self.ui.reset_frame()

    def load(self) -> None:
        self.constructions = []
        if self.save_dir is None:
            return
        file_path = path.join(self.save_dir, "constructions.json")
        if path.isfile(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                for c in json.load(file):
                    self.constructions.append(Construction(**c))
        self.carrier.load(path.join(self.save_dir, 'fccargo.json'))

    def save(self) -> None:
        if self.save_dir is None:
            return
        with open(path.join(self.save_dir, "constructions.json"), 'w', encoding='utf-8') as file:
            json.dump(self.constructions, file, ensure_ascii=False, indent=4, cls=ConstructionEncoder)

    def _get_total_shopping_list(self) -> dict[str, int]:
        ret: dict[str, int] = {}
        for i in self.constructions:
            for commodity, req in i.required.items():
                if commodity in ret:
                    ret[commodity] += req.needed()
                else:
                    ret[commodity] = req.needed()
        return dict(sorted(ret.items()))

    def add_cargo(self, commodity: str, qty: int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] += qty
        else:
            self.cargo[commodity] = qty
        return self.cargo[commodity]

    def remove_cargo(self, commodity: str, qty: int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] -= qty
        else:
            self.cargo[commodity] = 0
        return self.cargo[commodity]

    def setup_ui(self, ui: MainUi) -> None:
        self.ui = ui
        ui.on('prev', self._prev_construction)
        ui.on('next', self._next_construction)
        ui.on('track', self._track_station)
        ui.on('update', self.update_display)
        self.update_display()

    def _prev_construction(self, event: Any) -> None:  # pylint: disable=W0613
        if self.current_construction_id is None:
            return
        if self.current_construction_id < 0:
            self.current_construction_id = len(self.constructions) - 1
            if self.current_construction_id >= 0:
                self.current_construction = self.constructions[self.current_construction_id]
        elif self.current_construction_id == 0:
            self.current_construction_id = -1
            self.current_construction = None
        else:
            self.current_construction_id -= 1
            self.current_construction = self.constructions[self.current_construction_id]
        self.update_display()

    def _next_construction(self, event: Any) -> None:  # pylint: disable=W0613
        if self.current_construction_id is None:
            return
        self.current_construction_id += 1
        if self.current_construction_id >= len(self.constructions):
            self.current_construction_id = -1
            self.current_construction = None
        else:
            self.current_construction = self.constructions[self.current_construction_id]
        self.update_display()

    def _set_docked(self, state: dict[str, Any]) -> None:
        self.current_market_id = state['MarketID']
        found = next((c for c in self.constructions if c.market_id == state['MarketID']), None)
        if found:
            self.current_construction_id = self.constructions.index(found)
            self.current_construction = found
        self.update_display()

    def colonisation_construction_depot(self, system_name: str, station_name: str, market_id: int,
                                        construction_progress: float,
                                        construction_complete: bool, construction_failed: bool,
                                        required: dict[str, ConstructionResource]) -> None:
        found = next((c for c in self.constructions if c.market_id == market_id), None)
        self.docked_construction = True
        if found:
            self.current_construction_id = self.constructions.index(found)
            self.current_construction = found
            found.station_name = station_name
            found.construction_progress = construction_progress
            found.construction_complete = construction_complete
            found.construction_failed = construction_failed
            found.required = required
            self.save()
        else:
            self.current_construction_id = None
            self.current_construction = Construction(system=system_name, station_name=station_name, market_id=market_id,
                                                     construction_progress=construction_progress,
                                                     construction_complete=construction_complete,
                                                     construction_failed=construction_failed, required=required)
        self.update_display()

    def _colonisation_contribution(self, market_id: int, delivery: dict[str, int]) -> None:
        found = next((c for c in self.constructions if c.market_id == market_id), None)
        if not found and self.current_construction and self.current_construction.market_id == market_id:
            found = self.current_construction
        if found:
            for commodity, qty in delivery.items():
                found.deliver(commodity, qty)

    def _track_station(self, event: Any) -> None:  # pylint: disable=W0613
        if self.docked_construction and self.current_construction_id is None and self.current_construction:
            self.constructions.append(self.current_construction)
            self.current_construction_id = len(self.constructions) - 1
        self.update_display()
        self.save()

    def remove_construction(self, to_remove: Construction) -> None:
        self.constructions.remove(to_remove)
        if self.current_construction == to_remove:
            self.current_construction_id = -1
            self.current_construction = None
        self.update_display()
        self.save()

    @classmethod
    def commodity_from_name(cls, name: str) -> str:
        m = re.search('^\\$(.*)_', name)
        if not m:
            return name
        return m.group(1).lower()
