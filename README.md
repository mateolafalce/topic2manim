<div align="center">

<img width="489" height="162" alt="image" src="https://github.com/user-attachments/assets/8a61c5a0-d1e6-4de5-a261-6897c18c2830" />



# Topic2Manim

</div>

Automatic educational video generator using AI and Manim. Converts any topic into a professional animated video with narration and mathematical visualizations.

<div align="center">
  
## User Interface

![video](./public/output6.gif)

</div>

<div align="center">
  
## Examples

</div>

> propmt: How do machines learn to recognize MNIST dataset numbers?
> 
> model: claude-sonnet-4-5-20250929
> 
> response:

<div align="center">

![video](./public/output5.gif)

</div>

> propmt: What is a Markov chain and how are they related to LLMs?
> 
> model: claude-sonnet-4-5-20250929
> 
> response:

<div align="center">

![video](./public/output4.gif)

</div>

> propmt: How does Cramer's rule work for system of linear equations?
> 
> model: claude-sonnet-4-5-20250929
> 
> response:

<div align="center">

![video](./public/output3.gif)

</div>

> propmt: how chat gpt works?
> 
> model: gpt-5.2
> 
> response:

<div align="center">

![video](./public/output.gif)

</div>

> propmt: how tokenization works in chat gpt?
> 
> model: gpt-5.2
> 
> response:

<div align="center">

![video](./public/output2.gif)

</div>

## Features

- **Multi-LLM Support** with automatic fallback (OpenAI GPT, Claude)
- **Automatic script generation** using advanced language models
- **Educational animations** with Manim Community Edition
- **Multi-language support** (automatically detects topic language)
- **Optimized videos** of ~60 seconds with multiple scenes
- **Automatic concatenation** of fragments into final video

## Architecture

### System Overview

Topic2Manim is a multi-agent system that orchestrates several specialized components to transform a topic into an educational video. The system follows a pipeline architecture where each agent has a specific responsibility.

```mermaid
graph TB
    subgraph Input
        A[User Topic]
    end
    
    subgraph "LLM Configuration"
        B[setup_llm_client]
        B1[Claude API]
        B2[OpenAI API]
        B -->|Priority 1| B1
        B -->|Fallback| B2
    end
    
    subgraph "Agent 1: Script Generation"
        C[animations.py]
        C1[generate_script_json]
        C --> C1
    end
    
    subgraph "Agent 2: TTS Generation"
        D[tts_generator.py]
        D1[generate_complete_audio]
        D2[generate_audio_fragment]
        D3[concatenate_audio_fragments]
        D1 --> D2
        D2 --> D3
    end
    
    subgraph "Agent 3: Manim Code Generation"
        E[manim_generator.py]
        E1[generate_manim_code]
        E --> E1
    end
    
    subgraph "Agent 4: Video Compilation"
        F[concat_video.py]
        F1[compile_video]
        F2[concatenate_videos]
        F3[merge_video_and_audio]
        F1 --> F2
        F2 --> F3
    end
    
    subgraph Output
        G[Final Video with Audio]
    end
    
    A --> B
    B --> C1
    C1 -->|video-output.json| D1
    C1 -->|video-output.json| E1
    D1 -->|audio durations| E1
    E1 -->|.py files| F1
    F1 -->|.mp4 fragments| F2
    D3 -->|audio.mp3| F3
    F2 -->|output_silent.mp4| F3
    F3 --> G
    
    style A fill:#e1f5ff
    style G fill:#c8e6c9
    style C fill:#fff9c4
    style D fill:#ffe0b2
    style E fill:#f8bbd0
    style F fill:#d1c4e9
```

### Agent Interaction Flow

```mermaid
sequenceDiagram
    participant User
    participant Main as main.py
    participant LLM as LLM Client
    participant Script as animations.py
    participant TTS as tts_generator.py
    participant Manim as manim_generator.py
    participant Video as concat_video.py
    
    User->>Main: Provide Topic
    Main->>Main: setup_llm_client()
    Main->>Script: generate_script_json(topic)
    Script->>LLM: Request script generation
    LLM-->>Script: Return JSON scenes
    Script-->>Main: video-output.json
    
    Note over Main,TTS: TTS Generation Phase
    Main->>TTS: generate_complete_audio(video_data)
    loop For each scene
        TTS->>TTS: generate_audio_fragment(text)
        TTS->>TTS: get_audio_duration()
    end
    TTS->>TTS: concatenate_audio_fragments()
    TTS-->>Main: audio.mp3 + durations
    
    Note over Main,Video: Video Generation Phase
    loop For each scene
        Main->>Manim: generate_manim_code(text, animation, duration)
        Manim->>LLM: Request Manim code
        LLM-->>Manim: Python code
        Manim-->>Main: .py file + class_name
        Main->>Video: compile_video(filepath, class_name)
        Video->>Video: Execute manim command
        Video-->>Main: .mp4 fragment
    end
    
    Note over Main,Video: Final Assembly
    Main->>Video: concatenate_videos(fragments)
    Video-->>Main: output_silent.mp4
    Main->>Video: merge_video_and_audio(video, audio)
    Video-->>Main: output.mp4
    Main-->>User: Final Video
```

