# Research: Interactive & Editable Video — Topic2Manim

> Branch: `research/interactive-editable-video`  
> Date: 2026-05-31  
> Goal: Identify technologies and approaches to make Topic2Manim videos interactive, editable, and extensible with other libraries.

---

## 1. Interactive Video for Education

### 1.1 H5P (HTML5 Package) — The Gold Standard

**What it is:** Open-source framework for creating rich interactive HTML5 content. The "Interactive Video" content type lets authors overlay quizzes, explanations, images, tables, links, and branching scenarios on top of any video.

**Key features:**
- Multiple choice / fill-in-the-blank / drag-and-drop questions overlaid on video
- **Adaptive branching:** correct answer → skip ahead; wrong answer → jump to explanation
- Bookmarks for section navigation
- Interactive summaries at the end
- Works in any LMS (Moodle, Canvas, Blackboard) via LTI
- **No coding required** for content authors

**How it could apply to Topic2Manim:**
- After generating a video, produce an **H5P-compatible JSON manifest** alongside the MP4
- The manifest describes where each scene starts, what quiz questions to ask, and where explanations live
- Users can upload the video + manifest to any H5P-enabled platform
- **Even simpler:** generate an interactive HTML wrapper that embeds the MP4 with click overlays (no LMS needed)

**Relevance:** ⭐⭐⭐⭐⭐ (directly applicable, open source, proven in education)

### 1.2 Branching Narratives

**What it is:** Instead of a linear video, the viewer makes choices that affect what plays next. Think "choose your own adventure" for education.

**How it could apply:**
- The script generation stage could produce a **decision tree** instead of a linear scene list
- Scene nodes have conditions: "if viewer answers A → play scene 5; if B → play scene 6"
- Manim generates all branches; the player assembles them based on user input
- Export format: a JSON graph + MP4 segments + a lightweight HTML5 player

**Relevance:** ⭐⭐⭐⭐ (high engagement, but adds complexity to script generation)

---

## 2. Video Editing & Post-Processing Libraries

### 2.1 MoviePy v2.0 — Python Video Editing

**What it is:** A Python library for programmatic video editing. Treats video clips as Python objects (numpy arrays) that can be cut, composited, overlaid, and rendered.

**Key features:**
- `VideoFileClip`, `TextClip`, `CompositeVideoClip` for non-linear editing
- Subclip, resize, position, rotate, fade, speed changes
- Add text overlays, images, audio mixing
- Render to MP4/WebM/GIF
- **v2.0** (recent) has major breaking changes but is actively maintained

**How it could apply to Topic2Manim:**
- **Replace raw ffmpeg calls** in `concat_video.py` with MoviePy for cleaner scene assembly
- Add **title cards, watermarks, end screens** programmatically after Manim renders scenes
- **Composite multiple video layers:** background plate + Manim animation + text overlay + audio
- Better transitions: crossfade, slide, wipe (instead of just fade-to-black)
- Post-process individual scenes: color grade, add motion blur, stabilize

**Pros:** Pure Python, integrates well with existing stack, readable code  
**Cons:** Slower than raw ffmpeg for large files, dependency management can be tricky  
**Relevance:** ⭐⭐⭐⭐⭐ (easy integration, massive upgrade to current ffmpeg-only pipeline)

### 2.2 Remotion — React-Based Programmatic Video

**What it is:** Framework for creating videos programmatically using React components. You write JSX/CSS and Remotion renders it frame-by-frame to MP4 via headless browser + ffmpeg.

**Key features:**
- Real-time preview in browser (hot reload)
- Server-side rendering (Lambda, Node.js)
- Full React ecosystem: npm packages, TypeScript, hooks
- Timeline control via `useCurrentFrame()`
- Data-driven templates (generate 1000 personalized videos from one template)

**How it could apply:**
- **Not a replacement for Manim** (Manim is far superior for math animations)
- But excellent for **title sequences, intro/outro cards, lower thirds, social-media end screens**
- Could run a Remotion renderer alongside Manim for "packaging" the final video
- Alternative: use Remotion's **Media Parser** (launched 2025) for reading video metadata

**Pros:** Modern web stack, great for UI-heavy video elements  
**Cons:** Requires Node.js, licensing costs for commercial use at scale, overkill for math content  
**Relevance:** ⭐⭐⭐ (nice for packaging, but not core to math education)

### 2.3 Omniclip — Browser-Based Open Source Editor

**What it is:** Free open-source video editor that runs entirely in the browser using WebCodecs API. No uploads, no accounts.

**Key features:**
- Trim, split, text, audio, images, transitions
- Undo/redo, multi-resolution export up to 4K
- **Embeddable components:** `omni-text`, `omni-media`, `omni-timeline`
- "Omni Tools" coming: programmatic timeline creation from code

**How it could apply:**
- Embed an **Omniclip-based timeline editor** in the Topic2Manim frontend
- After scenes are rendered, users can drag them onto a timeline, trim, reorder, add transitions
- Export final video directly from the browser (no server round-trip)

**Pros:** Runs in browser, privacy-first, no server load for editing  
**Cons:** WebCodecs support limited on older browsers, early-stage project  
**Relevance:** ⭐⭐⭐⭐ (would give users real editing power without leaving the browser)

---

## 3. Complementary Animation & Visualization Libraries

### 3.1 Matplotlib + Matplotlib Animation

**What it is:** The standard Python plotting library. `matplotlib.animation` can generate animated plots (line charts, bar races, scatter evolutions).

