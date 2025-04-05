import csv
import json
from os import path

from . import construction
from .construction import Construction
from .requirements import requirements
from .fleetcarrier import FleetCarrier
from ui import MainUi

from EDMCLogging import get_main_logger
from monitor import monitor
logger = get_main_logger()

class ColonizationPlugin:

    def __init__(self, config):
        self.config = config
        self.commodityMap:dict[str,str] = self.getCommodityMap()
        self.constructions:list[Construction] = []
        self.carrier:FleetCarrier = FleetCarrier()
        self.cargo:dict[str,int] = {}
        self.currentConstruction:Construction|None = None
        self.currentConstructionId:int = -1
        self.pluginDir:str = None
        self.ui:MainUi = None
        self.dockedConstruction = None
        self.markets = {}
        self.currentMarketId:int = None
        logger.debug("initialized")

    def plugin_start3(self, plugin_dir:str):
        self.pluginDir = plugin_dir
        self.load()

    def cmdr_data(self, data, is_beta: bool):
        localCommodities = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if commodity['stock'] > 0:
                localCommodities.append(commodity['name'].lower())
        self.markets[data['lastStarport'].get('id')] = localCommodities
        self.updateDisplay()

    def journal_entry(self, cmdr, is_beta, system, station, entry, state):
        
        if entry['event'] == 'MarketBuy':
            self.addCargo(entry['Type'], entry['Count'])
            if (self.carrier.callSign and state['StationName'] == self.carrier.callSign):
                self.carrier.removeCargo(entry['Type'], entry['Count'])
            self.updateDisplay()
            
        if entry['event'] == "MarketSell":
            self.removeCargo(entry['Type'], entry['Count'])
            if (self.carrier.callSign and state['StationName'] == self.carrier.callSign):
                self.carrier.addCargo(entry['Type'], entry['Count'])
            self.updateDisplay()

        if entry['event'] == "CargoTransfer":
            for t in entry['Transfers']:    
                if t['Direction'] == "toship":
                    self.addCargo(t['Type'], t['Count'])
                    self.carrier.removeCargo(t['Type'], t['Count'])
                if t['Direction'] == "tocarrier":
                    self.removeCargo(t['Type'], t['Count'])
                    self.carrier.addCargo(t['Type'], t['Count'])
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
            self.currentMarketId = state['MarketID']
            self.setDocked(state)

        if entry['event'] == 'Docked':
            self.setDocked(state)

        if entry['event'] == "Undocked":
            self.currentMarketId = None
            self.dockedConstruction = None
            self.updateDisplay()
            
    def capi_fleetcarrier(self, data):
        self.carrier.syncData(data)
        self.updateDisplay()
        
    def updateDisplay(self, event=None):
        if self.ui:
            if self.currentConstruction:
                self.ui.setTitle(self.currentConstruction.name)
                if self.currentConstruction.marketId:
                    if (self.dockedConstruction and self.currentConstruction and self.dockedConstruction.get('MarketID', 0) == self.currentConstruction.marketId):
                        self.ui.setStation("{} (docked)".format(self.currentConstruction.stationName), 'green')
                    else:
                        self.ui.setStation(self.currentConstruction.stationName)
                else:
                    self.ui.setStation("STATION IS NOT BIND", color="#f00")
            else:
                self.ui.setTitle("Total")
                self.ui.setStation("")
            dockedTo = False
            if self.dockedConstruction and self.currentConstruction and self.dockedConstruction.get('MarketID', 0) == self.currentConstruction.marketId:
                dockedTo = "market"
            if self.carrier.callSign and monitor.state['StationName'] == self.carrier.callSign:
                dockedTo = "carrier"
            self.ui.setTable(self.getTable(), dockedTo)
            if self.ui.bind_btn:
                if self.currentConstruction and self.dockedConstruction and self.currentConstruction.marketId == None:
                    self.ui.bind_btn.grid()
                else:
                    self.ui.bind_btn.grid_remove()
            if self.ui.prev_btn and self.ui.next_btn:
                if self.dockedConstruction and self.currentConstruction and self.dockedConstruction.get('MarketID', 0) == self.currentConstruction.marketId:
                    self.ui.prev_btn.grid_remove()
                    self.ui.next_btn.grid_remove()
                else:
                    self.ui.prev_btn.grid()
                    self.ui.next_btn.grid()
                    

    def getTable(self):
        needed = self.currentConstruction.needed if self.currentConstruction else self.getTotalShoppingList()
        table = []
        localCommodities = self.markets.get(self.currentMarketId, []) if self.currentMarketId else []
        for commodity, qty in needed.items():
            table.append({
                'commodityName': self.commodityMap.get(commodity, commodity),
                'needed': qty,
                'cargo': self.cargo.get(commodity, 0),
                'carrier': self.carrier.getCargo(commodity),
                'available': commodity in localCommodities
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
        self.carrier.load(path.join(self.pluginDir, "fccargo.json"))   
            
    def save(self):
        with open(path.join(self.pluginDir, "constructions.json"), 'w', encoding='utf-8') as file:
            json.dump(self.constructions, file, ensure_ascii=False, indent=4, cls=construction.ConstructionEncoder)
        #self.carrier.save(path.join(self.pluginDir, "fccargo.json"))
        
        
    def addConstruction(self, name:str, type:str|None=None) -> Construction:
        logger.info("Adding construction %s %s", name, type)
        construction = Construction(name, requirements.get(type).get('needed', {}))
        self.constructions.append(construction)
        self.updateDisplay()
        self.save()
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

    def setUi(self, ui:MainUi):
        self.ui = ui
        ui.on('prev', self.prevConstruction)
        ui.on('next', self.nextConstruction)
        ui.on('bind', self.bindStation)
        ui.on('update', self.updateDisplay)
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
        self.currentMarketId=state['MarketID']
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
        