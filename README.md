# 🟣 AI Director Studio (v1.0 ARTIFACT)

> **Neural Ingestion & Auto-Marker Workstation Dedicated to Blackmagic DaVinci Resolve**  
> An end-to-end automated audio-visual semantic analysis, sharpness evaluation, and timeline marker injection workstation specifically built for **DaVinci Resolve (Studio & Free Editions)**.

---

## 🎬 Mandatory Workflow Requirement: DaVinci Resolve Integration

⚠️ **IMPORTANT NOTICE**: This software is **NOT** a standalone video player or general-purpose autonomous video editor. It is an **AI-powered companion pipeline designed exclusively for DaVinci Resolve**.

- **Compatible NLE**: Blackmagic DaVinci Resolve 18 / 19+ (Compatible with both **Studio** and **Free** editions).
- **How It Works**: AI Director Studio ingests raw footage, performs dual-track neural analysis, and **directly injects frame-accurate timeline markers, RPG color tiers, and editing notes into your active DaVinci Resolve project** via background Lua scripting.
- **Workflow Rule**: You must have DaVinci Resolve running with an active project/timeline for markers to be automatically delivered.

---

## 📥 Direct Downloads & Releases

Looking for pre-built binaries or packaged release files without using Git commands?
- 📦 **[Click Here to Download Latest Release (v1.0.0 Artifact)](https://github.com/Flyingboy0329/peepeepoopoo/releases/latest)**
- 🔖 You can also find all official builds on the right sidebar under **[Releases](https://github.com/Flyingboy0329/peepeepoopoo/releases)**.

---

## 🎯 Core Concept & Philosophy

AI Director Studio operates as an intelligent pre-editing co-pilot designed to streamline DaVinci Resolve post-production workflows:

- **AI Responsibilities**:
  - Ingest raw video streams dropped into the sentinel watch folder.
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

- **Seamless DaVinci Resolve Bridge**: Automated cross-process Lua marker injection with zero DOS window popups, duplicate marker cleanup, and automatic Media Pool clip imports.
- **Active File Sentinel**: Non-intrusive folder monitoring with write-lock detection to guarantee file integrity before triggering inference.
- **Dual-Track Neural Pipeline**:
  - **Speech & Semantics**: Faster-Whisper (CUDA FP16) with contextual domain prompt injection (reduces homophone errors in gaming, travel, and technical terminology).
  - **Visual Optics**: OpenCV frame sampling and edge sharpness evaluation to filter out camera shake and out-of-focus frames.
- **RPG Tier Decision Engine**: Continuous spectrum mapping that clusters AI scores into Resolve timeline marker colors (Legendary Gold 🟡, Epic Purple 🟣, Rare Blue 🔵, Uncommon Green 🟢, Common Beige ⚪).
- **Midnight Neon Cyber Dashboard**: Built on PyQt6 with native Windows DWM dark mode titlebar, real-time dual-GPU telemetry (RTX 5060 Ti / RTX 3060), and dynamic resource meters.

---

## 📦 Scope of MVP (Minimum Viable Product)

### Included in MVP:
Raw Footage ➔ Optics Analysis ➔ Speech Transcription ➔ Feature Synthesis ➔ Marker Proposal ➔ **Direct DaVinci Resolve Timeline Injection**

### NOT Included in MVP:
- Fully automated timeline cut generation (pure autonomous editing).
- Complete automated video generation.
- Direct programmatic control over Resolve playback head or physical panel dials.
- Automated background music scoring.
- Automated color grading passes.
- Ground-up foundation model training.

---

## 🚀 Quick Start Guide

### 1. Requirements
- **Operating System**: Windows 10 / 11 (64-bit)
- **Target NLE**: DaVinci Resolve installed (Studio or Free)
- **Python**: Python 3.10+
- **Hardware**: NVIDIA GPU with CUDA support (Recommended: 6GB+ VRAM)
- **Dependencies**: FFmpeg installed and configured in system PATH

### 2. How to Run with DaVinci Resolve
1. **Launch DaVinci Resolve** and open your target project and timeline.
2. Double-click the desktop shortcut `AI Director Studio` (or run `pythonw 03_Code/app_gui.py`).
3. Check the header status badge — it will transition to `RESOLVE: READY`.
4. Drop your raw video files into the watched directory (`02_Data` by default).
5. Watch the `EVENT STREAM LOG` analyze the footage and automatically populate your Resolve timeline with colored markers!

---

## 📥 Get the Software (Direct Download)

- 💾 **[Download Latest Package (v1.0.0 Artifact)](https://github.com/Flyingboy0329/peepeepoopoo/releases/latest)**
- 🔗 Repository URL: [https://github.com/Flyingboy0329/peepeepoopoo](https://github.com/Flyingboy0329/peepeepoopoo)

---

## 👨‍💻 Author & Credits

- **Developer**: Pan Bo-Han (潘柏翰)
- **Academic Advisor**: Prof. 郭俞霈 (National Kaohsiung University of Science and Technology)
