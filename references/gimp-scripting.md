# GIMP 3.x 脚本化抠图参考

官方文档：https://docs.gimp.org/3.2/en/ （Script-Fu 教程、批处理章节）；完整 PDB 可在 GIMP 内导出：
`gimp-console-3.2.exe -n -i --batch-interpreter=python-fu-eval -b "from gi.repository import Gimp, Gio; Gimp.get_pdb().dump_to_file(Gio.File.new_for_path('pdb.txt'))"`

## 批处理调用（最容易踩的坑）

```bash
# ✅ 正确：必须显式指定解释器，否则 -b 静默不执行
gimp-console-3.2.exe -n -i --batch-interpreter=plug-in-script-fu-eval \
  -b '(你的script-fu)' -b '(gimp-quit 0)'

# Python-Fu（GIMP 3 内置 Python3 + GObject Introspection），注意退出也要 Python 语法
gimp-console-3.2.exe -n -i --batch-interpreter=python-fu-eval \
  -b 'from gi.repository import Gimp; ...; Gimp.quit(False)'

# 常用 flag：-n 新实例  -i 无界面  -d 不加载数据(画笔等,更快)  -f 不加载字体
```

复杂脚本写进 `.scm` 文件再 `-b '(load "C:/path/script.scm")'`，避免命令行引号地狱。

## GIMP 3 相对 2.10 的 API 变化（实测 3.2.6）

| 用途 | GIMP 3.2 签名（PDB 实测） |
|---|---|
| 加载图像 | `(gimp-file-load RUN-NONINTERACTIVE "path.jpg")` → 返回 image |
| 连续选区(魔棒) | `(gimp-image-select-contiguous-color image OPERATION drawable x y)` |
| 按颜色选区 | `(gimp-image-select-color image OPERATION drawable color)` |
| 阈值/合并采样 | `(gimp-context-set-sample-threshold-int 60)`、`(gimp-context-set-sample-merged TRUE)` |
| 选区操作 | `(gimp-selection-grow image 2)` / `(gimp-selection-feather image 3)` / `(gimp-selection-invert image)` / `(gimp-selection-translate image dx dy)` / `(gimp-selection-none image)` |
| 新建图层 | `(gimp-layer-new image "name" w h RGBA-IMAGE 100 LAYER-MODE-NORMAL)` |
| 插入图层 | `(gimp-image-insert-layer image layer parent position)` position=-1 在最上 |
| 剪切 | `(gimp-edit-cut drawable)`（3.0 参数是 drawables 列表，单个也可） |
| 图层蒙版 | `(gimp-layer-create-mask layer ADD-MASK-WHITE)` → `(gimp-layer-add-mask layer mask)` |
| 选区转蒙版内容 | 选中状态下对蒙版执行 `(gimp-edit-fill mask FILL-WHITE)` 前先 `(gimp-image-select-item image CHANNEL-OP-REPLACE mask)` 反向操作；常用做法：把灰度蒙版 PNG 作为图层载入 → 全选复制 → 粘贴进 mask |
| 导出 PNG | `(file-png-export RUN-NONINTERACTIVE image "out.png" #f 0 9 1 1 1 1 1 0 #f #f #f #f #f #f "")`（3.0 由 file-png-save 改名，第4参 options 传 #f） |
| 选中图层 | `(gimp-image-set-selected-layers image (list layer))` |
| 合并/压平 | `(gimp-image-merge-visible-layers image CLIP-TO-IMAGE)` / `(gimp-image-flatten image)` |
| Script-Fu 输出 | 3.2 无 `print`，用 `(display x)` `(newline)`；`(gimp-message "...")` 走消息通道 |

颜色常量：`'(r g b)` 列表；操作常量：`CHANNEL-OP-REPLACE/ADD/SUBTRACT/INTERSECT`、`SELECT-REPLACE`? 用 `CHANNEL-OP-*` 稳。FILL-WHITE / FILL-FOREGROUND。`ADD-MASK-WHITE`（白=全显）。

