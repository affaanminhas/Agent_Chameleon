"""
Agent_Perry.py - Baseline version using Hugging Face API (no local model)
"""

import os
import re
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Internal imports
from Agent.memory.vector_store import Memory
from function_schema.tool_registry import ToolRegistry
from function_schema.nmap import Nmap

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

PERSONA = ("Steve Jobs", "The visionary co-founder of Apple, known for his charisma, design obsession, and leadership. Speak in a confident, inspiring tone. Focus on innovation, simplicity, and the user experience.")
MEMORY_PATH = "./data/LTM/STEVE_JOBS_LTM"

# Hugging Face API configuration
HF_TOKEN = os.getenv("HF_TOKEN")
API_BASE_URL = "https://router.huggingface.co/v1"
MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"  # Or "microsoft/phi-2"


# ============================================================
# AGENT CLASS
# ============================================================

class AgentPerry:
    """
    Baseline agent using Hugging Face API (no local model).
    """

    def __init__(self, persona: str = PERSONA, memory_path: str = None):
        self.persona = persona
        self.memory_path = memory_path or MEMORY_PATH
        
        # Set name and role
        self.name = self.persona[0]
        self.role = self.persona[1]

        # ── 1. Memory ────────────────────────────────────────────────
        print(f"Loading memory for {self.name}...")
        self.memory = Memory(persist_directory=self.memory_path)

        # ── 2. LLM Client (Hugging Face API) ─────────────────────────
        print(f"Connecting to Hugging Face API...")
        self.client = OpenAI(
            api_key=HF_TOKEN,
            base_url=API_BASE_URL
        )

        # ── 3. Tools ─────────────────────────────────────────────────
        print("Registering tools...")
        self.tools = ToolRegistry()
        self._register_tools()

        # ── 4. Session state ─────────────────────────────────────────
        self.session_history: List[Dict] = []

        print(f"\n✅ {self.name} ready!")
        print(f"   Role:     {self.role}")
        print(f"   Memories: {self.memory.count_memories()}")
        print(f"   Tools:    {self.tools.list_tools()}")
        print(f"   Model:    {MODEL_NAME} (API)")


    def _register_tools(self):
        nmap = Nmap()
        self.tools.register(
            name=nmap.name,
            func=nmap.execute,
            description=nmap.description
        )

    def _retrieve_memories(self, query: str) -> List[Dict]:
        memories = self.memory.recall_similar(query=query)
        return memories

    def _format_memories(self, memories: List[Dict]) -> str:
        if not memories:
            return ""
        lines = ["\n\nRelevant past conversations you've had:"]
        for i, mem in enumerate(memories, 1):
            parts = mem['text'].split('\n')
            user_part = parts[0].replace('User: ', '') if parts else ""
            persona_part = parts[1].replace(f"{self.name}: ", '') if len(parts) > 1 else ""
            lines.append(
                f"\n--- Memory {i} (from {mem['metadata'].get('timestamp', 'unknown')}) ---\n"
                f"Someone asked: {user_part}\n"
                f"You responded: {persona_part}"
            )
        return "\n".join(lines)

    def _classify_topic(self, text: str) -> str:
        text_lower = text.lower()
        topics = {
            "apple_products": ["iphone", "ipad", "mac", "apple", "product"],
            "design": ["design", "simplicity", "beautiful"],
            "leadership": ["leadership", "manage", "team"],
            "career": ["fired", "neXT", "pixar"],
            "philosophy": ["life", "death", "meaning", "hungry", "foolish"],
        }
        
        for topic, keywords in topics.items():
            if any(kw in text_lower for kw in keywords):
                return topic
        return "general"

    def _should_use_tool(self, text: str) -> bool:
        tool_triggers = ["scan", "nmap", "port", "network", "localhost"]
        text_lower = text.lower()
        return any(trigger in text_lower for trigger in tool_triggers)

    def _extract_tool_target(self, text: str) -> Optional[str]:
        match = re.search(r'(scan|check)\s+([a-zA-Z0-9.\-]+)', text.lower())
        return match.group(2) if match else None

    def build_prompt(self, user_input: str) -> str:
        base = f"You are {self.name}. {self.role}"
        
        memories = self._retrieve_memories(user_input)
        memory_block = self._format_memories(memories)
        if memory_block:
            base += f"\n\nHere is what you remember about this person:{memory_block}"
            
        recent = [h for h in self.session_history if h.get('action') == 'response'][-3:]
        if recent:
            base += "\n\nRecent conversation:"
            for entry in recent:
                base += f"\nUser: {entry['user_input']}\nYou: {entry['response']}"
        
        return base

    def respond(self, user_input: str, use_memory: bool = True) -> str:
        """Generate a response using the Hugging Face API."""
        print(f"\n▶ [{self.name}] Processing: '{user_input}'")

        # Tool path
        if self._should_use_tool(user_input):
            print("🔧 Tool trigger detected...")
            target = self._extract_tool_target(user_input)
            if target:
                print(f"   Target: {target}")
                result = self.tools.execute("nmap_scan", {"target": target})
                tool_response = f"Network scan results:\n{result}"
                self.memory.store_interaction(
                    user_input=user_input,
                    agent_response=tool_response,
                    topic="network_scan",
                    metadata={"persona": self.persona}
                )
                return tool_response

        # API path
        try:
                        
            response = self.client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": self.build_prompt(user_input)},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=500
            )
            agent_response = response.choices[0].message.content

        except Exception as e:
            agent_response = f"[Agent error: {e}]"

        # Memory storage
        topic = self._classify_topic(user_input)
        self.memory.store_interaction(
            user_input=user_input,
            agent_response=agent_response,
            topic=topic,
            metadata={"persona": self.persona[0]}
        )

        self.session_history.append({
            "timestamp": datetime.now().isoformat(),
            "action": "response",
            "user_input": user_input,
            "response": agent_response,
            "topic": topic
        })

        print(f"✅ Stored (topic: {topic})")
        return agent_response

    def get_stats(self) -> Dict:
        return {
            "persona": self.name,
            "total_memories": self.memory.count_memories(),
            "session_exchanges": len([h for h in self.session_history if h.get('action') == 'response']),
            "recent_topics": list(set([h.get('topic', 'unknown') for h in self.session_history[-5:] if h.get('action') == 'response']))
        }


