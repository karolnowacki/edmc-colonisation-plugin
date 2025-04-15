import json

from EDMCLogging import get_main_logger
logger = get_main_logger()

class ConstructionResource:
    def __init__(self, commodity, required, provided, payment):
        self.commodity:str = commodity
        self.required:int = required
        self.provided:int = provided
        self.payment:int = payment
        
    def needed(self):
        return self.required - self.provided

class Construction:
    
    def __init__(self, system=None, stationName=None, marketId=None, constructionProgress=0.0, constructionComplete=False, constructionFailed=False, required:dict[str,ConstructionResource]=None):
        self.required:dict[str,ConstructionResource] = {k: v if isinstance(v, ConstructionResource) else ConstructionResource(**v) for k,v in required.items()}
        self.constructionProgress = constructionProgress
        self.constructionComplete = constructionComplete
        self.constructionFailed = constructionFailed
        
        self.system:str = system
        self.stationName:str = stationName
        self.marketId:int = marketId

    def deliver(self, commodity:str, quantity:int):
        logger.info("Delivery %d of %s to %s", quantity, commodity, self.stationName)
        if commodity in self.required:
            self.required[commodity].provided += quantity

    def setStation(self, system:str, stationName:str, marketId:int):
        self.system = system
        self.stationName = stationName
        self.marketId = marketId

    def getShortName(self):
        if not self.stationName:
            return ""
        if self.stationName.startswith("$EXT_PANEL_ColonisationShip"):
            return self.system
        if "Construction Site: " in self.stationName:
            return self.stationName.split(": ")[1]
        return self.stationName

    def getSiteName(self):
        if self.stationName:
            if self.stationName.startswith("$EXT_PANEL_ColonisationShip:"):
                return ptl("$EXT_PANEL_ColonisationShip")+" "+self.system
            if self.stationName.startswith("Planetary Construction Site:"):
                return ptl("Planetary Construction Site")+": "+self.system
            if self.stationName.startswith("Orbital Construction Site:"):
                return ptl("Orbital Construction Site")+": "+self.system
        return self.stationName

    def getName(self):
        if not self.stationName:
            return ""
        suffix = ""
        if self.constructionComplete:
            suffix += " [complete]"
        if self.constructionFailed:
            suffix += " [failed]"
        if self.stationName.startswith("$EXT_PANEL_ColonisationShip"):
            return "System Colonisation Ship"+suffix
        return self.stationName+suffix

        
class ConstructionEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Construction):
            return o.__dict__
        if isinstance(o, ConstructionResource):
            return o.__dict__
        return super().default(o)