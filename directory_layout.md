lpm/
│
├── lpm/                          # main package
│   ├── __init__.py               # version, __all__
│   ├── __main__.py               # allows `python -m lpm`
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── app.py                # root typer/click app, registers all subcommands
│   │   ├── install.py            # `lpm install`
│   │   ├── publish.py            # `lpm publish` (gitea/pypi/github)
│   │   ├── config.py             # `lpm config get/set`
│   │   ├── init.py               # `lpm init` (first-run wizard)
│   │   └── package.py            # `lpm package new/list/remove`
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── package.py            # Package dataclass/model
│   │   ├── registry.py           # local package registry (index of installed packages)
│   │   ├── resolver.py           # dependency resolution logic
│   │   └── venv.py               # venv creation, editable installs, injection
│   │
│   ├── publishers/
│   │   ├── __init__.py
│   │   ├── base.py               # abstract Publisher base class
│   │   ├── gitea.py              # push to gitea
│   │   ├── github.py             # push to github
│   │   └── pypi.py               # build + upload to pypi
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   ├── schema.py             # pydantic/dataclass models for config
│   │   ├── loader.py             # reads config.toml + .env, merges, validates
│   │   └── defaults.py           # fallback values
│   │
│   └── utils/
│       ├── __init__.py
│       ├── git.py                # git helpers (init, commit, tag, remote)
│       ├── fs.py                 # path helpers, safe file ops
│       ├── subprocess.py         # thin wrapper around subprocess with logging
│       └── console.py            # rich console instance, shared styles
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # pytest fixtures (tmp dirs, fake config, etc)
│   ├── unit/
│   │   ├── test_resolver.py
│   │   ├── test_config_loader.py
│   │   └── test_venv.py
│   └── integration/
│       ├── test_install.py
│       └── test_publish.py
│
├── docs/
│   ├── getting-started.md
│   ├── configuration.md
│   ├── commands.md
│   └── architecture.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml                # run tests on push/PR
│       └── release.yml           # publish lpm itself to pypi on tag
│
├── pyproject.toml                # packaging, dependencies, tool config
├── .env.example                  # template showing which env vars are needed
├── .gitignore
├── README.md
└── CHANGELOG.md