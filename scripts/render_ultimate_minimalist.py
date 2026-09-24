import sys
import math
from pathlib import Path
from PyQt6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance()
if not app:
    app = QtWidgets.QApplication(sys.argv)

OUT_DIR = Path("/home/santima/.gemini/antigravity/brain/39b5e13b-a144-4a6d-8902-77a1d0ba7833")

def draw_clean_tile(painter, size=1024):
    # Pure dark modern squircle, zero photo lighting, zero desk shadow
    margin = size * 0.04
    rect = QtCore.QRectF(margin, margin, size - 2*margin, size - 2*margin)
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, size * 0.22, size * 0.22)
    
    # Flat / micro-gradient dark slate
    grad = QtGui.QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QtGui.QColor("#13151f"))
    grad.setColorAt(1.0, QtGui.QColor("#0a0b10"))
    painter.fillPath(path, grad)
    
    # Crisp 1.5px subtle border
    pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 18), size * 0.006)
    painter.strokePath(path, pen)
    return path

# -------------------------------------------------------------------------
# ICON M1: "The Pure Vector Prism Play"
# Recreating the exact motif of the user's favored shape,
# but as a pure, minimalist, crisp vector design (Zero photo artifacts!)
# -------------------------------------------------------------------------
def render_m1_prism_vector(size=1024):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_clean_tile(painter, size)

    # Component 1: Left Back Pillar (curved, sleek, deep violet/indigo)
    p_back = QtGui.QPainterPath()
    p_back.moveTo(370, 310)
    p_back.cubicTo(400, 310, 420, 335, 420, 370)
    p_back.lineTo(420, 654)
    p_back.cubicTo(420, 689, 400, 714, 370, 714)
    p_back.cubicTo(340, 714, 320, 689, 320, 654)
    p_back.lineTo(320, 370)
    p_back.cubicTo(320, 335, 340, 310, 370, 310)
    p_back.closeSubpath()

    grad_back = QtGui.QLinearGradient(320, 310, 420, 714)
    grad_back.setColorAt(0.0, QtGui.QColor("#4F46E5")) # Indigo
    grad_back.setColorAt(1.0, QtGui.QColor("#7C3AED")) # Violet
    painter.fillPath(p_back, grad_back)

    # Component 2: Upper Folding Ribbon (translucent bright cyan-to-violet)
    p_top = QtGui.QPainterPath()
    p_top.moveTo(375, 310)
    p_top.cubicTo(410, 310, 440, 330, 460, 360)
    p_top.lineTo(725, 495)
    p_top.cubicTo(755, 510, 755, 520, 725, 535)
    p_top.lineTo(540, 535)
    p_top.lineTo(400, 420)
    p_top.cubicTo(380, 400, 360, 370, 360, 340)
    p_top.cubicTo(360, 320, 365, 310, 375, 310)
    p_top.closeSubpath()

    grad_top = QtGui.QLinearGradient(360, 310, 750, 535)
    grad_top.setColorAt(0.0, QtGui.QColor("#C084FC")) # Light purple
    grad_top.setColorAt(0.5, QtGui.QColor("#818CF8")) # Indigo
    grad_top.setColorAt(1.0, QtGui.QColor("#38BDF8")) # Cyan
    painter.fillPath(p_top, grad_top)

    # Component 3: Lower Folding Ribbon
    p_bottom = QtGui.QPainterPath()
    p_bottom.moveTo(725, 520)
    p_bottom.lineTo(460, 664)
    p_bottom.cubicTo(430, 680, 395, 680, 370, 660)
    p_bottom.cubicTo(350, 640, 360, 615, 380, 600)
    p_bottom.lineTo(540, 520)
    p_bottom.closeSubpath()

    grad_bottom = QtGui.QLinearGradient(370, 660, 725, 520)
    grad_bottom.setColorAt(0.0, QtGui.QColor("#A855F7"))
    grad_bottom.setColorAt(1.0, QtGui.QColor("#06B6D4"))
    painter.fillPath(p_bottom, grad_bottom)

    painter.end()
    image.save(str(OUT_DIR / "m1_prism_vector.png"))
    print("Saved m1_prism_vector.png")

