import JSZip from 'jszip'
import { invoke } from '@tauri-apps/api/core'
import { contentBBox } from '../utils/bsfPacker'

export interface SpriteFrame {
  name: string
  blob: Blob
  url: string
}

export interface SpriteAnimation {
  name: string
  start: number
  end: number
  fps?: number
  loop?: boolean
  /** .bsf clip 的原始帧名序列（非连续帧时保留；编辑 start/end 后应清除） */
  frameNames?: string[]
}

/**
 * 自定义碰撞形状（画布坐标系，与 pivot 同一坐标空间）。
 * 语义对齐 Godot：rect = RectangleShape2D（中心+尺寸）；capsule = CapsuleShape2D
 * （竖直取向，height 含两端圆帽总高）；polygon 点集（运行时降 AABB，与地图碰撞编辑器先例一致）。
 * 无此字段 = 自动碰撞（引擎按内容包围盒计算，学生默认路径）。
 */
export type SpriteCollisionShape =
  | { type: 'rect'; cx: number; cy: number; w: number; h: number }
  | { type: 'capsule'; cx: number; cy: number; radius: number; height: number }
  | { type: 'polygon'; points: [number, number][] }

/**
 * 标记（挂点）条目：画布坐标 + 编辑器展示设置。
 * 展示设置只存在统一值（BsfMeta.markers）上，帧覆盖仍只记坐标。
 * 缺省：显示、标签、坐标都开，不锁定。
 */
export interface SpriteMarkerPoint {
  x: number
  y: number
  /** false = 画布上不显示该图钉（仍可在「标记管理」页里选中编辑） */
  visible?: boolean
  /** false = 图钉标签不显示名字 */
  showLabel?: boolean
  /** false = 图钉标签不显示坐标 */
  showCoords?: boolean
  /** true = 锁定位置：可点选但不能拖动 */
  locked?: boolean
}

export interface BsfFrameMeta {
  name: string
  rect: { x: number; y: number; w: number; h: number }
  offset: { x: number; y: number }
  /** 帧级中心点覆盖（画布坐标）：缺省时用 BsfMeta.pivot 统一值 */
  pivot?: { x: number; y: number }
  /** 帧级碰撞覆盖：缺省时用 BsfMeta.collision，再缺省走引擎自动碰撞 */
  collision?: SpriteCollisionShape
  /** 帧级挂点覆盖（按名字，画布坐标）：缺省时用 BsfMeta.markers 同名项 */
  markers?: Record<string, { x: number; y: number }>
}

/** .bsf（Bingo Sheet File）sheet 元数据：保存 manifest 时完整回写 */
export interface BsfMeta {
  canvas: { w: number; h: number }
  pivot: { x: number; y: number }
  /**
   * 素材原始中心点（画布坐标）：编辑器「中心点」面板显示偏移量的基准，
   * 未移动过中心点时显示 0,0。老文件缺省 = 当前 pivot。
   */
  pivotBase?: { x: number; y: number }
  frames: BsfFrameMeta[]
  /** 统一碰撞形状：缺省 = 自动碰撞（引擎内容包围盒） */
  collision?: SpriteCollisionShape
  /**
   * 碰撞作用（可选）：与地图图块/形状同一套语义。
   * solid = 碰撞（参与地形/边界物理阻挡）；sensor = 感应（不阻挡，仅可被检测）；
   * both = 碰撞 + 感应。缺省 solid。
   */
  collisionKind?: 'solid' | 'sensor' | 'both'
  /** 碰撞类型 / 标签（可选）：代码里 is_touch("标签") 查询用；缺省「身体」 */
  collisionTag?: string
  /** 禁用碰撞：true = 该角色完全不参与地形/边界物理阻挡（不影响碰到检测） */
  collisionDisabled?: boolean
  /** 单向碰撞（可选）：true = 可当单向碰撞体，只有从「方向」一侧靠近才挡住 */
  collisionOneWay?: boolean
  /** 单向碰撞方向（可选，世界坐标 y 向下）：缺省 (0,1) = 从上方踩住 */
  collisionOneWayDirX?: number
  collisionOneWayDirY?: number
  /** 单向碰撞厚度（可选，0~8 像素）：越大越容易踩住/挡住；缺省 0 */
  collisionOneWayMargin?: number
  /** 碰撞层级开关（可选）：当前仅编辑器保存，运行时尚未接入 */
  collisionLayersEnabled?: boolean
  /** 所在碰撞层（1~8，缺省 1）：仅编辑器保存，运行时尚未接入 */
  collisionLayer?: number
  /** 可碰撞掩码（1~8 的层号数组，缺省 [1]）：仅编辑器保存，运行时尚未接入 */
  collisionMask?: number[]
  /** 碰撞形状旋转角度（度，可选）：当前仅编辑器保存，运行时尚未接入 */
  collisionAngle?: number
  /** 受重力影响：false = 重力地图里也不下坠（撞墙/落地等碰撞照常）；缺省 = 受重力 */
  gravity?: boolean
  /** 初始隐藏：true = 角色创建时不可见（代码里 show() 后出现）；缺省 = 可见 */
  hidden?: boolean
  /** 默认图层：数字越大越靠前，同层按创建顺序；缺省 0 */
  layer?: number
  /** Y 轴排序：true = 同层内按脚底 Y 坐标排序（越靠下越靠前）；缺省不启用 */
  ySort?: boolean
  /** 水平翻转：true = 创建时左右镜像（素材朝左也能用）；缺省不翻转 */
  flipX?: boolean
  /** 垂直翻转：true = 创建时上下镜像；缺省不翻转 */
  flipY?: boolean
  /** 统一挂点（按名字，画布坐标）：武器/道具挂载锚点，如 hand_r / head；含编辑器展示设置 */
  markers?: Record<string, SpriteMarkerPoint>
}

