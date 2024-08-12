# Genenetwork work Tracker

## Set up
### For normal use

```
pipx install --force .
```

### For development

```
python3 -m venv .env
source .env/bin/activate
python -m pip install --editable ".[dev]"
```

## Usage


Normal usage:

```
export WORK_LOG=/absolute/path/to/logs.toml
work-log --add "task description"
work-log --task task_identifier --start
work-log --task task_identifier --pause
work-log --task task_identifier --complete
```

task_identifier is any unique combination of strings in the task's uuid. For
example:

```
$ export WORK_LOG=/tmp/logs.toml
$ work-log --add "task_description"
task added: 700d7751-3506-47a7-8fab-85a547337885
# you can use the last 4 parts of the ulid as the identifier for example
work-log --task 7885 --start
work-log --report
700d7751-3506-47a7-8fab-85a547337885 - task_description: 0.7666666666666667 RUNNING
Total time: 0.0 Hrs 0.7666666666666667 minutes
```

For reporting, we can do: (Note: I provide the `--date` flag so that we see the
reports in the examples log file)

```bash
# print out the daily report log for 2024-06-03
# Note that --file can also be set as an environment variable using `export WORK_LOG=/absolute/path/to/work_log`
work-log --file examples/example_work_log.toml --date 2024-06-03 --report
60d8dcb7-6c59-4579-8bc3-906c3b08166b - GUIX OS set up on laptop: 240.0
1b79478f-444b-480e-9f4b-84a14d250ca0 - Set up genenetwork locally and run unit tests successfully: 120.0
Total time: 6.0 Hrs 0.0 minutes
```

And we can get a monthly pdf report file by doing(Note: you need to have
pdflatex installed):

```bash
work-log --file examples/example_work_log.toml --date 2024-06-03 --monthly-pdf
```
