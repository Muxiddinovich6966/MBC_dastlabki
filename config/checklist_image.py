"""
Check-listni "oq daftar" ko'rinishidagi rasm (PNG) qilib chizadi.
Guruhga rasm sifatida yuboriladi (matn emas) — toza, ortiqcha yuklarsiz.
"""
import io
import os
import re

from PIL import Image, ImageDraw, ImageFont
from django.conf import settings

FONT_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')

# ── Ranglar (oq daftar uslubi) ───────────────────────────────
BG      = (250, 249, 244)   # krem-oq fon
INK     = (45, 45, 45)      # asosiy matn
MUTED   = (150, 148, 140)   # kulrang (mas'ul, sana)
LINE    = (226, 223, 214)   # yengil daftar chizig'i
BOX     = (120, 118, 110)   # katakcha ramkasi
GREEN   = (46, 160, 90)     # bajarilgan belgisi
DONE_TX = (170, 168, 160)   # bajarilgan vazifa matni (och)
CHIP_TX = (255, 255, 255)   # bo'lim chipchasidagi matn (oq)

# ── Har bo'lim uchun rang (chipcha foni) ─────────────────────
DEPT_COLORS = {
    'media':       (37, 99, 235),    # ko'k
    'organizator': (220, 38, 38),    # qizil
    'ceo':         (124, 58, 237),   # binafsha
    'menejer':     (13, 148, 136),   # yashil-ko'k
    'other':       (120, 118, 110),  # kulrang
}

# ── Har bo'lim boshlig'ining lavozim nomi (checklistda ism oldida) ──
HEAD_TITLES = {
    'media':       "Media boshlig'i",
    'organizator': "Organizator boshlig'i",
    'ceo':         "CEO",
    'menejer':     "Bosh menejer",
}

# ── Har status uchun rangli badge (matn, fon) ────────────────
STATUS_STYLES = {
    'pending':   ('Kutilmoqda',  (146, 100, 20),  (255, 244, 214)),  # amber
    'completed': ('Bajarildi',   (25, 120, 70),   (219, 247, 230)),  # yashil
    'overdue':   ('Kechikdi',    (183, 92, 12),   (255, 232, 205)),  # to'q sariq
    'not_done':  ('Bajarilmadi', (176, 32, 32),   (253, 224, 224)),  # qizil
}

# ── O'lchamlar ───────────────────────────────────────────────
W        = 900
PAD      = 60
BOX_SIZE = 34


_FONT_CACHE = {}


def _font(name, size):
    """Shriftni bir marta yuklab, keshdan qaytaradi (har render'da diskdan o'qimaydi)."""
    key = (name, size)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
        _FONT_CACHE[key] = f
    return f


def _clean_label(label):
    """Bo'lim nomidan emoji/belgilarni olib tashlab, katta harfda qaytaradi."""
    txt = re.sub(r'[^\w\s]', '', label or '', flags=re.UNICODE).strip()
    return txt.upper() or 'BOSHQA'


