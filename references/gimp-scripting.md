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
| 导出 PNG | `(gimp-file-save RUN-NONINTERACTIVE image "out.png" #f)`（**推荐**；`file-png-export` 参数类型苛刻易翻车） |
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

### B. GIMP 内应用蒙版 → 拆层导出（script-fu 骨架，**实战调试通过的版本**）

**关键坑（全部实测踩过）**：
1. **蒙版 PNG 必须转成"白色 + alpha=灰度值"的 RGBA**——`gimp-image-select-item` 按**图层 alpha** 选区，灰度 JPEG/PNG 无 alpha 时选区=全图！
   ```python
   rgba = np.zeros((*m.shape, 4), np.uint8); rgba[:,:,:3] = 255; rgba[:,:,3] = m
   cv2.imwrite("sel_mask.png", rgba)
   ```
2. **源层要先 `(gimp-layer-add-alpha base)`**，否则 JPG 源复制出的新图无 alpha（透明区变白底）。
3. GIMP 3 的 PDB 数组参数要 **vector**：`(gimp-image-set-selected-layers image (vector base))`、`(gimp-edit-copy (vector base))`；而 `gimp-image-get-selected-layers` 返回嵌套 vector，取第一层用 `(vector-ref (car (gimp-image-get-selected-layers image)) 0)`。
4. `(gimp-edit-paste-as-new-image)` 返回裁剪到选区 bbox 的新图像（自带 alpha，前提见坑 2）。

```scheme
(define (cut-layer src maskpath outpath)
  (let* ((image (car (gimp-file-load RUN-NONINTERACTIVE src)))
         (base (vector-ref (car (gimp-image-get-selected-layers image)) 0))
         (mlayer (car (gimp-file-load-layer RUN-NONINTERACTIVE image maskpath))))
    (gimp-layer-add-alpha base)
    (gimp-image-insert-layer image mlayer 0 -1)
    (gimp-context-set-feather TRUE)
    (gimp-context-set-feather-radius 2 2)          ; 选区羽化=边缘软化
    (gimp-image-select-item image CHANNEL-OP-REPLACE mlayer)
    (gimp-image-set-selected-layers image (vector base))
    (gimp-edit-copy (vector base))
    (let ((newimg (car (gimp-edit-paste-as-new-image))))
      (gimp-file-save RUN-NONINTERACTIVE newimg outpath #f)
      (gimp-image-delete newimg))
    (gimp-selection-none image)
    (gimp-image-remove-layer image mlayer)
    (gimp-image-delete image)
    (display (string-append "cut " outpath)) (newline)))
;; 多层循环调用后 (gimp-quit 0)
```
> 蒙版如有杂散小像素（<1000px 连通域），先在 Python 里清掉，否则 paste-as-new-image 的 bbox 会被撑到全画布。
> 段间接缝：GIMP 导出后用 Python 对各段 alpha 做重叠带线性渐变（如段1在 y300→332 渐隐、段2在 y298→330 渐显），静态合成无缝。

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
