import pytest

from psi_graph import studies

CATALOGUE = [
    {"id": "PSI-26", "title": "Burning and Suppression of Solids", "acronym": "BASS"},
    {
        "id": "PSI-27",
        "title": "Burning and Suppression of Solids II",
        "acronym": "BASS-II",
    },
]


def test_names_acronyms_ids_urls_and_duplicates(monkeypatch):
    calls = []
    monkeypatch.setattr(studies, "catalogue", lambda: calls.append(True) or CATALOGUE)
    assert studies.resolve_studies(
        [
            "burning and suppression of solids; BASS-II",
            "psi-26",
            studies.PAGE_URL + "PSI-27",
        ]
    ) == [studies.PAGE_URL + "PSI-26", studies.PAGE_URL + "PSI-27"]
    assert len(calls) == 1


def test_ids_do_not_need_catalogue(monkeypatch):
    monkeypatch.setattr(
        studies, "catalogue", lambda: pytest.fail("Unneeded network request")
    )
    assert studies.resolve_studies(["PSI-1; PSI-2"]) == [
        studies.PAGE_URL + "PSI-1",
        studies.PAGE_URL + "PSI-2",
    ]


def test_ambiguous_name_requires_selection(monkeypatch):
    monkeypatch.setattr(studies, "catalogue", lambda: CATALOGUE)
    with pytest.raises(ValueError, match="Multiple studies match"):
        studies.resolve_studies(["Suppression of Solids"])
    answers = iter(["99", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert studies.resolve_studies(["Suppression of Solids"], interactive=True) == [
        studies.PAGE_URL + "PSI-27"
    ]


@pytest.mark.parametrize(
    "value", ["", "; ;", "unknown study", "https://example.com/PSI-26", "PSI-invalid"]
)
def test_invalid_selection_is_not_guessed(monkeypatch, value):
    monkeypatch.setattr(studies, "catalogue", lambda: CATALOGUE)
    with pytest.raises(ValueError):
        studies.resolve_studies([value])


def test_catalogue_reads_all_pages(monkeypatch):
    calls = []

    def read(url):
        calls.append(url)
        source = CATALOGUE[len(calls) - 1]
        return {
            "hits": {
                "total": 2,
                "hits": [
                    {
                        "_source": {
                            "Accession": source["id"],
                            "Title": source["title"],
                            "Acronym": source["acronym"],
                        }
                    }
                ],
            }
        }

    monkeypatch.setattr(studies.nasa, "read_json", read)
    assert studies.catalogue() == CATALOGUE
    assert "from=0" in calls[0] and "from=1" in calls[1]


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"hits": {"total": 2, "hits": []}},
        {"timed_out": True, "hits": {"total": 0, "hits": []}},
    ],
)
def test_incomplete_catalogue_fails_closed(monkeypatch, response):
    monkeypatch.setattr(studies.nasa, "read_json", lambda _: response)
    with pytest.raises(RuntimeError, match="catalogue"):
        studies.catalogue()
