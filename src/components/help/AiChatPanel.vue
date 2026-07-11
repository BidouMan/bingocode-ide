<script setup lang="ts">
import { ref, nextTick, watch, onMounted } from 'vue'

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
7. jump() 只是施加向上的力，必须自己用 on_ground 判断能否跳

## 画面基本信息
- 画面尺寸：640 x 480 像素
- 坐标原点在左上角：(0,0) 是左上角，(640,480) 是右下角
- 角度：0=朝右，90=朝下，180=朝左，270=朝上（顺时针）
- while True 循环约每秒执行 60 次（60FPS）

## 引擎 API 详细参考

### 精灵 Sprite
- hero = Sprite("角色名") — 创建角色，角色名必须和资源面板中添加的角色文件夹名一致。初始位置在画面中央(320,240)，初始大小100%，朝向0度
- hero.delete() — 从画面删除角色，删后不能再使用
- hero.x, hero.y — 读取或设置位置（0~640, 0~480），赋值时自动检测碰撞
- hero.scale — 大小百分比，100=正常，200=两倍大，50=一半小（可直接赋值）
- hero.angle — 朝向角度（可直接赋值）
- hero.layer — 层级数字，越大越在前面，默认1000
- hero.on_ground — 布尔属性，角色脚底是否踩在有碰撞的地形上。每帧自动更新
- hero.vy — 垂直速度属性，正数=下落，负数=上升，静止=0

### 运动
- hero.goto(x, y) — 瞬间传送到(x,y)，自动检测碰撞
- hero.move(步数) — 朝当前 angle 方向移动指定像素，自动检测碰撞，会拆分成小步避免穿墙
- hero.jump(power=10) — 施加向上的力，vy 设为 -power。不判断地面！必须配合 on_ground 使用。用法：if hero.on_ground: hero.jump(10)
- hero.cut_jump() — 截断跳跃。只在 vy<0（正在上升）时生效，将 _jump_cut 标记为 True，下一帧重力从 0.5 变为 2.8，角色快速下落。用于控制跳跃高度：按住跳得高，轻点跳得矮
- hero.drop_through() — 穿过脚下跳板。必须在地面上调用，角色会短暂下穿跳板
- hero.add_x(n) / hero.add_y(n) — 直接修改坐标（不检测碰撞），正数向右/下，负数向左/上
- hero.set_x(x) / hero.set_y(y) — 设置坐标（检测碰撞），比 add_x/add_y 安全
- hero.set_angle(度数) — 设置朝向角度
- hero.look_at(target) — 自动转向面向 target（另一个 Sprite 或 mouse 对象）
- hero.set_speed(速度) — 设置持续移动速度，之后每帧自动沿当前方向移动，写 0 停下
- hero.edge_bounce() — 碰到画面边缘(640x480)自动反弹
- hero.goto_rand() — 随机传送到画面内任意位置

### 外观
- hero.show() / hero.hide() — 显示/隐藏（不是删除，隐藏后还能 show）
- hero.say("文字") / hero.say("文字", 2) — 头顶气泡。不写时间=一直显示，写时间=到时消失
- hero.set_scale(百分比) — 设置大小（100=正常）
- hero.add_scale(增量) — 在当前大小基础上增减
- hero.set_rotation_mode("all") — "all"=任意旋转（默认），"left_right"=只左右翻转，"none"=不旋转
- hero.play("动画名") — 播放角色资源中预设的动画

### 侦测
- hero.is_touch(target) — 碰撞检测。target 可以是：另一个 Sprite、mouse 对象、字符串标签。返回 True/False
- hero.is_touch_edge() — 是否碰到画面边缘(640x480)
- hero.is_out_side() — 是否整个角色都在画面外
- hero.distance_to(target) — 返回到另一个 Sprite 或 mouse 的像素距离
- bullet.touch_group("组名") — 检测子弹是否碰到组内成员，碰到返回那个角色，没碰到返回 None
- hero.is_on_floor() — 实时检测脚底1-2像素处是否有碰撞图块（比 on_ground 更精确但更耗性能）
- key_down("键名") — 按键是否正在被按住，每帧检测。键名小写：space, up, down, left, right, a-z
- key_pressed("键名") — 只在按下的那一帧返回 True（单次触发）。用于跳跃等一次性操作
- key_up("键名") — 只在松开的那一帧返回 True（单次触发）。用于 cut_jump 等
- mouse_down() — 鼠标左键是否按住
- mouse_pressed() — 鼠标左键按下那一帧
- mouse.x, mouse.y — 鼠标在画面上的坐标

