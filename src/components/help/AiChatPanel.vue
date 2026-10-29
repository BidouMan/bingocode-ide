<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'
import iconAiAssistant from '../../assets/icons/ai_助手.svg'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
}

interface ApiSettings {
  baseUrl: string
  apiKey: string
  model: string
}

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLDivElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const streamingContent = ref('')
const showSettings = ref(false)

// 默认设置
const defaultSettings: ApiSettings = {
  baseUrl: 'https://api.deepseek.com',
  apiKey: 'sk-2f0558358b3b45e8920f5b7b18e9fce5',
  model: 'deepseek-v4-flash',
}

const settings = ref<ApiSettings>({ ...defaultSettings })

// 从 localStorage 加载设置
onMounted(() => {
  try {
    const saved = localStorage.getItem('bingo-ai-settings')
    if (saved) {
      const parsed = JSON.parse(saved)
      settings.value = { ...defaultSettings, ...parsed }
      // 如果保存的是旧配置，更新为最新默认值
      if (parsed.baseUrl === 'https://api.openai.com' && parsed.apiKey === defaultSettings.apiKey) {
        settings.value.baseUrl = defaultSettings.baseUrl
        settings.value.model = defaultSettings.model
        localStorage.setItem('bingo-ai-settings', JSON.stringify(settings.value))
      }
      // 如果模型是旧的，更新为 deepseek-v4-flash
      if (parsed.model === 'deepseek-chat' || parsed.model === 'deepseek-v3') {
        settings.value.model = 'deepseek-v4-flash'
        localStorage.setItem('bingo-ai-settings', JSON.stringify(settings.value))
      }
    }
  } catch {}
})

function saveSettings() {
  localStorage.setItem('bingo-ai-settings', JSON.stringify(settings.value))
  showSettings.value = false
}

function resetSettings() {
  settings.value = { ...defaultSettings }
  localStorage.removeItem('bingo-ai-settings')
}