/**
 * 角色场景变换（角色自己的局部坐标系，原点 = 引擎默认出生位置）：
 * x 向右、y 向上为正，表示相对默认出生位置的偏移；angle 逆时针为正（度）；
 * scale 为百分比（100 = 原始大小）。
 * 缺省（未写入数据）= 0,0 / 0° / 100%，即完全不改变引擎的默认出生位置。
 */
export interface SpriteTransform {
  x: number
  y: number
  angle: number
  scale: number
  /** 非等比缩放（百分比）：仅「约束比例」取消勾选且 X / Y 不同时写入；缺省 = 用 scale */
  scaleX?: number
  scaleY?: number
}

/** 默认变换 = 原点、不旋转、100% 缩放（不写数据时引擎出生在舞台中心 320,240 的行为不变） */
export const DEFAULT_SPRITE_TRANSFORM: SpriteTransform = { x: 0, y: 0, angle: 0, scale: 100 }

/** 读取并校验角色初始变换：字段缺失/非法时回退默认值（scale 限制 5%~1000%） */
export function readSpriteTransform(raw: unknown): SpriteTransform | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  const obj = raw as Record<string, unknown>
  const num = (v: unknown, d: number) => (typeof v === 'number' && Number.isFinite(v) ? v : d)
  const clampScale = (v: number) => Math.min(1000, Math.max(5, v))
  const scale = clampScale(num(obj.scale, DEFAULT_SPRITE_TRANSFORM.scale))
  const sx = clampScale(num(obj.scaleX, scale))
  const sy = clampScale(num(obj.scaleY, scale))
  return {
    x: num(obj.x, DEFAULT_SPRITE_TRANSFORM.x),
    y: num(obj.y, DEFAULT_SPRITE_TRANSFORM.y),
    angle: num(obj.angle, DEFAULT_SPRITE_TRANSFORM.angle),
    scale,
    // 只在与统一缩放不一致时保留分轴值，减少无意义的字段
    ...(sx !== scale ? { scaleX: sx } : {}),
    ...(sy !== scale ? { scaleY: sy } : {}),
  }
}

export interface SpriteData {
  name: string
  frames: SpriteFrame[]
  animations: SpriteAnimation[]
  /** 默认渲染帧（下标）：编辑器选中帧持久化后，引擎初始渲染与缩略图都用它（对齐 Scratch 的"当前造型"语义） */
  defaultFrameIndex?: number
  /** 场景变换（可选）：x/y 是相对引擎默认出生位置的偏移，写入后才由引擎应用；未写入 = 默认位置 */
  transform?: SpriteTransform
  /** 仅 .bsf 角色有值 */
  bsf?: BsfMeta
}

