import sys
import math
from pathlib import Path
from PyQt6 import QtCore, QtGui, QtWidgets

app = QtWidgets.QApplication.instance()
if not app:
    app = QtWidgets.QApplication(sys.argv)

OUT_DIR = Path("/home/santima/.gemini/antigravity/brain/39b5e13b-a144-4a6d-8902-77a1d0ba7833")

def draw_squircle(painter, size, corner_radius=0.22, stroke_color=QtGui.QColor(255, 255, 255, 20)):
    margin = size * 0.04
    rect = QtCore.QRectF(margin, margin, size - 2*margin, size - 2*margin)
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, size * corner_radius, size * corner_radius)

    bg_grad = QtGui.QLinearGradient(0, margin, 0, size - margin)
    bg_grad.setColorAt(0.0, QtGui.QColor("#151722"))
    bg_grad.setColorAt(0.5, QtGui.QColor("#0f1017"))
    bg_grad.setColorAt(1.0, QtGui.QColor("#08090d"))
    painter.fillPath(path, bg_grad)

    pen = QtGui.QPen(stroke_color, size * 0.007)
    painter.strokePath(path, pen)
    return path

# -------------------------------------------------------------
# ICON 1: Precision Sliced Play (Masterpiece Minimalist)
# Equilateral play button with a clean 16px diagonal slice gap
# -------------------------------------------------------------
def render_sliced_play_pro(filename="icon_choice_1_sliced_play.png", transparent_bg=False):
    size = 1024
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    if not transparent_bg:
        draw_squircle(painter, size)

    # Full Play Triangle geometry:
    # Centered at (530, 512)
    # Left base: x = 320, top-left = (320, 272), bottom-left = (320, 752)
    # Tip: (736, 512)
    # Slice cut: Line from (445, 240) to (385, 780), width of gap = 28px
    
    # Left Segment:
    # top-left (320, 272) -> top-cut (425, 332) -> bottom-cut (375, 690) -> bottom-left (320, 752)
    p_left = QtGui.QPainterPath()
    p_left.moveTo(350, 272)
    p_left.cubicTo(330, 272, 320, 285, 320, 305)
    p_left.lineTo(320, 719)
    p_left.cubicTo(320, 739, 330, 752, 350, 752)
    p_left.cubicTo(362, 752, 372, 744, 382, 730)
    p_left.lineTo(440, 645)
    p_left.lineTo(440, 379)
    p_left.lineTo(382, 294)
    p_left.cubicTo(372, 280, 362, 272, 350, 272)
    p_left.closeSubpath()

    # Right Segment (Chevron Arrow):
    # Begins after 26px gap
    p_right = QtGui.QPainterPath()
    p_right.moveTo(475, 340)
    p_right.lineTo(725, 492)
    p_right.cubicTo(748, 506, 748, 524, 725, 538)
    p_right.lineTo(475, 690)
    p_right.cubicTo(462, 698, 450, 692, 450, 676)
    p_right.lineTo(450, 354)
    p_right.cubicTo(450, 338, 462, 332, 475, 340)
    p_right.closeSubpath()

    grad = QtGui.QLinearGradient(320, 270, 750, 750)
    grad.setColorAt(0.0, QtGui.QColor("#8B5CF6"))  # Vivid Purple
    grad.setColorAt(0.4, QtGui.QColor("#6366F1"))  # Indigo
    grad.setColorAt(0.85, QtGui.QColor("#06B6D4")) # Cyan
    grad.setColorAt(1.0, QtGui.QColor("#38BDF8"))  # Bright Sky

    painter.fillPath(p_left, grad)
    painter.fillPath(p_right, grad)

    painter.end()
    image.save(str(OUT_DIR / filename))
    print(f"Saved {filename}")

# -------------------------------------------------------------
# ICON 2: Sleek Geometric Ribbon Fold (Linear / Apple style)
# -------------------------------------------------------------
def render_modern_fold_pro(filename="icon_choice_2_modern_fold.png"):
    size = 1024
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_squircle(painter, size)

    # Base vertical pill
    pill = QtGui.QPainterPath()
    pill.addRoundedRect(QtCore.QRectF(310, 280, 130, 464), 40, 40)
    grad1 = QtGui.QLinearGradient(310, 280, 440, 744)
    grad1.setColorAt(0.0, QtGui.QColor("#4F46E5"))
    grad1.setColorAt(1.0, QtGui.QColor("#7C3AED"))
    painter.fillPath(pill, grad1)

    # Overlapping Play Chevron
    chev = QtGui.QPainterPath()
    chev.moveTo(395, 285)
    chev.cubicTo(412, 275, 435, 280, 452, 292)
    chev.lineTo(738, 492)
    chev.cubicTo(762, 508, 762, 526, 738, 542)
    chev.lineTo(452, 742)
    chev.cubicTo(435, 754, 412, 759, 395, 749)
    chev.lineTo(395, 638)
    chev.lineTo(600, 517)
    chev.lineTo(395, 396)
    chev.closeSubpath()

    grad2 = QtGui.QLinearGradient(395, 280, 760, 750)
    grad2.setColorAt(0.0, QtGui.QColor("#A855F7"))
    grad2.setColorAt(0.5, QtGui.QColor("#6366F1"))
    grad2.setColorAt(1.0, QtGui.QColor("#06B6D4"))
    painter.fillPath(chev, grad2)

    painter.end()
    image.save(str(OUT_DIR / filename))
    print(f"Saved {filename}")

# -------------------------------------------------------------
# ICON 3: Minimalist Film-Notch Play (DaVinci / CapCut style)
# Symmetrical play triangle with two clean film sprocket notches
# -------------------------------------------------------------
def render_film_notch_play(filename="icon_choice_3_film_notch.png"):
    size = 1024
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

    draw_squircle(painter, size)

    # Master Play Triangle with rounded corners
    path = QtGui.QPainterPath()
    # Left edge with 2 notch cutouts
    # We define outer triangle and subtract notches
    tri = QtGui.QPainterPath()
    tri.moveTo(330, 310)
    tri.cubicTo(330, 285, 355, 270, 378, 282)
    tri.lineTo(745, 494)
    tri.cubicTo(768, 507, 768, 527, 745, 540)
    tri.lineTo(378, 752)
    tri.cubicTo(355, 764, 330, 749, 330, 724)
    tri.closeSubpath()

    # Notches
    notch1 = QtGui.QPainterPath()
    notch1.addRoundedRect(QtCore.QRectF(300, 370, 70, 50), 12, 12)
    notch2 = QtGui.QPainterPath()
    notch2.addRoundedRect(QtCore.QRectF(300, 487, 70, 50), 12, 12)
    notch3 = QtGui.QPainterPath()
    notch3.addRoundedRect(QtCore.QRectF(300, 604, 70, 50), 12, 12)

    final_shape = tri.subtracted(notch1).subtracted(notch2).subtracted(notch3)

    grad = QtGui.QLinearGradient(330, 270, 770, 760)
    grad.setColorAt(0.0, QtGui.QColor("#9333EA"))
    grad.setColorAt(0.5, QtGui.QColor("#4F46E5"))
    grad.setColorAt(1.0, QtGui.QColor("#06B6D4"))

    painter.fillPath(final_shape, grad)

    painter.end()
    image.save(str(OUT_DIR / filename))
    print(f"Saved {filename}")

# Render options
render_sliced_play_pro("icon_choice_1_sliced_play.png")
render_modern_fold_pro("icon_choice_2_modern_fold.png")
render_film_notch_play("icon_choice_3_film_notch.png")
render_sliced_play_pro("icon_choice_1_pure_glyph.png", transparent_bg=True)