## 标准抠图流水线（AI 可全自动）

### A. 预计算精确蒙版（Python，不进 GIMP）

纯靠 GIMP 颜色选区抠复杂人物不够准，用 cv2 先算 mask（灰度 PNG：白=保留）：

```python
import cv2, numpy as np
img = cv2.imread("input.jpg")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
# 例：深色头发 vs 亮背景 —— 按目标色域做 inRange，配合形态学闭运算
mask = cv2.inRange(hsv, (80, 40, 20), (140, 255, 255))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7,7), np.uint8))
# 大区域人物可用 GrabCut 打底：init rect + iterate，再与颜色掩码求并/差
cv2.imwrite("mask_hair.png", mask)
```
**每一轮蒙版都要导出可视化小图（把 mask 叠在原图上）用 Read 目检**，调阈值直到干净。

### B. GIMP 内应用蒙版 → 拆层导出（script-fu 骨架）

```scheme
(let* ((image (car (gimp-file-load RUN-NONINTERACTIVE "C:/in.jpg")))
       (bg (car (gimp-image-get-selected-layers image)))   ; 底层
       (w (car (gimp-image-get-width image)))              ; 3.0 是 get-width（2.10 是 width）
       (h (car (gimp-image-get-height image))))
  ;; 1) 以"头发层"为例：新建透明层放最上
  (let* ((hair (car (gimp-layer-new image "hair" w h RGBA-IMAGE 100 LAYER-MODE-NORMAL))))
    (gimp-image-insert-layer image hair -1? -1)  ; parent 用 0/-1 视版本，实测填 0 顶层
    (gimp-image-set-selected-layers image (list hair))
    ;; 2) 载入灰度蒙版 PNG 成图层，选择其不透明区域
    (let* ((mimg (car (gimp-file-load RUN-NONINTERACTIVE "C:/mask_hair.png")))
           (mlayer (car (gimp-image-get-selected-layers mimg))))
      (gimp-image-select-item image CHANNEL-OP-REPLACE mlayer)
      ;; 3) 复制原图对应区域到 hair 层：激活原图层 copy，再 paste 到 hair
      (gimp-image-set-selected-layers image (list bg))
      (gimp-edit-copy (list bg))
      (let ((float (car (gimp-edit-paste hair TRUE))))
        (gimp-floating-sel-anchor float)))
    ;; 4) 羽化边缘更自然：重做选区时先 feather
    ;; 5) 导出
    (file-png-export RUN-NONINTERACTIVE image "C:/out_hair.png" #f 0 9 1 1 1 1 1 0 #f #f #f #f #f #f "")))
(gimp-quit 0)
```

> 注意：`gimp-edit-copy` 复制的是**选区内**的激活图层像素；粘贴目标决定归属。粘贴产生 floating selection，anchor 到目标层。
> 导出整图前用 `(gimp-image-set-selected-layers ...)` 只留目标层可见 + `file-png-export` 的 `save-transparent`；更稳的做法是每层单独 new image（复制选区→粘贴到新 image→flatten 到 alpha）导出。

### C. GIMP GUI 交互抠图（指导用户手动用）

- **前景选择工具（Foreground Select）**：画粗框 → 涂蓝色标前景 → 涂红色标背景 → 回车，矩阵算法抠图，抠人物最好用。
- **按颜色选择/模糊选择**：调"阈值"滑块，勾"合并采样"跨层取色。
- 选区菜单：选择→增长/收缩/羽化；选择→保存为通道（可复用）。
- 图层面板右键→"添加图层蒙版"→"选区"，选区直接变蒙版。

## 常见失败

- `-b` 不执行 → 忘了 `--batch-interpreter`。
- `unbound variable` → GIMP 3 改名了（width→get-width、file-png-save→file-png-export、print 没了）。
- 中文路径偶尔让 script-fu 崩 → 传 ASCII 临时路径最稳。
- gimp-console 启动 10-60s 正常（首次建字体缓存更久），别误判卡死。