### 控制
- while True: — 游戏主循环，引擎每帧自动执行循环体内的代码
- pause() / resume() — 暂停/继续游戏（角色停止移动但程序还在跑）
- is_paused() — 检查是否暂停
- stop() — 结束游戏，退出循环
- hero.on_hit("组名", lambda b, e: 代码) — 注册碰撞回调，b=自己，e=碰到的角色
- hero.add_to_group("组名") — 把角色加入组（如 "enemies"、"bullets"）
- broadcast("事件名") — 发送广播消息
- receive("事件名", lambda: 代码) — 注册广播接收器，收到消息时执行代码。必须在广播之前注册

### 声音
- play_sound("文件名") / play_sound("文件名", True) — 播放音效。不写循环参数=播放一次，True=循环播放
- stop_sound("文件名") — 停止指定音效。不写参数=停止所有音效
- 音效文件放在 assets/sounds/ 目录，写文件名不带后缀，引擎会自动搜索 .wav/.mp3/.ogg

### 地图
- load_map("地图名") — 加载并显示地图，地图名和资源面板中一致
- follow(hero) — 摄像机跟随指定角色移动，画面会跟着角色走

### 工具
- draw_text(x, y, 内容...) — 在(x,y)位置画文字，多个参数自动拼接为字符串
- shake(强度=5, 秒数=0.3) — 画面震动
- show_fps(True) / show_fps(False) — 显示/隐藏帧率
- show_collision(hero) — 画出角色的碰撞范围（调试用）
- Timer(秒数) / Timer(秒数, False) — 创建计时器。默认循环计时，False=只计一次
- clock.is_timeout() — 计时器时间到了返回 True
- wait(秒数) — 每隔N秒返回一次 True
- random_int(a, b) — 随机整数（包含a和b两端）
- random_float(a, b) — 随机浮点数

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
      <div v-if="visible" class="ai-overlay" @click.self="emit('close')">
        <div class="ai-panel">
          <!-- 标题栏 -->
          <div class="ai-header">
            <div class="ai-title-row">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgb(91, 251, 132)" stroke-width="2">
                <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/>
                <path d="M9 22h6"/>
                <path d="M10 2v2"/>
                <path d="M14 2v2"/>
              </svg>
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
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="rgb(91, 251, 132)" stroke-width="1.5">
                  <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/>
                  <path d="M9 22h6"/>
                  <path d="M10 2v2"/>
                  <path d="M14 2v2"/>
                </svg>
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

<style scoped>
.ai-slide-enter-active,
.ai-slide-leave-active { transition: opacity 0.25s ease; }
.ai-slide-enter-active .ai-panel,
.ai-slide-leave-active .ai-panel { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.ai-slide-enter-from,
.ai-slide-leave-to { opacity: 0; }
.ai-slide-enter-from .ai-panel,
.ai-slide-leave-to .ai-panel { transform: translateX(100%); }

.settings-slide-enter-active,
.settings-slide-leave-active { transition: all 0.2s ease; }
.settings-slide-enter-from,
.settings-slide-leave-to { opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; }
.settings-slide-enter-to,
.settings-slide-leave-from { opacity: 1; max-height: 300px; }

.ai-overlay {
  position: fixed; inset: 0; z-index: 9000;
  display: flex; justify-content: flex-end;
  background: rgba(0, 0, 0, 0.3);
}

.ai-panel {
  width: 420px; max-width: 92vw; height: 100%;
  display: flex; flex-direction: column;
  background: var(--bg-root);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}

/* ── 标题栏 ── */
.ai-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 40px; min-height: 40px; padding: 0 14px;
  border-bottom: 1px solid var(--border);
}
.ai-title-row { display: flex; align-items: center; gap: 8px; }
.ai-title { font-size: 14px; font-weight: 600; color: white; }
.ai-header-actions { display: flex; align-items: center; gap: 4px; }
.ai-settings-btn, .ai-clear-btn, .ai-close-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  background: transparent; border: none; border-radius: 4px;
  color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
}
.ai-settings-btn:hover, .ai-clear-btn:hover, .ai-close-btn:hover { background: var(--bg-hover); color: white; }
.ai-settings-btn.active { color: rgb(91, 251, 132); background: rgba(91, 251, 132, 0.1); }