const SYSTEM_PROMPT = `你是 BingoCodeIDE 的 AI 编程助手，专为教师设计。你只回答与 BingoCodeIDE 引擎 API 相关的问题。

## 严格规则
1. 只使用下面列出的 API 来编写代码，不要使用任何外部库或标准库（random、math 等也不要用，用引擎自带的 random_int、random_float）
2. 不要回答与 BingoCodeIDE 项目无关的任何问题（如通用编程知识、其他框架等）
3. 如果用户问了无关问题，礼貌地拒绝并引导回引擎相关话题
4. 代码中不要使用 import 语句
5. 所有代码必须能在 BingoCodeIDE 引擎中直接运行
6. 游戏循环必须用 while True:，不要用 def run()
7. jump() 只是施加向上的力，必须自己用 is_on_ground() 判断能否跳

## 画面基本信息
- 窗口尺寸：640 x 480 像素
- 坐标原点在地图左下角：(0,0) 是地图左下角，(地图宽, 地图高) 是右上角；单屏地图（640x480）时右上角就是 (640,480)
- y 轴向上增大（向上移动 y 变大），x 轴向右增大
- 鼠标坐标是屏幕坐标：以窗口左下角为 (0,0)，不随地图高度变化
- 角度：0=朝右，90=朝上，180=朝左，270=朝下（逆时针）
- while True 循环约每秒执行 60 次（60FPS）

## 引擎 API 详细参考

### 精灵 Sprite
- hero = Sprite("角色名") — 创建角色，角色名必须和资源面板中添加的角色文件夹名一致。初始位置在画面中央(320,240)，初始大小100%，朝向0度
- hero.delete() — 从画面删除角色，删后不能再使用
- hero.x, hero.y — 读取或设置位置（0~地图宽度, 0~地图高度），赋值时自动检测碰撞
- hero.pos — 一次性读取角色坐标 (x, y)，只能读取：x, y = hero.pos
- hero.scale — 大小百分比，100=正常，200=两倍大，50=一半小（可直接赋值）
- hero.angle — 朝向角度（可直接赋值）
- hero.layer — 层级数字，越大越在前面，默认0（写 1、2、3 就能盖在别的角色前面，写负数躲到后面）
- hero.vy — 垂直速度属性，正数=上升，负数=下落，静止=0

### 运动
- hero.goto(x, y) — 瞬间传送到(x,y)，自动检测碰撞。也接受标记引用（hero.goto(player.get_marker())）或另一个 Sprite（hero.goto(enemy)），对准目标的注册点
- hero.move(步数) — 朝当前 angle 方向移动指定像素，自动检测碰撞（撞墙停下/贴墙滑动、不会穿墙，也不会自己绕路），会拆分成小步避免穿墙
- hero.jump(power=10) — 施加向上的力（角色 vy 变为正数）。不判断地面！必须配合 is_on_ground() 使用。用法：if hero.is_on_ground(): hero.jump(10)
- hero.smart_jump(power=10) — 大小跳：按下起跳、按住跳得高、松手就落下。必须写在 if key_down("up"): 里面（每帧调用一次），松手时引擎自动停止跳跃，不需要 stop_jump
- hero.stop_jump() — 停止跳跃：只在角色正在上升时生效，停止继续上升并提前落下（上升重力从 0.5 变为 2.8）。自己不会起跳，需配合 jump；用于敌人、撞天花板等没有松手的场景（普通按键跳跃用 smart_jump）
- hero.drop_down() — 从脚下的跳板掉下去。只有站在碰撞类型为「跳板」的平台上才生效，不在地面上调用会被自动忽略，不用自己判断 is_on_ground()
- hero.add_x(n) / hero.add_y(n) — 直接加/减坐标（正数向右/上），改完做一次碰撞修正；小步会被墙挡住，一次移动太远可能穿墙
- hero.set_x(x) / hero.set_y(y) — 直接设置坐标并立即做一次碰撞修正；落点在墙里会被推到最近一侧，不检查中间路径
- hero.set_angle(度数) — 设置朝向角度
- hero.look_at(target) — 自动转向面向 target（另一个 Sprite 或 mouse 对象）
- hero.set_speed(速度) — 设置持续移动速度，之后每帧自动沿当前方向移动，写 0 停下
- hero.edge_bounce() — 碰到地图边界自动反弹
- hero.goto_rand() — 随机传送到地图内任意位置

### 标记与挂载（仅 .bsf 角色有标记）
- 标记是角色身上预先画好的锚点（在角色编辑器「标记」图层添加，默认名「标记」，新增自动编号「标记1」「标记2」…），用于把武器/道具挂到角色身上
- m = hero.get_marker() — 获取第一个标记（名「标记」）的引用；hero.get_marker("标记1") 取指定名字的标记
- m.x / m.y — 读取该标记此刻在画面上的坐标（已算上角色的位置、旋转、缩放和左右翻转；动画换帧时标记位置也会跟着变）
- sword.follow(m) — 让 sword 每帧贴在标记 m 上。只同步位置和左右翻转，**不改变朝向**，所以仍可 sword.look_at(mouse) 单独瞄准
- sword.follow(m, flip=False) — 同上但不继承角色的左右翻转（鼠标瞄准类武器用这个）
- sword.unfollow() — 解除跟随，恢复自由移动；保留脱离时的朝向，不会自动变回正向
- 目标角色被 delete 后跟随自动停止；不写 follow 时可用手写循环 sword.goto(m) 每帧对准（等价效果）
- 注意：follow 是普通方法调用，不是属性赋值（不要写成 sword.follow = m）

### 外观
- hero.show() / hero.hide() — 显示/隐藏（不是删除，隐藏后还能 show）
- hero.say("文字") / hero.say("文字", 2) — 头顶气泡。不写时间=一直显示，写时间=到时消失
- hero.set_scale(百分比) — 设置大小（100=正常）
- hero.add_scale(增量) — 在当前大小基础上增减
- hero.set_rotation_mode("all") — "all"=任意旋转（默认），"left_right"=只左右翻转，"none"=不旋转
- hero.play("动画名") — 播放角色资源中预设的动画

### 侦测
- hero.is_touch(target) — 碰撞检测。target 可以是：另一个 Sprite、mouse 对象、字符串标签。返回 True/False
- hero.is_touch_edge() — 是否碰到地图边界
- hero.is_out_screen() — 是否整个角色都飞出游戏画面（地图再大也只看一屏）
- hero.distance_to(target) — 返回到另一个 Sprite 或 mouse 的像素距离
- bullet.is_touch_group("组名") — 检测子弹是否碰到组内成员，碰到返回那个角色，没碰到返回 None
- hero.is_on_ground() — 是否真正站在地面上（由物理落地接触决定，上升中/从下方穿过跳板时为 False）；跳跃前用它判断
- key_down("键名") — 按键是否正在被按住，每帧检测。键名小写：space, up, down, left, right, a-z
- key_pressed("键名") — 只在按下的那一帧返回 True（单次触发）。用于跳跃等一次性操作
- key_up("键名") — 只在松开的那一帧返回 True（单次触发）。用于 stop_jump 等
- mouse_down() — 鼠标左键是否按住
- mouse_pressed() — 鼠标左键按下那一帧
- mouse_up() — 鼠标左键松开那一帧
- mouse.x, mouse.y — 鼠标在画面上的坐标
- mouse.pos — 一次性拿到鼠标坐标，可拆包：x, y = mouse.pos

### 控制
- while True: — 游戏主循环，引擎每帧自动执行循环体内的代码
- pause() / resume() — 暂停/继续游戏（角色停止移动但程序还在跑）
- is_paused() — 检查是否暂停
- stop() — 结束游戏，退出循环
- hero.on_touch_group("组名") — 注册碰撞：对方要先 add_to_group("组名")。对同一个角色注册一次即可（不要每帧调用）；每次新建的子弹需在创建后各注册一次。注册后碰到组内成员时，引擎自动把「自己」和「对方」一起删除，无需再写 is_touch_group 判断和 delete()。要自定义（加分/播声音/扣血）就传函数：on_touch_group("组名", 函数)，函数参数为 (自己, 碰到的角色)
- hero.add_to_group("组名") — 把角色加入组（如 "enemies"、"bullets"）
- broadcast("事件名") — 发送广播消息
- if hero.receive("事件名") — 检查这一帧有没有收到广播（入门写法，不需要写函数）。广播发出后的下一帧返回一次 True，必须写在 while True 里
- on_receive("事件名", 函数) — 进阶写法：全局函数（不是角色方法，不能写 monster.on_receive()），注册广播接收器，收到广播时执行该函数。函数不需要参数；必须在广播之前注册，且写在循环外（放进循环会重复注册导致执行多次）。它不返回 True/False，不能放在 if 里判断。简单场景优先用 if hero.receive("事件名")

### 声音
- play_sound("文件名") / play_sound("文件名", True) — 播放音效。不写循环参数=播放一次，True=循环播放
- stop_sound("文件名") — 停止指定音效。不写参数=停止所有音效
- 音效文件放在 assets/sounds/ 目录，写文件名不带后缀，引擎会自动搜索 .wav/.mp3/.ogg

### 地图
- load_map("地图名") — 加载并显示地图，返回地图对象（map = load_map("地图1")），地图名和资源面板中一致
- camera_follow(hero) — 摄像机跟随指定角色移动，画面会跟着角色走
- map.get_marker("标记名") — 按名字取地图上放的标记；可直接 player.goto(pos)，也可读 pos.x/.y/.pos 或拆包 x, y = pos；找不到返回 None
- map.get_markers("类型名") — 按类型取一组标记（列表），可直接 for 遍历；不传类型返回全部标记

### 工具
- show_text(x, y, 内容...) — 在(x,y)位置显示文字，多个参数自动拼接为字符串
- shake(强度=5, 秒数=0.3) — 画面震动
- show_fps(True) / show_fps(False) — 显示/隐藏帧率
- show_collision(hero) — 画出角色的碰撞范围（调试用）
- Timer(秒数, 循环=True) — 创建并自动开始的计时器；is_timeout() 到点返回 True（循环计时器自动重新计时）；第二个参数 False=只触发一次；timer.stop()/start() 暂停/重新计时
- time_passed(秒数) — 每隔几秒做一件事，简单定时就用它；需要暂停、重新计时、只做一次，用 Timer
- random_int(a, b) — 随机整数（包含a和b两端）
- random_float(a, b, 位数=2) — 随机小数，默认保留 2 位小数；需要更精确可传第三个数，或传 None 表示完整精度。范围小于 0.01 时要传更大的位数，否则随机性会丢失

## 回答格式
- 用中文回答
- 代码用 markdown 代码块包裹，语言标注 python
- 解释简洁明了
- 如果用户的请求不明确，先询问清楚再写代码`

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => messages.value.length, scrollToBottom)
watch(() => streamingContent.value, scrollToBottom)

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return

  const userMsg: ChatMessage = {
    role: 'user',
    content: text,
    timestamp: Date.now(),
  }
  messages.value.push(userMsg)
  inputText.value = ''
  isLoading.value = true
  streamingContent.value = ''

  nextTick(() => {
    if (textareaRef.value) {
      textareaRef.value.style.height = 'auto'
    }
  })

  const apiMessages = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...messages.value.map(m => ({ role: m.role, content: m.content })),
  ]

  const baseUrl = settings.value.baseUrl.replace(/\/+$/, '')

  try {
    // 先尝试流式请求
    const response = await fetch(`${baseUrl}/v1/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${settings.value.apiKey}`,
      },
      body: JSON.stringify({
        model: settings.value.model,
        messages: apiMessages,
        stream: true,
        temperature: 0.7,
        max_tokens: 2048,
      }),
    })

    if (!response.ok) {
      const errText = await response.text().catch(() => '无法读取错误信息')
      throw new Error(`API 返回 ${response.status}: ${errText.slice(0, 200)}`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('响应流不可用')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === '[DONE]') continue

        try {
          const parsed = JSON.parse(data)
          const delta = parsed.choices?.[0]?.delta?.content
          if (delta) {
            streamingContent.value += delta
          }
        } catch {
          // 忽略解析错误
        }
      }
    }

    if (streamingContent.value) {
      messages.value.push({
        role: 'assistant',
        content: streamingContent.value,
        timestamp: Date.now(),
      })
    } else {
      throw new Error('未收到任何内容，请检查 API 设置')
    }
  } catch (error: any) {
    // 流式失败时尝试非流式请求
    if (streamingContent.value) {
      // 已经有部分内容了，保存已有内容
      messages.value.push({
        role: 'assistant',
        content: streamingContent.value,
        timestamp: Date.now(),
      })
      streamingContent.value = ''
      isLoading.value = false
      return
    }

    try {
      const response = await fetch(`${baseUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${settings.value.apiKey}`,
        },
        body: JSON.stringify({
          model: settings.value.model,
          messages: apiMessages,
          stream: false,
          temperature: 0.7,
          max_tokens: 2048,
        }),
      })

      if (!response.ok) {
        const errText = await response.text().catch(() => '')
        throw new Error(`API 返回 ${response.status}: ${errText.slice(0, 200)}`)
      }

      const result = await response.json()
      const content = result.choices?.[0]?.message?.content
      if (content) {
        messages.value.push({
          role: 'assistant',
          content,
          timestamp: Date.now(),
        })
      } else {
        throw new Error('响应中没有内容')
      }
    } catch (fallbackError: any) {
      const errMsg = error.message || String(error)
      const fallbackMsg = fallbackError.message || String(fallbackError)

      // 判断是否是网络/连接问题
      let hint = ''
      if (errMsg.includes('Load failed') || errMsg.includes('NetworkError') || errMsg.includes('Failed to fetch')) {
        hint = `无法连接到 ${baseUrl}\n\n可能的原因：\n1. API 地址不正确\n2. 网络连接问题\n3. 服务器不支持 HTTPS\n\n请点击右上角齿轮图标检查 API 设置。`
      } else {
        hint = errMsg !== fallbackMsg ? `${errMsg}\n\n${fallbackMsg}` : errMsg
      }

      messages.value.push({
        role: 'assistant',
        content: `请求失败：${hint}`,
        timestamp: Date.now(),
      })
    }
  } finally {
    isLoading.value = false
    streamingContent.value = ''
  }
}

