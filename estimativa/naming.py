from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata

from .models import Quote, QuoteInfo


PROPOSAL_ID_RE = re.compile(
    r"(?<!\d)(?P<number>\d{1,4})-(?P<year>\d{2}|\d{4})-(?:(?:rev|r)[-_ ]*)?(?P<revision>\d{1,2})(?!\d)",
    re.IGNORECASE,
)
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ProposalIdentity:
    number: int
    year: int
    revision: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.number <= 9999:
            raise ValueError("O número da proposta deve estar entre 0001 e 9999.")
        if not 0 <= self.revision <= 99:
            raise ValueError("A revisão da proposta deve estar entre 00 e 99.")

    @property
    def text(self) -> str:
        return f"{self.number:04d}-{self.year % 100:02d}-{self.revision:02d}"


def parse_proposal_identity(value: str) -> ProposalIdentity | None:
    match = PROPOSAL_ID_RE.search(value or "")
    if not match:
        return None
    year = int(match.group("year"))
    if year < 100:
        year += 2000
    return ProposalIdentity(
        number=int(match.group("number")),
        year=year,
        revision=int(match.group("revision")),
    )


def identity_from_info(info: QuoteInfo) -> ProposalIdentity | None:
    if info.proposal_number and info.proposal_year:
        return ProposalIdentity(info.proposal_number, info.proposal_year, info.proposal_revision)
    return parse_proposal_identity(info.proposal)


def set_quote_identity(quote: Quote, identity: ProposalIdentity) -> None:
    quote.info.proposal_number = identity.number
    quote.info.proposal_year = identity.year
    quote.info.proposal_revision = identity.revision
    quote.info.proposal = identity.text


def safe_filename_component(value: str, fallback: str, max_length: int = 70) -> str:
    value = unicodedata.normalize("NFC", value or "")
    value = INVALID_FILENAME_CHARS_RE.sub(" ", value)
    value = WHITESPACE_RE.sub(" ", value).strip(" .-")
    value = value or fallback
    return value[:max_length].rstrip(" .-")


def quote_stem(quote: Quote) -> str:
    identity = identity_from_info(quote.info)
    if identity is None:
        raise ValueError("A proposta não possui um número válido.")
    client = safe_filename_component(quote.info.client, "Sem cliente", 35)
    location = safe_filename_component(quote.info.location or quote.info.city, "Sem local", 30)
    project = safe_filename_component(quote.info.project, "Sem projeto")
    return f"{identity.text} - {client} {location} - {project}"


def quote_path(quote: Quote, directory: str | Path, suffix: str = ".json") -> Path:
    return Path(directory).expanduser() / f"{quote_stem(quote)}{suffix}"


def _identity_from_json(path: Path) -> ProposalIdentity | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        info = data.get("info", {})
        if info.get("proposal_number") and info.get("proposal_year"):
            return ProposalIdentity(
                int(info["proposal_number"]),
                int(info["proposal_year"]),
                int(info.get("proposal_revision", 0)),
            )
        return parse_proposal_identity(str(info.get("proposal", "")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def saved_identities(directory: str | Path) -> list[ProposalIdentity]:
    folder = Path(directory).expanduser()
    if not folder.exists():
        return []
    identities: list[ProposalIdentity] = []
    for path in folder.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".json", ".pdf"}:
            continue
        identity = parse_proposal_identity(path.stem)
        if identity is None and path.suffix.lower() == ".json":
            identity = _identity_from_json(path)
        if identity is not None:
            identities.append(identity)
    return identities


def next_quote_identity(directory: str | Path, year: int) -> ProposalIdentity:
    numbers = [identity.number for identity in saved_identities(directory) if identity.year == year]
    next_number = max(numbers, default=0) + 1
    return ProposalIdentity(next_number, year, 0)


def next_revision_identity(directory: str | Path, current: ProposalIdentity) -> ProposalIdentity:
    revisions = [
        identity.revision
        for identity in saved_identities(directory)
        if identity.number == current.number and identity.year == current.year
    ]
    return ProposalIdentity(current.number, current.year, max(revisions, default=current.revision) + 1)