/* ── 设置面板 ── */
.ai-settings-panel {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  background: rgba(0, 0, 0, 0.15);
  overflow: hidden;
}
.ai-settings-title {
  font-size: 12px; font-weight: 600; color: var(--text-secondary);
  margin-bottom: 10px;
}
.ai-settings-field {
  margin-bottom: 8px;
}
.ai-settings-field label {
  display: block;
  font-size: 11px; color: var(--text-muted);
  margin-bottom: 4px;
}
.ai-settings-input {
  width: 100%; height: 30px;
  padding: 0 8px;
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: white; font-size: 12px;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  outline: none; transition: border-color 0.15s;
}
.ai-settings-input:focus { border-color: rgba(91, 251, 132, 0.4); }
.ai-settings-input::placeholder { color: var(--text-muted); }
.ai-settings-actions {
  display: flex; gap: 8px; margin-top: 10px;
}
.ai-settings-reset {
  padding: 4px 12px;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-muted);
  font-size: 11px; cursor: pointer;
  transition: all 0.15s;
}
.ai-settings-reset:hover { color: white; border-color: var(--text-muted); }
.ai-settings-save {
  padding: 4px 16px;
  background: rgb(91, 251, 132);
  border: none; border-radius: 4px;
  color: rgb(20, 20, 20);
  font-size: 11px; font-weight: 500;
  cursor: pointer; transition: all 0.15s;
}
.ai-settings-save:hover { opacity: 0.9; }
.ai-settings-hint {
  margin-top: 8px;
  font-size: 10.5px; color: var(--text-muted);
  line-height: 1.6; opacity: 0.7;
}

/* ── 消息区 ── */
.ai-messages {
  flex: 1; min-height: 0; overflow-y: auto;
  padding: 16px;
  display: flex; flex-direction: column; gap: 16px;
}
.ai-messages::-webkit-scrollbar { width: 6px; }
.ai-messages::-webkit-scrollbar-track { background: transparent; }
.ai-messages::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 3px; }

/* ── 空状态 ── */
.ai-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; padding: 20px;
}
.ai-empty-icon { opacity: 0.6; margin-bottom: 4px; }
.ai-empty-title {
  font-size: 16px; font-weight: 600; color: white;
}
.ai-empty-desc {
  font-size: 13px; color: var(--text-muted);
  text-align: center; line-height: 1.6;
}
.ai-empty-hints {
  display: flex; flex-direction: column; gap: 6px;
  margin-top: 8px; width: 100%; max-width: 280px;
}
.ai-hint-btn {
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 12.5px; text-align: left;
  cursor: pointer; transition: all 0.15s;
}
.ai-hint-btn:hover {
  background: rgba(91, 251, 132, 0.08);
  border-color: rgba(91, 251, 132, 0.3);
  color: white;
}

/* ── 消息 ── */
.ai-msg {
  display: flex; gap: 10px;
}
.ai-msg-avatar {
  width: 28px; height: 28px; min-width: 28px;
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ai-msg-user .ai-msg-avatar {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-secondary);
}
.ai-msg-assistant .ai-msg-avatar {
  background: rgba(91, 251, 132, 0.12);
}
.ai-msg-body {
  flex: 1; min-width: 0;
}
.ai-msg-content {
  font-size: 13px; line-height: 1.7;
  color: rgb(210, 210, 210);
  word-break: break-word;
}
.ai-msg-user .ai-msg-content {
  color: white;
}

