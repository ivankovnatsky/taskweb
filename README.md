# TaskWeb

A web interface for [Taskwarrior 3](https://taskwarrior.org/).

## Screenshots

### Light Mode

![Light Mode](screenshots/light-mode.png)

### Dark Mode

![Dark Mode](screenshots/dark-mode.png)

### Annotations (Light)

![Annotations Light](screenshots/annotations-light.png)

### Annotations (Dark)

![Annotations Dark](screenshots/annotations-dark.png)

### Completed Tasks

![Completed Tasks](screenshots/completed.png)

## Features

- View pending tasks sorted by urgency
- Add new tasks with project, tags, priority, and due date
- Complete, start/stop, and delete tasks
- Filter by project or tag
- View completed tasks
- Light/dark mode with system preference detection
- Responsive design

## Quick Start

```sh
task serve
```

Or with custom host/port:

```sh
python -m taskweb serve --host 0.0.0.0 --port 8080
```

## Configuration

TaskWeb reads from your Taskwarrior 3 configuration by default. You can override the data location with environment variables:

```sh
export TASKDATA=~/.local/share/task
export TASKRC=~/.config/task/taskrc
```

A demo database with sample tasks is included in `data/` for development.

Example config in `configs/example.yaml`.

## Development

```sh
# Enter nix dev shell
task dev

# Run tests
task test

# Format code
task format

# Start dev server
task serve
```

## Stack

- Python 3.10+
- Flask
- Taskwarrior 3 (via subprocess)
- Nix flakes for development environment

## License

MIT

## Repository Setup

After creating the repository on GitHub:

1. Set the default branch to `main`:
   ```sh
   gh repo edit ivankovnatsky/taskweb --default-branch main
   ```

2. Make the repository private:
   ```sh
   gh repo edit ivankovnatsky/taskweb --visibility private
   ```
