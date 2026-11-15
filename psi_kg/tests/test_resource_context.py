import json

from psi_graph.resource_context import ResourceContext, select_inventory


def resource(id, **fields):
    return dict(id=id, title=fields.pop("title", "Supporting data"), **fields)


def selected_ids(resources, text, **document):
    return [r["id"] for r in select_inventory(document, [{"text": text}], resources)]


def test_large_unrelated_inventory_is_not_repeated_and_records_remain_intact():
    resources = [
        resource(
            f"res:PSI-25:{number}",
            filename=f"BASS_test_{number:04d}_temperature.csv",
            source_url=f"https://example.test/files/BASS_test_{number:04d}_temperature.csv",
        )
        for number in range(1000)
    ]
    before = json.dumps(resources)
    context = ResourceContext(resources)
    selected = context.select(
        {"id": "res:PSI-25:7"},
        [{"text": "The reported comparison uses BASS_test_0042_temperature.csv."}],
    )
    assert [r["id"] for r in selected] == ["res:PSI-25:7", "res:PSI-25:42"]
    assert selected[0] is resources[7]
    assert json.dumps(resources) == before
    assert len(json.dumps(selected)) < len(before) / 100


def test_own_resource_by_id_url_and_parent_archives_are_kept():
    resources = [
        resource("archive", filename="BASS_experiments.zip"),
        resource("nested", parent_resource_id="archive", filename="nested_archive.zip"),
        resource(
            "member",
            parent_resource_id="nested",
            filename="results.csv",
            source_url="https://example.test/archive#member=folder%2Fresults.csv",
        ),
        resource("other", filename="unrelated.csv"),
    ]
    assert selected_ids(resources, "", id="member") == ["archive", "nested", "member"]
    assert selected_ids(
        resources,
        "",
        source_url="https://example.test/archive#member=folder/results.csv",
    ) == ["archive", "nested", "member"]
    assert selected_ids(resources, "", resource_id="member") == [
        "archive",
        "nested",
        "member",
    ]


def test_exact_references_case_whitespace_url_decoding_and_boundaries():
    resources = [
        resource("csv", filename="BASS_42.csv"),
        resource("path", nasa_path="PSI-25/raw/flow results.csv"),
        resource(
            "paper",
            title="The measured limits of flame spread",
            doi="https://doi.org/10.1234/bass.2020",
        ),
        resource("url", source_url="https://example.test/measurements%20new.pdf"),
    ]
    assert selected_ids(resources, "bAsS_42.csv") == ["csv"]
    assert selected_ids(resources, "xBASS_42.csv and BASS_42.csv.backup") == []
    assert selected_ids(resources, "PSI-25/raw/flow%20results.csv") == ["path"]
    assert selected_ids(resources, "The measured\n limits of flame spread") == ["paper"]
    assert selected_ids(resources, "doi:10.1234/bass.2020.") == ["paper"]
    assert selected_ids(resources, "https://example.test/measurements new.pdf") == [
        "url"
    ]


def test_generic_names_and_titles_do_not_expand_metadata_inventory():
    resources = [
        resource("data", filename="data.csv", title="Analyzed data"),
        resource("readme", filename="README.txt", title="Metadata"),
        resource("paper", title="Data measurements and scientific interpretation"),
    ]
    assert (
        selected_ids(
            resources,
            "Read metadata and analyzed data in README.txt or data.csv.",
            id="metadata:PSI-25",
        )
        == []
    )
    assert selected_ids(resources, "", id="readme") == ["readme"]


def test_ambiguous_explicit_basename_keeps_all_candidates_without_cap():
    resources = [
        resource(f"run-{n}", filename="BASS_test_42.csv", parent_resource_id="archive")
        for n in range(40)
    ] + [resource("archive", filename="BASS_complete.zip")]
    selected = selected_ids(resources, "BASS_test_42.csv")
    assert selected == [r["id"] for r in resources]


def test_separate_sections_do_not_fabricate_a_title_and_parent_cycles_terminate():
    resources = [
        resource(
            "paper",
            title="The measured limits of flame spread",
            parent_resource_id="parent",
        ),
        resource("parent", parent_resource_id="paper"),
    ]
    context = ResourceContext(resources)
    assert (
        context.select(
            {}, [{"text": "The measured limits"}, {"text": "of flame spread"}]
        )
        == []
    )
    assert [r["id"] for r in context.select({"id": "paper"}, [])] == ["paper", "parent"]


def test_doi_and_url_prefixes_do_not_select_a_different_resource():
    resources = [
        resource("doi", doi="10.1234/bass.2020"),
        resource("url", source_url="https://example.test/bass.pdf"),
    ]
    assert selected_ids(resources, "10.1234/bass.2020-supplement") == []
    assert selected_ids(resources, "https://example.test/bass.pdf.backup") == []
    assert selected_ids(resources, "https://example.test/bass.pdf.") == ["url"]