/* ── 打字动画 ── */
.ai-typing {
  display: flex; gap: 4px; padding: 8px 0;
}
.ai-typing span {
  width: 6px; height: 6px;
  background: rgb(91, 251, 132);
  border-radius: 50%;
  animation: ai-bounce 1.4s ease-in-out infinite;
}
.ai-typing span:nth-child(2) { animation-delay: 0.16s; }
.ai-typing span:nth-child(3) { animation-delay: 0.32s; }
@keyframes ai-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ── 光标 ── */
.ai-cursor {
  display: inline-block;
  width: 2px; height: 14px;
  background: rgb(91, 251, 132);
  margin-left: 2px;
  animation: ai-blink 0.8s step-end infinite;
  vertical-align: text-bottom;
}
@keyframes ai-blink {
  50% { opacity: 0; }
}

/* ── 输入区 ── */
.ai-input-area {
  padding: 12px 14px;
  border-top: 1px solid var(--border);
}
.ai-input-box {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  transition: border-color 0.2s;
}
.ai-input-box:focus-within {
  border-color: rgba(91, 251, 132, 0.4);
}
.ai-input {
  flex: 1; min-height: 20px; max-height: 120px;
  background: transparent; border: none; outline: none;
  font-size: 13px; color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  resize: none; line-height: 1.5;
  padding: 0; margin: 0;
}
.ai-input::placeholder { color: var(--text-muted); }
.ai-input:disabled { opacity: 0.5; }
.ai-send-btn {
  width: 32px; height: 32px; min-width: 32px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  border: none; border-radius: 8px;
  color: var(--text-muted);
  cursor: pointer; transition: all 0.15s;
}
.ai-send-active {
  background: rgb(91, 251, 132) !important;
  color: rgb(20, 20, 20) !important;
}
.ai-send-btn:disabled { cursor: not-allowed; }
.ai-input-hint {
  padding: 6px 4px 0;
  font-size: 11px; color: var(--text-muted);
  opacity: 0.6;
}
</style>

<style>
/* ── 代码块样式（非 scoped，因为 v-html 渲染） ── */
.ai-code-block {
  margin: 2px 0 6px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  overflow: hidden;
}
.ai-code-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 12px;
  background: rgb(28, 28, 32);
  border-bottom: 1px solid var(--border-light);
}
.ai-code-lang {
  font-size: 11px; color: var(--text-muted);
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
}
.ai-copy-btn {
  font-size: 11px; padding: 2px 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 4px; color: var(--text-secondary);
  cursor: pointer; transition: all 0.15s;
}
.ai-copy-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}
.ai-code-block pre {
  margin: 0; padding: 12px;
  background: rgb(22, 22, 26);
  overflow-x: auto;
}
.ai-code-block pre::-webkit-scrollbar { height: 4px; }
.ai-code-block pre::-webkit-scrollbar-track { background: transparent; }
.ai-code-block pre::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 2px; }
.ai-code-block code {
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px; color: rgb(156, 227, 170);
  white-space: pre;
}
.ai-inline-code {
  padding: 2px 5px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px; color: rgb(156, 227, 170);
}
.ai-h1 {
  font-size: 16px; font-weight: 700; color: white;
  margin: 10px 0 6px; line-height: 1.4;
}
.ai-h2 {
  font-size: 14px; font-weight: 600; color: white;
  margin: 8px 0 4px; line-height: 1.4;
}
.ai-h3 {
  font-size: 13px; font-weight: 600; color: rgb(220, 220, 220);
  margin: 6px 0 4px; line-height: 1.4;
}
.ai-list-item {
  padding: 2px 0 2px 8px;
  font-size: 13px; color: rgb(200, 200, 200);
  line-height: 1.6;
}
</style>

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