/** 从配置里的 defaultFrame 字段解析默认帧下标（缺省/无效 → 0） */
function resolveDefaultFrameIndex(defaultFrame: unknown, frameNames: string[]): number {
  if (typeof defaultFrame === 'string') {
    const idx = frameNames.indexOf(defaultFrame)
    if (idx >= 0) return idx
  }
  if (typeof defaultFrame === 'number' && Number.isInteger(defaultFrame)
    && defaultFrame >= 0 && defaultFrame < frameNames.length) {
    return defaultFrame
  }
  return 0
}

/** 解码图片（Blob 或 data URL → HTMLImageElement；老 WebView 无 createImageBitmap） */
export function loadImage(source: Blob | string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    let url: string
    let revoke = false
    if (typeof source === 'string') {
      url = source
    } else {
      url = URL.createObjectURL(source)
      revoke = true
    }
    const img = new Image()
    img.onload = () => {
      if (revoke) URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      if (revoke) URL.revokeObjectURL(url)
      reject(new Error('图片解码失败'))
    }
    img.src = url
  })
}

/**
 * 把 sheet 中的一帧画回完整参考画布（canvas + offset 定位）。
 * 紧致裁剪的帧直接展示会比 .bgs 整帧导出的观感"大一圈"且预览帧间不齐；
 * 按 manifest 语义还原画布尺寸后，缩略图边距与动画预览对齐都和 .bgs 一致。
 */
async function cropSheetFrame(
  image: HTMLImageElement,
  frame: BsfFrameMeta,
  canvasSize: { w: number; h: number },
): Promise<SpriteFrame> {
  const canvas = document.createElement('canvas')
  canvas.width = canvasSize.w
  canvas.height = canvasSize.h
  const ctx = canvas.getContext('2d')!
  const offset = frame.offset || { x: 0, y: 0 }
  ctx.drawImage(
    image,
    frame.rect.x, frame.rect.y, frame.rect.w, frame.rect.h,
    offset.x, offset.y, frame.rect.w, frame.rect.h,
  )
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(b => (b ? resolve(b) : reject(new Error('canvas.toBlob 失败'))), 'image/png')
  })
  return { name: '', blob, url: URL.createObjectURL(blob) }
}

/**
 * .bsf 缩略图：渲染 defaultFrame（缺省第一帧）→ dataURL。
 * 支持两种形态：内置库的 .bsf zip 文件 / 项目内解压后的 sheet 目录。
 */
export async function getBsfThumbnail(
  path: string,
  contentRatio?: number,
): Promise<{ dataUrl: string; width: number; height: number }> {
  let manifest: any
  let sheetImage: HTMLImageElement

  if (path.toLowerCase().endsWith('.bsf')) {
    const bytes = await invoke<number[]>('read_binary', { path })
    const JSZip = (await import('jszip')).default
    const zip = await JSZip.loadAsync(new Uint8Array(bytes))
    const manifestEntry = zip.file('manifest.json')
    const sheetEntry = zip.file('sheet.png')
    if (!manifestEntry || !sheetEntry) throw new Error('.bsf 缺少 manifest.json 或 sheet.png')
    manifest = JSON.parse(await manifestEntry.async('text'))
    sheetImage = await loadImage(await sheetEntry.async('blob'))
  } else {
    manifest = JSON.parse(await invoke<string>('read_file', { path: `${path}/manifest.json` }))
    const dataUrl = await invoke<string>('read_image_as_data_url', {
      path: `${path}/${manifest.sheet || 'sheet.png'}`,
    })
    sheetImage = await loadImage(dataUrl)
  }

  const allFrames: any[] = manifest.frames || []
  const defaultIdx = resolveDefaultFrameIndex(
    manifest.defaultFrame,
    allFrames.map(f => f.name),
  )
  const frame = allFrames[defaultIdx] ?? allFrames[0]
  if (!frame?.rect) throw new Error('manifest.frames 为空')
  // 画布尺寸：manifest.canvas 优先；否则用所有帧并集的最大边界，兜底用 sheet 尺寸
  const width: number = manifest.canvas?.width ?? frame.rect.w
  const height: number = manifest.canvas?.height ?? frame.rect.h
  // 与悬停动画共用同一套归一化：默认帧内容框为锚点，缩略图与动画帧尺寸一致，悬停不跳大
  const off = frame.offset || { x: 0, y: 0 }
  const anchor = { x: off.x, y: off.y, w: frame.rect.w, h: frame.rect.h }
  const { renderNormalizedBsfFrames } = await import('../utils/spriteThumb')
  const [out] = renderNormalizedBsfFrames(sheetImage, [frame], anchor, contentRatio)
  return { dataUrl: out!.toDataURL('image/png'), width, height }
}

