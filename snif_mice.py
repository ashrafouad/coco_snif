import json
import re
from datetime import datetime
from enum import Enum, unique
from typing import Any, Iterator

import urllib3 as url
from bs4 import BeautifulSoup

CAPT_WEBSITE = "https://capt.gov.kw/en"
OPEN_TENDER = "tenders/opening-tenders"
WARRANTY_TENDER = "tenders/warranties"

STANDARD_TIME_FORMAT = "%d %b %Y"

TARGET_FILE = "env/tenders.json"

http = url.PoolManager()
Tender = dict[str, Any]


class Template:
    @classmethod
    def warranty_page(cls) -> str:
        return f"{CAPT_WEBSITE}/{WARRANTY_TENDER}"

    @classmethod
    def warranty_tender_id(cls, code) -> str:
        return (
            f"{CAPT_WEBSITE}/{WARRANTY_TENDER}/?ministry_code={code}&select2_data=true"
        )

    @classmethod
    def open_tender_id(cls, code) -> str:
        return f"{CAPT_WEBSITE}/{OPEN_TENDER}/?ministry_code={code}&ministry_tender_search=true"

    @classmethod
    def open_tender(cls, code, id) -> str:
        print(
            f"PROCESSING: {CAPT_WEBSITE}/{OPEN_TENDER}/?ministry_code={code}&tender_no={id}"
        )
        return f"{CAPT_WEBSITE}/{OPEN_TENDER}/?ministry_code={code}&tender_no={id}"

    @classmethod
    def warranty_tender(cls, code, id) -> str:
        print(
            f"PROCESSING: {CAPT_WEBSITE}/{WARRANTY_TENDER}/?ministry_code={code}&tender_no={id}"
        )
        return f"{CAPT_WEBSITE}/{WARRANTY_TENDER}/?ministry_code={code}&tender_no={id}"

    @classmethod
    def null(cls) -> str:
        return ""


