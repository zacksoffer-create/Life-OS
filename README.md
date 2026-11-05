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
- `docs/play/` - the built phone app, published by GitHub Pages (Settings > Pages: deploy from the `main` branch, the
  `/docs` folder). Rebuild it with `python3 lifeos/tools/build_phone_app.py`.
