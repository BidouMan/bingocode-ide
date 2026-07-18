<script setup lang="ts">
import { useEditorStore } from '../../stores/editor'

const editorStore = useEditorStore()

// 预置代码片段 - 适合新手小白
const snippets = [
  {
    name: 'Hello World',
    desc: '最简单的程序',
    code: 'print("Hello, World!")',
  },
  {
    name: '变量与输出',
    desc: '定义变量并打印',
    code: 'name = "小明"\nage = 12\nprint(f"我叫{name}，今年{age}岁")',
  },
  {
    name: '输入与判断',
    desc: '获取用户输入并判断',
    code: 'answer = input("请输入：")\nif answer == "yes":\n    print("好的！")\nelse:\n    print("不行哦")',
  },
  {
    name: 'for 循环',
    desc: '重复执行指定次数',
    code: 'for i in range(5):\n    print(f"第 {i+1} 次")',
  },
  {
    name: 'while 循环',
    desc: '满足条件时重复执行',
    code: 'count = 0\nwhile count < 5:\n    print(f"计数: {count}")\n    count += 1',
  },
  {
    name: '列表操作',
    desc: '创建和使用列表',
    code: 'fruits = ["苹果", "香蕉", "橘子"]\nfor fruit in fruits:\n    print(f"我喜欢{fruit}")',
  },
  {
    name: '猜数字游戏',
    desc: '完整的猜数字小游戏',
    code: 'import random\n\ntarget = random.randint(1, 100)\nprint("猜一个1到100之间的数字！")\n\nwhile True:\n    guess = int(input("你的猜测："))\n    if guess < target:\n        print("太小了！")\n    elif guess > target:\n        print("太大了！")\n    else:\n        print("恭喜你猜对了！")\n        break',
  },
  {
    name: '函数定义',
    desc: '定义和调用函数',
    code: 'def greet(name):\n    return f"你好，{name}！"\n\nresult = greet("小红")\nprint(result)',
  },
  {
    name: '绘图 - 画圆',
    desc: '使用 turtle 画圆',
    code: 'import turtle\n\nt = turtle.Turtle()\nt.circle(50)\nturtle.done()',
  },
  {
    name: '绘图 - 彩色方块',
    desc: '使用 turtle 画彩色方块',
    code: 'import turtle\n\ncolors = ["red", "green", "blue", "yellow"]\nt = turtle.Turtle()\n\nfor color in colors:\n    t.fillcolor(color)\n    t.begin_fill()\n    for _ in range(4):\n        t.forward(50)\n        t.right(90)\n    t.end_fill()\n    t.forward(60)\n\nturtle.done()',
  },
]

function insertSnippet(code: string) {
  const tab = editorStore.currentTab
  if (tab) {
    // 通过事件通知 Monaco 编辑器在光标位置插入
    window.dispatchEvent(new CustomEvent('editor:insert-text', { detail: { text: code } }))
  } else {
    // 没有打开的标签，创建新标签
    editorStore.createTab('代码片段.py', '', code)
  }
}
</script>

<template>
  <div class="snippet-panel">
    <div class="snippet-header">代码片段</div>
    <div class="snippet-hint">点击即可插入到编辑器</div>
    <div class="snippet-list">
      <div
        v-for="snippet in snippets"
        :key="snippet.name"
        class="snippet-item"
        @click="insertSnippet(snippet.code)"
      >
        <div class="snippet-name">{{ snippet.name }}</div>
        <div class="snippet-desc">{{ snippet.desc }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.snippet-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-root);
  user-select: none;
}
.snippet-header {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 10px 12px 2px;
}
.snippet-hint {
  font-size: 10px;
  color: var(--text-muted);
  padding: 0 12px 8px;
}
.snippet-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 6px;
}
.snippet-item {
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.12s;
  margin-bottom: 2px;
}
.snippet-item:hover { background: var(--bg-hover); }
.snippet-item:active { background: var(--bg-active); }
.snippet-name {
  font-size: 12px;
  color: var(--text);
  margin-bottom: 2px;
}
.snippet-desc {
  font-size: 10px;
  color: var(--text-muted);
}
</style>
