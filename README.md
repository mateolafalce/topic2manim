<div align="center">

<img width="489" height="162" alt="image" src="https://github.com/user-attachments/assets/8a61c5a0-d1e6-4de5-a261-6897c18c2830" />



# Topic2Manim

</div>

Automatic educational video generator using AI and Manim. Converts any topic into a professional animated video with narration and mathematical visualizations.

<div align="center">
  
## Examples

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


## Installation

```bash
git clone https://github.com/mateolafalce/topic2manim.git
cd topic2manim

pip install -r requirements.txt

cp .env.example .env
```

## Usage

```bash
python main.py
```

The final video will be saved in `media/output.mp4`

### LLM Provider Selection

The system automatically selects the LLM provider based on available API keys:

1. **Priority 1**: If `OPENAI_API_KEY` is configured, uses OpenAI GPT models
2. **Priority 2**: If OpenAI is not available, falls back to Anthropic Claude
3. **Error**: If neither API key is configured, the system will exit with an error

## Roadmap

- [x] **Text Generation Agent**: GPT-based agent that creates educational scripts from any topic
- [x] **Scene Generation**: Automatic Manim code generation for each scene
- [x] **Video Compilation**: Individual scene rendering and concatenation
- [x] **Multi-language Support**: Automatic language detection and localization
- [ ] **TTS Integration**: Text-to-Speech narration for generated scripts
  - Voice synthesis for educational content
  - Audio synchronization with video scenes
  - Multi-language voice support