# ── Interactive session ───────────────────────────────────────────────

def interactive_session():
    print("\n" + "=" * 60)
    print("=" * 60)
    
    agent = AgentPerry()
    # Check what's actually in memory
    print(f"\n📦 Memory count: {agent.memory.count_memories()}")
    recent = agent.memory.get_recent_memories(5)
    for mem in recent:
        print(f"   {mem['metadata'].get('timestamp')} — {mem['text'][:80]}")

    print(f"\n{agent.name}: Hello. I'm {agent.name}.")
    print("\nCommands:")
    print("  'exit'  - quit")
    print("  'stats' - show statistics")
    print("  'debug' - toggle memory debug")
    print("  'raw'   - toggle raw mode (no memory context)")
    print("=" * 60 + "\n")

    show_debug = False
    raw_mode = False

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
            
        elif user_input.lower() == 'exit':
            print(f"\n{agent.name}: Stay hungry. Stay foolish.")
            break
            
        elif user_input.lower() == 'stats':
            stats = agent.get_stats()
            print(f"\n📊 Stats:")
            for k, v in stats.items():
                print(f"   {k}: {v}")
            continue
            
        elif user_input.lower() == 'debug':
            show_debug = not show_debug
            print(f"\n🔍 Debug: {'ON' if show_debug else 'OFF'}")
            continue
            
        elif user_input.lower() == 'raw':
            raw_mode = not raw_mode
            print(f"\n🧪 Raw mode: {'ON — no memory context' if raw_mode else 'OFF — full memory context'}")
            continue

        if show_debug:
            memories = agent._retrieve_memories(user_input)
            print(f"\n🔍 {len(memories)} memories retrieved:")
            for mem in memories:
                print(f"   • {mem['similarity']:.2f} — {mem['metadata']['topic']}")

        response = agent.respond(user_input, use_memory=not raw_mode)
        print(f"\n{agent.name}: {response}")


if __name__ == "__main__":
    interactive_session()