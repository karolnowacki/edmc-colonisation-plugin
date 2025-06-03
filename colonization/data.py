from l10n import translations

_ENGLISH_TRANSLATIONS = {
    "SortingMode.MARKET": "Market",
    "SortingMode.CARRIER": "Carrier",
    "SortingMode.ALPHABET": "Alphabet",
}


def ptl(x: str) -> str:
    result = translations.translate(x, context=__file__)
    return result if result != x else _ENGLISH_TRANSLATIONS.get(x, x)


class Commodity:
    def __init__(self, symbol:str, category:str, name:str):
        self.symbol = symbol.strip() if symbol else ''
        self.category = category
        self.name = name.strip() if name else self.symbol
        self.market_ord: int = 0
        self.carrier_ord: int = 0


class TableEntry:
    def __init__(self, commodity:Commodity, demand:int, cargo:int, carrier:int, available:bool):
        self.commodity = commodity
        self.demand = demand
        self.cargo = cargo
        self.carrier = carrier
        self.available = available

    def category(self):
        return self.commodity.category

    def unload(self) -> int:
        result = self.demand
        if result < 0:
            result = 0
        return result

    def buy(self) -> int:
        result = self.demand - self.cargo - self.carrier
        if result < 0:
            result = 0
        return result
    
    def export(self) -> str:
        result = self.commodity.name + '\t' + str(self.buy()) + '\t' + str(self.demand) + '\t' + str(self.cargo) + '\t' + str(self.carrier)
        return result
