import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class ExternalCorpusSource:
    title: str
    agency: str
    url: str
    license_note: str


class MainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self._skip_depth = 0
        self._main_depth = 0
        self._body_depth = 0
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized = tag.lower()
        self._stack.append(normalized)
        if normalized in {"script", "style", "noscript", "svg", "header", "footer", "nav"}:
            self._skip_depth += 1
        if normalized == "main":
            self._main_depth += 1
        if normalized == "body":
            self._body_depth += 1
        if self._should_collect() and normalized in {
            "article",
            "br",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "li",
            "p",
            "section",
        }:
            self._text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if self._should_collect() and normalized in {
            "article",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "li",
            "p",
            "section",
        }:
            self._text_parts.append("\n")
        if normalized == "main" and self._main_depth:
            self._main_depth -= 1
        if normalized == "body" and self._body_depth:
            self._body_depth -= 1
        if normalized in {"script", "style", "noscript", "svg", "header", "footer", "nav"}:
            self._skip_depth = max(0, self._skip_depth - 1)
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._should_collect():
            self._text_parts.append(data)

    def text(self) -> str:
        text = "".join(self._text_parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s+", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _should_collect(self) -> bool:
        if self._skip_depth:
            return False
        if self._main_depth:
            return True
        return self._body_depth > 0 and "main" not in self._stack


def load_sources(manifest_path: Path) -> list[ExternalCorpusSource]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = payload.get("sources") or []
    return [
        ExternalCorpusSource(
            title=str(source["title"]),
            agency=str(source["agency"]),
            url=str(source["url"]),
            license_note=str(source["license_note"]),
        )
        for source in sources
    ]


def download_sources(
    *,
    manifest_path: Path,
    output_dir: Path,
    timeout_seconds: int,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = []
    for source in load_sources(manifest_path):
        try:
            text = fetch_main_text(source.url, timeout_seconds=timeout_seconds)
        except OSError as exc:
            raise RuntimeError(f"{source.title}: {exc}") from exc
        output_path = output_dir / source.title
        output_path.write_text(
            build_corpus_document(source=source, text=text),
            encoding="utf-8",
        )
        output_paths.append(output_path)
    return output_paths


def fetch_main_text(url: str, *, timeout_seconds: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = MainTextParser()
    parser.feed(html)
    text = parser.text()
    if not text:
        raise RuntimeError(f"No readable text extracted from {url}")
    return text


def build_corpus_document(*, source: ExternalCorpusSource, text: str) -> str:
    text = clean_extracted_text(text)
    return (
        f"Title: {source.title}\n"
        f"Source: {source.agency}\n"
        f"URL: {source.url}\n"
        f"License note: {source.license_note}\n\n"
        f"{text}\n"
    )


def clean_extracted_text(text: str) -> str:
    ignored_lines = {
        "Skip to main content",
        "The .gov means it’s official.",
        "The site is secure.",
        "Español",
        "Report Fraud",
        "Read Consumer Alerts",
        "Get Consumer Alerts",
        "Visit ftc.gov",
        "Article",
    }
    ignored_prefixes = (
        "Federal government websites often end in",
        "Before sharing sensitive information",
        "The https:// ensures that you are connecting",
        "Vea esta página en español",
    )
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in ignored_lines:
            continue
        if any(stripped.startswith(prefix) for prefix in ignored_prefixes):
            continue
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download public-domain eval corpus sources.")
    parser.add_argument("--manifest-path", default="evals/external_corpus_sources.json")
    parser.add_argument("--output-dir", default="evals/corpus")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    try:
        output_paths = download_sources(
            manifest_path=Path(args.manifest_path),
            output_dir=Path(args.output_dir),
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print(f"Failed to download eval corpus sources: {exc}")
        return 1

    print("Downloaded eval corpus sources.")
    for output_path in output_paths:
        print(f"- {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
