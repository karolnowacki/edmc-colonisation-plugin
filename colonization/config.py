from enum import Enum
from typing import Any
import tkinter as tk

from config import config as edmc_config


PREFIX="colonization."

class Config(Enum):
    IGNORE_FC_UPDATE=f"{PREFIX}ignoreFCUpdate", bool, True
    SHOW_STATION_NAME = f"{PREFIX}showStationName", bool, True
    SHOW_TOTALS = f"{PREFIX}showTotals", bool, True
    CATEGORIES = f"{PREFIX}Categories", bool, True
    COLLAPSABLE = f"{PREFIX}Collapsable", bool, True
    ROWS = f"{PREFIX}Rows", int, 25

    def __init__(self, key:str, var_type:type, default:Any=None):
        self.key = key
        self.var_type = var_type
        self.default = default

    def __str__(self) -> str:
        return self.name

    def get(self) -> int | str | list[str] | bool:
        if self.var_type == bool:
            return self.get_bool()
        if self.var_type == int:
            return self.get_int()
        if self.var_type == str:
            return self.get_str()
        if self.var_type == list:
            return self.get_list()

        raise NotImplementedError(f"Cannot handle get value of type {self.var_type}")

    def get_bool(self) -> bool:
        return edmc_config.get_bool(self.key, default=self.default)

    def get_int(self) -> int:
        return edmc_config.get_int(self.key, default=self.default)

    def get_str(self) -> str:
        return edmc_config.get_str(self.key, default=self.default)

    def get_list(self) -> list:
        return edmc_config.get_list(self.key, default=self.default)

    def set(self, val: int | str | list[str] | bool) -> None:
        edmc_config.set(self.key, val)

    def tk_var(self) -> tk.Variable:
        if self.var_type == bool:
            return tk.BooleanVar(value=self.get_bool())
        if self.var_type == int:
            return tk.IntVar(value=self.get_int())
        if self.var_type == str:
            return tk.StringVar(value=self.get_str())

        raise NotImplementedError(f"Cannot handle get value of type {self.var_type}")

    def tk_string_var(self) -> tk.StringVar:
        return tk.StringVar(value=str(self.get()))
