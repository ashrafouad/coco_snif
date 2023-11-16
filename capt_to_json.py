import json
import sys
from snif_mice import save_snapshot

def open_tenders_file(file_path="env/tenders.json", refresh=False):
    if refresh:
        save_snapshot(file_path)

    with open(file_path, "r+", encoding="utf-8") as file:
        tenders = json.load(file)

    return tenders["opening_tenders"], tenders["warranties"]


def extract_slice(d):
    return {code: {"tenders": [id for id in d[code]["tenders"]]} for code in d}


def save_slice(opening_tenders, warranties, file_path="env/tender.slices.json"):
    with open(file_path, "w+", encoding="utf-8") as file:
        json.dump(
            {
                "opening_tenders": extract_slice(opening_tenders),
                "warranties": extract_slice(warranties),
            },
            file,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    args = sys.argv[1:]
    refresh = False
    if len(args) == 1 and args[0] == 'refresh':
        refresh=True
    save_slice(*open_tenders_file(refresh=refresh))
