# The Daily Dispatch — 21 November 2026 in one image

[![make.fun bounty](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121)
[![Entry rank](https://make.fun/badge/news-image-20261121/annisaputriwati/daily-dispatch-21-nov-2026/rank.svg)](https://make.fun/bounty/news-image-20261121)
[![Entry reward](https://make.fun/badge/news-image-20261121/annisaputriwati/daily-dispatch-21-nov-2026/reward.svg)](https://make.fun/bounty/news-image-20261121)

Entry for the [make.fun](https://make.fun) bounty ["Sum up 21 November's world news in one image"](https://make.fun/bounty/news-image-20261121).

`main.py` renders a complete newspaper front page for Saturday, 21 November 2026 —
masthead, hero story, markets strip and region columns carrying 37 dated stories
from that day's reporting (plus business and sport briefs) — and writes it to
`/output/entry.png`.

## Run it

```bash
pip install pillow
python3 main.py
```

Requirements: Python 3.13 (also runs on 3.12) and Pillow. The program uses no
network, reads no input files besides system fonts, and is fully deterministic:
repeated runs produce byte-identical output.

Output: a 1024×1024 PNG, ~263 KiB (limit: 1024×1024, 1 MiB).

## License

MIT — see `LICENSE`.
