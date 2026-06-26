export interface FileResult {
  name: string
  content: string | null
  file: File
}

export function useFileDialog() {
  function openFile(accept: string, multiple = false): Promise<FileResult | null> {
    return new Promise((resolve) => {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = accept
      input.multiple = multiple
      document.body.appendChild(input)

      input.onchange = () => {
        const file = input.files?.[0]
        if (!file) { resolve(null); return }

        // 文本文件用 readAsText，其他用 readAsArrayBuffer
        const isText = /\.(py|json|txt|md|js|ts|css|html)$/i.test(file.name)
        const reader = new FileReader()
        reader.onload = () => {
          resolve({
            name: file.name,
            content: isText ? (reader.result as string) : null,
            file,
          })
        }
        reader.onerror = () => resolve(null)

        if (isText) {
          reader.readAsText(file)
        } else {
          reader.readAsArrayBuffer(file)
        }
        input.remove()
      }

      input.oncancel = () => { resolve(null); input.remove() }
      input.click()
    })
  }

  function saveFile(filename: string, content: string) {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = filename
    a.click()
    URL.revokeObjectURL(a.href)
    a.remove()
  }

  return { openFile, saveFile }
}