def _wrap(draw, text, font, max_w):
    """Matnni max_w kenglikka sig'dirib, qatorlarga bo'ladi."""
    words = str(text).split()
    lines, cur = [], ''
    for word in words:
        trial = (cur + ' ' + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or ['—']


def _person_header(worker, dept, dept_label):
    """Checklistdagi sarlavha. Boshliq bo'lsa: "<Lavozim>: <ism>" (masalan "Bosh menejer: Axmad")."""
    if worker is None:
        return "Biriktirilmagan"
    if getattr(worker, 'is_head', False):
        title = HEAD_TITLES.get(dept, f"{dept_label.capitalize()} boshlig'i")
        return f"{title}: {worker.name}"
    return worker.name


def _grouped_tasks(work_event, department=None):
    """Bo'lim → odam → vazifalar tuzilishida guruhlaydi.
    Har section: (dept_label, dept, persons)
      persons: [(worker|None, is_boss, header, items), ...]
      items:   [(task, task_workers), ...]  — deadline bo'yicha saralangan.
    Bitta vazifa bir necha odamga biriktirilgan bo'lsa — har odam ostida chiqadi.
    department berilsa — faqat o'sha bo'lim.
    """
    from apps.workers.models import Task, Worker

    tasks = list(
        Task.objects.filter(event=work_event)
        .select_related('completed_by')
        .prefetch_related('workers')
        .order_by('deadline_date')
    )
    labels = dict(Worker.DEPARTMENT_CHOICES)

    # dept -> { worker_id(None=biriktirilmagan): (worker, [(task, tw)]) }
    dept_map = {}
    for t in tasks:
        tw = list(t.workers.all())
        if tw:
            for w in tw:
                dept = w.department or 'other'
                bucket = dept_map.setdefault(dept, {})
                bucket.setdefault(w.id, (w, []))[1].append((t, tw))
        else:
            bucket = dept_map.setdefault('other', {})
            bucket.setdefault(None, (None, []))[1].append((t, tw))

    order = [d for d, _ in Worker.DEPARTMENT_CHOICES] + ['other']
    if department is not None:
        order = [department]

    def _dl_key(it):
        dl = it[0].deadline_date
        return (dl is None, dl)

    result = []
    for dept in order:
        if dept not in dept_map:
            continue
        dept_label = _clean_label(labels.get(dept, 'Boshqa'))
        entries = list(dept_map[dept].values())
        # Tartib: bo'lim boshlig'i birinchi, keyin ism bo'yicha, biriktirilmagan oxirida
        entries.sort(key=lambda e: (
            2 if e[0] is None else (0 if getattr(e[0], 'is_head', False) else 1),
            (e[0].name.lower() if e[0] else ''),
        ))
        persons = []
        for w, items in entries:
            items.sort(key=_dl_key)
            persons.append((w, (w is not None and getattr(w, 'is_head', False)),
                            _person_header(w, dept, dept_label), items))
        result.append((dept_label, dept, persons))
    return tasks, result


def _draw(draw, work_event, sections, fonts, do_draw=True, update_note=None):
    """Bir marta chizadi (yoki faqat balandlikni o'lchaydi). Yakuniy y ni qaytaradi."""
    f_title, f_date, f_sec, f_task, f_meta, f_foot = fonts
    x = PAD
    max_text_w = W - PAD * 2 - BOX_SIZE - 22
    y = PAD

    # ── "Yangilandi" banneri (tahrirlaganda) ──
    if update_note:
        pad_in = 16
        tw = draw.textlength(update_note, font=f_meta)
        bar_h = f_meta.size + pad_in
        if do_draw:
            draw.rounded_rectangle(
                [x, y, x + tw + pad_in * 2, y + bar_h],
                radius=bar_h // 2, fill=(255, 240, 219),
            )
            draw.text((x + pad_in, y + pad_in // 2), update_note, font=f_meta, fill=(184, 106, 20))
        y += bar_h + 18

    # ── Sarlavha: tadbir nomi ──
    ev_date = work_event.event_date
    date_str = ev_date.strftime('%d.%m.%Y') if hasattr(ev_date, 'strftime') else str(ev_date)
    if getattr(work_event, 'event_time', None):
        t = work_event.event_time
        date_str += '  ·  ' + (t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)[:5])

    for line in _wrap(draw, work_event.name, f_title, W - PAD * 2):
        if do_draw:
            draw.text((x, y), line, font=f_title, fill=INK)
        y += f_title.size + 8
    y += 4
    if do_draw:
        draw.text((x, y), date_str, font=f_date, fill=MUTED)
    y += f_date.size + 14

    # ── Umumiy progress (takroriy vazifa bir marta sanaladi) ──
    uniq = {}
    for _, _, persons in sections:
        for _, _, _, items in persons:
            for tsk, _ in items:
                uniq[tsk.id] = tsk
    total = len(uniq)
    done = sum(1 for t in uniq.values() if t.status == 'completed')
    if do_draw:
        draw.text((x, y), f"Bajarildi: {done}/{total}", font=f_date, fill=INK)
    y += f_date.size + 10
    if do_draw:
        draw.line([(x, y), (W - PAD, y)], fill=LINE, width=2)
    y += 24

    # ── Bo'lim → odam → vazifalar ──
    for label, dept, persons in sections:
        color = DEPT_COLORS.get(dept, DEPT_COLORS['other'])
        # Bo'limdagi jami/bajarilgan (takrorsiz)
        d_uniq = {}
        for _, _, _, items in persons:
            for tsk, _ in items:
                d_uniq[tsk.id] = tsk
        s_done = sum(1 for t in d_uniq.values() if t.status == 'completed')
        chip_pad_x, chip_pad_y = 16, 8
        lbl_w = draw.textlength(label, font=f_sec)
        chip_h = f_sec.size + chip_pad_y * 2
        if do_draw:
            # Rangli chipcha (bo'lim nomi ajralib tursin)
            draw.rounded_rectangle(
                [x, y, x + lbl_w + chip_pad_x * 2, y + chip_h],
                radius=chip_h // 2, fill=color,
            )
            draw.text((x + chip_pad_x, y + chip_pad_y), label, font=f_sec, fill=CHIP_TX)
            cnt = f"{s_done}/{len(d_uniq)}"
            draw.text((W - PAD - draw.textlength(cnt, font=f_sec), y + chip_pad_y),
                      cnt, font=f_sec, fill=color)
        y += chip_h + 16

        # ── Har bir odam ──
        for worker, is_boss, header, items in persons:
            # Boshliq — lavozim+ism bo'lim rangida; oddiy ishchi — qora ism
            hcolor = color if is_boss else INK
            for hline in _wrap(draw, header, f_sec, W - PAD * 2):
                if do_draw:
                    draw.text((x, y), hline, font=f_sec, fill=hcolor)
                y += f_sec.size + 6
            y += 6

            tx = x + BOX_SIZE + 22
            max_pw = W - PAD - tx
            for idx, (tsk, tw) in enumerate(items, start=1):
                done_it = tsk.status == 'completed'
                box_top = y
                # Katakcha
                if do_draw:
                    draw.rounded_rectangle(
                        [x, box_top, x + BOX_SIZE, box_top + BOX_SIZE],
                        radius=7, outline=(GREEN if done_it else BOX), width=3,
                    )
                    if done_it:
                        draw.line(
                            [(x + 8, box_top + 18), (x + 15, box_top + 25),
                             (x + 27, box_top + 9)],
                            fill=GREEN, width=4, joint='curve',
                        )
                tcolor = DONE_TX if done_it else INK
                desc = f"{idx}. {tsk.description}"
                lines = _wrap(draw, desc, f_task, max_pw)
                for i, line in enumerate(lines):
                    ly = box_top + i * (f_task.size + 6)
                    if do_draw:
                        draw.text((tx, ly), line, font=f_task, fill=tcolor)
                        if done_it:  # ustidan chiziq
                            lw = draw.textlength(line, font=f_task)
                            cy = ly + f_task.size / 2 + 2
                            draw.line([(tx, cy), (tx + lw, cy)], fill=DONE_TX, width=2)
                y = box_top + len(lines) * (f_task.size + 6) + 6

                # ── Rangli status badge + deadline (bir qatorda) ──
                s_label, s_tx, s_bg = STATUS_STYLES.get(
                    tsk.status, STATUS_STYLES['pending'])
                bpx, bpy = 12, 5
                bw = draw.textlength(s_label, font=f_meta)
                bh = f_meta.size + bpy * 2
                dl = tsk.deadline_date
                dl_str = dl.strftime('%d/%m') if hasattr(dl, 'strftime') else str(dl)
                if do_draw:
                    draw.rounded_rectangle(
                        [tx, y, tx + bw + bpx * 2, y + bh],
                        radius=bh // 2, fill=s_bg,
                    )
                    draw.text((tx + bpx, y + bpy), s_label, font=f_meta, fill=s_tx)
                    draw.text((tx + bw + bpx * 2 + 16, y + bpy),
                              f"deadline: {dl_str}", font=f_meta, fill=MUTED)
                y += bh + 8

                # Bir vazifa bir necha ishchiga tegishli bo'lsa — hammasini yozamiz
                if len(tw) > 1:
                    who = "Birga: " + ", ".join(w.name for w in tw)
                    for wl in _wrap(draw, who, f_meta, max_pw):
                        if do_draw:
                            draw.text((tx, y), wl, font=f_meta, fill=MUTED)
                        y += f_meta.size + 4
                    y += 2

                # Yengil ajratuvchi chiziq
                if do_draw:
                    draw.line([(tx, y), (W - PAD, y)], fill=LINE, width=1)
                y += 14
            y += 10
        y += 6

    # ── Yakuniy qator ──
    y += 6
    if total == 0:
        foot = "Hali vazifa qo'shilmagan."
    elif done == total:
        foot = "Hammasi bajarildi! Ajoyib ish!"
    else:
        foot = f"Yana {total - done} ta qoldi — davom etamiz!"
    if do_draw:
        draw.text((x, y), foot, font=f_foot, fill=MUTED)
    y += f_foot.size + PAD

    return y


def render_checklist_image(work_event, update_note=None, department=None):
    """WorkEvent uchun PNG rasm yasab, BytesIO qaytaradi.
    update_note berilsa — tepada "Yangilandi" banneri chiziladi.
    department berilsa — faqat o'sha bo'lim uchun rasm chiziladi.
    """
    _, sections = _grouped_tasks(work_event, department=department)
    fonts = (
        _font('DejaVuSans-Bold.ttf', 46),   # title
        _font('DejaVuSans.ttf', 26),        # date
        _font('DejaVuSans-Bold.ttf', 24),   # section
        _font('DejaVuSans.ttf', 30),        # task
        _font('DejaVuSans.ttf', 22),        # meta
        _font('DejaVuSans.ttf', 26),        # footer
    )

    # 1-o'tish: balandlikni o'lchaymiz
    measure_img = Image.new('RGB', (W, 10))
    height = int(_draw(ImageDraw.Draw(measure_img), work_event, sections, fonts,
                       do_draw=False, update_note=update_note))
    height = max(height, 200)

    # 2-o'tish: haqiqiy rasm
    img = Image.new('RGB', (W, height), BG)
    _draw(ImageDraw.Draw(img), work_event, sections, fonts,
          do_draw=True, update_note=update_note)

    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    buf.name = 'checklist.png'
    return buf
