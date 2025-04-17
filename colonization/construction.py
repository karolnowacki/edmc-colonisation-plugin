import json
from typing import Any, Optional

from .data import ptl

from EDMCLogging import get_main_logger

logger = get_main_logger()


class ConstructionResource:
    def __init__(self, commodity: str, required: int, provided: int, payment: int) -> None:
        self.commodity: str = commodity
        self.required: int = required
        self.provided: int = provided
        self.payment: int = payment

    def needed(self) -> int:
        return self.required - self.provided


class Construction:

    def __init__(self, system: Optional[str] = None, station_name: Optional[str] = None,
                 market_id: Optional[int] = None, construction_progress: float = 0.0,
                 construction_complete: float = False, construction_failed: float = False,
                 required: Optional[dict[str, ConstructionResource] | dict[str, dict[str, Any]]] = None) -> None:
        self.required: dict[str, ConstructionResource] = {
            k: ConstructionResource(**v) if isinstance(v, dict) else v for k, v in required.items()
        } if required else {}
        self.construction_progress = construction_progress
        self.construction_complete = construction_complete
        self.construction_failed = construction_failed

        self.system: Optional[str] = system
        self.station_name: Optional[str] = station_name
        self.market_id: Optional[int] = market_id

    def deliver(self, commodity: str, quantity: int) -> None:
        logger.info("Delivery %d of %s to %s", quantity, commodity, self.station_name)
        if commodity in self.required:
            self.required[commodity].provided += quantity

    def set_station(self, system: str, station_name: str, market_id: int) -> None:
        self.system = system
        self.station_name = station_name
        self.market_id = market_id

    def get_short_name(self) -> str:
        if not self.station_name:
            return ""
        if self.station_name.startswith("$EXT_PANEL_ColonisationShip"):
            return self.system if self.system else "Colonisation Ship"
        if "Construction Site: " in self.station_name:
            return self.station_name.split(": ")[1]
        return self.station_name

    def get_name(self) -> str:
        if not self.station_name:
            return ""
        suffix = ""
        if self.construction_complete:
            suffix += " [complete]"
        if self.construction_failed:
            suffix += " [failed]"
        if self.station_name.startswith("$EXT_PANEL_ColonisationShip"):
            return "System Colonisation Ship" + suffix
        return self.station_name + suffix


class ConstructionEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Construction):
            return o.__dict__
        if isinstance(o, ConstructionResource):
            return o.__dict__
        return super().default(o)
