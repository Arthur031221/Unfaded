# Configuration

Unfaded has no config file. Everything is a command line option, a field in the web interface, or one of the environment variables below.

## Environment

| Variable | Default | Effect |
| --- | --- | --- |
| `UNFADED_HOME` | `~/.cache/unfaded` | Parent folder of the `models` cache. |

## Tuning knobs worth knowing

| Setting | Where | Default | When to change it |
| --- | --- | --- | --- |
| Face strength | `--face-strength`, slider per face | 35 | Raise it for very blurry faces. Lower it if faces start to look like someone else. |
| Colour strength | `--color-strength` | 100 | Lower it when the predicted colours look too strong. |
| Scale | `--scale` | 1 on the CLI, 2 in the web interface | Only matters when upscaling. |
| Force tone recovery | `--force-fade` | off | Prints that look flat but already span most of the range. |
| Steps | `--skip`, `--enable`, step chips | split, fade, repair, faces | Turn off what you do not want. |

## Limits set in code

These are module constants, listed so there are no surprises.

| Constant | Value | Meaning |
| --- | --- | --- |
| `pipeline.MAX_MASK_FRACTION` | 0.15 | Repair is skipped above this share of damaged pixels. |
| `pipeline.TONE_RANGE_LIMIT` | 0.8 | Tone recovery is skipped at or above this share of used range. |
| `pipeline.MAX_OUTPUT_PIXELS` | 120 000 000 | Upscaling refuses to go beyond this. |
| `scratch.THRESHOLD` | 0.4 | Detector probability that counts as damage. |
| `server.MAX_SESSIONS` | 4 | Uploaded scans kept in memory. |
| `server.MAX_UPLOAD_BYTES` | 200 MB | Largest accepted upload. |

## Server

`unfaded serve --host 127.0.0.1 --port 8765`. The server keeps scans in memory, writes nothing to disk and rejects state changing requests whose `Origin` differs from its own `Host`. If you bind it to a non local address, put it behind your own authentication. There is none built in.
