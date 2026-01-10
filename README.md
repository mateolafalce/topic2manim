# Topic2Manim

Automatic educational video generator using AI and Manim. Converts any topic into a professional animated video with narration and mathematical visualizations.

## Features

- **Automatic script generation** using GPT-5.2
- **Educational animations** with Manim Community Edition
- **Multi-language support** (automatically detects topic language)
- **Optimized videos** of ~60 seconds with multiple scenes
- **Automatic concatenation** of fragments into final video


## Installation

```bash
git clone https://github.com/mateolafalce/topic2manim.git
cd topic2manim

pip install -r requirements.txt

cp .env.example .env
```

## Usage

```bash
TOPIC="how ChatGPT works"
python videoresearch.py
```

The final video will be saved in `media/output.mp4`

## Configuration

Edit the `.env` file:

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o
TOPIC=your_topic_here
```


## How It Works

1. **Script generation**: GPT-5.2 creates an educational script divided into scenes
2. **Manim code**: For each scene, Python Manim code is generated
3. **Compilation**: Each scene is compiled into an individual video
4. **Concatenation**: FFmpeg joins all fragments into a final video