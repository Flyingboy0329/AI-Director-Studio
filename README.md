# 🟣 AI Director Studio (v1.0 ARTIFACT)

> **Neural Ingestion & Auto-Marker Workstation for DaVinci Resolve**  
> An end-to-end automated audio-visual semantic analysis, sharpness evaluation, and timeline marker injection workstation.

---

## 📥 Direct Downloads & Releases

Don't know where to look or prefer not to use Git commands?
- 📦 **[Click Here to Download Latest Release (v1.0.0 Artifact)](https://github.com/Flyingboy0329/peepeepoopoo/releases/latest)**
- 🔖 You can also find all official builds on the right sidebar under **[Releases](https://github.com/Flyingboy0329/peepeepoopoo/releases)**.

---

## 🎯 Core Concept & Philosophy

AI Director Studio operates as an intelligent pre-editing co-pilot designed to streamline post-production workflows:

- **AI Responsibilities**:
  - Ingest and analyze raw video streams.
  - Compute frame clarity via Laplacian Variance metrics.
  - Transcribe speech with CUDA-accelerated Whisper models.
  - Synthesize features and recommend prioritized timeline markers.
- **Human Editor Responsibilities**:
  - Validate creative reasoning behind AI recommendations.
  - Approve or adjust suggested marker grades.
  - Conduct final story cuts and creative assembly in DaVinci Resolve.

> **Guiding Principle**: *AI recommends, human decides.*

---

## ⚡ Key Features

- **Active File Sentinel**: Non-intrusive folder monitoring with write-lock detection to guarantee file integrity before triggering inference.
- **Dual-Track Neural Pipeline**:
  - **Speech & Semantics**: Faster-Whisper (CUDA FP16) with contextual domain prompt injection (reduces homophone errors in gaming/travel/tech jargon).
  - **Visual Optics**: OpenCV frame sampling and edge sharpness evaluation to filter out camera shake and out-of-focus frames.
- **RPG Tier Decision Engine**: Continuous spectrum mapping that clusters AI scores into Resolve timeline marker colors (Legendary Gold 🟡, Epic Purple 🟣, Rare Blue 🔵, Uncommon Green 🟢, Common Beige ⚪).
- **Silent Cross-Process Marker Injection**: Automated Win32 and Lua bridge targeting DaVinci Resolve with zero terminal popups, duplicate cleanup, and automatic media pool imports.
- **Midnight Neon Cyber Dashboard**: Built on PyQt6 with native Windows DWM dark mode titlebar, real-time dual-GPU telemetry (RTX 5060 Ti / RTX 3060), and dynamic resource meters.

---

## 📦 Scope of MVP (Minimum Viable Product)

### Included in MVP:
Raw Footage ➔ Optics Analysis ➔ Speech Transcription ➔ Feature Synthesis ➔ Marker Proposal ➔ Structured Resolve Injection

### NOT Included in MVP:
- Fully automated timeline cut generation (pure autonomous editing).
- Complete automated video generation.
- Direct programmatic control over Resolve playback head or panel dials.
- Automated background music scoring.
- Automated color grading passes.
- Ground-up foundation model training.

---

## 🚀 Quick Start

### 1. Requirements
- Windows 10 / 11 (64-bit)
- Python 3.10+
- NVIDIA GPU with CUDA support (Recommended: 6GB+ VRAM)
- DaVinci Resolve (Studio or Free edition)
- FFmpeg installed and configured in system PATH

### 2. Launch Studio
Double-click the desktop shortcut `AI Director Studio` or run:
```bash
pythonw 03_Code/app_gui.py
