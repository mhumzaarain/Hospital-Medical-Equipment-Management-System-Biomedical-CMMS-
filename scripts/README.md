# Frontend asset vendoring

This project vendors its JS libraries and the Tailwind CSS CLI instead of
pulling them from a CDN, so the app works fully offline / self-contained.
Nothing here is installed via npm — everything is a static download.

## Windows (dev machine)

```powershell
New-Item -ItemType Directory -Force static\js, bin
Invoke-WebRequest https://unpkg.com/htmx.org@2/dist/htmx.min.js -OutFile static\js\htmx.min.js
Invoke-WebRequest https://unpkg.com/alpinejs@3/dist/cdn.min.js -OutFile static\js\alpine.min.js
Invoke-WebRequest https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.js -OutFile static\js\chart.umd.js
Invoke-WebRequest https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-windows-x64.exe -OutFile bin\tailwindcss.exe
```

## Linux (CI / Docker rebuilds)

Same JS downloads, but the Tailwind binary is the Linux x64 build:

```bash
mkdir -p static/js bin
curl -L https://unpkg.com/htmx.org@2/dist/htmx.min.js -o static/js/htmx.min.js
curl -L https://unpkg.com/alpinejs@3/dist/cdn.min.js -o static/js/alpine.min.js
curl -L https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.js -o static/js/chart.umd.js
curl -L https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 -o bin/tailwindcss
chmod +x bin/tailwindcss
```

`bin/` is gitignored (the binary is a build tool, not shipped code). The three
JS files under `static/js/` ARE committed, since they are runtime assets the
app depends on.

## Rebuilding the CSS

After any template change that introduces new Tailwind utility classes,
rebuild `static/css/app.css` and commit the result (Docker image builds do
not run the Tailwind binary — they just use the committed, pre-built CSS):

```powershell
bin\tailwindcss.exe -i static\css\input.css -o static\css\app.css --minify
```

```bash
bin/tailwindcss -i static/css/input.css -o static/css/app.css --minify
```