### Module Structure

```mermaid
graph LR
    subgraph "Core Orchestrator"
        M[main.py]
    end
    
    subgraph "Agent Modules"
        A[animations.py<br/>Script Agent]
        T[tts_generator.py<br/>TTS Agent]
        MG[manim_generator.py<br/>Code Agent]
        C[concat_video.py<br/>Video Agent]
    end
    
    subgraph "External Services"
        LLM1[Claude API]
        LLM2[OpenAI API]
        MANIM[Manim CLI]
        FFMPEG[FFmpeg]
    end
    
    subgraph "Data Flow"
        JSON[video-output.json]
        PY[*.py files]
        MP4[*.mp4 fragments]
        MP3[audio.mp3]
        OUT[output.mp4]
    end
    
    M --> A
    M --> T
    M --> MG
    M --> C
    
    A --> LLM1
    A --> LLM2
    A --> JSON
    
    T --> LLM2
    T --> MP3
    
    MG --> LLM1
    MG --> LLM2
    MG --> PY
    
    C --> MANIM
    C --> FFMPEG
    PY --> C
    C --> MP4
    MP4 --> OUT
    MP3 --> OUT
    
    style M fill:#4fc3f7
    style A fill:#fff59d
    style T fill:#ffcc80
    style MG fill:#f48fb1
    style C fill:#ce93d8
```

### Data Flow Architecture

```mermaid
flowchart TD
    Start([User Input: Topic]) --> Setup[Setup LLM Client]
    
    Setup --> Agent1{Script Agent}
    Agent1 -->|LLM Call| Script[Generate JSON Script<br/>6-8 scenes]
    Script --> JSON[(video-output.json)]
    
    JSON --> Agent2{TTS Agent}
    Agent2 -->|For each scene| TTS1[Generate Audio Fragment]
    TTS1 --> TTS2[Get Duration]
    TTS2 --> TTS3{More scenes?}
    TTS3 -->|Yes| TTS1
    TTS3 -->|No| TTS4[Concatenate Fragments]
    TTS4 --> Audio[(audio.mp3 + durations)]
    
    JSON --> Loop{For each scene}
    Audio -->|durations| Loop
    
    Loop --> Agent3{Code Agent}
    Agent3 -->|LLM Call + Context| Code[Generate Manim Code<br/>with audio sync]
    Code --> PyFile[(scene-N.py)]
    
    PyFile --> Agent4{Video Agent}
    Agent4 -->|manim -pql| Compile[Compile Scene]
    Compile --> Fragment[(scene-N.mp4)]
    
    Fragment --> Check{More scenes?}
    Check -->|Yes| Loop
    Check -->|No| Concat[Concatenate Videos]
    
    Concat --> Silent[(output_silent.mp4)]
    Audio --> Merge[Merge Video + Audio]
    Silent --> Merge
    
    Merge --> Final([output.mp4])
    
    style Start fill:#e1f5ff
    style Agent1 fill:#fff9c4
    style Agent2 fill:#ffe0b2
    style Agent3 fill:#f8bbd0
    style Agent4 fill:#d1c4e9
    style Final fill:#c8e6c9
```

### Context Propagation

```mermaid
graph LR
    S1[Scene 1] -->|context| S2[Scene 2]
    S2 -->|context| S3[Scene 3]
    S3 -->|context| SN[Scene N]
    
    subgraph Context
        T[Previous Text]
        A[Previous Animation]
        C[Previous Code]
    end
    
    S1 -.-> Context
    S2 -.-> Context
    S3 -.-> Context
    
    style S1 fill:#ffeb3b
    style S2 fill:#ffc107
    style S3 fill:#ff9800
    style SN fill:#ff5722
```

Each scene receives context from the previous scene to maintain visual and narrative continuity.


## Installation

```bash
git clone https://github.com/mateolafalce/topic2manim.git
cd topic2manim

pip install -r requirements.txt

cp .env.example .env
```

## Usage

Start the Flask server:

```bash
python main.py
```

Then open your browser and navigate to:
```
http://localhost:5000
```

or 

```bash
docker compose up
```


