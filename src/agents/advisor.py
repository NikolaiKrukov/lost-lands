"""首席顾问：只说话，不改状态。"""

from __future__ import annotations

from src.agents.provider import LLMProvider
from src.engine.briefing import briefing_text
from src.engine.config import GameData
from src.engine.state import GameState


def ask_advisor(data: GameData, state: GameState, provider: LLMProvider, question: str) -> str:
    preset = data.game.advisor.presets[data.game.advisor.provider]
    text = provider.chat(
        [
            {"role": "system", "content": data.game.advisor.prompt},
            {"role": "user", "content": briefing_text(data, state, question)},
        ],
        temperature=preset.temperature,
    )
    state.last_advisor = text.strip()
    return state.last_advisor
