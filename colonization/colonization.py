import csv
import json
import re
import os
from os import path
from typing import Any, Optional

from EDMCLogging import get_main_logger
from monitor import monitor
from config import config
from companion import CAPIData

from . import construction
from .construction import Construction, ConstructionResource
from .fleetcarrier import FleetCarrier
from .ui import MainUi
from .config import Config

logger = get_main_logger()

class ColonizationPlugin:

    def __init__(self) -> None:
        self.commodityMap: dict[str, str] = self.get_commodity_map()
        self.constructions: list[Construction] = []
        self.carrier: FleetCarrier = FleetCarrier()
        self.cargo: dict[str, int] = {}
        self.maxcargo: int = 0
        self.currentConstruction: Construction | None = None
        self.currentConstructionId: int | None = -1
        self.saveDir: str | None = None
        self.ui: MainUi | None = None
        self.dockedConstruction = False
        self.markets: dict[str, list[str]] = {}
        self.currentMarketId = None
        logger.debug("initialized")

    def plugin_start3(self, plugin_dir: str) -> None:
        self.saveDir = path.abspath(path.join(plugin_dir, "../../colonization"))
        print(self.saveDir)
        if not path.exists(self.saveDir):
            os.makedirs(self.saveDir)
        self.load()

    def cmdr_data(self, data: CAPIData, is_beta: bool) -> None:
        local_commodities: list[str] = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if commodity['stock'] > 0:
                local_commodities.append(commodity['name'].lower())
        self.markets[data['lastStarport'].get('id')] = local_commodities
        self.update_display()

    def journal_entry(self, cmdr: str, is_beta: bool, system: str, station: str, entry: dict[str, Any],
                      state: dict[str, Any]) -> str:

        if entry['event'] == 'MarketBuy':
            self.add_cargo(entry['Type'], entry['Count'])
            if self.carrier.callSign and state['StationName'] == self.carrier.callSign:
                self.carrier.remove(entry['Type'], entry['Count'])
            self.update_display()

        if entry['event'] == "MarketSell":
            self.remove_cargo(entry['Type'], entry['Count'])
            if self.carrier.callSign and state['StationName'] == self.carrier.callSign:
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
            self.colonisation_contribution(entry['MarketID'], delivery)
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

        if entry['event'] == 'StartUp':
            self.cargo = state['Cargo'].copy()
            self.maxcargo = max(int(entry.get("Count", 0)), self.maxcargo)
            self.set_docked(state)

        if entry['event'] == 'Docked':
            self.set_docked(state)

        if entry['event'] == "Undocked":
            self.dockedConstruction = False
            self.currentMarketId = None
            self.update_display()
        return ''

    def capi_fleetcarrier(self, data: CAPIData) -> str:
        self.carrier.sync_data(data)
        self.update_display()
        return ''

    def update_display(self, event: Any = None) -> None:
        if self.ui:
            if self.currentConstruction:
                self.ui.set_title(self.currentConstruction.get_short_name())
                if self.currentConstructionId is None:
                    self.ui.set_station("This construction is not tracked", color="#f00")
                elif self.dockedConstruction:
                    self.ui.set_station("{} (docked)".format(self.currentConstruction.get_name()), 'green')
                else:
                    self.ui.set_station(self.currentConstruction.get_name())
            else:
                self.ui.set_title("TOTAL")
                if len(self.constructions) == 0:
                    self.ui.set_title("")
                    self.ui.set_station("Dock to construction site to start tracking progress")
                else:
                    self.ui.set_title("TOTAL")
                    self.ui.set_station("")

            self.ui.set_total(self.get_total_shopping_value(), self.maxcargo)
            docked_to: Optional[str] = None
            if self.dockedConstruction:
                docked_to = "construction"
            if self.carrier.callSign and monitor.state['StationName'] == self.carrier.callSign:
                docked_to = "carrier"
            self.ui.set_table(self.get_table(), docked_to)
            if self.ui.track_btn and self.ui.total_label:
                if self.dockedConstruction and self.currentConstructionId is None:
                    self.ui.track_btn.grid()
                    if Config.SHOW_TOTALS.get():
                        self.ui.total_label.grid_remove()
                else:
                    self.ui.track_btn.grid_remove()
                    if Config.SHOW_TOTALS.get():
                        self.ui.total_label.grid()
            if self.ui.prev_btn and self.ui.next_btn:
                if self.dockedConstruction or len(self.constructions) == 0:
                    self.ui.prev_btn.grid_remove()
                    self.ui.next_btn.grid_remove()
                else:
                    self.ui.prev_btn.grid()
                    self.ui.next_btn.grid()

    def get_table(self) -> list[dict[str, Any]]:
        needed = self.currentConstruction.required if self.currentConstruction else self.get_total_shopping_list()
        table = []
        local_commodities: list[str] = self.markets.get(self.currentMarketId, []) if self.currentMarketId else []
        for commodity, required in needed.items():
            table.append({
                'commodityName': self.commodityMap.get(commodity, commodity),
                'needed': required.needed() if isinstance(required, ConstructionResource) else required,
                'cargo': self.cargo.get(commodity, 0),
                'carrier': self.carrier.get(commodity),
                'available': commodity in local_commodities
            })
        return table

    def get_total_shopping_value(self) -> int:
        needed = self.currentConstruction.required if self.currentConstruction else self.get_total_shopping_list()
        value = 0
        for commodity, required in needed.items():
            value += required.needed() if isinstance(required, ConstructionResource) else required
        return value

    @classmethod
    def get_commodity_map(cls) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for f in ('commodity.csv', 'rare_commodity.csv'):
            if not (config.app_dir_path / 'FDevIDs' / f).is_file():
                continue
            with open(config.app_dir_path / 'FDevIDs' / f, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    mapping[row['symbol'].lower()] = row['name']
        return mapping

    def load(self) -> None:
        self.constructions = []
        if self.saveDir is None:
            return
        file_path = path.join(self.saveDir, "constructions.json")
        if path.isfile(file_path):
            for c in json.load(open(file_path, 'r', encoding='utf-8')):
                self.constructions.append(Construction(**c))
        self.carrier.load(path.join(self.saveDir, 'fccargo.json'))

    def save(self) -> None:
        if self.saveDir is None:
            return
        with open(path.join(self.saveDir, "constructions.json"), 'w', encoding='utf-8') as file:
            json.dump(self.constructions, file, ensure_ascii=False, indent=4, cls=construction.ConstructionEncoder)

    def get_total_shopping_list(self) -> dict[str, int]:
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
        ui.on('prev', self.prev_construction)
        ui.on('next', self.next_construction)
        ui.on('track', self.track_station)
        ui.on('update', self.update_display)
        self.update_display()

    def prev_construction(self, event: Any) -> None:
        if self.currentConstructionId is None:
            return
        if self.currentConstructionId < 0:
            self.currentConstructionId = len(self.constructions) - 1
            if self.currentConstructionId >= 0:
                self.currentConstruction = self.constructions[self.currentConstructionId]
        elif self.currentConstructionId == 0:
            self.currentConstructionId = -1
            self.currentConstruction = None
        else:
            self.currentConstructionId -= 1
            self.currentConstruction = self.constructions[self.currentConstructionId]
        self.update_display()

    def next_construction(self, event: Any) -> None:
        if self.currentConstructionId is None:
            return
        self.currentConstructionId += 1
        if self.currentConstructionId >= len(self.constructions):
            self.currentConstructionId = -1
            self.currentConstruction = None
        else:
            self.currentConstruction = self.constructions[self.currentConstructionId]
        self.update_display()

    def set_docked(self, state: dict[str, Any]) -> None:
        self.currentMarketId = state['MarketID']
        found = next((c for c in self.constructions if c.market_id == state['MarketID']), None)
        if found:
            self.currentConstructionId = self.constructions.index(found)
            self.currentConstruction = found
        self.update_display()

    def colonisation_construction_depot(self, system_name: str, station_name: str, market_id: int,
                                        construction_progress: float,
                                        construction_complete: bool, construction_failed: bool,
                                        required: dict[str, ConstructionResource]) -> None:
        found = next((c for c in self.constructions if c.market_id == market_id), None)
        self.dockedConstruction = True
        if found:
            self.currentConstructionId = self.constructions.index(found)
            self.currentConstruction = found
            found.station_name = station_name
            found.construction_progress = construction_progress
            found.construction_complete = construction_complete
            found.construction_failed = construction_failed
            found.required = required
            self.save()
        else:
            self.currentConstructionId = None
            self.currentConstruction = Construction(system=system_name, station_name=station_name, market_id=market_id,
                                                    construction_progress=construction_progress,
                                                    construction_complete=construction_complete,
                                                    construction_failed=construction_failed, required=required)
        self.update_display()

    def colonisation_contribution(self, market_id: int, delivery: dict[str, int]) -> None:
        found = next((c for c in self.constructions if c.market_id == market_id), None)
        if not found and self.currentConstruction and self.currentConstruction.market_id == market_id:
            found = self.currentConstruction
        if found:
            for commodity, qty in delivery.items():
                found.deliver(commodity, qty)

    def track_station(self, event: Any) -> None:
        if self.dockedConstruction and self.currentConstructionId is None and self.currentConstruction:
            self.constructions.append(self.currentConstruction)
            self.currentConstructionId = len(self.constructions) - 1
        self.update_display()
        self.save()

    def remove_construction(self, to_remove: Construction) -> None:
        self.constructions.remove(to_remove)
        if self.currentConstruction == to_remove:
            self.currentConstructionId = -1
            self.currentConstruction = None
        self.update_display()
        self.save()

    @classmethod
    def commodity_from_name(cls, name: str) -> str:
        m = re.search('^\\$(.*)_', name)
        if not m:
            return name
        return m.group(1).lower()
