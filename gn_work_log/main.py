import os
import shutil
from dateutil import relativedelta
import pathlib
from strenum import StrEnum
import argparse
from typing import Optional, List, Any, Tuple
import datetime
import toml
import uuid
import jinja2
import tempfile
import subprocess

import json

from gn_work_log import tasks


class Actions(StrEnum):
    START = "start"
    PAUSE = "pause"
    COMPLETE = "complete"
    NOTE = "note"


class TomlDocument:
    def __init__(self, filename: str, working_date: datetime.date) -> None:
        self.filename = pathlib.Path(filename)
        self.working_date = working_date
        self._create_empty_doc()
        self.other_data, self.tasks_data = self._parse()

    def _create_empty_doc(self) -> None:
        if self.filename.exists():
            return
        toml_content = {"version": "0.0.0"}
        with open(self.filename, "w") as f:
            toml.dump(toml_content, f)

    def _parse(self) -> Tuple[dict[str, Any], dict[str, List[tasks.Task]]]:
        with open(self.filename) as f:
            data = toml.load(f)
            tasks_data = {}
            other_data = {}
            for key, value in data.items():
                if not isinstance(value, list):
                    other_data[key] = value
                    continue
                parsed_tasks = [tasks.TomlHelper.deserialize(x) for x in value]
                tasks_data[key] = parsed_tasks
            return other_data, tasks_data

    def add_task(self, description: str, date: datetime.date):
        task = tasks.Task(
            uuid=uuid.uuid4(),
            description=description,
            status=tasks.TaskStates.CREATED,
            times=[],
        )
        today_key = date.isoformat()
        self.tasks_data.setdefault(today_key, [])
        self.tasks_data[today_key].append(task)
        self.write()
        print(f"task added: {task.uuid}")

    def report_daily_json(self):
        corresponding_tasks = self.tasks_data.get(self.working_date.isoformat())
        if corresponding_tasks is None:
            print(json.dumps("No tasks found"))
            return
        serialized_tasks = [tasks.TomlHelper.serialize(t) for t in corresponding_tasks]
        print(json.dumps(serialized_tasks))

    def report_daily(self, output_format="terminal"):
        if output_format == "json":
            self.report_daily_json()
            return
        corresponding_tasks = self.tasks_data.get(self.working_date.isoformat())
        if corresponding_tasks is None:
            print("No tasks found")
            return
        total_time = 0
        for t in corresponding_tasks:
            if output_format == "email":
                print(t.terminal_report())
            elif output_format == "terminal":
                print(t.terminal_report_with_uuid())
            else:
                raise NotImplementedError(
                    f"Output format: {output_format} not supported"
                )
            total_time += t.minutes()
        print(f"Total time: {total_time // 60} Hrs { total_time % 60 } minutes")

    def report_monthly(self):
        start = datetime.date(self.working_date.year, self.working_date.month, 1)
        end = start + relativedelta.relativedelta(months=1)
        total_time = 0
        for date_str, ts in self.tasks_data.items():
            iso_date = datetime.date.fromisoformat(date_str)
            if not start <= iso_date < end:
                continue
            print(date_str)
            for t in ts:
                total_time += t.minutes()
                print(t.report())
        print(f"Total time: {total_time // 60} Hrs { total_time % 60 } minutes")

    def monthly_pdf(self):
        current_folder = pathlib.Path(__file__).parent
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(current_folder / "templates"),
            autoescape=jinja2.select_autoescape(),
        )
        start = datetime.date(self.working_date.year, self.working_date.month, 1)
        end = start + relativedelta.relativedelta(months=1)
        template = env.get_template("monthly_log.tex.jinja")
        total_time = 0
        filtered_data = {}
        for date_str, ts in self.tasks_data.items():
            iso_date = datetime.date.fromisoformat(date_str)
            if not start <= iso_date < end:
                continue
            filtered_data[date_str] = ts
            for t in ts:
                total_time += t.minutes()
        summary_msg = f"Total time: {total_time // 60} Hrs { total_time % 60 } minutes"
        final_filename = f"/tmp/Work_Log_For_{start.year}_{start.month}.pdf"
        with tempfile.NamedTemporaryFile(suffix=".tex") as fp:
            content = template.render(dates=filtered_data, summary=summary_msg)
            fp.write(content.encode())
            fp.flush()
            pdflatex_flags = [
                "pdflatex",
                "-halt-on-error",
                "-output-directory",
                "/tmp",
                "-output-format=pdf",
                fp.name,
            ]
            temporary_path = pathlib.Path(fp.name)
            subprocess.run(pdflatex_flags)
            shutil.move(
                f"/tmp/{temporary_path.name.replace('.tex', '.pdf')}", final_filename
            )
        print(f"Pdf file located at: {final_filename}")

    def update_task(self, uuid: str, action: Actions, note: Optional[str] = None):
        working_key = self.working_date.isoformat()
        today_tasks = self.tasks_data[working_key]
        relevant_tasks = [x for x in today_tasks if uuid in str(x.uuid)]
        if len(relevant_tasks) == 0:
            raise LookupError(
                f"No tasks found. Try to use the correct uuid. Used {uuid}"
            )
        if len(relevant_tasks) > 1:
            raise LookupError(
                f"More than 1 task found. Try to add more text to your uuid. Used {uuid}"
            )
        relevant_task = relevant_tasks[0]
        match action:
            case Actions.START:
                relevant_task.start()
            case Actions.PAUSE:
                relevant_task.pause()
            case Actions.COMPLETE:
                relevant_task.complete()
            case Actions.NOTE:
                if not note:
                    raise AttributeError(f"Expected valid note but got {note}")
                relevant_task.add_note(note)
        self.write()

    def errors(self):
        """
        We only handle and work on today's tasks. Any other incomplete task from a previous time is invalid.
        """
        today = datetime.datetime.now(datetime.timezone.utc).date()
        today_key = today.isoformat()
        errors = {}
        for date, ts in self.tasks_data.items():
            if date == today_key:
                continue
            error_tasks = [t for t in ts if t.status != tasks.TaskStates.COMPLETED]
            if error_tasks:
                errors[date] = error_tasks
        if not errors:
            print("No errors found")
            return
        for date, errs in errors.items():
            print(f"\x1b[1;33m{date}\x1b[0m")
            for t in errs:
                print(t.report())

    def write(self):
        serialized_data = self.other_data.copy()
        for date, date_tasks in self.tasks_data.items():
            serialized_tasks = [tasks.TomlHelper.serialize(t) for t in date_tasks]
            serialized_data[date] = serialized_tasks
        with open(self.filename, "w") as f:
            toml.dump(serialized_data, f)


