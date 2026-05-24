import argparse
import json
import mimetypes
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SUPPORTED_CORPUS_SUFFIXES = {".csv", ".md", ".txt"}


@dataclass(frozen=True)
class SeededDocument:
    title: str
    path: str
    document_id: str
    ingest_status: str
    vectors_indexed: int
    warnings: list[str]


def discover_corpus_files(corpus_dir: Path) -> list[Path]:
    if not corpus_dir.exists():
        raise RuntimeError(f"Corpus directory does not exist: {corpus_dir}")

    files = sorted(
        path
        for path in corpus_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_CORPUS_SUFFIXES
    )
    if not files:
        supported = ", ".join(sorted(SUPPORTED_CORPUS_SUFFIXES))
        raise RuntimeError(
            f"No supported corpus files found in {corpus_dir}. Expected: {supported}"
        )
    return files


def seed_corpus(
    *,
    base_url: str,
    corpus_dir: Path,
    manifest_path: Path,
    min_vectors_per_document: int,
) -> list[SeededDocument]:
    corpus_files = discover_corpus_files(corpus_dir)
    seeded_documents: list[SeededDocument] = []

    with httpx.Client(base_url=base_url, timeout=60) as client:
        for corpus_file in corpus_files:
            seeded_document = _upload_and_ingest_document(
                client=client,
                corpus_file=corpus_file,
                min_vectors=min_vectors_per_document,
            )
            seeded_documents.append(seeded_document)

    write_manifest(
        manifest_path=manifest_path,
        base_url=base_url,
        corpus_dir=corpus_dir,
        seeded_documents=seeded_documents,
    )
    return seeded_documents


def write_manifest(
    *,
    manifest_path: Path,
    base_url: str,
    corpus_dir: Path,
    seeded_documents: list[SeededDocument],
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "corpus_dir": str(corpus_dir),
        "documents": [asdict(document) for document in seeded_documents],
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload and ingest the local RAG eval corpus.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--corpus-dir", default="evals/corpus")
    parser.add_argument("--manifest-path", default="reports/evals/eval-corpus-manifest.json")
    parser.add_argument("--min-vectors-per-document", type=int, default=1)
    args = parser.parse_args()

    try:
        seeded_documents = seed_corpus(
            base_url=args.base_url,
            corpus_dir=Path(args.corpus_dir),
            manifest_path=Path(args.manifest_path),
            min_vectors_per_document=args.min_vectors_per_document,
        )
    except httpx.ConnectError:
        print(f"Could not connect to API at {args.base_url}. Start the local API and retry.")
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Corpus seed request failed with HTTP {exc.response.status_code}.")
        return 1
    except httpx.RequestError as exc:
        print(f"Corpus seed request failed: {exc.__class__.__name__}.")
        return 1
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print("RAG eval corpus seeded.")
    for document in seeded_documents:
        print(
            "- "
            f"{document.title}: document_id={document.document_id}, "
            f"vectors_indexed={document.vectors_indexed}"
        )
    print(f"Manifest: {args.manifest_path}")
    return 0


def _upload_and_ingest_document(
    *,
    client: httpx.Client,
    corpus_file: Path,
    min_vectors: int,
) -> SeededDocument:
    media_type = mimetypes.guess_type(corpus_file.name)[0] or "text/plain"
    upload = client.post(
        "/documents",
        files={"file": (corpus_file.name, corpus_file.read_bytes(), media_type)},
    )
    upload.raise_for_status()
    document_id = str(upload.json()["document_id"])

    ingest = client.post(f"/ingest/{document_id}")
    ingest.raise_for_status()
    ingest_body = ingest.json()
    vectors_indexed = int(ingest_body.get("vectors_indexed", 0))
    if vectors_indexed < min_vectors:
        raise RuntimeError(
            f"Ingest for {corpus_file.name} indexed {vectors_indexed} vectors; "
            f"expected at least {min_vectors}."
        )

    return SeededDocument(
        title=corpus_file.name,
        path=str(corpus_file),
        document_id=document_id,
        ingest_status=str(ingest_body.get("status", "")),
        vectors_indexed=vectors_indexed,
        warnings=list(ingest_body.get("warnings") or []),
    )


if __name__ == "__main__":
    sys.exit(main())
