import json
from pathlib import Path

from scripts.download_eval_corpus import (
    ExternalCorpusSource,
    MainTextParser,
    build_corpus_document,
    clean_extracted_text,
    load_sources,
)


def test_load_sources_reads_external_corpus_manifest(tmp_path) -> None:
    manifest_path = tmp_path / "sources.json"
    manifest_path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "title": "source.txt",
                        "agency": "Agency",
                        "url": "https://example.gov/source",
                        "license_note": "Public domain.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    sources = load_sources(manifest_path)

    assert sources == [
        ExternalCorpusSource(
            title="source.txt",
            agency="Agency",
            url="https://example.gov/source",
            license_note="Public domain.",
        )
    ]


def test_committed_external_corpus_manifest_is_well_formed() -> None:
    sources = load_sources(Path("evals/external_corpus_sources.json"))
    titles = [source.title for source in sources]

    assert len(sources) == 4
    assert len(titles) == len(set(titles))
    for source in sources:
        assert source.title.startswith("ftc_")
        assert source.title.endswith(".txt")
        assert source.url.startswith("https://consumer.ftc.gov/")
        assert "public domain" in source.license_note.lower()


def test_main_text_parser_skips_scripts_and_navigation() -> None:
    parser = MainTextParser()
    parser.feed(
        """
        <html>
          <body>
            <nav>Global navigation</nav>
            <main>
              <h1>Refund help</h1>
              <script>ignore()</script>
              <p>Customers can dispute a charge.</p>
            </main>
          </body>
        </html>
        """
    )

    text = parser.text()

    assert "Refund help" in text
    assert "Customers can dispute a charge." in text
    assert "Global navigation" not in text
    assert "ignore" not in text


def test_build_corpus_document_includes_source_metadata() -> None:
    document = build_corpus_document(
        source=ExternalCorpusSource(
            title="source.txt",
            agency="Agency",
            url="https://example.gov/source",
            license_note="Public domain.",
        ),
        text="Main document text.",
    )

    assert "Title: source.txt" in document
    assert "Source: Agency" in document
    assert "URL: https://example.gov/source" in document
    assert "License note: Public domain." in document
    assert document.endswith("Main document text.\n")


def test_clean_extracted_text_removes_common_site_boilerplate() -> None:
    text = clean_extracted_text(
        "\n".join(
            [
                "Skip to main content",
                "The .gov means it’s official.",
                "Online Shopping",
                "Read reviews with a critical eye",
            ]
        )
    )

    assert text == "Online Shopping\nRead reviews with a critical eye"
