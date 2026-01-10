import json
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_script_json(client, topic_name, output_file="video-output.json", provider='openai', model='gpt-4o'):
    """Generates the JSON file with script and animations using the LLM"""
    prompt = f"""Develop an educational script for this topic: {topic_name}

INSTRUCTIONS:
- Create an engaging and educational script about the topic
- Divide the script into logical scenes/fragments (between 6-8 scenes)
- For each scene, provide:
  1. The script text (narration) - BRIEF and CONCISE
  2. A detailed description of the Manim animation that should accompany that text
- Avoid using commercial logos (like ChatGPT, OpenAI, etc.)
- I DON'T want Python Manim code, just the description of what you want to visualize
- Animations should be specific and detailed so they can be implemented in Manim

LANGUAGE REQUIREMENT:
- The script and animations MUST be in the SAME LANGUAGE as the topic
- If the topic is in Spanish, write everything in Spanish
- If the topic is in English, write everything in English
- Match the language exactly

CRITICAL TIME RESTRICTION:
- The COMPLETE video must last MAXIMUM 60 seconds (1 minute)
- Each scene should last approximately 6-8 seconds
- The text of each scene must be SHORT (maximum 2-3 sentences)
- Animations must be SIMPLE and FAST

OUTPUT FORMAT (JSON):
Respond ONLY with a valid JSON array, where each element has this structure:
{{
  "text": "script text for this scene (BRIEF, 2-3 sentences maximum)",
  "animation": "detailed description of the specific animation for this fragment"
}}

Example of a scene:
{{
  "text": "Language models process text by converting it into numbers.",
  "animation": "Show the word 'Hello' in the center. Then, divide it into visual tokens with colored boxes. Finally, transform each token into a number (ID) with a morphing animation."
}}

IMPORTANT: Respond ONLY with the JSON array, without any additional text before or after."""

    try:
        print(f"Generating script for: {topic_name}...")
        
        if provider == 'openai':
            # OpenAI API call
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert in creating educational video scripts. You always respond in valid JSON format without additional text. IMPORTANT: Match the language of the topic exactly - if the topic is in Spanish, write in Spanish; if in English, write in English."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_completion_tokens=4000
            )
            response_text = response.choices[0].message.content.strip()
            
        elif provider == 'claude':
            # Claude API call
            response = client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.8,
                system="You are an expert in creating educational video scripts. You always respond in valid JSON format without additional text. IMPORTANT: Match the language of the topic exactly - if the topic is in Spanish, write in Spanish; if in English, write in English.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            response_text = response.content[0].text.strip()
        
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Try to extract JSON if wrapped in markdown
        if "```json" in response_text:
            response_text = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
        elif "```" in response_text:
            response_text = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL).group(1)
        
        # Parse JSON
        script_data = json.loads(response_text)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] Script generated successfully: {output_file}")
        print(f"Total scenes: {len(script_data)}")
        
        return script_data
        
    except Exception as e:
        print(f"[ERROR] Error generating script: {e}")
        return None
