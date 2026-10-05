# gimp-cutout-wallpaper

[中文](#简介) | [English](#english)

## 简介

一个让 AI 编码助手（ZCode / Claude Code 等）把**单张人物插画变成动态壁纸**的完整流水线技能：

```
插画.jpg ──> GIMP 脚本化抠图拆层 ──> Wallpaper Engine 场景壁纸（头发摆动/眨眼/骨骼链）
```

- **GIMP 抠图**：GIMP 3.x 批处理（Script-Fu / Python-Fu）+ OpenCV 蒙版预计算，全自动拆出 背景/身体/头发段/眼睛 等图层
- **骨骼式动画**：foliagesway 权重风摆（蒙皮思想）、SceneScript 驱动 FK 骨骼链与眨眼、官方 Puppet Warp 工作流讲解
- **scene.json 手写模板**：图层/材质/特效/脚本接线全部有实测可运行的格式说明（从官方预览工程逆向验证）
- **命令行验证闭环**：`wallpaper64.exe -control openWallpaper` 应用壁纸 + 桌面截图目检迭代，全程不开 GUI

## 安装

```bash
git clone https://github.com/laoye666-6/gimp-cutout-wallpaper.git "$HOME/.agents/skills/gimp-cutout-wallpaper"
```

依赖：GIMP 3.x、Wallpaper Engine（Steam）、Python 3 + OpenCV/Pillow/numpy。

## 使用示例

- 「把这张初音图做成壁纸，头发随风摆、眼睛 3 秒一眨」
- 「用 GIMP 把人物抠出来分层，背景虚化」
- 「这个壁纸的头发摆动太僵了，调柔和一点」

## 目录结构

```
gimp-cutout-wallpaper/
├── SKILL.md                        # 流水线主文档
├── references/
│   ├── gimp-scripting.md           # GIMP 3.x 批处理 API + 抠图流程（含 2.10 差异）
│   └── scene-format.md             # WE scene.json / 内置特效 / SceneScript 格式
└── scripts/
    └── make_masks.py               # OpenCV 蒙版预计算模板
```

## English

A ZCode/Claude Code skill that turns a single character illustration into a live Wallpaper Engine scene wallpaper: GIMP 3.x scripted cutout into layers (background/body/hair segments/eyes), OpenCV-assisted masks, `foliagesway` weighted wind sway, SceneScript-driven blinking and FK bone chains, hand-authored `scene.json` (schema reverse-verified from official preview projects), and a full verify loop via `wallpaper64.exe -control openWallpaper` + desktop screenshots — zero GUI automation needed.

## 参考

- GIMP 官方文档：https://docs.gimp.org/3.2/en/
- Wallpaper Engine 设计文档：https://docs.wallpaperengine.io
- 配套技能：[wallpaper-engine-editor](https://github.com/laoye666-6/wallpaper-engine-editor)（WE 编辑器通用用法）

## License

[MIT](LICENSE)
