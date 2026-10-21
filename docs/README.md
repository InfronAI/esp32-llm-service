# Documentation

**English** | [简体中文](README.zh-CN.md)

The default documentation is English. Each guide has a Simplified Chinese companion with a language switch at the top. Start with the hardware guide if this is your first ESP32 project, then follow setup and installation in order.

| Guide | What it covers |
| --- | --- |
| [Project README](../README.md) | Overview, hardware list, purchase links, architecture, installation steps, and first request |
| [Hardware and shopping](hardware.md) | Exact reference SKUs, memory suffixes, cable/USB selection, first connection, and success checkpoints |
| [Environment setup](setup.md) | Mac tools, Python environment, cross compiler, dependency downloads, and proxies |
| [Installation and recovery](installation.md) | Port detection, backup, firmware installation, private configuration, deployment, and restore |
| [Codex workflow](codex.md) | Local Codex setup, USB access, task prompts, and testing boundaries |
| [Architecture](architecture.md) | Startup, threads, request flow, native inference, and memory ownership |
| [Model choices and constraints](models.md) | RAM/Flash/KV budgets, six candidate models, upstream repositories, and integration requirements |
| [HTTP API](api.md) | curl and SDK examples, JSON/SSE, supported parameters, and errors |
| [Operations](operations.md) | Shell login and commands, code/configuration updates, and troubleshooting |
| [Validation](validation.md) | Host/device checks and historical hardware measurements |
| [Native build](../BUILD.md) | Pinned compiler/ABI settings and numerical comparison |
| [CI template](../ci/README.md) | Host workflow contents and how to enable it |
| [Contributor instructions](../AGENTS.md) | Repository constraints and documentation synchronization |
| [Third-party notices](../THIRD_PARTY_NOTICES.md) | Source provenance and license handling |

Machine-readable manifests and validation JSON are shared between languages; the original [MIT license](../LICENSE) remains the authoritative license text. Private configuration and backups stay outside Git.
