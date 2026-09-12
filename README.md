# Disaster news atlas

Pins recent natural and industrial disasters on a map. Live: [minlos.site/news](https://minlos.site/news).

Code lives here. The site is a static export on the VPS (`~/minlos.site/news`). The birthday homepage at [minlos.site](https://minlos.site) is a different tree and must not be overwritten.

## Work and deploy

1. Edit on `main` (this repo).
2. `./deploy.sh` — `git push`, then `git pull` on the VPS.
3. Rebuild the map only when you want:  
   `ssh minlos@minlos.site 'cd ~/news-atlas && ./run.sh'`

There is **no cron**. Grok is a proof of concept: `grok-4.3`, **24 headlines per UTC day**, misses first. Key: `~/grok_api` on the VPS (or `news-atlas/.env`, gitignored). Compare gazetteer vs Grok at `/news/compare.html`.

## Local

```bash
cp .env.example .env   # optional; ~/grok_api is enough
python3 build.py
```

Writes `index.html` / `news-map.html` / `compare.html` in this directory (or `$OUT_DIR`).