def main():
    parser = argparse.ArgumentParser("Time tracking GN script")
    parser.add_argument(
        "--file",
        help="File that contains all the work logs, also use env variable WORK_LOG",
    )
    parser.add_argument(
        "--date",
        help="Date to used for various actions e.g. 2024-07-03, defaults to todays date",
    )
    parser.add_argument("--add", help="Add task for the day")
    parser.add_argument(
        "--report", action="store_true", help="List report for what I've done today"
    )
    parser.add_argument(
        "--monthly-report",
        action="store_true",
        help="List report for what I've done in a month. Uses --date to determine the month.",
    )
    parser.add_argument(
        "--monthly-pdf",
        action="store_true",
        help="Generate pdf file for monthly work log. Uses --date to determine the month.",
    )
    parser.add_argument(
        "--task", help="Pass in uuid or a shorter substring to filter out tasks"
    )
    parser.add_argument(
        "--action",
        type=Actions,
        help="What action to do to the passed in task",
        choices=list(Actions),
    )
    parser.add_argument(
        "--start", action="store_true", help="Start a task. Similar to --action start"
    )
    parser.add_argument(
        "--pause", action="store_true", help="Pause a task. Similar to --action pause"
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Complete a task. Similar to --action complete",
    )
    parser.add_argument("--note", help="Note to add. Works with --action note")
    parser.add_argument(
        "--errors", action="store_true", help="Potential errors in the work-log"
    )
    parser.add_argument(
        "--output-format",
        help="Output format we want, can be json, email or terminal",
        default="terminal",
    )
    args = parser.parse_args()

    filename = args.file or os.environ.get("WORK_LOG")
    if filename is None:
        raise RuntimeError(
            "Expected file to work on, either passed using the --file flat of WORK_LOG env variable"
        )

    if args.date:
        date_key = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        date_key = datetime.datetime.now(datetime.timezone.utc).date()

    toml_doc = TomlDocument(filename, date_key)

    if args.add:
        toml_doc.add_task(args.add, date_key)

    if args.report:
        toml_doc.report_daily(args.output_format)

    if args.monthly_report:
        toml_doc.report_monthly()

    if args.monthly_pdf:
        toml_doc.monthly_pdf()

    _action = args.action

    if args.note:
        _action = Actions.NOTE
    if args.start:
        _action = Actions.START
    if args.complete:
        _action = Actions.COMPLETE
    if args.pause:
        _action = Actions.PAUSE

    if args.task and _action:
        toml_doc.update_task(args.task, _action, args.note)
    if args.errors:
        toml_doc.errors()


if __name__ == "__main__":
    main()