/** 路径是否为单图角色（单张 png/jpg/... 贴图，而非目录角色） */
export function isImageSpritePath(path: string): boolean {
  return /\.(png|jpe?g|gif|bmp|webp)$/i.test(path)
}

/** 统一入口：项目内的角色资源（图片 / .bgs 目录 / .bsf sheet 目录） */
export async function readSpriteFromPath(path: string): Promise<SpriteData> {
  if (isImageSpritePath(path)) {
    return readImageAsSprite(path)
  }
  // 本地目录：优先检测 .bsf（manifest.json），否则按 .bgs（config.json）
  if (path.startsWith('/') || /^[A-Z]:\\/i.test(path)) {
    const hasManifest = await invoke<boolean>('path_exists', { path: `${path}/manifest.json` })
      .catch(() => false)
    if (hasManifest) return readBsfFromDir(path)
  }
  return readBgsFromUrl(path)
}

/** 读取 .bsf 解压目录（manifest.json + sheet.png）：帧从 sheet 裁剪，clips 映射为动画段 */
export async function readBsfFromDir(dirPath: string): Promise<SpriteData> {
  const manifestText = await invoke<string>('read_file', { path: `${dirPath}/manifest.json` })
  const manifest = JSON.parse(manifestText)
  const sheetDataUrl = await invoke<string>('read_image_as_data_url', {
    path: `${dirPath}/${manifest.sheet || 'sheet.png'}`,
  })
  const sheetImage = await loadImage(sheetDataUrl)
  return buildBsfSpriteData(manifest, sheetImage)
}

/** 读取 .bsf zip 包文件（内置库用）：帧从 sheet 裁剪回全画布 */
export async function readBsfFile(file: File): Promise<SpriteData> {
  const zip = await JSZip.loadAsync(file)
  const manifestEntry = zip.file('manifest.json')
  const sheetEntry = zip.file('sheet.png')
  if (!manifestEntry || !sheetEntry) throw new Error('.bsf 缺少 manifest.json 或 sheet.png')
  const manifest = JSON.parse(await manifestEntry.async('text'))
  const sheetImage = await loadImage(await sheetEntry.async('blob'))
  return buildBsfSpriteData(manifest, sheetImage)
}