# -------------------------------------------------------------------------
# ICON M2: "The Razor Play" (Ultra-Minimalist Apple/Linear)
# A bold equilateral play button with smooth 32px rounded corners,
# cleanly sliced diagonally with an offset negative space gap.
# -------------------------------------------------------------------------
def render_m2_razor_play(size=1024):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_clean_tile(painter, size)

    # Triangle dimensions:
    # Centered at (525, 512)
    # Height = 480, Width = 430
    # Left base = 315, Right tip = 745
    # Diagonal cut line from (480, 220) to (390, 800)
    
    # Left slice:
    p_l = QtGui.QPainterPath()
    p_l.moveTo(355, 272)
    p_l.cubicTo(330, 272, 315, 290, 315, 315)
    p_l.lineTo(315, 709)
    p_l.cubicTo(315, 734, 330, 752, 355, 752)
    p_l.cubicTo(370, 752, 385, 742, 395, 725)
    p_l.lineTo(440, 642)
    p_l.lineTo(440, 382)
    p_l.lineTo(395, 299)
    p_l.cubicTo(385, 282, 370, 272, 355, 272)
    p_l.closeSubpath()

    # Right slice (tip chevron):
    p_r = QtGui.QPainterPath()
    p_r.moveTo(480, 342)
    p_r.lineTo(720, 492)
    p_r.cubicTo(745, 508, 745, 526, 720, 542)
    p_r.lineTo(480, 692)
    p_r.cubicTo(462, 702, 448, 695, 448, 675)
    p_r.lineTo(448, 359)
    p_r.cubicTo(448, 339, 462, 332, 480, 342)
    p_r.closeSubpath()

    grad = QtGui.QLinearGradient(315, 270, 745, 750)
    grad.setColorAt(0.0, QtGui.QColor("#8B5CF6")) # Violet
    grad.setColorAt(0.5, QtGui.QColor("#6366F1")) # Indigo
    grad.setColorAt(1.0, QtGui.QColor("#06B6D4")) # Cyan
    
    painter.fillPath(p_l, grad)
    painter.fillPath(p_r, grad)

    painter.end()
    image.save(str(OUT_DIR / "m2_razor_play.png"))
    print("Saved m2_razor_play.png")

# -------------------------------------------------------------------------
# ICON M3: "The Minimalist Loop / Clip Aperture"
# A sleek continuous single-path ribbon that twists into a play glyph
# -------------------------------------------------------------------------
def render_m3_ribbon_loop(size=1024):
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_clean_tile(painter, size)

    # Master thick stroke path
    path = QtGui.QPainterPath()
    path.moveTo(360, 710)
    path.lineTo(360, 330)
    path.cubicTo(360, 290, 400, 270, 435, 290)
    path.lineTo(730, 485)
    path.cubicTo(760, 505, 760, 525, 730, 545)
    path.lineTo(435, 740)
    path.cubicTo(400, 760, 360, 740, 360, 710)
    path.closeSubpath()

    grad = QtGui.QLinearGradient(340, 270, 760, 760)
    grad.setColorAt(0.0, QtGui.QColor("#A855F7"))
    grad.setColorAt(0.5, QtGui.QColor("#6366F1"))
    grad.setColorAt(1.0, QtGui.QColor("#06B6D4"))

    pen = QtGui.QPen(grad, 80, QtCore.Qt.PenStyle.SolidLine, QtCore.Qt.PenCapStyle.RoundCap, QtCore.Qt.PenJoinStyle.RoundJoin)
    painter.strokePath(path, pen)

    painter.end()
    image.save(str(OUT_DIR / "m3_ribbon_loop.png"))
    print("Saved m3_ribbon_loop.png")

render_m1_prism_vector()
render_m2_razor_play()
render_m3_ribbon_loop()
