import datetime
import json
from os import path

class FleetCarrier:
    
    def __init__(self):
        self.cargo:dict[str,int] = {}
        self.lastSync = None
        self.callSign = None
        self.filePath = None
        self.autoSave = None
        
    def load(self, filePath, autoSave = True):
        self.carrier = {}
        self.filePath = filePath
        self.autoSave = - autoSave
        if path.isfile(filePath):
            data = json.load(open(filePath, 'r', encoding='utf-8'))
            self.cargo = data.get('cargo', {})
            self.lastSync = data.get('lastSync', None)
            self.callSign = data.get('callSign', None)
    
    def save(self, filePath = None):
        if filePath == None and self.autoSave:
            filePath = self.filePath
        with open(filePath, 'w', encoding='utf-8') as file:
            json.dump(self, file, ensure_ascii=False, indent=4, cls=FleetCarrierEncoder, sort_keys=True)
    
    def syncData(self, data):
        self.callSign = data['name']['callsign']
        if not self.callSign:
            return None
        self.lastSync = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
        
        self.cargo = {}
        for c in data['cargo']:
            cn = c['commodity'].lower()
            if cn in self.cargo:
                self.cargo[cn] += c['qty']
            else:
                self.cargo[cn] = c['qty']
        self.save()
        return self
                
    def getCargo(self, commodity):
        return self.cargo.get(commodity, 0)
    
    def addCargo(self, commodity:str, qty:int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] += qty
        else:
            self.cargo[commodity] = qty
        self.save()
        return self.cargo[commodity]

    def removeCargo(self, commodity:str, qty:int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] -= qty
            if self.cargo[commodity] < 0:
                self.cargo[commodity] = 0
        else:
            self.cargo[commodity] = 0
        self.save()
        return self.cargo[commodity]
                
    
class FleetCarrierEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, FleetCarrier):
            return o.__dict__
        return super().default(o)