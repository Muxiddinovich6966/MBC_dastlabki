"""
Ishchilar boti uchun FSM holatlar.
"""
from aiogram.fsm.state import State, StatesGroup


class ProofState(StatesGroup):
    """Vazifa bajarilganda isbot yuborish oqimi."""
    waiting_for_instruction = State()  # instruksiyani o'qish
    waiting_for_proof = State()        # isbot (rasm/fayl/matn) kutish