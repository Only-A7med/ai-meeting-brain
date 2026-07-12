from dataclasses import dataclass, field, asdict


@dataclass
class Segment:
    speaker: str
    text: str


@dataclass
class Meeting:
    id: str
    title: str
    date: str
    project: str
    attendees: list
    segments: list = field(default_factory=list)

    def to_dict(self, with_transcript=True):
        d = asdict(self)
        if not with_transcript:
            d.pop("segments")
        return d


@dataclass
class Commitment:
    id: str
    meeting_id: str
    person: str
    text: str
    date: str
    due: str | None = None
    status: str = "open"
    delivered_on: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Decision:
    id: str
    meeting_id: str
    project: str
    text: str
    date: str
    speaker: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Deadline:
    id: str
    meeting_id: str
    owner: str
    task: str
    due: str
    date: str
    status: str = "open"

    def to_dict(self):
        return asdict(self)
