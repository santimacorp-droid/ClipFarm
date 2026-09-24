import sys
from pathlib import Path
from PyQt6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance()
if not app:
    app = QtWidgets.QApplication(sys.argv)

OUT_DIR = Path("/home/santima/.gemini/antigravity/brain/39b5e13b-a144-4a6d-8902-77a1d0ba7833")

def create_superellipse_path(rect, radius):
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path

# -------------------------------------------------------------
# ICON 1: "The Precision Sliced Play" (Ultra-Minimalist Tech)
# Pure geometric play button sliced with a razor-thin angle cut
# (representing video clipping), deep dark slate tile, electric gradient.
# -------------------------------------------------------------
def render_icon_sliced_play(size=1024):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    # 1. Dark Modern Background Squircle
    margin = size * 0.04
    tile_rect = QtCore.QRectF(margin, margin, size - 2*margin, size - 2*margin)
    corner_radius = size * 0.22
    tile_path = create_superellipse_path(tile_rect, corner_radius)

    # Background gradient
    bg_grad = QtGui.QLinearGradient(0, 0, size, size)
    bg_grad.setColorAt(0.0, QtGui.QColor("#13151f"))
    bg_grad.setColorAt(0.5, QtGui.QColor("#0d0e15"))
    bg_grad.setColorAt(1.0, QtGui.QColor("#090a0f"))
    painter.fillPath(tile_path, bg_grad)

    # Subtle inner border stroke
    pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 22), size * 0.008)
    painter.strokePath(tile_path, pen)

    # 2. Minimalist Sliced Play Icon
    # Center = (512, 512)
    # Piece 1: Left pillar / shear block
    p1 = QtGui.QPainterPath()
    p1.moveTo(330, 290)
    p1.lineTo(460, 290)
    p1.lineTo(410, 734)
    p1.lineTo(330, 734)
    p1.closeSubpath()

    # Piece 2: Forward play chevron
    p2 = QtGui.QPainterPath()
    p2.moveTo(490, 290)
    p2.lineTo(760, 512)
    p2.lineTo(440, 734)
    p2.closeSubpath()

    # Round the path corners slightly or draw clean
    # Primary electric gradient
    icon_grad = QtGui.QLinearGradient(300, 250, 780, 750)
    icon_grad.setColorAt(0.0, QtGui.QColor("#8B5CF6"))  # Electric Purple
    icon_grad.setColorAt(0.5, QtGui.QColor("#6366F1"))  # Indigo
    icon_grad.setColorAt(1.0, QtGui.QColor("#06B6D4"))  # Cyan Neon

    painter.fillPath(p1, icon_grad)
    painter.fillPath(p2, icon_grad)

    painter.end()
    image.save(str(OUT_DIR / "minimalist_sliced_play.png"))
    print("Rendered minimalist_sliced_play.png")

# -------------------------------------------------------------
# ICON 2: "The Minimalist Dual-Blade Play" (Linear / Figma Style)
# Two sleek overlapping curved geometric ribbons forming a play chevron
# Smooth ambient glow, crisp vector edges, pure modern digital asset.
# -------------------------------------------------------------
def render_icon_dual_ribbon(size=1024):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    # Dark background tile
    margin = size * 0.05
    tile_rect = QtCore.QRectF(margin, margin, size - 2*margin, size - 2*margin)
    corner_radius = size * 0.22
    tile_path = create_superellipse_path(tile_rect, corner_radius)

    bg_grad = QtGui.QLinearGradient(0, 0, 0, size)
    bg_grad.setColorAt(0.0, QtGui.QColor("#161824"))
    bg_grad.setColorAt(1.0, QtGui.QColor("#0a0b10"))
    painter.fillPath(tile_path, bg_grad)

    # Delicate top highlight on border
    border_pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 24), size * 0.008)
    painter.strokePath(tile_path, border_pen)

    # Back Ribbon (Left Vertical Blade)
    blade1 = QtGui.QPainterPath()
    blade1.moveTo(340, 310)
    blade1.cubicTo(370, 300, 420, 310, 440, 340)
    blade1.lineTo(440, 684)
    blade1.cubicTo(420, 714, 370, 724, 340, 714)
    blade1.cubicTo(320, 704, 320, 320, 340, 310)
    blade1.closeSubpath()

    grad1 = QtGui.QLinearGradient(320, 300, 440, 720)
    grad1.setColorAt(0.0, QtGui.QColor("#4F46E5"))
    grad1.setColorAt(1.0, QtGui.QColor("#7C3AED"))
    painter.fillPath(blade1, grad1)

    # Front Ribbon (Folding Chevron Blade)
    blade2 = QtGui.QPainterPath()
    blade2.moveTo(420, 340)
    blade2.cubicTo(430, 310, 470, 300, 500, 320)
    blade2.lineTo(740, 490)
    blade2.cubicTo(775, 512, 775, 532, 740, 554)
    blade2.lineTo(500, 724)
    blade2.cubicTo(470, 744, 430, 734, 420, 704)
    blade2.cubicTo(440, 670, 460, 640, 480, 610)
    blade2.lineTo(650, 522)
    blade2.lineTo(480, 410)
    blade2.cubicTo(460, 380, 440, 360, 420, 340)
    blade2.closeSubpath()

    grad2 = QtGui.QLinearGradient(400, 300, 770, 700)
    grad2.setColorAt(0.0, QtGui.QColor("#A855F7")) # Vivid Purple
    grad2.setColorAt(0.6, QtGui.QColor("#6366F1")) # Indigo
    grad2.setColorAt(1.0, QtGui.QColor("#06B6D4")) # Cyan
    painter.fillPath(blade2, grad2)

    painter.end()
    image.save(str(OUT_DIR / "minimalist_dual_ribbon.png"))
    print("Rendered minimalist_dual_ribbon.png")

# -------------------------------------------------------------
# ICON 3: "Minimalist Pure Glyph (Transparent, No Container)"
# Just the pure logo mark itself on transparent background,
# perfect for any dock or taskbar.
# -------------------------------------------------------------
def render_icon_pure_glyph(size=1024):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    # Stylized Minimalist Geometric Shear Mark
    # Outer play chevron
    path = QtGui.QPainterPath()
    # Left bar
    path.addRoundedRect(QtCore.QRectF(220, 220, 140, 584), 40, 40)
    
    # Forward play arrow
    arrow = QtGui.QPainterPath()
    arrow.moveTo(380, 230)
    arrow.lineTo(790, 490)
    arrow.cubicTo(825, 512, 825, 532, 790, 554)
    arrow.lineTo(380, 814)
    arrow.closeSubpath()

    grad = QtGui.QLinearGradient(200, 200, 820, 820)
    grad.setColorAt(0.0, QtGui.QColor("#A855F7"))
    grad.setColorAt(0.5, QtGui.QColor("#6366F1"))
    grad.setColorAt(1.0, QtGui.QColor("#06B6D4"))

    painter.fillPath(path, grad)
    painter.fillPath(arrow, grad)

    painter.end()
    image.save(str(OUT_DIR / "minimalist_pure_glyph.png"))
    print("Rendered minimalist_pure_glyph.png")

render_icon_sliced_play()
render_icon_dual_ribbon()
render_icon_pure_glyph()
