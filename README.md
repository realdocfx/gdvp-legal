# gdvp-legal

**The single source of truth for GDVP's legal kit.**

`LICENSE.md` (the Unified Master Proprietary License) is the SSOT. Everything
else is **generated** from it by `generate_eula.py` — never edit the outputs by
hand:

| Output | Consumer |
|--------|----------|
| `EULA.rtf` | the desktop installer / app (bundled license) |
| `templates/eula_master.html` | the license server — `{% include %}`d by `templates/legal.html` |
| `templates/legal.html` | the server's `/legal` page |

Regenerate after editing `LICENSE.md`:

```bash
python generate_eula.py          # rewrite the outputs
python generate_eula.py --check  # CI drift gate: exit 1 if outputs are stale
```

Consumed as a **git submodule** so the exact legal text in force is pinned per
release and reviewed like code. The server adds `templates/` to its Jinja loader;
the installer bundles `EULA.rtf`.

Stdlib only — no dependencies.
