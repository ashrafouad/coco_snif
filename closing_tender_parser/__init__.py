from html.parser import HTMLParser

from enum import Enum


class ParsingState(Enum):
    HandlingPriceList = 1
    PriceListKey = 2
    PriceListVal = 2


class ClosingTenderParser(HTMLParser):
    """
    <img src="..."> <-- starttag == 'img' [('src', '...')]
        ... <-- data (handledata)
    </tag> <-- endtag
    """

    def __init__(self) -> None:
        super().__init__()
        self.state: ParsingState | None = None
        self.price_list = {}

        self._previous_key: str | None = None
        self._previous_val: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.state is not ParsingState.HandlingPriceList and tag == "div":
            for att, val in attrs:
                if value := val:
                    if att == "class" and "detail-list" in value.split():
                        self.state = ParsingState.HandlingPriceList
        elif self.state is ParsingState.HandlingPriceList:
            if tag == 'li':
                self.state = ParsingState.PriceListKey

    def handle_data(self, data: str) -> None:
        if self.state is ParsingState.PriceListKey:
            self._previous_key = data.strip()
        elif self.state is ParsingState.PriceListVal:
            self.price_list[self._previous_key] = data.strip()

    def handle_endtag(self, tag: str) -> None:
        if self.state is ParsingState.HandlingPriceList and tag == "div":
            self.state = None
        elif tag == 'li':
            if ParsingState.PriceListKey:
                self.state = ParsingState.PriceListVal
            else:
                self.state = ParsingState.HandlingPriceList


with open("capt_closing_tenders.html", encoding="utf-8") as file:
    parser = ClosingTenderParser()
    parser.feed(file.read())
    print(parser.price_list)