**How it could apply:**
- For **data-driven scenes**, instead of asking Manim to draw a graph from scratch, generate a Matplotlib animation and overlay it
- Manim handles the narrative framing (titles, transitions); Matplotlib handles the precise data viz
- Export Matplotlib animation as MP4 segment → concat with Manim scenes

**Relevance:** ⭐⭐⭐⭐ (excellent for statistics, economics, data science topics)

### 3.2 Plotly + Plotly Express

**What it is:** Interactive web-based plotting library. Can export static images or HTML embeds.

**How it could apply:**
- Generate **interactive 3D plots, animated scatter plots, choropleth maps**
- For topics that need real data visualization (geography, epidemiology, finance)
- Can export frames and feed them into the Manim pipeline as image sequences

**Relevance:** ⭐⭐⭐ (great for specific topics, but Manim already handles most math viz)

### 3.3 Pygame — Game/Physics Simulations

**What it is:** 2D game development library. Excellent for physics simulations, particle systems, real-time interactions.

**How it could apply:**
- **Physics simulations:** projectile motion, orbital mechanics, collisions, fluid dynamics
- Record Pygame screen output as video frames, then composite into Manim scenes
- More natural for "living systems" than Manim's frame-by-frame approach

**Relevance:** ⭐⭐⭐ (niche use case, but powerful for physics education)

---

## 4. Editable Video Formats & Project Files

### 4.1 The Problem

Right now Topic2Manim produces:
- An MP4 file (final video)
- Scene Python files (Manim code)
- A JSON script

But there's no way for a user to **re-open a finished video and edit it** without regenerating from scratch.

### 4.2 Solutions

**A. Project File Export (.t2m)**
- Export a zip containing: `script.json` + `scene_codes/` + `audio.mp3` + `assets/`
- User can re-import this project later, edit any scene, and re-render only changed scenes
- Already partially supported via checkpointing — just needs a UI for import/export

**B. FCPXML / DaVinci Resolve Project Export**
- Export an XML project file that professional editors (Final Cut Pro, DaVinci Resolve, Premiere) can open
- Each Manim scene becomes a clip on the timeline with markers for scene boundaries
- Audio track is synced
- Professional editors can then add color grading, motion graphics, sound design

**C. EDL (Edit Decision List)**
- Simple text format describing cuts and transitions
- Universal format supported by almost every editor
- Very easy to generate from our scene list

**Relevance:** ⭐⭐⭐⭐⭐ (makes Topic2Manim a first-class citizen in professional workflows)

---

## 5. Specific Recommendations for Topic2Manim

### Immediate Wins (Low Effort, High Impact)

| # | Idea | Effort | Impact |
|---|------|--------|--------|
| 1 | **Integrate MoviePy** for post-processing: title cards, end screens, better transitions, text overlays | Medium | Very High |
| 2 | **Export `.t2m` project files** (zip of script + code + audio) for re-editing later | Low | High |
| 3 | **Add interactive HTML wrapper** — embed the MP4 with scene bookmarks and clickable chapter navigation | Low | High |
| 4 | **Export EDL/FCPXML** so users can open projects in DaVinci Resolve / Final Cut Pro | Medium | High |

### Medium-Term (Moderate Effort)

| # | Idea | Effort | Impact |
|---|------|--------|--------|
| 5 | **H5P-compatible manifest generation** — quizzes and explanations overlaid on the video | Medium | Very High |
| 6 | **Timeline editor in frontend** (Omniclip-style) — drag scenes, trim, reorder, add transitions | High | Very High |
| 7 | **Branching narrative support** — script generator produces decision trees, player handles branches | High | High |
| 8 | **Matplotlib integration** — data viz scenes rendered with Matplotlib, composited into Manim | Medium | Medium |

### Long-Term / Experimental

| # | Idea | Effort | Impact |
|---|------|--------|--------|
| 9 | **Remotion integration** for intro/outro sequences and social-media packaging | High | Medium |
| 10 | **Pygame physics simulations** as an alternative renderer for physics topics | High | Medium |
| 11 | **Real-time collaborative editing** — multiple users editing the same script simultaneously | Very High | Medium |

---

## 6. Competitor Landscape

| Tool | What it does | vs Topic2Manim |
|------|-------------|----------------|
| **AnimG** (animg.app) | Browser-based Manim AI generator + online editor | Similar concept, but closed-source, no local rendering, limited customization |
| **Manim Video Generator (Motia)** | Node.js + TypeScript Manim pipeline with skills system | More architecture-heavy, no interactive elements, no editing |
| **Code2Video (arxiv 2025)** | Academic agent framework (Planner-Coder-Critic) | Similar pipeline to ours, but research-only, no product |
| **TheoremExplainAgent** | Multi-agent system for STEM theorem videos | Academic, no open source product |
| **H5P Interactive Video** | Add quizzes/hotspots to existing videos | Complementary — we could generate H5P content |
| **Remotion** | React programmatic video | General-purpose, not math-focused |

**Our differentiation:** Topic2Manim is the only open-source, self-hostable tool that combines AI script generation, Manim rendering, TTS, visual QA, AND has a web UI with script review. Adding interactivity and editability would make it truly unique.

---

## 7. Next Steps

1. **Spike MoviePy integration** — replace `concat_video.py` ffmpeg calls with MoviePy, add title card generation
2. **Prototype `.t2m` project export** — zip checkpoint data into a downloadable project file
3. **Research H5P manifest format** — design a JSON schema for Topic2Manim → H5P interactive video
4. **Evaluate Omniclip embedding** — test if Omniclip components can be embedded in our frontend for timeline editing

---

*End of research document.*
