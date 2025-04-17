import datetime
import json
from typing import Any, Self
from os import path
from companion import CAPIData


class FleetCarrier:

    def __init__(self) -> None:
        self.cargo: dict[str, int] = {}
        self.last_sync: str | None = None
        self.call_sign: str | None = None
        self.file_path: str | None = None
        self.auto_save: bool = False

    def load(self, file_path: str, auto_save: bool = True) -> None:
        self.file_path = file_path
        self.auto_save = auto_save
        if path.isfile(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            self.cargo = data.get('cargo', {})
            self.last_sync = data.get('lastSync', None)
            self.call_sign = data.get('callSign', None)

    def save(self, file_path: str | None = None) -> None:
        if file_path is None and self.auto_save:
            file_path = self.file_path
        if file_path is None:
            return
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(self, file, ensure_ascii=False, indent=4, cls=FleetCarrierEncoder, sort_keys=True)

    def sync_data(self, data: CAPIData) -> Self | None:
        self.call_sign = data['name']['callsign']
        if not self.call_sign:
            return None
        self.last_sync = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

        self.cargo = {}
        for c in data['cargo']:
            cn = c['commodity'].lower()
            if cn in self.cargo:
                self.cargo[cn] += c['qty']
            else:
                self.cargo[cn] = c['qty']
        self.save()
        return self

    def get(self, commodity: str) -> int:
        return self.cargo.get(commodity, 0)

    def add(self, commodity: str, qty: int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] += qty
        else:
            self.cargo[commodity] = qty
        self.save()
        return self.cargo[commodity]

    def remove(self, commodity: str, qty: int) -> int:
        if commodity in self.cargo:
            self.cargo[commodity] -= qty
            if self.cargo[commodity] < 0:
                self.cargo[commodity] = 0
        else:
            self.cargo[commodity] = 0
        self.save()
        return self.cargo[commodity]


class FleetCarrierEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, FleetCarrier):
            return o.__dict__
        return super().default(o)
