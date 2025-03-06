import json

class Construction:
    
    def __init__(self, name:str, needed:str, system=None, stationName=None, marketId=None):
        self.name:str = name
        self.needed:dict[str,int] = needed
        
        self.system:str = system
        self.stationName:str = stationName
        self.marketId:int = marketId

    def deliver(self, commodity:str, quantity:int):
        if commodity in self.needed:
            self.needed[commodity] -= quantity

    def setStation(self, system:str, stationName:str, marketId:int):
        self.system = system
        self.stationName = stationName
        self.marketId = marketId
        
class ConstructionEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Construction):
            return o.__dict__
        return super().default(o)