/** manifest + sheet 图 → SpriteData（readBsfFromDir / readBsfFile 共用） */
async function buildBsfSpriteData(manifest: any, sheetImage: HTMLImageElement): Promise<SpriteData> {
  if (manifest.format !== 'bsf' || !Array.isArray(manifest.frames) || manifest.frames.length === 0) {
    throw new Error('不是合法的 .bsf manifest（需要 format=bsf 且 frames 非空）')
  }
  const canvasSize = manifest.canvas || {
    w: manifest.frames[0]?.rect.w ?? 1,
    h: manifest.frames[0]?.rect.h ?? 1,
  }

  const frames: SpriteFrame[] = []
  for (const f of manifest.frames as BsfFrameMeta[]) {
    const cropped = await cropSheetFrame(sheetImage, f, canvasSize)
    cropped.name = f.name
    frames.push(cropped)
  }

  const frameIndex = new Map((manifest.frames as BsfFrameMeta[]).map((f, i) => [f.name, i]))
  const animations: SpriteAnimation[] = (manifest.clips || []).map((c: any) => {
    const names: string[] = Array.isArray(c.frames) ? c.frames : []
    const idxs = names.map(n => frameIndex.get(n)).filter((i): i is number => i !== undefined)
    return {
      name: c.name,
      start: idxs.length ? idxs[0] + 1 : 1,
      end: idxs.length ? idxs[idxs.length - 1] + 1 : 1,
      fps: c.fps || 10,
      loop: c.loop !== false,
      frameNames: names.length ? names : undefined,
    }
  })

  return {
    name: manifest.name || '未知角色',
    frames,
    animations,
    defaultFrameIndex: resolveDefaultFrameIndex(
      manifest.defaultFrame,
      (manifest.frames as BsfFrameMeta[]).map(f => f.name),
    ),
    // 场景变换（可选）：缺省不写字段 = 引擎默认出生位置（舞台中心）
    ...(manifest.transform ? { transform: readSpriteTransform(manifest.transform) } : {}),
    bsf: {
      canvas: canvasSize,
      pivot: manifest.pivot || { x: canvasSize.w / 2, y: canvasSize.h / 2 },
      // 素材原始中心点（编辑器「中心点」显示 0,0 的基准）：老文件没有该字段时以当前 pivot 为基准
      pivotBase: manifest.pivotBase || manifest.pivot || { x: canvasSize.w / 2, y: canvasSize.h / 2 },
      frames: manifest.frames,
      ...(manifest.collision ? { collision: manifest.collision } : {}),
      ...(manifest.collisionKind === 'sensor' || manifest.collisionKind === 'both'
        ? { collisionKind: manifest.collisionKind }
        : {}),
      ...(typeof manifest.collisionTag === 'string' && manifest.collisionTag.trim()
        ? { collisionTag: manifest.collisionTag.trim() }
        : {}),
      ...(manifest.collisionDisabled ? { collisionDisabled: true } : {}),
      ...(manifest.collisionOneWay
        ? {
            collisionOneWay: true,
            ...(typeof manifest.collisionOneWayDirX === 'number'
              ? { collisionOneWayDirX: manifest.collisionOneWayDirX }
              : {}),
            ...(typeof manifest.collisionOneWayDirY === 'number'
              ? { collisionOneWayDirY: manifest.collisionOneWayDirY }
              : {}),
            ...(typeof manifest.collisionOneWayMargin === 'number'
              ? { collisionOneWayMargin: manifest.collisionOneWayMargin }
              : {}),
          }
        : {}),
      ...(manifest.collisionLayersEnabled
        ? {
            collisionLayersEnabled: true,
            collisionLayer: typeof manifest.collisionLayer === 'number' ? manifest.collisionLayer : 1,
            collisionMask: Array.isArray(manifest.collisionMask) ? manifest.collisionMask : [1],
          }
        : {}),
      ...(typeof manifest.collisionAngle === 'number' ? { collisionAngle: manifest.collisionAngle } : {}),
      ...(manifest.gravity === false ? { gravity: false } : {}),
      ...(manifest.hidden ? { hidden: true } : {}),
      ...(manifest.flipX ? { flipX: true } : {}),
      ...(manifest.flipY ? { flipY: true } : {}),
      ...(typeof manifest.layer === 'number' ? { layer: manifest.layer } : {}),
      ...(manifest.ySort ? { ySort: true } : {}),
      ...(manifest.markers ? { markers: manifest.markers } : {}),
    },
  }
}

/**
 * 保存 .bsf 角色的 manifest.json（仅回写 clips；sheet 像素与帧矩形不动）。
 * clip 帧序列规则：若 start/end 与加载时 frameNames 一致则保留原序列，否则按 start-end 区间重建。
 */
