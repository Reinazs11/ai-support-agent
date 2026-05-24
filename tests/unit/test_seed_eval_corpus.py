import json

from scripts.seed_eval_corpus import SeededDocument, discover_corpus_files, write_manifest


def test_discover_corpus_files_returns_supported_files_sorted(tmp_path) -> None:
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.md").write_text("a", encoding="utf-8")
    (tmp_path / "ignore.exe").write_text("ignored", encoding="utf-8")

    files = discover_corpus_files(tmp_path)

    assert [file.name for file in files] == ["a.md", "z.txt"]


def test_write_manifest_omits_document_content(tmp_path) -> None:
    manifest_path = tmp_path / "reports" / "manifest.json"

    write_manifest(
        manifest_path=manifest_path,
        base_url="http://localhost:8000",
        corpus_dir=tmp_path / "corpus",
        seeded_documents=[
            SeededDocument(
                title="refund_policy.txt",
                path="evals/corpus/refund_policy.txt",
                document_id="doc-1",
                ingest_status="indexed",
                vectors_indexed=1,
                warnings=[],
            )
        ],
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["documents"] == [
        {
            "title": "refund_policy.txt",
            "path": "evals/corpus/refund_policy.txt",
            "document_id": "doc-1",
            "ingest_status": "indexed",
            "vectors_indexed": 1,
            "warnings": [],
        }
    ]
    assert "Refund Policy" not in manifest_path.read_text(encoding="utf-8")
