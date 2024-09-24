from __future__ import annotations
from dataclasses import dataclass, field
from strenum import StrEnum
from datetime import datetime, timezone
from typing import List, Tuple, Optional
import uuid


DATE_FORMAT = "%Y-%m-%dT%H:%M"


class TaskStates(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


def tex_clean_up(sentence: str) -> str:
    result = []
    for word in sentence.strip().split():
        if word.strip().startswith("http"):
            word = "\\href{" + word + "}{link}"
        else:
            word = word.replace("_", "\_")
        result.append(word)
    return " ".join(result)


@dataclass
class Task:
    uuid: uuid.UUID
    description: str
    status: TaskStates
    times: List[Tuple[datetime, Optional[datetime]]]
    notes: List[str] = field(default_factory=list)

    def tex_description(self):
        main_description = tex_clean_up(self.description)
        if self.notes:
            notes_section = "\n\\begin{itemize}"
            for note in self.notes:
                note = tex_clean_up(note)
                notes_section += f"\n\\item {note}"
            notes_section += "\n\\end{itemize}"
            main_description += notes_section
        return main_description

    def minutes(self):
        seconds = 0
        for start, end in self.times:
            if not end:
                end = datetime.now(timezone.utc)
            if end.date() != start.date():
                raise RuntimeError("We expect all end dates to happen in the same day")
            seconds += (end - start).seconds
        return seconds / 60

    def terminal_report(self):
        status = ""
        notes = "\n".join(f"  - {x}" for x in self.notes)
        if notes:
            notes = f"\n{notes}"
        if self.status != TaskStates.COMPLETED:
            status = str(self.status)
        return f"- {self.description}: {self.minutes()} {status}{notes}"

    def terminal_report_with_uuid(self):
        return f"{self.uuid} {self.terminal_report()}"

    def start(self):
        if self.status == TaskStates.CREATED or self.status == TaskStates.PAUSED:
            self.status = TaskStates.RUNNING
        now = datetime.now(timezone.utc)
        if self.times:
            prev_start, prev_end = self.times[-1]
            if not isinstance(prev_start, datetime) or not isinstance(
                prev_end, datetime
            ):
                raise TypeError(f"{self.uuid} has incorrect times: {self.times}")
        new_times = (now, None)
        self.times.append(new_times)

    def pause(self):
        if self.status != TaskStates.RUNNING:
            print("Task is not running")
            return
        self.status = TaskStates.PAUSED
        prev_start, prev_end = self.times[-1]
        if prev_end is not None:
            raise TypeError(
                f"{self.uuid} Previous time had an actual value: {self.times}"
            )

        now = datetime.now(timezone.utc)
        self.times[-1] = (prev_start, now)

    def complete(self):
        if self.status != TaskStates.RUNNING:
            print("Task is not running")
            return
        self.status = TaskStates.COMPLETED
        prev_start, prev_end = self.times[-1]
        if prev_end is not None:
            raise TypeError(
                f"{self.uuid} Previous time had an actual value: {self.times}"
            )

        now = datetime.now(timezone.utc)
        self.times[-1] = (prev_start, now)

    def add_note(self, note: str):
        self.notes.append(note)


class TomlHelper:
    @staticmethod
    def deserialize(toml_dict: dict) -> Task:
        times = []
        for x, y in toml_dict.get("times", []):
            x = datetime.strptime(x, DATE_FORMAT).replace(tzinfo=timezone.utc)
            y = (
                None
                if y.lower() == "none"
                else datetime.strptime(y, DATE_FORMAT).replace(tzinfo=timezone.utc)
            )
            times.append((x, y))
        toml_dict["times"] = times
        if "minutes" in toml_dict:
            del toml_dict["minutes"]
        return Task(**toml_dict)

    @staticmethod
    def serialize(task: Task, with_minutes=False) -> dict:
        times = []
        for x, y in task.times:
            new_start = x.strftime(DATE_FORMAT)
            new_end = str(y) if y is None else y.strftime(DATE_FORMAT)
            times.append((new_start, new_end))

        bare_bones = {
            "uuid": str(task.uuid),
            "description": task.description,
            "status": str(task.status),
            "times": times,
            "notes": task.notes,
        }

        if with_minutes:
            bare_bones["minutes"] = task.minutes()
        return bare_bones