export async function saveBsfManifest(dirPath: string, sprite: SpriteData): Promise<void> {
  if (!sprite.bsf) throw new Error('不是 .bsf 角色（缺少 sheet 元数据）')
  const allNames = sprite.bsf.frames.map(f => f.name)

  const clips = sprite.animations.map(a => {
    let frameList: string[]
    if (a.frameNames && a.frameNames.length > 0) {
      const firstIdx = allNames.indexOf(a.frameNames[0])
      const lastIdx = allNames.indexOf(a.frameNames[a.frameNames.length - 1])
      // start/end 被编辑过 → 丢弃旧序列，按区间重建
      if (firstIdx === a.start - 1 && lastIdx === a.end - 1) {
        frameList = [...a.frameNames]
      } else {
        frameList = allNames.slice(a.start - 1, a.end)
      }
    } else {
      frameList = allNames.slice(a.start - 1, a.end)
    }
    return {
      name: a.name,
      frames: frameList,
      fps: a.fps ?? 10,
      loop: a.loop !== false,
    }
  })

  const manifest = {
    format: 'bsf',
    version: 2,
    name: sprite.name,
    sheet: 'sheet.png',
    canvas: sprite.bsf.canvas,
    pivot: sprite.bsf.pivot,
    // 素材原始中心点（编辑器显示偏移的基准）：持久化后再次打开仍能看出累计移动量
    ...(sprite.bsf.pivotBase ? { pivotBase: sprite.bsf.pivotBase } : {}),
    // 自定义碰撞（可选）：无 = 引擎自动碰撞
    ...(sprite.bsf.collision ? { collision: sprite.bsf.collision } : {}),
    // 碰撞作用 / 类型（可选）：solid 与空标签是默认值，不写字段
    ...(sprite.bsf.collisionKind && sprite.bsf.collisionKind !== 'solid'
      ? { collisionKind: sprite.bsf.collisionKind }
      : {}),
    ...(sprite.bsf.collisionTag?.trim() ? { collisionTag: sprite.bsf.collisionTag.trim() } : {}),
    // 禁用碰撞（可选）：true = 不参与物理阻挡；缺省不写字段
    ...(sprite.bsf.collisionDisabled ? { collisionDisabled: true } : {}),
    // 单向碰撞（可选）：true = 角色可当单向碰撞体；缺省不写字段
    ...(sprite.bsf.collisionOneWay
      ? {
          collisionOneWay: true,
          // 方向缺省 (0,1) 从上方踩住，不写冗余字段
          ...(sprite.bsf.collisionOneWayDirX !== undefined
            && sprite.bsf.collisionOneWayDirY !== undefined
            && (sprite.bsf.collisionOneWayDirX !== 0 || sprite.bsf.collisionOneWayDirY !== 1)
            ? {
                collisionOneWayDirX: sprite.bsf.collisionOneWayDirX,
                collisionOneWayDirY: sprite.bsf.collisionOneWayDirY,
              }
            : {}),
          ...(sprite.bsf.collisionOneWayMargin
            ? { collisionOneWayMargin: sprite.bsf.collisionOneWayMargin }
            : {}),
        }
      : {}),
    // 碰撞层级 / 掩码 / 旋转（可选）：当前仅编辑器保存，运行时尚未接入
    ...(sprite.bsf.collisionLayersEnabled
      ? {
          collisionLayersEnabled: true,
          collisionLayer: sprite.bsf.collisionLayer ?? 1,
          collisionMask: sprite.bsf.collisionMask ?? [1],
        }
      : {}),
    ...(typeof sprite.bsf.collisionAngle === 'number' && sprite.bsf.collisionAngle !== 0
      ? { collisionAngle: sprite.bsf.collisionAngle }
      : {}),
    // 受重力影响（可选）：false = 不受地图重力；缺省不写字段（= 受重力）
    ...(sprite.bsf.gravity === false ? { gravity: false } : {}),
    // 初始隐藏（可选）：缺省不写字段（= 可见）
    ...(sprite.bsf.hidden ? { hidden: true } : {}),
    // 翻转模式（可选）：缺省不写字段（= 不翻转）
    ...(sprite.bsf.flipX ? { flipX: true } : {}),
    ...(sprite.bsf.flipY ? { flipY: true } : {}),
    // 默认图层（可选）：缺省不写字段（= 0）
    ...(typeof sprite.bsf.layer === 'number' && sprite.bsf.layer !== 0
      ? { layer: sprite.bsf.layer }
      : {}),
    // Y 轴排序（可选）：缺省不写字段（= 不启用）
    ...(sprite.bsf.ySort ? { ySort: true } : {}),
    // 挂点（可选）：名字 → 画布坐标；空表不写字段
    ...(sprite.bsf.markers && Object.keys(sprite.bsf.markers).length > 0
      ? { markers: sprite.bsf.markers }
      : {}),
    // 场景初始变换（可选）：仅用户编辑过后才写入，旧资源保持引擎默认行为
    ...(sprite.transform ? { transform: sprite.transform } : {}),
    frames: sprite.bsf.frames,
    clips,
    // 默认渲染帧（编辑器选中帧）：可选字段，读取方缺省回退第一帧
    ...(allNames[sprite.defaultFrameIndex ?? 0]
      ? { defaultFrame: allNames[sprite.defaultFrameIndex ?? 0] }
      : {}),
  }
  await invoke('write_file', {
    path: `${dirPath}/manifest.json`,
    content: JSON.stringify(manifest, null, 2),
  })
}

