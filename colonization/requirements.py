import csv
from os import path

class Requirements:

    def __init__(self):
        self.requirements = []
        commoditiesSet = set()
        with open(path.join(path.dirname(__file__), "..", "requirements.csv"), 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                needed = {k.lower(): int(v) for k, v in row.items() if v and k != 'type'}
                self.requirements.append({'type': row['type'], 'needed': needed})
                commoditiesSet.update(needed.keys())
        self.commodities = sorted(list(commoditiesSet))
    
    def types(self):
        return [ r['type'] for r in self.requirements ]
    
    def get(self, type):
        if type == None:
            return {}
        return next(r for r in self.requirements if r['type'] == type)

requirements = Requirements()
