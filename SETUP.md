# Setup

This repo renders your GitHub profile README (`README.md`) as an image
(`dark_mode.svg` / `light_mode.svg`) that a daily GitHub Action keeps up to
date. Nothing in the repo touches the network unless you run it.

## 1. Name the repository

GitHub only shows `README.md` as your profile page if the repository is named
exactly `<your-username>/<your-username>` (this one: `maxxqcty/maxxqcty`).
Rename it if needed.

## 2. Edit `config.json`

```json
{
  "username": "maxxqcty",
  "birthday": "2004-09-13"
}
```

- `username` — your GitHub login (used for every API query)
- `birthday` — `YYYY-MM-DD`, used for the age line. Public on your profile.

## 3. Create the access token

1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate.
2. **Account permissions**: read Followers, read Starring, read Watching.
3. **Repository permissions**: read Commit statuses, Contents, Issues, Metadata,
   Pull Requests (Issues/PRs are optional, for future use).
4. Repository access: **All repositories** (own + contributed).
5. Repo → Settings → Secrets and variables → Actions → New repository secret:
   name `ACCESS_TOKEN`, value = the token.

`USER_NAME` is no longer a secret — the username comes from `config.json`.

## 4. Personalize the decorative text in the SVGs

The stats rows are written by the script, but these rows are static text you
edit by hand in **both** `dark_mode.svg` and `light_mode.svg` (they sit around
line 47-66):

`maxxqcty@dev`, OS, Host, Kernel, IDE, Languages.*, Hobbies.*, Email.*,
LinkedIn, Discord.

The dot leaders between a label and its value are cosmetic — if your value is
longer or shorter than the placeholder, add or remove `.` characters after it
so the row still lines up with its neighbours.

## 5. Run it

- **Automatically**: the Action runs daily at 04:00 UTC, and can be triggered
  manually from the Actions tab (*Run workflow*).
- **Locally**:
  ```sh
  pip install -r requirements.txt
  $env:ACCESS_TOKEN = "<token>"   # PowerShell; use ACCESS_TOKEN=<token> in bash
  python today.py
  ```

## 6. Tests

```sh
python -m pytest tests
```

## How the cache works

`cache/<sha256 of username>.txt` stores, per repository, its commit count and
your lines added/deleted, so unchanged repositories are never re-walked. Delete
the file to force a full rebuild (the first run after adding a repository can
take a while — it walks the commit history of everything you own).