export async function readBgsFile(file: File): Promise<SpriteData> {
  const zip = await JSZip.loadAsync(file)
  const configEntry = zip.file('config.json')
  if (!configEntry) throw new Error('config.json not found in .bgs')

  const config = JSON.parse(await configEntry.async('text'))

  const frames: SpriteFrame[] = []
  const frameNames: string[] = config.frames || []

  for (const frameName of frameNames) {
    const entry = zip.file(frameName)
    if (entry) {
      const blob = await entry.async('blob')
      const url = URL.createObjectURL(blob)
      frames.push({ name: frameName, blob, url })
    }
  }

  const animations: SpriteAnimation[] = (config.segments || config.animations || []).map(
    (seg: any) => ({
      name: seg.name,
      start: seg.start || 1,
      end: seg.end || seg.start || 1,
      fps: seg.fps || 10,
      loop: seg.loop !== false,
    })
  )

  return {
    name: config.name || '未知角色',
    frames,
    animations,
    defaultFrameIndex: resolveDefaultFrameIndex(config.defaultFrame, frameNames),
    ...(config.transform ? { transform: readSpriteTransform(config.transform) } : {}),
  }
}

export async function readBgsFromUrl(url: string): Promise<SpriteData> {
  // 本地文件系统路径：通过 Tauri invoke 读取
  if (url.startsWith('/') || /^[A-Z]:\\/i.test(url)) {
    return readLocalSpriteDir(url)
  }
  // HTTP URL（engine/assets 通过 Vite publicDir 提供）：用 fetch 读取 .bgs zip
  const resp = await fetch(url)
  const blob = await resp.blob()
  const file = new File([blob], 'sprite.bgs')
  return readBgsFile(file)
}

/** 从本地解压目录读取角色（config.json + 帧图片） */
async function readLocalSpriteDir(dirPath: string): Promise<SpriteData> {
  const configText = await invoke<string>('read_file', { path: `${dirPath}/config.json` })
  const config = JSON.parse(configText)

  const frames: SpriteFrame[] = []
  const frameNames: string[] = config.frames || []

  for (const frameName of frameNames) {
    try {
      const dataUrl = await invoke<string>('read_image_as_data_url', { path: `${dirPath}/${frameName}` })
      const resp = await fetch(dataUrl)
      const blob = await resp.blob()
      const objectUrl = URL.createObjectURL(blob)
      frames.push({ name: frameName, blob, url: objectUrl })
    } catch (e) {
      console.warn(`读取帧 ${frameName} 失败:`, e)
    }
  }

  const animations: SpriteAnimation[] = (config.segments || config.animations || []).map(
    (seg: any) => ({
      name: seg.name,
      start: seg.start || 1,
      end: seg.end || seg.start || 1,
      fps: seg.fps || 10,
      loop: seg.loop !== false,
    })
  )

  return {
    name: config.name || '未知角色',
    frames,
    animations,
    defaultFrameIndex: resolveDefaultFrameIndex(config.defaultFrame, frameNames),
    ...(config.transform ? { transform: readSpriteTransform(config.transform) } : {}),
  }
}

export function createFrameUrl(blob: Blob): string {
  return URL.createObjectURL(blob)
}

/** 释放 SpriteData 中所有 ObjectURL，防止内存泄漏 */
export function revokeSpriteUrls(sprite: SpriteData | null) {
  if (!sprite) return
  for (const frame of sprite.frames) {
    if (frame.url) URL.revokeObjectURL(frame.url)
  }
}

/**
 * 将动画/帧修改写回 config.json（自动保存）
 * 保持与旧版 PySide6 sprite_model.py save() 相同的格式：
 * 使用 "segments" 数组，保留 name/count 等原有字段
 */
