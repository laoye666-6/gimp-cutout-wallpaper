#!/usr/bin/env python3
"""Generate grayscale cutout masks for the GIMP cutout pipeline.

Usage: python make_masks.py <input.jpg> <out_dir> [--cuda]
Outputs <out_dir>/mask_<name>.png (white = keep). Always render a preview
overlay (<name>_preview.jpg) and visually inspect it before proceeding.

Adapt the COLOR RANGES below per artwork; use cv2.GrabCut for large
subjects where color alone is ambiguous.
"""
import sys, os
import cv2
import numpy as np


def color_mask(img_bgr, lo, hi, close_k=7):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array(lo), np.array(hi))
    k = np.ones((close_k, close_k), np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)


def grabcut_mask(img_bgr, rect, iters=5):
    m = np.zeros(img_bgr.shape[:2], np.uint8)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img_bgr, m, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    return np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)


def preview(img_bgr, mask, path):
    ov = img_bgr.copy()
    ov[mask == 0] = (ov[mask == 0] * 0.35).astype(np.uint8)
    cv2.imwrite(path, ov)


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    img = cv2.imread(src)
    # ---- EDIT PER ARTWORK --------------------------------------------------
    masks = {
        # "hair": color_mask(img, (80, 40, 20), (140, 255, 255)),
        # "body": grabcut_mask(img, (x0, y0, w, h)),
    }
    for name, m in masks.items():
        cv2.imwrite(os.path.join(out, f"mask_{name}.png"), m)
        preview(img, m, os.path.join(out, f"{name}_preview.jpg"))
        print("wrote mask_" + name)
