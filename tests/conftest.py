from typing import Any


def nop() -> None:
    pass


class Config(dict):
    def __getattr__(self, key: str) -> Any:
        return self[key]

    def __setattr__(self, key: str, value: Any) -> Any:
        self[key] = value
