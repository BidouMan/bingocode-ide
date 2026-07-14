fn main() {
    // 确保 portable-python 目录存在（含 marker 文件），
    // 否则 Tauri 构建会因为 glob 不匹配而失败。
    // 在 CI 中，这个目录会被真实的便携 Python 替换。
    let portable_dir = std::path::Path::new("../engine/portable-python");
    if !portable_dir.exists() {
        std::fs::create_dir_all(portable_dir).ok();
    }
    // 确保至少有 1 个文件使 **/* glob 匹配
    let marker = portable_dir.join(".gitkeep");
    if !marker.exists() {
        std::fs::write(&marker, b"").ok();
    }

    tauri_build::build()
}
