# System Architecture

## Overview
**quickshell-kde** follows a strict model-view-service architectural pattern.

```
┌────────────────────────────────────────────────────────┐
│                      UI Views                          │
│   (modules/bar, modules/dock, modules/launcher, etc.)  │
└───────────────────────────┬────────────────────────────┘
                            │ QML Data Bindings & Actions
┌───────────────────────────▼────────────────────────────┐
│                   Singleton Services                   │
│ (KWinService, AudioService, ApplicationService, etc.) │
└─────────────┬────────────────────────────┬─────────────┘
              │ System IPC                 │ Local File I/O
┌─────────────▼─────────────┐   ┌──────────▼─────────────┐
│    KWin DBus / Protocols  │   │   XDG Config / JSON    │
└───────────────────────────┘   └────────────────────────┘
```

## Layers

### 1. Presentation Layer (`components/` & `modules/`)
* **Components**: Stateless, reusable UI primitives (buttons, surfaces, sliders, badges, icons).
* **Modules**: Functional desktop widgets composed of primitives, listening to singleton services.

### 2. Service Layer (`services/`)
* **Singletons**: Global services exported via `qmldir`.
* **State Encapsulation**: Services hold state (e.g., active desktop, volume, notification list) and emit change signals.
* **Asynchronous Execution**: Subprocesses and DBus requests run asynchronously without blocking the UI thread.

### 3. Storage & Configuration Layer (`config/` & `services/core/`)
* Configured through JSON files in `$XDG_CONFIG_HOME/quickshell-kde/`.
* `JsonStore.qml` ensures atomic and asynchronous reading/writing.