@unique
class HTTPRequest(str, Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PUT = "PUT"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTION = "OPTION"


def open_tender_cmap() -> Iterator[tuple[str, str]]:
    """Retrieve the ministry code mapping from [CAPT](https://www.cpt.gov.kw), ingnores
    any entry that has either an empty or and empyt value.

    Returns:
        dict[str, str]: {"ministry_code": "ministry_name", ...}
    """
    return (
        (code, name)
        for code, name in filter(
            junk_field,
            {
                option["value"]: ""
                if not option.string
                else "".join(option.string.strip())
                for optgroup in BeautifulSoup(
                    http.request(HTTPRequest.GET, CAPT_WEBSITE).data, "html.parser"
                ).find_all("optgroup")
                for option in optgroup.find_all("option")
            }.items(),
        )
    )


def open_tender_ids(code: str) -> list:
    """Get open tender ids


    Args:
        code (str): `<org_code>`

    Returns:
        list[str]: `[<ids>]`
    """
    return eval(
        http.request(HTTPRequest.GET, Template.open_tender_id(code)).data.decode()
    )


def get_opening_tender(ministry_code: str, tender_id: str) -> list[Tender] | Tender:
    return opening_tender_from_response(
        http.request(
            HTTPRequest.GET,
            Template.open_tender(ministry_code, tender_id),
        )
    )


def opening_tender_from_response(page: url.BaseHTTPResponse) -> list[Tender] | Tender:
    parser = BeautifulSoup(page.data, "html.parser")
    tenders = parser.find_all("div", {"class": "tender-info"})
    res = []

    for tbl in (
        table
        for tender in tenders
        for table in tender.find_all("div", {"class": "table"})
    ):
        tender = {}
        for div in tbl.find_all("div"):
            for ul in div.find_all("ul"):
                item = (
                    "" if not li.string else li.string.strip()
                    for li in ul.find_all("li")
                )

                k = next(item)
                if k in ("Request date", "Last date", "Initial meeting date"):
                    v = parse_datetime(next(item))
                elif k in ("Price", "Insurance"):
                    v = add_money(next(item))
                elif k in ("Files", "Insurance Items"):
                    v = add_links(ul)
                elif k == "Bidding type":
                    v = process_bidding_type(ul)
                elif k in ("Purchase", "Tender no.", "Organisation"):
                    continue
                else:
                    v = "" if not item else next(item)

                if k and v:
                    tender[k] = v
        res.append(tender)
    return res[0] if len(res) == 1 else res


def process_bidding_type(tag):
    list_item = tag.find_next().find_next()
    content = list_item.find()

    if not content:
        return list_item.string.strip()
    elif content.name == "button":
        popup = content["data-popup-url"][4:]  # skipping the `/en/` part
        ctn = http.request(HTTPRequest.GET, f"{CAPT_WEBSITE}/{popup}")
        table = BeautifulSoup(ctn.data, "html.parser").find("table")
        return table_to_aos(table)

    raise NotImplementedError(
        f"TODO: complete the cases of {content.name} for processing bidding type"
    )


def add_links(tag) -> list[str]:
    return [link.string.strip() for link in tag.find_all("a")]


def add_money(amount: str) -> float | str:
    try:
        amount_num = re.sub("[ KD]", "", amount)
        amount_num = re.sub(",", "_", amount_num)
        return float(amount_num)
    except Exception:
        return amount


def parse_datetime(date: str) -> str:
    """Storing dates according to ISO-8601, as god intended"""
    try:
        if date == "-":
            return ""
        date = re.sub("[.,]", "", date)
        month, day, year = date.split(" ")
        month = month[:3] if len(month) > 3 else month
        return datetime.strptime(
            f"{day} {month} {year}", STANDARD_TIME_FORMAT
        ).__str__()
    except Exception:
        return date


def junk_field(t: tuple[str, str]) -> bool:
    """A junk has either a key or value that doesn't have any alphabet.

    Args:
        t (tuple[str, str]): A tuple of a field name `t[0]` and it's value `t[1]`

    Returns:
        bool: `True` if the field is junk
    """
    return re.sub("\W", "", t[0]) and re.sub("\W", "", t[1])  # type: ignore


def table_to_aos(table):
    """Create a list of dictionaries out of HTML tables, the dictionaries keys consist of
    the table header. In case that the header or it's correspoding data field doesn't
    contain anything but junk the whole field is removed the object

    Args:
        table (Tag): HTML `table` tag

    Returns:
        list[dict[str, str]]: An array of dictionaries corresponding to table instances
    """
    head = table.find("thead")
    body = head.find_next_siblings("tr") or table.find("tbody").find_all("tr")

    obj_fields = [
        "" if not data.string else data.string.strip()
        for row in head.find_all("tr")
        for data in row.find_all("th")
    ]
    objs = [
        filter(
            junk_field,
            zip(obj_fields, (data.string.strip() for data in row.find_all("td"))),
        )
        for row in body
    ]
    return [dict([*obj]) for obj in objs]


def save_snapshot(file=TARGET_FILE):
    omni = {
        "opening_tenders": {
            code: {
                "name": name,
                "tenders": {
                    id: opening_tender_from_response(
                        http.request(HTTPRequest.GET, Template.open_tender(code, id))
                    )
                    for id in open_tender_ids(code)
                },
            }
            for code, name in open_tender_cmap()
        },
        "warranties": {
            code: {
                "name": name,
                "tenders": {
                    id: warranty_from_page(
                        BeautifulSoup(
                            http.request(
                                HTTPRequest.GET,
                                Template.warranty_tender(code, id),
                                headers={"X-Requested-With": "XMLHttpRequest"},
                            ).data,
                            "html.parser",
                        )
                    )
                    for id in warranty_tender_ids(code)
                },
            }
            for code, name in warranty_tender_cmap()
        },
        "pre_tenders": [],
        "closing_tenders": [],
        "winning_bids": [],
        "postponement_of_tenders": [],
        "company_qualifications": [],
    }
    with open(file, "w+", encoding="utf-8") as target:
        target.write(json.dumps(omni, ensure_ascii=False))


def warranty_tender_cmap() -> Iterator[tuple[str, str]]:
    return (
        (code, name)
        for code, name in filter(
            junk_field,
            {
                option["value"]: option.string.strip()
                for option in (
                    options
                    for optgroup in BeautifulSoup(
                        http.request(HTTPRequest.GET, Template.warranty_page()).data,
                        "html.parser",
                    )
                    .find("select", {"class": "ajax-select", "name": "ministry_code"})
                    .find_all("optgroup")  # type: ignore
                    for options in optgroup.find_all("option")
                )
            }.items(),
        )
    )


def warranty_tender_ids(code: str) -> list:
    """Get warranty tender ids


    Args:
        code (str): `<org_code>`

    Returns:
        list: `<ids>`
    """
    return eval(
        http.request(HTTPRequest.GET, Template.warranty_tender_id(code)).data.decode()
    )


def warranty_tender_contractors(page):
    return filter(
        junk_field,
        (
            (
                "" if not col[1].string else col[1].string.strip(),
                "" if not col[2].string else col[2].string.strip(),
            )
            for col in (
                row.find_all("div", {"class": "table-cell"})
                for row in page.find_all("div", {"class": "tbody"})
            )
        ),
    )


def get_warranty(ministry_code: str, tender_id: str) -> Tender:
    return warranty_from_page(
        BeautifulSoup(
            http.request(
                HTTPRequest.GET,
                Template.warranty_tender(ministry_code, tender_id),
                headers={"X-Requested-With": "XMLHttpRequest"},
            ).data,
            "html.parser",
        )
    )


def warranty_from_page(page):
    lbl, tender_subject = page.find("ul", {"class": "info-list"}).find_all("li")
    res = {lbl.string.strip(): tender_subject.string.strip()}
    if contractors := dict(warranty_tender_contractors(page)):
        res["Contractors"] = contractors

    if doc_count := len(page.find_all("span", {"class": "counter"})):
        res["Guarantee Documents"] = doc_count

    return res


COMPANIES_LIST = [
    "شركة الصناعات الهندسية الثقيلة وبناء السف",
    "شركة الصناعات الهندسية الثقيلة وبناء السفن / مساهمة عامة",
    "شركة الخليج للانشاءات والاعمال البحرية والمقاولات العامة ش م ك م",
]


def fetch_all_warranties() -> dict:
    return {
        code: {
            "name": name,
            "tenders": {
                id: warranty_from_page(
                    BeautifulSoup(
                        http.request(
                            HTTPRequest.GET,
                            Template.warranty_tender(code, id),
                            headers={"X-Requested-With": "XMLHttpRequest"},
                        ).data,
                        "html.parser",
                    )
                )
                for id in warranty_tender_ids(code)
            },
        }
        for code, name in warranty_tender_cmap()
    }
