"""
Ishchilar boti uchun FSM holatlar.
"""
from aiogram.fsm.state import State, StatesGroup


class ProofState(StatesGroup):
    """Vazifa bajarilganda isbot yuborish oqimi."""
    waiting_for_instruction = State()  # instruksiyani o'qish
    waiting_for_proof = State()        # isbot (rasm/fayl/matn) kutish


class BossTaskState(StatesGroup):
    """Boshliq bot orqali ishchiga vazifa biriktirish oqimi."""
    waiting_for_text = State()          # vazifa matni
    waiting_for_worker = State()        # ishchini tanlash (inline)
    waiting_for_deadline = State()      # deadline tanlash (inline/kalendar)
    waiting_for_manual_date = State()   # deadline'ni qo'lda yozish