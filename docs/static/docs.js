/**
 * BingoCode 帮助文档 · 页面脚本
 * 负责：侧边栏、搜索、代码复制。
 */
(function () {
  'use strict'

  var doc = document

  /* ─── 当前页面到文档根目录的前缀（兼容 file:// 与任意部署路径）─── */
  function getPrefix() {
    var script = doc.querySelector('script[src$="docs.js"]')
    if (script) {
      var src = script.getAttribute('src') || ''
      var index = src.indexOf('static/')
      if (index >= 0) return src.slice(0, index)
    }
    return './'
  }

  var PREFIX = getPrefix()

  /* ─── 移动端侧边栏 ─── */
  window.toggleSidebar = function () {
    var sidebar = doc.querySelector('.sidebar')
    var overlay = doc.querySelector('.sidebar-overlay')
    if (!sidebar) return
    sidebar.classList.toggle('open')
    if (overlay) overlay.classList.toggle('open')
  }

  /* ─── 导航分组折叠 ─── */
  function initNavGroups() {
    var state = {}
    try {
      state = JSON.parse(localStorage.getItem('bingo-nav-state') || '{}')
    } catch (error) {
      state = {}
    }

    doc.querySelectorAll('.nav-group').forEach(function (group) {
      var header = group.querySelector('.nav-group-header')
      var label = group.getAttribute('data-group') || ''
      if (label && typeof state[label] === 'boolean') {
        group.classList.toggle('expanded', state[label])
      }

      if (!header) return
      header.setAttribute('aria-expanded', group.classList.contains('expanded') ? 'true' : 'false')

      header.addEventListener('click', function () {
        group.classList.toggle('expanded')
        header.setAttribute('aria-expanded', group.classList.contains('expanded') ? 'true' : 'false')
        if (label) {
          state[label] = group.classList.contains('expanded')
          try {
            localStorage.setItem('bingo-nav-state', JSON.stringify(state))
          } catch (error) {
            /* 忽略隐私模式下的写入失败 */
          }
        }
      })
    })

    // 移动端点导航后自动收起侧边栏
    doc.querySelectorAll('.nav-item').forEach(function (item) {
      item.addEventListener('click', function () {
        var sidebar = doc.querySelector('.sidebar')
        var overlay = doc.querySelector('.sidebar-overlay')
        if (sidebar && sidebar.classList.contains('open')) {
          sidebar.classList.remove('open')
          if (overlay) overlay.classList.remove('open')
        }
      })
    })
  }

  /* ─── 搜索 ─── */
  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  function initSearch() {
    var input = doc.getElementById('search-input')
    var results = doc.getElementById('search-results')
    if (!input || !results) return

    var index = typeof SEARCH_INDEX !== 'undefined' && Array.isArray(SEARCH_INDEX) ? SEARCH_INDEX : []

    function close() {
      results.classList.remove('active')
    }

    function render(query) {
      var matches = index
        .filter(function (item) {
          return (
            item.title.toLowerCase().indexOf(query) >= 0 ||
            item.content.toLowerCase().indexOf(query) >= 0
          )
        })
        .slice(0, 8)

      if (!matches.length) {
        results.innerHTML = '<div class="search-no-result">没有找到相关内容</div>'
      } else {
        var pattern = new RegExp('(' + escapeRegex(query) + ')', 'gi')
        results.innerHTML = matches
          .map(function (item) {
            var text = item.content
            var hit = text.toLowerCase().indexOf(query)
            var excerpt = text.slice(0, 90)
            if (hit > 30) {
              excerpt = '…' + text.slice(hit - 30, hit + 60) + '…'
            }
            return (
              '<a class="search-result-item" href="' +
              PREFIX +
              item.path.replace(/^\.\//, '') +
              '">' +
              '<div class="search-result-title">' +
              item.title.replace(pattern, '<span class="search-result-highlight">$1</span>') +
              '</div>' +
              '<div class="search-result-excerpt">' +
              excerpt.replace(pattern, '<span class="search-result-highlight">$1</span>') +
              '</div></a>'
            )
          })
          .join('')
      }

      results.classList.add('active')
    }

    input.addEventListener('input', function () {
      var query = input.value.trim().toLowerCase()
      if (query.length < 1) {
        close()
        return
      }
      render(query)
    })

    input.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        input.value = ''
        close()
        input.blur()
      }
      if (event.key === 'Enter') {
        var first = results.querySelector('.search-result-item')
        if (first) window.location.href = first.getAttribute('href')
      }
    })

    input.addEventListener('blur', function () {
      setTimeout(close, 160)
    })

    doc.addEventListener('keydown', function (event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        input.focus()
        input.select()
      }
    })
  }

  /* ─── 代码复制（事件委托）─── */
  function initCopyButtons() {
    doc.addEventListener('click', function (event) {
      var button = event.target.closest('.copy-btn')
      if (!button) return
      var block = button.closest('.code-block')
      if (!block) return
      var code = block.querySelector('code')
      if (!code) return

      var text = code.textContent
      var done = function () {
        button.textContent = '已复制'
        button.classList.add('copied')
        setTimeout(function () {
          button.textContent = '复制'
          button.classList.remove('copied')
        }, 1600)
      }

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {
          fallbackCopy(text, done)
        })
      } else {
        fallbackCopy(text, done)
      }
    })
  }

  function fallbackCopy(text, done) {
    var area = doc.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    doc.body.appendChild(area)
    area.select()
    try {
      doc.execCommand('copy')
      done()
    } catch (error) {
      /* 复制失败时不打扰用户 */
    }
    doc.body.removeChild(area)
  }

  /* ─── 首页主界面截图：缺失时显示占位 ─── */
  function initHomeShot() {
    doc.querySelectorAll('.home-app-shot').forEach(function (img) {
      var frame = img.closest('.home-app')
      if (!frame) return

      function showPlaceholder() {
        frame.classList.add('no-shot')
        img.remove()
      }

      function showImage() {
        frame.classList.remove('no-shot')
      }

      if (img.complete) {
        if (img.naturalWidth > 0) showImage()
        else showPlaceholder()
        return
      }

      img.addEventListener('load', showImage)
      img.addEventListener('error', showPlaceholder)
    })
  }

  /* ─── 本地开发热重载：dev 服务提供 __dev 版本号时自动刷新 ─── */
  function initDevReload() {
    if (!window.fetch) return
    var stamp = null
    fetch(PREFIX + '__dev', { cache: 'no-store' })
      .then(function (res) {
        return res.ok ? res.text() : null
      })
      .then(function (value) {
        if (value === null) return
        stamp = value
        setInterval(function () {
          fetch(PREFIX + '__dev', { cache: 'no-store' })
            .then(function (res) {
              return res.ok ? res.text() : null
            })
            .then(function (next) {
              if (next && next !== stamp) window.location.reload()
            })
            .catch(function () {})
        }, 800)
      })
      .catch(function () {})
  }

  doc.addEventListener('DOMContentLoaded', function () {
    initNavGroups()
    initSearch()
    initCopyButtons()
    initHomeShot()
    initDevReload()
  })
})()
