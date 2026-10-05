---
name: gimp-cutout-wallpaper
description: 用 GIMP 抠图拆层 + Wallpaper Engine 场景/骨骼动画制作人物动态壁纸的完整流水线：GIMP 脚本化抠图拆分图层（头发/眼睛/身体/背景）、foliagesway 权重摆动、SceneScript 驱动眨眼与骨骼链、scene.json 手写模板、openWallpaper 命令行应用与截图验证。当用户想把插画/动漫图做成会动的壁纸（头发摆动、眨眼、分层视差）、提到 GIMP 抠图、分层壁纸、骨骼动画、Puppet Warp、Wallpaper Engine 场景壁纸时使用。
---

# GIMP 抠图 + Wallpaper Engine 骨骼动画动态壁纸

把一张人物插画变成"活的"：**GIMP 拆层 → 场景分层合成 → 骨骼式摆动 + 眨眼**。全程脚本化，无需 GUI 操作。

## 流水线总览

```
原图.jpg ──GIMP 批处理抠图──> layers/ (背景/身体/头发段/眼睛×2, PNG+alpha)
         ──组装──> myprojects/<项目>/{project.json, scene.json, models/, materials/, scripts/}
         ──验证──> wallpaper64.exe -control openWallpaper → 桌面截图 → 迭代
```

## 第一步：环境探测

```bash
# GIMP（3.x 与 2.10 的 API 不同，见 references/gimp-scripting.md）
ls "D:/Program/GIMP/bin/gimp-console-3.2.exe"   # 或注册表 HKLM\...\Uninstall\GIMP-* 查 InstallLocation
# Wallpaper Engine：先 reg query "HKCU\Software\Valve\Steam" //v SteamPath，再遍历 libraryfolders.vdf
# 项目目录 = <steam>/steamapps/common/wallpaper_engine/projects/myprojects/
# 主程序 = wallpaper_engine/wallpaper64.exe（注意在根目录不在 bin/）
python -c "import cv2, numpy, PIL"   # 辅助抠图库
```

## 第二步：GIMP 拆层（→ [references/gimp-scripting.md](references/gimp-scripting.md)）

关键规则：**GIMP 3 批处理必须加 `--batch-interpreter=plug-in-script-fu-eval`**，否则静默不执行。

1. 精确蒙版用 Python（cv2 颜色阈值 + GrabCut）预计算成灰度 PNG（本 skill 的 `scripts/make_masks.py` 模板）。
2. 用 GIMP 完成抠图本体：加载蒙版 → 选区 → 羽化 → 剪切为图层 → 导出带 alpha 的 PNG。核心 Script-Fu 流程见 reference。
3. **分层方案**（人物动态壁纸标准五/七层）：
   - `background` 整图（人物区域 inpaint 修掉，露出后面）
   - `body` 人物（不含摆动件；脸部挖掉眼睛区域）
   - 摆动件按"关节"切段：双马尾 = 上段（贴头）+ 下段（发梢），各带羽化边缘
   - `eyes_open` 睁眼贴片 + `eyes_closed` 闭眼贴片（把睁眼图纵向压扁 15% 即成闭眼）
4. 每层导出后**用 Read 工具目检 PNG**，边缘有 halo/缺块就回头调阈值重跑。

## 第三步：组装 scene.json（→ [references/scene-format.md](references/scene-format.md)）

scene.json 可手写（**本 skill 全流程实测跑通**）。坐标体系：`orthogonalprojection` 定义世界像素尺寸；**origin=图层中心，x 同屏幕像素，y 需翻转（world_y = H - 屏幕y）**——可用纯色标记块对照实验校准。图层 = models/*.json(→materials/*.json→图片) 三层嵌套；**骨骼式动画不用 Puppet Warp 也能做**：

- **摆动**：摆动层挂 `effects/foliagesway/effect.json`（内置风场效果，cornerweights 底锚顶摆 = 蒙皮权重思想），每段 `constantshadervalues` 里调 Speed/Strength/Phase/Power。
- **骨骼链**：每段一个对象，origin 设在"关节"，用 SceneScript 按相位差旋转（FK 链）。swing/foliagesway 二选一或叠加。
- **眨眼**：eyes_open/eyes_closed 两层 alpha 用内联 SceneScript 切换（3 秒周期、约 150ms 闭眼），脚本走 `"alpha": {"script": "..."}`。
- 真正的 Puppet Warp（GUI 画骨）工作流也写在 reference 里，供用户手动进阶。

## 第四步：应用与验证

```bash
"<WE>/wallpaper64.exe" -control openWallpaper -file "<项目>/project.json"
# WE 必须已在运行；未运行则先启动 launcher.exe 等待再发命令
```
然后用计算机截图工具截取桌面，目检动画/分层是否正确，迭代修正。改完 scene.json 重发 openWallpaper 即可热替换。

## 开发原则

1. 项目放 `<WE>/projects/myprojects/<项目名>/`，命名用 ASCII 更稳（中文实测也可用，但引号转义易错）。
2. 未发布的工程直接读 materials/ 下的 jpg/png 源文件（.tex 是发布编译产物，不用管）。
3. 大图先降采样（单边 ≤4096，一般 2560×1440 或 3840×2160），纹理超上限会黑屏。
4. 动画参数（摆动幅度/速度/眨眼时刻）全部做成 scene.json 可调数值，截图对比迭代，不要猜一次就定稿。
