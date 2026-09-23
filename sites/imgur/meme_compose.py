"""Compose a meme image (template + top/bottom text) with Pillow.

Used by the meme-generator flow: renders the classic impact-style caption
block on the chosen template and stores the composed image under
static/images/uploads/. Deterministic output for identical inputs.
"""
from __future__ import annotations

import hashlib
import os


def compose_meme(base_dir: str, template_rel: str, top_text: str, bottom_text: str) -> tuple[str, int, int]:
    from PIL import Image, ImageDraw, ImageFont

    template_path = os.path.join(base_dir, template_rel)
    with Image.open(template_path) as img:
        image = img.convert("RGB")
        width, height = image.size
        draw = ImageDraw.Draw(image)

        font_path = os.path.join(base_dir, "static", "icons", "fonts", "proxima-nova-bold.woff2")
        font_size = max(22, int(height / 12))
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        def render_line(text: str, y: int) -> None:
            if not text:
                return
            words = text.split()
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = (current + " " + word).strip()
                if draw.textlength(candidate, font=font) <= width * 0.92:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            cursor = y
            for line in lines:
                line_width = draw.textlength(line, font=font)
                x = max(2, (width - line_width) / 2)
                stroke = max(2, font_size // 14)
                draw.text((x, cursor), line, font=font, fill="#ffffff",
                          stroke_width=stroke, stroke_fill="#000000")
                cursor += font_size + 8

        render_line(top_text.upper(), int(height * 0.03))
        if bottom_text:
            dummy = draw.textbbox((0, 0), bottom_text.upper(), font=font)
            block_height = (dummy[3] - dummy[1]) + 12
            render_line(bottom_text.upper(), int(height - block_height - height * 0.05))

        digest = hashlib.sha256(
            f"{template_rel}|{top_text}|{bottom_text}".encode("utf-8")).hexdigest()[:12]
        upload_dir = os.path.join(base_dir, "instance", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        rel = f"instance/uploads/meme_{digest}.jpg"
        image.save(os.path.join(base_dir, rel), "JPEG", quality=88)
        return rel, width, height
