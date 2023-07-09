# utilities

## Caddy
Download at: https://caddyserver.com/download

Run with: `proxy\caddy.exe run --config proxy\Caddyfile`

## Usage

1. Create `service.csv` and `user.csv` following format of `_example.csv`.

2. From root path, run `python3 vpn\gen\main.py <old> <new>`, in which `<old>` is the name of the previous version, and `<new>` is the name of the current version. The current version's name must not match with any of the old versions' names. If you wish to create from scratch, let `<old>` be `-`. The `-` folder has been created to accommodate this.

3. Serve the files with Caddy using the example Caddyfile in `proxy\`
