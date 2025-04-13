import csv
import json
import re
import l10n
import functools
from os import path

from . import construction
from .construction import Construction,ConstructionResource
from .fleetcarrier import FleetCarrier
from ui import MainUi, Commodity

from EDMCLogging import get_main_logger
from monitor import monitor
logger = get_main_logger()

ptl = functools.partial(l10n.translations.tl, context=__file__)

class ColonizationPlugin:

    def __init__(self, config):
        self.config = config
        self.commodityMap:dict[str,Commodity] = {}
        self.constructions:list[Construction] = []
        self.carrier:FleetCarrier = FleetCarrier()
        self.cargo:dict[str,int] = {}
        self.currentConstruction:Construction|None = None
        self.currentConstructionId:int = -1
        self.pluginDir:str = None
        self.ui:MainUi = None
        self.dockedConstruction = False
        self.markets = {}
        self.currentMarketId = None
        logger.debug("initialized")

    def plugin_start3(self, plugin_dir:str):
        self.pluginDir = plugin_dir
        self._loadCommodityMap()
        self._loadCommoditySorting()
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
            
        if entry['event'] == "ColonisationContribution":
            delivery = {}
            for c in entry['Contributions']:
                delivery[self.commodityFromName(c['Name'])] = c['Amount']
            self.colonisationContribution(entry['MarketID'], delivery)
            self.updateDisplay()
            self.save()
            
        if entry['event'] == "ColonisationConstructionDepot":
            required={}
            for r in entry['ResourcesRequired']:
                required[self.commodityFromName(r['Name'])] = ConstructionResource(
                    commodity=self.commodityFromName(r['Name']), 
                    required=r['RequiredAmount'],
                    provided=r['ProvidedAmount'],
                    payment=r['Payment'])
            self.colonisationConstructionDepot(
                systemName=state['SystemName'],
                stationName=state['StationName'],
                marketId=entry['MarketID'],
                constructionProgress=entry['ConstructionProgress'],
                constructionComplete=entry['ConstructionComplete'], 
                constructionFailed=entry['ConstructionFailed'], 
                required=required)
            self.updateDisplay()
            self.save()

        if entry['event'] == "Cargo":
            self.cargo = state['Cargo'].copy()
            self.updateDisplay()
            self.save()

        if entry['event'] == 'StartUp':
            self.cargo = state['Cargo'].copy()
            self.setDocked(state)

        if entry['event'] == 'Docked':
            self.setDocked(state)

        if entry['event'] == "Undocked":
            self.dockedConstruction = False
            self.currentMarketId = None
            self.updateDisplay()
            
    def capi_fleetcarrier(self, data):
        self.carrier.syncData(data)
        self.updateDisplay()
        
    def updateDisplay(self, event=None):
        if self.ui:
            isTotal = False
            if self.currentConstruction:
                self.ui.setTitle(self.currentConstruction.getSiteName())
                shortName = self.currentConstruction.getShortName()
                if (self.currentConstructionId == None):
                    self.ui.setStation(ptl("{} (not tracked)").format(shortName), color="#f00")
                elif (self.dockedConstruction):
                    self.ui.setStation(ptl("{} (docked)").format(shortName), 'green')
                else:
                    self.ui.setStation(shortName)
            else:
                self.ui.setTitle(ptl("Total"))
                self.ui.setStation("")
                isTotal = True
                
            dockedTo = False
            if self.dockedConstruction:
                dockedTo = "construction"
            if self.carrier.callSign and monitor.state['StationName'] == self.carrier.callSign:
                dockedTo = "carrier"
            self.ui.setTable(self.getTable(), dockedTo, isTotal)
            if self.ui.track_btn:
                if self.dockedConstruction and self.currentConstructionId == None:
                    self.ui.track_btn.grid()
                else:
                    self.ui.track_btn.grid_remove()
            if self.ui.prev_btn and self.ui.next_btn:
                if self.dockedConstruction:
                    self.ui.prev_btn.grid_remove()
                    self.ui.next_btn.grid_remove()
                else:
                    self.ui.prev_btn.grid()
                    self.ui.next_btn.grid()
                    

    def getTable(self):
        needed = self.currentConstruction.required if self.currentConstruction else self.getTotalShoppingList()
        table = []
        localCommodities = self.markets.get(self.currentMarketId, []) if self.currentMarketId else []
        for commodity, required in needed.items():
            table.append({
                'commodity': self.commodityMap[commodity],
                'needed': required.needed() if isinstance(required, ConstructionResource) else required,
                'cargo': self.cargo.get(commodity, 0),
                'carrier': self.carrier.getCargo(commodity),
                'available': commodity in localCommodities
            })
        return table

    def _loadCommodityMap(self):
        for f in ('commodity.csv', 'rare_commodity.csv'):
            if not (self.config.app_dir_path / 'FDevIDs' / f).is_file():
                continue
            with open(self.config.app_dir_path / 'FDevIDs' / f, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    symbol = row['symbol']
                    self.commodityMap[symbol.lower()] = Commodity(symbol, row['category'], row['name'])

    def _loadCommoditySorting(self):
        language = self.config.get_str('language', default='en')
        filePath = path.join(self.pluginDir, 'L10n', f"sorting-{language}.csv")
        if not path.isfile(filePath):
            filePath = path.join(self.pluginDir, 'L10n', "sorting-en.csv")
        if path.isfile(filePath):
            with open(filePath, mode='r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                category = ''
                for row in reader:
                    symbol = row['symbol'].strip()
                    if symbol == '*':
                        category = row['name'].strip()
                    else:
                        commodity = self.commodityMap.get(symbol.lower())
                        if not commodity:
                            commodity = Commodity(symbol, category, row['name'].strip())
                            self.commodityMap[symbol.lower()] = commodity
                        commodity.name = row['name'].strip()
                        commodity.market_ord = int(row['market'].strip())
                        commodity.carrier_ord = int(row['carrier'].strip())

    def updateLanguage(self):
        self._loadCommoditySorting()

    def load(self):
        self.constructions = []
        filePath = path.join(self.pluginDir, "constructions.json")
        if path.isfile(filePath):
            for c in json.load(open(filePath, 'r', encoding='utf-8')):
                if ("needed" in c):
                    # skip old version
                    continue;
                self.constructions.append(Construction(**c))
        self.carrier.load(path.join(self.pluginDir, "fccargo.json"))

    def save(self):
        with open(path.join(self.pluginDir, "constructions.json"), 'w', encoding='utf-8') as file:
            json.dump(self.constructions, file, ensure_ascii=False, indent=4, cls=construction.ConstructionEncoder)
    
    def getShoppingList(self, marketId:int|None=None) -> dict[str, int]:
        if marketId == None:
            return self.getTotalShoppingList()
        return next((i.needed for i in self.constructions if i.marketId == marketId), {})
    
    def getTotalShoppingList(self) -> dict[str, int]:
        ret = {}
        for i in self.constructions:
            for commodity,req in i.required.items():
                if commodity in ret:
                    ret[commodity] += req.needed()
                else:
                    ret[commodity] = req.needed()
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
        ui.on('track', self.trackStation)
        ui.on('update', self.updateDisplay)
        self.updateDisplay()

    def prevConstruction(self, event):
        if self.dockedConstruction:
            return
        if not self.currentConstructionId:
            self.currentConstructionId = 0
            self.currentConstruction = None
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
        if self.dockedConstruction:
            return
        if not self.currentConstructionId:
            self.currentConstructionId = 0
            self.currentConstruction = None
        self.currentConstructionId += 1
        if (self.currentConstructionId >= len(self.constructions)):
            self.currentConstructionId = -1
            self.currentConstruction = None
        else:
            self.currentConstruction = self.constructions[self.currentConstructionId]
        self.updateDisplay()

    def setDocked(self, state):
        self.currentMarketId = state['MarketID']
        found = next((c for c in self.constructions if c.marketId == state['MarketID']), None)
        if found:
            self.currentConstructionId = self.constructions.index(found)
            self.currentConstruction = found
        self.updateDisplay()
        
    def colonisationConstructionDepot(self, systemName, stationName, marketId, constructionProgress, constructionComplete, constructionFailed, required):
        found = next((c for c in self.constructions if c.marketId == marketId), None)
        self.dockedConstruction = True
        if found:
            self.currentConstructionId = self.constructions.index(found)
            self.currentConstruction = found
            found.constructionProgress = constructionProgress
            found.constructionComplete = constructionComplete
            found.constructionFailed = constructionFailed
            found.required = required
        else:
            self.currentConstructionId = None
            self.currentConstruction = Construction(system=systemName, stationName=stationName,
                                                    marketId=marketId, constructionProgress=constructionProgress,
                                                    constructionComplete=constructionComplete, constructionFailed=constructionFailed, required=required)
        self.updateDisplay()
        
    def colonisationContribution(self, marketId, delivery):
        found = next((c for c in self.constructions if c.marketId == marketId), None)
        if not found and self.currentConstruction.marketId == marketId:
            found = self.currentConstruction
        if found:
            for commodity,qty in delivery.items():
                found.deliver(commodity, qty)

    def trackStation(self, event):
        if self.dockedConstruction and self.currentConstructionId == None:
            self.constructions.append(self.currentConstruction)
            self.currentConstructionId = len(self.constructions)-1
        self.updateDisplay()
        self.save()
            
    def removeConstruction(self, construction):
        self.constructions.remove(construction)
        if self.currentConstruction == construction:
            self.currentConstructionId = -1
            self.currentConstruction = None
        self.updateDisplay()
        self.save()
        
    def commodityFromName(self, name):
        m = re.search('^\\$(.*)_', name)
        if not m:
            return name
        return m.group(1).lower()
        