function clearChat() {
  messages.value = []
  streamingContent.value = ''
}

// 简单的 markdown 渲染
function renderMarkdown(text: string): string {
  const blocks: string[] = []
  let html = text

  // 代码块 → 占位符（避免被后续 <br> 影响）
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    const block = `<div class="ai-code-block"><div class="ai-code-header"><span class="ai-code-lang">${lang || 'code'}</span><button class="ai-copy-btn" onclick="window.__aiCopyCode(this)" data-code="${escaped.replace(/"/g, '&quot;')}">复制</button></div><pre><code>${escaped}</code></pre></div>`
    blocks.push(block)
    return `%%BLOCK${blocks.length - 1}%%`
  })

  // 标题
  html = html.replace(/^### (.+)$/gm, '<div class="ai-h3">$1</div>')
  html = html.replace(/^## (.+)$/gm, '<div class="ai-h2">$1</div>')
  html = html.replace(/^# (.+)$/gm, '<div class="ai-h1">$1</div>')
  // 列表
  html = html.replace(/^[*-] (.+)$/gm, '<div class="ai-list-item">• $1</div>')
  html = html.replace(/^\d+\. (.+)$/gm, (_m, p1) => {
    const num = _m.match(/^(\d+)\./)?.[1] || '1'
    return `<div class="ai-list-item">${num}. ${p1}</div>`
  })
  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="ai-inline-code">$1</code>')
  // 加粗
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // 换行
  html = html.replace(/\n/g, '<br>')
  // 清理块级元素前后 <br>
  html = html.replace(/<br>(<div class="ai-(?:h[123]|list-item)">)/g, '$1')
  html = html.replace(/(<\/div>)<br>/g, '$1')

  // 还原占位符
  html = html.replace(/%%BLOCK(\d+)%%/g, (_m, i) => blocks[parseInt(i)])
  return html
}
</script>

<template>
  <Teleport to="body">
    <Transition name="ai-slide">
      <div v-if="visible" class="ai-overlay">
        <div class="ai-panel">
          <!-- 标题栏 -->
          <div class="ai-header">
            <div class="ai-title-row">
              <img :src="iconAiAssistant" class="ai-header-icon" />
              <span class="ai-title">AI 编程助手</span>
            </div>
            <div class="ai-header-actions">
              <button class="ai-settings-btn" @click="showSettings = !showSettings" v-tooltip="'API 设置'">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                </svg>
              </button>
              <button class="ai-clear-btn" @click="clearChat" v-tooltip="'清空对话'">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
                  <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                </svg>
              </button>
              <button class="ai-close-btn" @click="emit('close')">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- API 设置面板 -->
          <Transition name="settings-slide">
            <div v-if="showSettings" class="ai-settings-panel">
              <div class="ai-settings-title">API 设置</div>
              <div class="ai-settings-field">
                <label>API 地址</label>
                <input v-model="settings.baseUrl" class="ai-settings-input" placeholder="https://api.openai.com" />
              </div>
              <div class="ai-settings-field">
                <label>API Key</label>
                <input v-model="settings.apiKey" type="password" class="ai-settings-input" placeholder="sk-..." />
              </div>
              <div class="ai-settings-field">
                <label>模型</label>
                <input v-model="settings.model" class="ai-settings-input" placeholder="gpt-4o-mini" />
              </div>
              <div class="ai-settings-actions">
                <button class="ai-settings-reset" @click="resetSettings">恢复默认</button>
                <button class="ai-settings-save" @click="saveSettings">保存</button>
              </div>
              <div class="ai-settings-hint">
                常见 API 地址：<br/>
                DeepSeek: https://api.deepseek.com<br/>
                OpenAI: https://api.openai.com<br/>
                模型: deepseek-v4-flash(便宜) / deepseek-reasoner(推理)
              </div>
            </div>
          </Transition>

          <!-- 消息区 -->
          <div ref="messagesContainer" class="ai-messages">
            <!-- 空状态 -->
            <div v-if="messages.length === 0 && !isLoading" class="ai-empty">
              <div class="ai-empty-icon">
                <img :src="iconAiAssistant" width="64" height="64" />
              </div>
              <div class="ai-empty-title">Bingo 引擎 AI 助手</div>
              <div class="ai-empty-desc">我可以帮你编写游戏代码、解答 API 用法、检查代码问题</div>
              <div class="ai-empty-hints">
                <button class="ai-hint-btn" @click="inputText = '帮我写一个简单的平台跳跃游戏'">帮我写一个平台跳跃游戏</button>
                <button class="ai-hint-btn" @click="inputText = '怎么让角色左右移动和跳跃？'">怎么让角色左右移动？</button>
                <button class="ai-hint-btn" @click="inputText = '帮我检查一下我的代码有没有问题'">检查我的代码</button>
              </div>
            </div>

            <!-- 消息列表 -->
            <template v-for="(msg, i) in messages" :key="i">
              <div class="ai-msg" :class="`ai-msg-${msg.role}`">
                <div class="ai-msg-avatar">
                  <template v-if="msg.role === 'user'">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                  </template>
                  <template v-else>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="rgb(91, 251, 132)"><path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/><path d="M9 22h6"/></svg>
                  </template>
                </div>
                <div class="ai-msg-body">
                  <div class="ai-msg-content" v-html="renderMarkdown(msg.content)"></div>
                </div>
              </div>
            </template>

            <!-- 流式输出中 -->
            <div v-if="isLoading && streamingContent" class="ai-msg ai-msg-assistant">
              <div class="ai-msg-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="rgb(91, 251, 132)"><path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/><path d="M9 22h6"/></svg>
              </div>
              <div class="ai-msg-body">
                <div class="ai-msg-content" v-html="renderMarkdown(streamingContent)"></div>
                <span class="ai-cursor"></span>
              </div>
            </div>

            <!-- 加载动画 -->
            <div v-if="isLoading && !streamingContent" class="ai-msg ai-msg-assistant">
              <div class="ai-msg-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="rgb(91, 251, 132)"><path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/><path d="M9 22h6"/></svg>
              </div>
              <div class="ai-msg-body">
                <div class="ai-typing">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>

          <!-- 输入区 -->
          <div class="ai-input-area">
            <div class="ai-input-box">
              <textarea
                ref="textareaRef"
                v-model="inputText"
                class="ai-input"
                placeholder="问我关于 Bingo 引擎的问题..."
                rows="1"
                :disabled="isLoading"
                @keydown="handleKeydown"
                @input="($event.target as HTMLTextAreaElement).style.height = 'auto'; ($event.target as HTMLTextAreaElement).style.height = Math.min(($event.target as HTMLTextAreaElement).scrollHeight, 120) + 'px'"
              ></textarea>
              <button
                class="ai-send-btn"
                :class="{ 'ai-send-active': inputText.trim() && !isLoading }"
                :disabled="!inputText.trim() || isLoading"
                @click="sendMessage"
              >
                <svg v-if="!isLoading" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/>
                </svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="6" y="6" width="12" height="12" rx="2"/>
                </svg>
              </button>
            </div>
            <div class="ai-input-hint">
              <span>Enter 发送 · Shift+Enter 换行 · 仅回答引擎相关问题</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped src="./AiChatPanel.scoped.css"></style>

<style src="./AiChatPanel.global.css"></style>

<script lang="ts">
// 全局复制函数（供 v-html 中的按钮调用）
;(window as any).__aiCopyCode = function(btn: HTMLElement) {
  const code = btn.getAttribute('data-code') || ''
  const decoded = code.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  navigator.clipboard.writeText(decoded)
  btn.textContent = '已复制'
  setTimeout(() => { btn.textContent = '复制' }, 1500)
}
</script>
