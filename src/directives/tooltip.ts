import type { Directive, DirectiveBinding } from 'vue'

type TooltipPosition = 'top' | 'bottom' | 'left' | 'right'

/** v-tooltip 支持纯字符串（默认下方）或 { text, position } 对象 */
interface TooltipValue {
  text: string
  position?: TooltipPosition
}

function parseTooltipValue(value: unknown): { text: string; position: TooltipPosition } {
  if (typeof value === 'string' || value == null) {
    return { text: value == null ? '' : String(value), position: 'bottom' }
  }
  if (typeof value === 'object' && 'text' in (value as object)) {
    const v = value as TooltipValue
    return { text: v.text ?? '', position: v.position ?? 'bottom' }
  }
  return { text: String(value), position: 'bottom' }
}

interface TooltipElement extends HTMLElement {
  _tooltip?: {
    element: HTMLDivElement
    showTimeout: ReturnType<typeof setTimeout> | 0
    hideTimeout: ReturnType<typeof setTimeout> | 0
  }
  _tooltipHandlers?: {
    onMouseEnter: () => void
    onMouseLeave: () => void
    onFocus: () => void
    onBlur: () => void
  }
  _tooltipCurrentText?: string
  _tooltipPosition?: TooltipPosition
}

function createTooltipElement(text: string): HTMLDivElement {
  const el = document.createElement('div')
  el.className = 'custom-tooltip'
  el.textContent = text
  el.style.cssText = `
    position: fixed;
    z-index: 10000;
    padding: 6px 10px;
    background: rgba(30, 30, 30, 0.95);
    color: rgb(220, 220, 220);
    font-size: 12px;
    line-height: 1.4;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s ease;
    white-space: nowrap;
  `
  return el
}

function positionTooltip(
  element: HTMLElement,
  tooltip: HTMLDivElement,
  position: TooltipPosition = 'bottom'
): void {
  const rect = element.getBoundingClientRect()
  const tooltipRect = tooltip.getBoundingClientRect()

  let left: number
  let top: number
  switch (position) {
    case 'right':
      left = rect.right + 4
      top = rect.top + (rect.height - tooltipRect.height) / 2
      break
    case 'left':
      left = rect.left - tooltipRect.width - 8
      top = rect.top + (rect.height - tooltipRect.height) / 2
      break
    case 'top':
      left = rect.left + (rect.width - tooltipRect.width) / 2
      top = rect.top - tooltipRect.height - 8
      break
    default: // bottom
      left = rect.left + (rect.width - tooltipRect.width) / 2
      top = rect.bottom + 8
  }

  // Keep within viewport
  if (left < 8) left = 8
  if (left + tooltipRect.width > window.innerWidth - 8) {
    left = window.innerWidth - tooltipRect.width - 8
  }
  if (top < 8) top = 8
  if (top + tooltipRect.height > window.innerHeight - 8) {
    top = window.innerHeight - tooltipRect.height - 8
  }

  tooltip.style.left = `${left}px`
  tooltip.style.top = `${top}px`
}

function showTooltip(el: TooltipElement, text: string, position: TooltipPosition): void {
  if (!text) return
  
  // Clear any pending hide
  if (el._tooltip?.hideTimeout) {
    clearTimeout(el._tooltip.hideTimeout)
  }
  
  // Create tooltip if not exists
  if (!el._tooltip) {
    const tooltipEl = createTooltipElement(text)
    document.body.appendChild(tooltipEl)
    el._tooltip = {
      element: tooltipEl,
      showTimeout: 0,
      hideTimeout: 0
    }
  }
  
  // Update text if changed
  const tooltip = el._tooltip!
  if (tooltip.element.textContent !== text) {
    tooltip.element.textContent = text
  }
  
  // Position and show after delay
  tooltip.showTimeout = setTimeout(() => {
    positionTooltip(el, el._tooltip!.element, position)
    el._tooltip!.element.style.opacity = '1'
  }, 500)
}

function hideTooltip(el: TooltipElement): void {
  if (!el._tooltip) return
  
  // Clear any pending show
  if (el._tooltip.showTimeout) {
    clearTimeout(el._tooltip.showTimeout)
  }
  
  // Hide immediately
  el._tooltip.element.style.opacity = '0'
  
  // Remove from DOM after transition
  el._tooltip.hideTimeout = setTimeout(() => {
    if (el._tooltip?.element.parentNode) {
      el._tooltip.element.parentNode.removeChild(el._tooltip.element)
    }
    delete el._tooltip
  }, 150)
}

export const vTooltip: Directive = {
  mounted(el: TooltipElement, binding: DirectiveBinding) {
    const parsed = parseTooltipValue(binding.value)
    el._tooltipCurrentText = parsed.text
    el._tooltipPosition = parsed.position

    const onMouseEnter = () =>
      showTooltip(el, el._tooltipCurrentText!, el._tooltipPosition ?? 'bottom')
    const onMouseLeave = () => hideTooltip(el)
    const onFocus = () =>
      showTooltip(el, el._tooltipCurrentText!, el._tooltipPosition ?? 'bottom')
    const onBlur = () => hideTooltip(el)

    el.addEventListener('mouseenter', onMouseEnter)
    el.addEventListener('mouseleave', onMouseLeave)
    el.addEventListener('focus', onFocus)
    el.addEventListener('blur', onBlur)

    el._tooltipHandlers = { onMouseEnter, onMouseLeave, onFocus, onBlur }
  },

  updated(el: TooltipElement, binding: DirectiveBinding) {
    const parsed = parseTooltipValue(binding.value)
    const changed = parsed.text !== el._tooltipCurrentText
    el._tooltipCurrentText = parsed.text
    el._tooltipPosition = parsed.position
    if (el._tooltip && changed) {
      el._tooltip.element.textContent = parsed.text || ''
    }
  },

  unmounted(el: TooltipElement) {
    if (el._tooltipHandlers) {
      el.removeEventListener('mouseenter', el._tooltipHandlers.onMouseEnter)
      el.removeEventListener('mouseleave', el._tooltipHandlers.onMouseLeave)
      el.removeEventListener('focus', el._tooltipHandlers.onFocus)
      el.removeEventListener('blur', el._tooltipHandlers.onBlur)
      delete el._tooltipHandlers
    }
    delete el._tooltipCurrentText
    if (el._tooltip) {
      clearTimeout(el._tooltip.showTimeout)
      clearTimeout(el._tooltip.hideTimeout)
      if (el._tooltip.element.parentNode) {
        el._tooltip.element.parentNode.removeChild(el._tooltip.element)
      }
      delete el._tooltip
    }
  }
}
