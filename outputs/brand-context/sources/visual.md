# AM 视觉规范（Angrymiao Protocol v4.0: Visual Alchemy）

> 涉及视觉创意、KV/海报、产品渲染图、AI 出图时必读。
> 原始规范存档：品牌资料/VI规范-Angrymiao-Protocol-v4.0.md（本文件为其可执行版）。

## 视觉 DNA（CORE CONTEXT，不可修改）

- **Aesthetic**：Future Art / Cyberpunk Luxury / Streetwear Tech
- **Key Elements**：Polycarbonate（透明）/ CNC Aluminum / LED Matrix / Graffiti / AM Monogram
- **视觉 TA**：Global High-Net-Worth Gen Z（Hypebeast、Geek、Crypto-Rich）
- **目标**：每张图一眼是 Angry Miao，而不是 Razer 或 Logitech

## 双角色工作流

AI 依次扮演两个角色，先策略后视觉：
1. **Planner（策略脑）**：定义商业目的、叙事角度、核心冲突 → 完成 Block A
2. **Designer（视觉脑）**：Prompt Engineering、光影逻辑、材质物理属性 → 完成 Block B & C

工单编号规范：`[PROJ]-[SKU]-[PHASE]-[VER]`

## Block A：策略锚点（Planner）

定义这张图要解决的商业问题：
- **Campaign Theme**：战役主题（如 #RethinkV3P 尺寸盲测）
- **Hero Product**：主角产品 + 配色 + 角度（如 AM 65 Less 冰川银、侧面特写）
- **The Hook（第一眼视觉重心）**：如"手指触摸键盘边缘的瞬间，强调金属冷冽感"
- **Scenario（场景叙事）**：如"昏暗极客桌面，只有屏幕挂灯和键盘底灯"
- **Output Channel**：渠道与画幅（如 Instagram Story 9:16，需上下留白放文字）

## Block B：视觉编译（Designer 覆写）

把策略语言翻译为物理渲染参数。编译示例：

| Planner 描述 | Designer 重构 |
|--------------|---------------|
| 很有压迫感，像电影大片 | Low angle shot, macro photography, depth of field, f/1.8, focus on texture, cinematic composition |
| 冷冷的，像银翼杀手，有点紫色 | Volumetric lighting, neon purple and cyan rim light, moody atmosphere, contrasty, ray tracing reflections |
| 看起来很贵，金属质感好，半透明 | Brushed aluminum texture, frosted polycarbonate, sub-surface scattering (SSS), imperceptible scratches (adds realism), 8k textures |

## Block C：品牌 DNA 与防呆（Designer）

**Monogram 规则**：AM 标识必须作为物理材质存在，禁止后期贴图。
- `"Laser etched Angrymiao monogram pattern on the metal surface"` 或 `"LED matrix displaying pixel art cat logo"`

**负面清单（Anti-Brand，绝对禁止）**：
cartoon, illustration, low poly, warm cozy lighting, messy cables, cheap plastic, over-saturated, human faces (unless specified), cute style

> ⚠️ 例外流程：治愈系/温暖向主题（如 DANCING CAT 猫咪线）与"no warm cozy lighting / cute style"冲突时，须在 Block A 显式标注偏离项并与用户确认——默认遵守负面清单。

**Tech Specs**：Unreal Engine 5 render / Octane render, hyper-realistic, 8k resolution；画幅按渠道 16:9 / 9:16 / 4:5

## 出图执行

**最终提示词结构**：
`[Block A: Scenario & Hero Product] + [Block B: Camera, Lighting, Material] + [Block C: Monogram] + [Block C: Tech Specs] + [Block C: Negative Constraints] + [画幅]`

**工具适配**：
- 使用 Kimi `image_generation` 出图时：提示词按上述结构编译（英文）；MJ 专属参数（`--ar`/`--v`/`--stylize`/`--no`）转换为 image_generation 的尺寸参数与正文负面描述
- 需要真实 Logo/VI 素材时：从网上检索 Angry Miao 官方素材（用户认可的做法），注明来源，不修改原始素材文件
- 真实产品照片优先于 AI 渲染：涉及在售产品细节（配列、接口、工艺）时，AI 图不能替代实物图，避免"渲染图与实物不符"触碰 audience.md 红线（"只有视觉渲染，没有真实质感"）
- **KS 合规**：Kickstarter 明确禁止 photorealistic renderings——KS 页面与 Updates 的证据型素材必须以工作原型实拍/开发进展为核心，AI 渲染图仅可用于氛围/概念物料，不得充当产品证据