export async function saveSpriteConfig(spritePath: string, sprite: SpriteData): Promise<void> {
  const config: Record<string, any> = { name: sprite.name }
  config.frames = sprite.frames.map(f => f.name)
  config.segments = sprite.animations.map(a => {
    const seg: Record<string, any> = {
      name: a.name,
      start: a.start,
      end: a.end,
    }
    if (a.fps != null) seg.fps = a.fps
    if (a.loop != null) seg.loop = a.loop
    return seg
  })
  // 默认渲染帧（编辑器选中帧）：可选字段，缺省时读取方回退第一帧
  const defaultFrame = sprite.frames[sprite.defaultFrameIndex ?? 0]?.name
  if (defaultFrame) config.defaultFrame = defaultFrame
  // 场景初始变换（可选）：仅用户编辑过后才写入
  if (sprite.transform) config.transform = sprite.transform

  const json = JSON.stringify(config, null, 4)
  await invoke('write_file', { path: `${spritePath}/config.json`, content: json })
}

// 图片文件 → 单帧 SpriteData（上传图片直接作角色时使用）
export async function readImageAsSprite(path: string): Promise<SpriteData> {
  const dataUrl = await invoke<string>('read_image_as_data_url', { path })
  const blob = await (await fetch(dataUrl)).blob()
  const fileName = path.split(/[\\/]/).pop() || '角色'
  const name = fileName.replace(/\.[^.]+$/, '')
  return {
    name,
    frames: [{ name, blob, url: dataUrl }],
    animations: [{ name: '默认动画', start: 1, end: 1, fps: 10, loop: true }],
  }
}

/** 图片非透明内容包围盒（图片坐标）；整图全透明时回退整图 */
export function imageContentBox(img: HTMLImageElement): { x: number; y: number; w: number; h: number } {
  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth || img.width
  canvas.height = img.naturalHeight || img.height
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(img, 0, 0)
  return contentBBox(canvas) ?? { x: 0, y: 0, w: canvas.width, h: canvas.height }
}

/**
 * 单图角色（单张 png 贴图）→ 单帧 .bsf 元数据。
 * 画布 = 图片尺寸，帧矩形 = 非透明内容框、中心点 = 内容框中心——
 * 与引擎对单图角色的原有语义（x/y 落在内容重心、自动碰撞取内容框）完全一致，
 * 转正后位置/碰撞/缩放表现不变，但多了 pivot/碰撞/挂点的承载字段。
 */
export async function buildSingleFrameBsfMeta(sprite: SpriteData): Promise<BsfMeta> {
  const img = await loadImage(sprite.frames[0].blob)
  const w = img.naturalWidth || img.width
  const h = img.naturalHeight || img.height
  const box = imageContentBox(img)
  const name = sprite.frames[0]?.name || 'frame_001'
  return {
    canvas: { w, h },
    pivot: { x: box.x + box.w / 2, y: box.y + box.h / 2 },
    frames: [{
      name,
      rect: { x: box.x, y: box.y, w: box.w, h: box.h },
      offset: { x: box.x, y: box.y },
    }],
  }
}

/**
 * 单图角色转正为 .bsf 目录（sheet.png = 原图 + manifest.json）。
 * 中心点/碰撞/挂点只能由 manifest 承载（引擎也只读 .bsf 的这些字段），
 * 因此第一次标注时把角色升级成 .bsf 目录。返回新目录路径。
 */
export async function imageSpriteToBsfDir(imgPath: string, sprite: SpriteData): Promise<string> {
  if (!sprite.bsf) throw new Error('缺少 .bsf 元数据，无法转正单图角色')
  const dirPath = imgPath.replace(/\.[^./\\]+$/, '')
  const img = await loadImage(sprite.frames[0].blob)
  const canvas = document.createElement('canvas')
  canvas.width = img.naturalWidth || img.width
  canvas.height = img.naturalHeight || img.height
  canvas.getContext('2d')!.drawImage(img, 0, 0)
  const sheetBlob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(b => (b ? resolve(b) : reject(new Error('canvas.toBlob 失败'))), 'image/png')
  })

  await invoke('create_dir', { path: dirPath })
  await invoke('write_binary', {
    path: `${dirPath}/sheet.png`,
    data: Array.from(new Uint8Array(await sheetBlob.arrayBuffer())),
  })
  // 先写 manifest 再删原图：中途失败也不会出现"目录缺 manifest、原图已删"
  await saveBsfManifest(dirPath, sprite)
  await invoke('delete_path', { path: imgPath }).catch(() => {})
  return dirPath
}
