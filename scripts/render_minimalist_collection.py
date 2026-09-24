import sys
import math
from pathlib import Path
from PyQt6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance()
if not app:
    app = QtWidgets.QApplication(sys.argv)

OUT_DIR = Path("/home/santima/.gemini/antigravity/brain/39b5e13b-a144-4a6d-8902-77a1d0ba7833")

def draw_squircle_tile(painter, size, bg_top="#141622", bg_bottom="#090a0f"):
    margin = size * 0.04
    rect = QtCore.QRectF(margin, margin, size - 2*margin, size - 2*margin)
    radius = size * 0.224
    
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    
    grad = QtGui.QLinearGradient(0, margin, 0, size - margin)
    grad.setColorAt(0.0, QtGui.QColor(bg_top))
    grad.setColorAt(1.0, QtGui.QColor(bg_bottom))
    painter.fillPath(path, grad)
    
    # 1px crisp subtle highlight border
    pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 20), size * 0.007)
    painter.strokePath(path, pen)
    return path

# ------------------------------------------------------------------
# Concept 1: The Sliced Play (The quintessential video clip icon)
# Perfectly balanced play triangle with an angled negative-space cut
# representing the razor-sharp video clip action.
# ------------------------------------------------------------------
def render_sliced_play(filename="minimalist_1_sliced_play.png", with_squircle=True):
    size = 1024
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    if with_squircle:
        draw_squircle_tile(painter, size)

    # Coordinates for Play Triangle:
    # Centered around (525, 512)
    # Left base x=330, Top-left y=270, Bottom-left y=754, Right tip x=745, y=512
    # Sliced by an angled line at slope
    
    # Segment 1: Left Anchor Blade
    p1 = QtGui.QPainterPath()
    p1.moveTo(330, 290)
    p1.cubicTo(330, 270, 350, 260, 365, 270)
    p1.lineTo(470, 340)
    p1.lineTo(415, 730)
    p1.lineTo(350, 750)
    p1.cubicTo(330, 755, 330, 740, 330, 720)
    p1.closeSubpath()

    # Segment 2: Dynamic Right Chevron
    p2 = QtGui.QPainterPath()
    p2.moveTo(505, 360)
    p2.lineTo(725, 495)
    p2.cubicTo(748, 508, 748, 526, 725, 539)
    p2.lineTo(445, 715)
    p2.lineTo(495, 370)
    p2.closeSubpath()

    grad = QtGui.QLinearGradient(330, 260, 750, 750)
    grad.setColorAt(0.0, QtGui.QColor("#8B5CF6"))  # Violet
    grad.setColorAt(0.45, QtGui.QColor("#6366F1")) # Indigo
    grad.setColorAt(1.0, QtGui.QColor("#06B6D4"))  # Cyan

    painter.fillPath(p1, grad)
    painter.fillPath(p2, grad)

    painter.end()
    image.save(str(OUT_DIR / filename))
    print(f"Saved {filename}")

# ------------------------------------------------------------------
# Concept 2: The Modern Fold (Geometric Origami / Linear style)
# Sleek, minimalist folding planes with subtle depth and clean geometry.
# ------------------------------------------------------------------
def render_modern_fold(filename="minimalist_2_modern_fold.png"):
    size = 1024
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_squircle_tile(painter, size)

    # Left vertical blade (darker violet/indigo)
    blade1 = QtGui.QPainterPath()
    blade1.addRoundedRect(QtCore.QRectF(315, 270, 130, 484), 36, 36)
    grad1 = QtGui.QLinearGradient(315, 270, 445, 754)
    grad1.setColorAt(0.0, QtGui.QColor("#4F46E5"))
    grad1.setColorAt(1.0, QtGui.QColor("#7C3AED"))
    painter.fillPath(blade1, grad1)

    # Forward Play Chevron (overlapping, bright neon gradient)
    blade2 = QtGui.QPainterPath()
    blade2.moveTo(400, 275)
    blade2.cubicTo(415, 265, 440, 270, 455, 282)
    blade2.lineTo(745, 492)
    blade2.cubicTo(770, 508, 770, 526, 745, 542)
    blade2.lineTo(455, 752)
    blade2.cubicTo(440, 764, 415, 769, 400, 759)
    blade2.lineTo(400, 640)
    blade2.lineTo(605, 517)
    blade2.lineTo(400, 394)
    blade2.closeSubpath()

    grad2 = QtGui.QLinearGradient(400, 270, 770, 760)
    grad2.setColorAt(0.0, QtGui.QColor("#C084FC")) # Lavender
    grad2.setColorAt(0.4, QtGui.QColor("#818CF8")) # Indigo neon
    grad2.setColorAt(1.0, QtGui.QColor("#38BDF8")) # Sky cyan
    painter.fillPath(blade2, grad2)

    painter.end()
    image.save(str(OUT_DIR / filename))
    print(f"Saved {filename}")

# ------------------------------------------------------------------
# Concept 3: The Minimalist Aperture / Clip Blade (Raycast / Figma style)
# Two sleek precision curved geometric elements forming a play triangle
# ------------------------------------------------------------------
def render_minimalist_aperture(filename="minimalist_3_aperture.png"):
    size = 1024
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_squircle_tile(painter, size)

    # Upper Blade
    p_up = QtGui.QPainterPath()
    p_up.moveTo(330, 290)
    p_up.cubicTo(330, 270, 355, 260, 375, 272)
    p_up.lineTo(740, 495)
    p_up.cubicTo(760, 507, 760, 527, 740, 539)
    p_up.lineTo(580, 539)
    p_up.lineTo(330, 390)
    p_up.closeSubpath()

    # Lower Blade
    p_down = QtGui.QPainterPath()
    p_down.moveTo(330, 425)
    p_down.lineTo(540, 555)
    p_down.lineTo(410, 735)
    p_down.cubicTo(395, 755, 365, 760, 345, 745)
    p_down.cubicTo(330, 730, 330, 710, 330, 690)
    p_down.closeSubpath()

    grad_up = QtGui.QLinearGradient(330, 260, 760, 540)
    grad_up.setColorAt(0.0, QtGui.QColor("#A855F7"))
    grad_up.setColorAt(1.0, QtGui.QColor("#06B6D4"))

    grad_down = QtGui.QLinearGradient(330, 420, 540, 750)
    grad_down.setColorAt(0.0, QtGui.QColor("#6366F1"))
    grad_down.setColorAt(1.0, QtGui.QColor("#3B82F6"))

    painter.fillPath(p_up, grad_up)
    painter.fillPath(p_down, grad_down)

    painter.end()
    image.save(str(OUT_DIR / filename))
    print(f"Saved {filename}")

# Concept 4: Pure Glyph (No Squircle) for Desktop/Dock
render_sliced_play("minimalist_4_pure_glyph.png", with_squircle=False)

render_sliced_play()
render_modern_fold()
render_minimalist_aperture()
