# Life-OS

LIFE OS: a life-simulation game. You play one person from the first day of high school in Guilford, Connecticut
(fall 2010) through college, with your own family, people and storylines.

- **Play on your phone:** https://zacksoffer-create.github.io/Life-OS/play/ (Safari on iPhone, then Share > Add to
  Home Screen). It runs entirely on the phone and saves there.
- **Play on a computer:** download `docs/play/LIFE-OS-desktop.zip`, unzip it, and open *Start LIFE OS*.
- **Everything else** (how it plays, writing storylines with ChatGPT, texting, the editor, sports, the lab): see
  [lifeos/README.md](lifeos/README.md).

## Layout

- `lifeos/` - the game: the Python engine (`backend/`), the screens (`frontend/`), tools and tests.
- `fantasy/` - Rolling 10, fantasy basketball numbers (rolling windows, points per minute, advanced stats). Separate
  from the game; see [fantasy/README.md](fantasy/README.md). On the phone at
  https://zacksoffer-create.github.io/Life-OS/fantasy/, refreshed every morning by the "Rolling 10 data" workflow. The
  whole 2025-26 season, replayed: https://zacksoffer-create.github.io/Life-OS/fantasy/2025-26/.
- `docs/play/` - the built phone app, published by GitHub Pages (Settings > Pages: deploy from the `main` branch, the
  `/docs` folder). Rebuild it with `python3 lifeos/tools/build_phone_app.py`.

## If the phone app doesn't update

Every push to `main` starts a "pages build and deployment" run (the repo's Actions tab). The Me tab in the app shows
`Engine … · screens …` at the bottom; when the run finishes, closing and reopening the app picks up the new screens.

- **Run stuck on "Queued" for more than ~15 minutes:** that's GitHub, not the game (check
  https://www.githubstatus.com for an Actions or Pages incident). Re-running a stuck run often stays stuck too; a new
  push starts a fresh run that usually goes straight through.
- **Run failed with "in progress deployment":** an older run is still holding the site. Cancel it on the Actions tab,
  then re-run the newest one.
