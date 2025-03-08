import csv
import json
from os import path

from . import construction
from .construction import Construction
from .requirements import requirements
from ui import MainUi

from EDMCLogging import get_main_logger
logger = get_main_logger()

class ColonizationPlugin:

    def __init__(self, config):
        self.config = config
        self.commodityMap:dict[str,str] = self.getCommodityMap()
        self.constructions:list[Construction] = []
        self.carrier:dict[str,int] = {}
        self.cargo:dict[str,int] = {}
        self.localCommodities:list[str] = []
        self.currentConstruction:Construction|None = None
        self.currentConstructionId:int = -1
        self.pluginDir:str = None
        self.ui:MainUi = None
        self.dockedConstruction = None
        self.fcCallsign = None
        logger.debug("initialized")

    def plugin_start3(self, plugin_dir:str):
        self.pluginDir = plugin_dir
        self.load()

    def cmdr_data(self, data, is_beta: bool):
        self.localCommodities = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if commodity['stock'] > 0:
                self.localCommodities.append(commodity['name'].lower())
        self.updateDisplay()

    def journal_entry(self, cmdr, is_beta, system, station, entry, state):
        if entry['event'] == 'MarketBuy':
            self.addCargo(entry['Type'], entry['Count'])
            self.updateDisplay()

        if entry['event'] == "CargoTransfer":
            for t in entry['Transfers']:    
                if t['Direction'] == "toship":
                    self.addCargo(t['Type'], t['Count'])
                    self.removeCarrier(t['Type'], t['Count'])
                if t['Direction'] == "tocarrier":
                    self.removeCargo(t['Type'], t['Count'])
                    self.addCarrier(t['Type'], t['Count'])
            self.updateDisplay()

        if entry['event'] == "Cargo":
            cargo = state['Cargo'].copy()
            if state['StationType'] == "PlanetaryConstructionDepot" or state['StationType'] == "SpaceConstructionDepot":
                for commodity, qty in self.cargo.items():
                    inCargo = cargo.get(commodity, 0)
                    if qty > inCargo and self.currentConstruction:
                        self.currentConstruction.deliver(commodity, qty-inCargo)
            self.cargo = cargo
            self.updateDisplay()
            self.save()

        if entry['event'] == 'StartUp':
            self.cargo = state['Cargo'].copy()
            self.setDocked(state)

        if entry['event'] == 'Docked':
            self.setDocked(state)

        if entry['event'] == "Undocked":
            self.localCommodities = []
            self.dockedConstruction = None
            self.updateDisplay()
            
    def capi_fleetcarrier(self, data):
        self.fcCallsign = data['name']['callsign']
        if not self.fcCallsign:
            return
        
        self.carrier = {}
        for c in data['cargo']:
            cn = c['commodity'].lower()
            if cn in self.carrier:
                self.carrier[cn] += c['qty']
            else:
                self.carrier[cn] = c['qty']
        self.updateDisplay()
        
    def updateDisplay(self):
        if self.ui:
            if self.currentConstruction:
                self.ui.setTitle(self.currentConstruction.name)
                if self.currentConstruction.marketId:
                    if (self.dockedConstruction and self.dockedConstruction['MarketID'] == self.currentConstruction.marketId):
                        self.ui.setStation("{} (docked)".format(self.currentConstruction.stationName), 'green')
                    else:
                        self.ui.setStation(self.currentConstruction.stationName)
                else:
                    self.ui.setStation("STATION IS NOT BIND", color="#f00")
            else:
                self.ui.setTitle("Total")
                self.ui.setStation("")
            self.ui.setTable(self.getTable())
            if self.ui.bind_btn:
                if self.currentConstruction and self.dockedConstruction and self.currentConstruction.marketId == None:
                    self.ui.bind_btn.grid()
                else:
                    self.ui.bind_btn.grid_remove()
            if self.ui.prev_btn and self.ui.next_btn:
                if self.dockedConstruction and self.currentConstruction and self.dockedConstruction['MarketID'] == self.currentConstruction.marketId:
                    self.ui.prev_btn.grid_remove()
                    self.ui.next_btn.grid_remove()
                else:
                    self.ui.prev_btn.grid()
                    self.ui.next_btn.grid()
                    

    def getTable(self):
        needed = self.currentConstruction.needed if self.currentConstruction else self.getTotalShoppingList()
        table = []
        for commodity, qty in needed.items():
            table.append({
                'commodityName': self.commodityMap.get(commodity, commodity),
                'needed': qty,
                'cargo': self.cargo.get(commodity, 0),
                'carrier': self.carrier.get(commodity, 0),
                'available': commodity in self.localCommodities
            })
        return table

    def getCommodityMap(self):
        map = {}
        for f in ('commodity.csv', 'rare_commodity.csv'):
            if not (self.config.app_dir_path / 'FDevIDs' / f).is_file():
                continue
            with open(self.config.app_dir_path / 'FDevIDs' / f, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    map[row['symbol'].lower()] = row['name']
        return map
    
    def load(self):
        self.constructions = []
        filePath = path.join(self.pluginDir, "constructions.json")
        if path.isfile(filePath):
            for c in json.load(open(filePath, 'r', encoding='utf-8')):
                self.constructions.append(Construction(**c))
        self.carrier = {}
        filePath = path.join(self.pluginDir, "fccargo.json")
        if path.isfile(filePath):
            self.carrier = json.load(open(filePath, 'r', encoding='utf-8'))       
            
    def save(self):
        with open(path.join(self.pluginDir, "constructions.json"), 'w', encoding='utf-8') as file:
            json.dump(self.constructions, file, ensure_ascii=False, indent=4, cls=construction.ConstructionEncoder)
        with open(path.join(self.pluginDir, "fccargo.json"), 'w', encoding='utf-8') as file:
            json.dump(self.carrier, file, ensure_ascii=False, indent=4, sort_keys=True)
        
    def addConstruction(self, name:str, type:str|None=None) -> Construction:
        logger.info("Adding construction %s %s", name, type)
        construction = Construction(name, requirements.get(type).get('needed', {}))
        self.constructions.append(construction)
        return construction
    
    def getShoppingList(self, marketId:int|None=None) -> dict[str, int]:
        if marketId == None:
            return self.getTotalShoppingList()
        return next((i.needed for i in self.constructions if i.marketId == marketId), {})
    
    def getTotalShoppingList(self) -> dict[str, int]:
        ret = {}
        for i in self.constructions:
            for commodity,qty in i.needed.items():
                if commodity in ret:
                    ret[commodity] += qty
                else:
                    ret[commodity] = qty
        return dict(sorted(ret.items()))

    def addCargo(self, commodity:str, qty:int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] += qty
        else:
            self.cargo[commodity] = qty
        return self.cargo[commodity]

    def removeCargo(self, commodity:str, qty:int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] -= qty
        else:
            self.cargo[commodity] = 0
        return self.cargo[commodity]
        
    def addCarrier(self, commodity:str, qty:int) -> int:
        if commodity in self.carrier:
            self.carrier[commodity] += qty
        else:
            self.carrier[commodity] = qty
        return self.carrier[commodity]

    def removeCarrier(self, commodity:str, qty:int) -> int:
        if commodity in self.carrier:
            self.carrier[commodity] -= qty
        else:
            self.carrier[commodity] = 0
        return self.carrier[commodity]

    def setUi(self, ui:MainUi):
        self.ui = ui
        ui.on('prev', self.prevConstruction)
        ui.on('next', self.nextConstruction)
        ui.on('bind', self.bindStation)
        self.updateDisplay()

    def prevConstruction(self, event):
        if self.dockedConstruction and self.currentConstruction and self.dockedConstruction['MarketID'] == self.currentConstruction.marketId:
            return
        if self.currentConstructionId < 0:
            self.currentConstructionId = len(self.constructions)-1
            self.currentConstruction = self.constructions[self.currentConstructionId]
        elif self.currentConstructionId == 0:
           self.currentConstructionId = -1
           self.currentConstruction = None
        else:
            self.currentConstructionId -= 1
            self.currentConstruction = self.constructions[self.currentConstructionId]
        self.updateDisplay()

    def nextConstruction(self, event):
        if self.dockedConstruction and self.currentConstruction and self.dockedConstruction['MarketID'] == self.currentConstruction.marketId:
            return
        self.currentConstructionId += 1
        if (self.currentConstructionId >= len(self.constructions)):
            self.currentConstructionId = -1
            self.currentConstruction = None
        else:
            self.currentConstruction = self.constructions[self.currentConstructionId]
        self.updateDisplay()

    def setDocked(self, state):
        if state['StationType'] == "PlanetaryConstructionDepot" or state['StationType'] == "SpaceConstructionDepot":
            self.dockedConstruction = {
                'StationName': state['StationName'],
                'SystemName': state['SystemName'],
                'MarketID': state['MarketID'],
            }
            found = next((c for c in self.constructions if c.marketId == state['MarketID']), None)
            if found:
                self.currentConstructionId = self.constructions.index(found)
                self.currentConstruction = found
        self.updateDisplay()

    def bindStation(self, event):
        if self.dockedConstruction and self.currentConstruction and self.currentConstruction.marketId == None:
            self.currentConstruction.setStation(stationName=self.dockedConstruction['StationName'], 
                                                system=self.dockedConstruction['SystemName'],
                                                marketId=self.dockedConstruction['MarketID'])
        self.updateDisplay()
        self.save()
    
    def unbindStation(self, marketId):
        construction = next(i for i in self.constructions if i.marketId == marketId)
        if construction:
            construction.marketId = None
            construction.system = None
            construction.stationName = None
        self.updateDisplay()
        self.save()
            
    def removeConstruction(self, construction):
        self.constructions.remove(construction)
        if self.currentConstruction == construction:
            self.currentConstructionId = -1
            self.currentConstruction = None
        self.updateDisplay()
        self.save()
        