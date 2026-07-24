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

    // ═══ 校验便携 Python 是否真的存在 ═══
    // 防止"忘下载 Python 就打包"的静默失败：
    //   - dev 构建：只打印警告，允许继续（开发时通常用系统 venv）
    //   - release 构建（pnpm tauri build）：直接 panic，让打包失败
    //
    // 触发条件：portable-python 目录里只有 .gitkeep 这种占位文件，
    // 没有真正的 python 二进制。
    let py_name = if cfg!(target_os = "windows") {
        "python.exe"
    } else {
        "bin/python3"
    };
    let py_bin = portable_dir.join(py_name);

    // PROFILE 由 cargo 在 build.rs 中自动设置（debug/release）。
    // 仅当明确为 "release" 时才视为发布构建，否则一律按 dev 处理（更安全的默认）。
    let is_release = std::env::var("PROFILE")
        .map(|v| v == "release")
        .unwrap_or(false);

    if !py_bin.exists() {
        let msg = format!(
            "\n┌──────────────────────────────────────────────────────────────\n\
             │ ⚠️  便携 Python 缺失: {}\n\
             │     期望路径: {}\n\
             │\n\
             │     这会导致打包后的安装包运行时报 \"Python not found\"。\n\
             │     请在打包前执行: bash scripts/setup-portable-python.sh\n\
             │     或参考 .github/workflows/release.yml 中的 setup 步骤。\n\
             └──────────────────────────────────────────────────────────────",
            if is_release { "[RELEASE] 构建中止" } else { "[DEV] 仅警告" },
            py_bin.display()
        );

        if is_release {
            panic!("{}", msg);
        } else {
            println!("cargo:warning={}", msg);
        }
    } else {
        // 进一步检查：如果便携 Python 大小异常小（< 1MB），可能解压不完整
        if let Ok(meta) = std::fs::metadata(&py_bin) {
            let size_mb = meta.len() as f64 / 1024.0 / 1024.0;
            if size_mb < 0.01 {
                let msg = format!(
                    "便携 Python 二进制异常小 ({:.2} KB)，可能解压不完整: {}",
                    size_mb * 1024.0,
                    py_bin.display()
                );
                if is_release {
                    panic!("{}", msg);
                } else {
                    println!("cargo:warning={}", msg);
                }
            }
        }
    }

    tauri_build::build()
}
