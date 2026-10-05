# Wallpaper Engine scene.json 场景格式与动画参考

来源：官方文档 docs.wallpaperengine.io + 本机安装目录逆向验证（assets/effects/*/preview/scene.json 为官方真实范例）。

## 项目结构

```
myprojects/<项目>/
├── project.json          # {"file":"scene.json","title":"...","general":{"properties":{...}}}
├── scene.json            # 场景本体
├── models/<层名>.json    # {"autosize":true,"material":"materials/<层名>.json"}
├── materials/<层名>.json # {"passes":[{"shader":"genericimage4","blending":"translucent",
│                         #   "depthtest":"disabled","depthwrite":"disabled","cullmode":"nocull",
│                         #   "textures":["<层名>"]}]}
├── materials/<层名>.png  # 图片本体（未发布工程直接读源图；.tex 是发布编译产物）
└── scripts/*.js          # SceneScript（可选）
```

## scene.json 骨架（实测可运行）

```json
{
    "camera": { "center": "0 0 -1", "eye": "0 0 0", "up": "0 1 0" },
    "general": {
        "orthogonalprojection": { "width": 2560, "height": 1440 },
        "clearenabled": true, "clearcolor": "0 0 0",
        "cameraparallax": false, "bloom": false
    },
    "objects": [ /* 自下而上 = 绘制顺序（depth 也可控层级） */ ],
    "version": 5
}
```

坐标：世界尺寸 = orthogonalprojection，原点在屏幕中心（2560x1440 时中心 1280,720）。**z 越大越靠前**（camera 朝 -z 看）。

## 图层对象（图片）

```json
{
    "id": 1, "name": "body", "visible": true,
    "image": "models/body.json",
    "origin": "1280 720 0",            // 层中心的世界坐标
    "size": "2560 1440",               // 显示尺寸（world 单位）
    "scale": "1 1 1", "angles": "0 0 0",
    "alpha": 1.0, "depth": 0, "solid": true
}
```
`angles` 单位是弧度（绕 z 轴）。`origin` 同时是旋转/缩放的轴心。layer 全字段的权威来源：编辑器任意项目另存的 scene.json，或 assets/presets/clock/preset.json。

## 内置特效挂接（foliagesway 风摆 = 伪骨骼蒙皮）

```json
"effects": [ {
    "file": "effects/foliagesway/effect.json",
    "passes": [ { "constantshadervalues": {
        "Speed": 2.5, "Strength": 40, "Phase": 0.5, "Power": 0.8
    } } ]
} ]
```
- 变量名 = 特效 shader 里 `// {"material":"..."}` 元数据的首字母大写形式。查某特效有哪些变量：读 `<WE>/assets/effects/<名>/shaders/effects/*.vert|frag`。
- **foliagesway**：噪声风场，`direction`（风向弧度）、`scale`（噪声尺度）、`strength`、`speed`、`power`、`phase`、`cornerweights`（四角权重，默认"1 1 0 0"= 顶随底不动 → 把图层"根"放底部即可根锚定尖摆动，权重即蒙皮思想）、`directionweights`。
- **swing**：整层正弦摆（amount/speed/phase），无梯度，适合整体轻摆。
- 其他常用：opacity、transform、blur、tint、shine、lightshafts（体积光）、waterripple。
- 加 mask：特效支持 `MASK` combo 时，passes 里可带 `"textures"` 给蒙版图（参考各 effect 的 preview 工程）。

## SceneScript（眨眼/骨骼链的引擎内脚本）

接线：**任意可数值属性都能换成脚本** —— `"alpha": {"script": "'use strict'; ...js..."}`（text 对象的 `"text": {"script":...}` 是官方范例）。脚本导出 `update(value)`，每帧调用，返回值成为属性值：

```js
'use strict';
// 可用全局：engine（IEngine）、thisLayer（IImageLayer）、thisObject、color/vector/math 模块
// IImageLayer 提供 bone API（getBoneCount/setLocalBoneAngles/...，需图层已有 puppet 骨架）
let cycle = 3.0;    // 眨眼周期 3 秒
let closed = 0.15;  // 闭眼时长 150ms
export function update(value) {
    let t = engine.getRuntime() % cycle;         // 也可用 Date.now()/1000
    return (t < closed) ? 0.0 : 1.0;             // alpha：闭眼时睁眼层透明
}
```
- 闭眼层配反向脚本（或 alpha = 1 - value 的同款）。
- **骨骼链**：每段层 origin 设在关节点，绑 angles 脚本 `sin(t*speed+phase)*amp`，段间 phase 递增 + 幅度递增 = 传导摆动的 FK 链。
- 修改脚本后重发 openWallpaper 热生效。

## Puppet Warp（真骨骼，GUI 操作，进阶）

官方骨骼系统：编辑器选中图层 → "Puppet Warp"效果 → 打点（钉）连骨 → 蒙皮权重自动/手刷，数据存 `.puppet` 文件（顶点+骨骼索引+混合贴图）。SceneScript 可通过 `thisLayer.getBoneCount()/getLocalBoneAngles()/setLocalBoneAngles(...)` 驱动已有骨架做程序动画。**无法纯脚本创建骨架**，需要用户在编辑器画一次；本 skill 的分段+权重风摆是其全自动替代。

## 应用与验证

```bash
# WE 运行中：
"<WE>/wallpaper64.exe" -control openWallpaper -file "<项目>/project.json"
# 可选 -location "0,0,2560,1440" 指定显示器
# 其他命令：-control closeWallpaper / pause / play / stop
```
没生效就查 `%WE%/log.txt`。发布走编辑器 → Workshop（见 wallpaper-engine-editor skill）。

## 排错

- 壁纸黑屏/空白：纹理超 GPU 上限（>4096）→ 降采样；material shader 名拼错；scene.json JSON 语法（WE 用的是宽松 JSON，允许尾逗号与否以实测为准，建议不写尾逗号）。
- 层级错乱：用 z 深度 + objects 数组顺序双保险。
- 中文路径/文件名：工程实测可用，但 script/命令行传参易出错，资源文件名建议 ASCII。
